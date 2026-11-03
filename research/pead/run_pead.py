"""PEAD with an XBRL-based SUE, as set out in PREREGISTRATION.md.

Usage:
    python run_pead.py            development (announcements 2012-2023)
    python run_pead.py --holdout  hold-out (announcements from 2024); only once development is closed
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

HERE = Path(__file__).parent
BT = HERE.parent.parent / "equity-screener" / "data" / "backtest"
COST = 0.0010
HOLD = (2, 61)
DEV = ("2012-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"


def nw(x, lags=3):
    x = x.dropna()
    fit = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return x.mean() * 12, fit.tvalues[0]


def announcement_dates(sue: pd.DataFrame) -> pd.DataFrame:
    """First 8-K with item 2.02 between the quarter end and the 10-Q/10-K; if there is none, the 10-Q/10-K."""
    f = pd.read_parquet(HERE / "data" / "filings.parquet")
    ek = f[(f.form == "8-K") & f["items"].fillna("").str.contains("2.02", regex=False)][["cik", "filingDate"]]
    m = sue[["cik", "period_end", "report_filed"]].merge(ek, on="cik")
    m = m[(m.filingDate > m.period_end) & (m.filingDate <= m.report_filed.dt.normalize())]
    first = m.groupby(["cik", "period_end"]).filingDate.min().rename("ek_date")
    out = sue.merge(first, on=["cik", "period_end"], how="left")
    out["from_8k"] = out.ek_date.notna()
    out["ann_date"] = out.ek_date.fillna(out.report_filed.dt.normalize())
    return out


def deciles_prior_quarter(ev: pd.DataFrame) -> pd.Series:
    """SUE decile using the cut-offs from the previous calendar quarter's events."""
    ev = ev.assign(qtr=ev.ann_date.dt.to_period("Q"))
    cuts = ev.groupby("qtr").sue.apply(lambda s: np.quantile(s, np.linspace(0.1, 0.9, 9)))
    prev = ev.qtr - 1
    dec = pd.Series(np.nan, index=ev.index)
    for q, idx in ev.groupby(prev).groups.items():
        if q in cuts.index:
            dec[idx] = np.searchsorted(cuts[q], ev.loc[idx, "sue"].values, side="right") + 1
    return dec


def load():
    uni = pd.read_pickle(BT / "universe.pkl")
    cik2sym = uni.dropna(subset=["cik"]).drop_duplicates("cik").set_index("cik")["symbol"]
    px = pd.read_parquet(BT / "prices_adj_close.parquet")
    ret = px.pct_change(fill_method=None).clip(-0.9, 3.0)
    sue = pd.read_parquet(HERE / "data" / "sue.parquet").dropna(subset=["sue"])
    sue = sue[sue.cik.isin(cik2sym.index)]
    ev = announcement_dates(sue)
    ev["symbol"] = ev.cik.map(cik2sym)
    ev = ev[ev.symbol.isin(ret.columns)].copy()
    days = ret.index
    ev["i0"] = days.searchsorted(ev.ann_date)
    ev = ev[ev.i0 < len(days)]
    ev["decile"] = deciles_prior_quarter(ev)
    ev = ev.dropna(subset=["decile"])
    # size: market cap at the end of the month before the announcement
    pan = pd.read_parquet(BT / "panel.parquet", columns=["date", "cik", "market_cap_basic"])
    ev["mdate"] = ev.ann_date - pd.offsets.MonthEnd(1)
    ev = ev.merge(pan.rename(columns={"date": "mdate"}), on=["mdate", "cik"], how="left")
    return ev, ret


def calendar_portfolio(ev: pd.DataFrame, ret: pd.DataFrame) -> pd.DataFrame:
    """Equal-weighted daily return of the stocks inside their [2, 61] window, gross and net."""
    T, cols = len(ret), {s: k for k, s in enumerate(ret.columns)}
    hold = np.zeros((T + 1, len(cols)))
    entries, exits = np.zeros(T + 1), np.zeros(T + 1)
    for i0, s in zip(ev.i0.values, ev.symbol.values):
        a, b = i0 + HOLD[0], min(i0 + HOLD[1] + 1, T)
        if a >= T:
            continue
        hold[a, cols[s]] += 1
        hold[b, cols[s]] -= 1
        entries[a] += 1
        exits[b] += 1
    hold = np.cumsum(hold, axis=0)[:T]
    r = np.nan_to_num(ret.values)
    n = hold.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        gross = (hold * r).sum(axis=1) / n
        cost = COST * (entries[:T] + exits[:T]) / n
    out = pd.DataFrame({"gross": gross, "net": gross - cost, "n": n}, index=ret.index)
    return out[out.n > 0]


def monthly(daily: pd.Series) -> pd.Series:
    return (1 + daily).groupby(daily.index.to_period("M")).prod() - 1


def event_car(ev: pd.DataFrame, ab: np.ndarray, window) -> np.ndarray:
    a, b = window
    cs = np.vstack([np.zeros(ab.shape[1]), np.cumsum(np.nan_to_num(ab), axis=0)])
    cols = {s: k for k, s in enumerate(ab_cols)}
    lo = np.clip(ev.i0.values + a, 0, len(ab))
    hi = np.clip(ev.i0.values + b + 1, 0, len(ab))
    j = np.array([cols[s] for s in ev.symbol.values])
    car = cs[hi, j] - cs[lo, j]
    return np.where(ev.i0.values + b < len(ab), car, np.nan)


def main(holdout: bool):
    global ab_cols
    ev, ret = load()
    last_ok = ret.index[-HOLD[1] - 2]
    if holdout:
        ev = ev[(ev.ann_date >= HOLDOUT_START) & (ev.ann_date <= last_ok)]
        label = f"HOLD-OUT {HOLDOUT_START}..{last_ok:%Y-%m-%d}"
    else:
        ev = ev[ev.ann_date.between(*DEV)]
        label = f"DESARROLLO {DEV[0]}..{DEV[1]}"
    print(f"\n=== {label} ===  events {len(ev):,}  companies {ev.cik.nunique():,}  with 8-K {ev.from_8k.mean():.0%}")

    uni_d = ret.mean(axis=1)
    start = ev.ann_date.min()
    end = ret.index[min(ev.i0.max() + HOLD[1], len(ret) - 1)]
    p10 = calendar_portfolio(ev[ev.decile == 10], ret)
    p1 = calendar_portfolio(ev[ev.decile == 1], ret)
    m = pd.DataFrame({
        "d10": monthly(p10.gross), "d1": monthly(p1.gross), "d10_net": monthly(p10.net),
        "uni": monthly(uni_d.loc[start:end]),
    }).dropna()
    m = m.iloc[1:]  # the first month is partial
    tests = {
        "1. D10 − D1 (gross)": m.d10 - m.d1,
        "2. D10 − universe (net)": m.d10_net - m.uni,
        "   D10 − universe (gross)": m.d10 - m.uni,
        "   D1 − universe (gross)": m.d1 - m.uni,
    }
    print(f"\nCalendar-time portfolio, {len(m)} months, annualised (Newey-West t, 3 lags)")
    for k, x in tests.items():
        a, t = nw(x)
        print(f"  {k:28s} {a:+.2%}  t {t:5.2f}")
    print(f"  average names held: D10 {p10.n.mean():.0f}, D1 {p1.n.mean():.0f}")

    # descriptive: CAR by decile in event time
    ab = ret.sub(uni_d, axis=0).values
    ab_cols = list(ret.columns)
    ev["car01"] = event_car(ev, ab, (0, 1))
    ev["car261"] = event_car(ev, ab, HOLD)
    print("\nMean CAR by decile (abnormal against the EW universe)")
    print(ev.groupby("decile")[["car01", "car261"]].mean().mul(100).round(2).T.to_string())
    ev["size"] = pd.qcut(ev.market_cap_basic, 3, labels=["small", "mid", "large"])
    for col, name in [("size", "size tercile"), ("from_8k", "8-K date")]:
        t = ev[ev.decile.isin([1, 10])].pivot_table(index=col, columns="decile", values="car261", aggfunc="mean", observed=True)
        t["D10−D1"] = t[10.0] - t[1.0]
        print(f"\nCAR[2,61] by {name} (%)\n{t.mul(100).round(2).to_string()}")
    if not holdout:
        sub = ev[ev.decile.isin([1, 10])].assign(per=lambda d: np.where(d.ann_date < "2018-01-01", "2012-17", "2018-23"))
        t = sub.pivot_table(index="per", columns="decile", values="car261", aggfunc="mean")
        t["D10−D1"] = t[10.0] - t[1.0]
        print(f"\nCAR[2,61] by subperiod (%)\n{t.mul(100).round(2).to_string()}")
        for per, (a, b) in {"2012-17": ("2012", "2017"), "2018-23": ("2018", "2024-03")}.items():
            x = (m.d10 - m.d1).loc[a:b]
            v, t_ = nw(x)
            print(f"  calendario D10−D1 {per}: {v:+.2%} t {t_:.2f}")
    m.to_csv(HERE / f"monthly_{'holdout' if holdout else 'dev'}.csv")
    ev.to_parquet(HERE / "data" / f"events_{'holdout' if holdout else 'dev'}.parquet")


ab_cols = []

if __name__ == "__main__":
    main("--holdout" in sys.argv)
