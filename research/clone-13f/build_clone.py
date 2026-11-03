"""A "best ideas" portfolio of concentrated, patient managers, as set out in PREREGISTRATION.md.

Usage:
    python build_clone.py            development (formations Nov 2014 to Nov 2023)
    python build_clone.py --holdout  hold-out (formations from Feb 2024); only once development is closed
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

HERE = Path(__file__).resolve().parent
D13 = HERE / "data" / "13f"
BT = HERE.parent.parent / "equity-screener" / "data" / "backtest"
FIGI = HERE / "data" / "figi.json"
TOP_IDEAS, N_HOLD = 5, 20
COST, FX = 0.0010, 0.0050
DEV = ("2014-11-01", "2023-11-30")
HOLDOUT = "2024-02-01"


# ------------------------------------------------------------------ 13F

def load_13f():
    """Valid filings, and positions of those holding between 10 and 50 stocks (rules 1-3)."""
    subs = [pd.read_parquet(f) for f in sorted(D13.glob("*_sub.parquet"))]
    sub = pd.concat(subs).drop_duplicates("ACCESSION_NUMBER")
    sub["filed"] = pd.to_datetime(sub.FILING_DATE, format="%d-%b-%Y", errors="coerce")
    sub["period"] = pd.to_datetime(sub.PERIODOFREPORT, format="%d-%b-%Y", errors="coerce")
    sub = sub.dropna(subset=["filed", "period"])
    sub = sub[(sub.filed - sub.period).dt.days.between(0, 45)]
    sub = sub.sort_values("filed").drop_duplicates(["CIK", "period"])
    ok = set(sub.ACCESSION_NUMBER)
    holds = []
    for f in sorted(D13.glob("*_hold.parquet")):
        h = pd.read_parquet(f, columns=["ACCESSION_NUMBER", "CUSIP", "value", "shares"])
        h = h[h.ACCESSION_NUMBER.isin(ok) & (h.value > 0)]
        n = h.groupby("ACCESSION_NUMBER").CUSIP.transform("size")
        h = h[n.between(10, 50)].copy()
        # VALUE switched from thousands to dollars in 2023; I detect it from the implied price
        implied = (h.value / h.shares.replace(0, np.nan)).groupby(h.ACCESSION_NUMBER).transform("median")
        h["usd"] = h.value * np.where(implied < 2, 1000, 1)
        h["w"] = h.usd / h.groupby("ACCESSION_NUMBER").usd.transform("sum")
        tot = h.groupby("ACCESSION_NUMBER").usd.transform("sum")
        top10 = h.groupby("ACCESSION_NUMBER").w.transform(lambda w: w.nlargest(10).sum())
        holds.append(h[tot.between(2e8, 5e10) & (top10 >= 0.5)])
    hold = pd.concat(holds)
    return sub[["ACCESSION_NUMBER", "CIK", "period", "filed", "FILINGMANAGER_NAME"]], hold


def select_managers(sub, hold):
    """Managers who are also patient (rule 4), with their 5 largest positions."""
    h = hold.merge(sub[["ACCESSION_NUMBER", "CIK", "period"]], on="ACCESSION_NUMBER")
    # patience: % of current value in CUSIPs already held 4 quarters earlier. For the past I use
    # all of their filings, not only the ones that pass rules 1-3.
    all_prev = []
    for f in sorted(D13.glob("*_hold.parquet")):
        x = pd.read_parquet(f, columns=["ACCESSION_NUMBER", "CUSIP"])
        all_prev.append(x[x.ACCESSION_NUMBER.isin(set(sub.ACCESSION_NUMBER))].drop_duplicates())
    prev = pd.concat(all_prev).merge(sub[["ACCESSION_NUMBER", "CIK", "period"]], on="ACCESSION_NUMBER")
    prev["period"] = (prev.period + pd.DateOffset(months=12)) + pd.offsets.QuarterEnd(0)
    prev = prev[["CIK", "period", "CUSIP"]].drop_duplicates().assign(old=True)
    had_prev = prev[["CIK", "period"]].drop_duplicates().assign(has=True)
    h["period"] = h.period + pd.offsets.QuarterEnd(0)
    h = h.merge(prev, on=["CIK", "period", "CUSIP"], how="left").merge(had_prev, on=["CIK", "period"], how="left")
    pat = (h.w * h.old.fillna(False)).groupby(h.ACCESSION_NUMBER).sum().where(
        h.groupby("ACCESSION_NUMBER").has.first().fillna(False))
    s = sub.set_index("ACCESSION_NUMBER").loc[pat.index].assign(patience=pat)
    s["period"] = s.period + pd.offsets.QuarterEnd(0)
    s = s[s.patience >= 0.6]
    top = (h[h.ACCESSION_NUMBER.isin(s.index)].sort_values("w", ascending=False)
           .groupby("ACCESSION_NUMBER").head(TOP_IDEAS).drop(columns="period"))
    return s, top


# ------------------------------------------------------------------ CUSIP -> ticker

def figi_map(cusips):
    cache = json.loads(FIGI.read_text()) if FIGI.exists() else {}
    todo = [c for c in sorted(set(cusips)) if c not in cache]
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        jobs = [{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in batch]
        for attempt in range(10):
            try:
                r = requests.post("https://api.openfigi.com/v3/mapping", json=jobs, timeout=60)
            except requests.exceptions.RequestException:
                time.sleep(30)
                continue
            if r.status_code == 429 or r.status_code >= 500:  # rate limit or temporary outage
                time.sleep(30 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError("OpenFIGI no responde")
        for c, res in zip(batch, r.json()):
            data = res.get("data") or []
            eq = [d for d in data if d.get("marketSector") == "Equity"] or data
            cache[c] = eq[0]["ticker"] if eq else None
        FIGI.write_text(json.dumps(cache))
        time.sleep(2.5)  # without a key: 25 requests a minute
        if i % 500 == 0:
            print(f"  OpenFIGI {i}/{len(todo)}", flush=True)
    return cache


# ------------------------------------------------------------------ carteras

def buy_and_hold(px, members_by_date, dates_in):
    """Daily return of equal-weighted portfolios formed on dates_in and held without rebalancing."""
    rets, turns = [], {}
    prev_w = None
    for k, d0 in enumerate(dates_in):
        d1 = dates_in[k + 1] if k + 1 < len(dates_in) else px.index[-1]
        names = [s for s in members_by_date[d0] if s in px.columns and pd.notna(px.at[d0, s])]
        seg = px.loc[d0:d1, names].ffill()
        rel = seg / seg.iloc[0]
        val = rel.mean(axis=1)
        rets.append(val.pct_change().iloc[1:])
        w_new = pd.Series(1 / len(names), index=names)
        turns[d0] = (w_new.sub(prev_w, fill_value=0).abs().sum() if prev_w is not None else 1.0)
        end = rel.iloc[-1]
        prev_w = end / end.sum()
    return pd.concat(rets), pd.Series(turns)


def monthly(daily, turn, cost):
    d = daily.copy()
    for dt, t in turn.items():
        nxt = d.index[d.index > dt]
        if len(nxt):
            d.loc[nxt[0]] -= t * cost
    return (1 + d).groupby(d.index.to_period("M")).prod() - 1


def nw(x, lags=3):
    x = x.dropna()
    fit = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return x.mean() * 12, fit.tvalues[0]


def main(holdout: bool):
    sub, hold = load_13f()
    sel, top = select_managers(sub, hold)
    tick = figi_map(top.CUSIP)
    top = top.merge(sel[["period"]], left_on="ACCESSION_NUMBER", right_index=True)
    top["ticker"] = top.CUSIP.map(tick).str.replace("/", "-", regex=False)

    uni = pd.read_pickle(BT / "universe.pkl")
    sym2cik = uni.dropna(subset=["cik"]).set_index("symbol")["cik"]
    px = pd.read_parquet(BT / "prices_adj_close.parquet")
    pan = pd.read_parquet(BT / "panel.parquet", columns=["date", "cik", "market_cap_basic"])
    cik2sym = {v: k for k, v in sym2cik.items()}

    periods = sorted(top.period.unique())
    form = {p: px.index[px.index.searchsorted(p + pd.Timedelta(days=46))] for p in periods
            if px.index.searchsorted(p + pd.Timedelta(days=46)) < len(px.index)}
    clone, universe, info = {}, {}, []
    for p, d0 in form.items():
        me = (d0 - pd.offsets.MonthEnd(1)).normalize()
        big = pan[(pan.date == me) & (pan.market_cap_basic > 1e9)].cik.map(cik2sym).dropna()
        big = [s for s in big if s in px.columns and pd.notna(px.at[d0, s])]
        t = top[(top.period == p) & top.ticker.isin(big)]
        score = t.groupby("ticker").agg(n=("CIK", "nunique"), w=("w", "sum")).sort_values(["n", "w"], ascending=False)
        clone[d0] = list(score.index[:N_HOLD])
        universe[d0] = big
        info.append({"form": d0, "managers": sel[sel.period == p].shape[0], "names": len(clone[d0]),
                     "max_n": score.n.max() if len(score) else 0, "top5": ", ".join(score.index[:5])})
    info = pd.DataFrame(info).set_index("form")

    a, b = (pd.Timestamp(HOLDOUT), px.index[-1]) if holdout else map(pd.Timestamp, DEV)
    fd = [d for d in form.values() if a <= d <= b and len(clone[d]) >= 10]
    if not holdout:
        fd = fd  # the last development quarter is held until the first hold-out formation
    end = next((d for d in form.values() if d > fd[-1]), px.index[-1])
    pxs = px.loc[:end]
    c_d, c_t = buy_and_hold(pxs, clone, fd)
    u_d, u_t = buy_and_hold(pxs, universe, fd)
    spy = pxs["SPY"].pct_change().loc[c_d.index] if "SPY" in pxs else None

    out = pd.DataFrame({"clone": monthly(c_d, c_t, COST), "clone_fx": monthly(c_d, c_t, COST + FX),
                        "universe": monthly(u_d, u_t, COST)})
    if spy is not None:
        out["spy"] = (1 + spy).groupby(spy.index.to_period("M")).prod() - 1
    out = out.iloc[1:-1] if len(out) > 3 else out  # partial months at both ends
    lbl = "HOLD-OUT" if holdout else "DEVELOPMENT"
    print(f"\n=== {lbl}: {len(fd)} formations {fd[0]:%Y-%m} to {fd[-1]:%Y-%m}, {len(out)} months ===")
    print(f"managers selected per quarter: median {info.loc[fd, 'managers'].median():.0f} "
          f"(min {info.loc[fd, 'managers'].min()}, max {info.loc[fd, 'managers'].max()}); "
          f"average turnover {c_t.iloc[1:].mean() / 2:.0%} per quarter")
    for name, x in [("1. clone − universe (net 10 bp)", out.clone - out.universe),
                    ("3. clone − SPY (net 10 bp)", out.clone - out.spy),
                    ("   clone − universe (with 0.5% FX)", out.clone_fx - out.universe),
                    ("   clone − SPY (with 0.5% FX)", out.clone_fx - out.spy),
                    ("   universe − SPY", out.universe - out.spy)]:
        v, t = nw(x)
        print(f"  {name:34s} {v:+.2%}/yr  t {t:5.2f}")
    cagr = lambda r: (1 + r).prod() ** (12 / len(r)) - 1  # noqa: E731
    print("  CAGR:", {k: f"{cagr(out[k]):.1%}" for k in out})
    if not holdout:
        for p, q in [("2014-11", "2018-12"), ("2019-01", "2023-12")]:
            v, t = nw((out.clone - out.universe).loc[p:q])
            v2, t2 = nw((out.clone - out.spy).loc[p:q])
            print(f"  {p}..{q}: − universe {v:+.2%} (t {t:.2f}) | − SPY {v2:+.2%} (t {t2:.2f})")
    print("\nlatest formations, top 5 ideas:")
    print(info.loc[fd].tail(4)[["managers", "max_n", "top5"]].to_string())
    out.to_csv(HERE / f"monthly_{'holdout' if holdout else 'dev'}.csv")
    info.to_csv(HERE / "formations.csv")


if __name__ == "__main__":
    main("--holdout" in sys.argv)
