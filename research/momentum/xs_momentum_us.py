"""Cross-sectional momentum on the equity-screener point-in-time US universe (mcap > $1B at each month end).
Signal: return t-12 -> t-1 (skip last month). Monthly rebalance, equal weight. 10 bp per side on turnover.
Caveat: universe = names listed TODAY (survivorship): delisted losers are missing -> loser leg looks too good."""
import numpy as np, pandas as pd, statsmodels.api as sm
from pathlib import Path
B = Path(__file__).resolve().parents[2] / "equity-screener" / "data" / "backtest"  # built by equity-screener/run_backtest.py
px = pd.read_parquet(B / "prices_adj_close.parquet")
px.index = pd.to_datetime(px.index)
me = px.resample("ME").last()
ret = me.pct_change(fill_method=None)
ret = ret.where(ret.abs() < 3)                        # drop obvious bad prints (>+300%)
panel = pd.read_parquet(B / "panel.parquet", columns=["symbol", "date", "market_cap_basic", "sector"])
panel["date"] = pd.to_datetime(panel.date) + pd.offsets.MonthEnd(0)
mcap = panel.pivot_table(index="date", columns="symbol", values="market_cap_basic", aggfunc="last")
mcap = mcap.reindex(columns=me.columns)
elig = (mcap > 1e9) & me.reindex(mcap.index).notna()

def mom(lb, skip=1):
    return me.shift(skip) / me.shift(lb) - 1

COST = 0.0010
def backtest(signal, q=5, name=""):
    rows = []; prev = {}
    dates = [d for d in elig.index if d in signal.index][12:-1]
    for d in dates:
        nxt = ret.index[ret.index.get_loc(d) + 1]
        s = signal.loc[d][elig.loc[d]].dropna()
        r = ret.loc[nxt]
        s = s[r.reindex(s.index).notna()]            # need next-month return (survivor universe => mostly yes)
        if len(s) < 100: continue
        bins = pd.qcut(s.rank(method="first"), q, labels=False)
        out = {"date": nxt, "n": len(s), "univ": r[s.index].mean()}
        for k in range(q):
            names = bins.index[bins == k]
            w = pd.Series(1 / len(names), index=names)
            tov = (w.sub(prev.get(k, pd.Series(dtype=float)), fill_value=0)).abs().sum()
            out[f"Q{k+1}"] = r[names].mean() - tov * COST
            out[f"tov{k+1}"] = tov
            prev[k] = w * (1 + r[names]) / (1 + r[names]).mean()   # drifted weights
        rows.append(out)
    df = pd.DataFrame(rows).set_index("date")
    df["WML"] = df[f"Q{q}"] - df["Q1"]
    df["TopXS"] = df[f"Q{q}"] - df["univ"]
    return df

def nw_t(x, lags=3):
    m = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return m.params[0] * 12, m.tvalues[0]

def report(df, label, q=5):
    print(f"\n=== {label}  ({df.index[0]:%Y-%m} – {df.index[-1]:%Y-%m}, avg n={df.n.mean():.0f}) ===")
    cagr = lambda x: (1 + x).prod() ** (12 / len(x)) - 1
    for c in [f"Q{k+1}" for k in range(q)] + ["univ"]:
        x = df[c]; print(f"  {c:5s} CAGR={cagr(x):6.1%} vol={x.std()*np.sqrt(12):5.1%}" + (f"  turnover/mes={df['tov'+c[1:]].mean():.0%}" if c.startswith("Q") else ""))
    for c in ["WML", "TopXS"]:
        a, t = nw_t(df[c]); print(f"  {c:5s} {a:+6.1%}/año  t(NW)={t:5.2f}  peor mes={df[c].min():+.1%} ({df[c].idxmin():%Y-%m})")
    for a, b in [("2012", "2016"), ("2017", "2021"), ("2022", "2026")]:
        x = df.loc[a:b]
        print(f"    {a}-{b}: WML {x.WML.mean()*12:+6.1%}  Top-univ {x.TopXS.mean()*12:+6.1%}")
    return df

if __name__ == "__main__":
    res = {}
    for lb, lab in [(12, "12-1 (estándar)"), (6, "6-1"), (3, "3-1")]:
        res[lab] = report(backtest(mom(lb)), f"Momentum {lab}")
    # short-term reversal control: last month return (expected negative)
    report(backtest(me / me.shift(1) - 1), "1 mes (reversal a corto)")
    # risk-adjusted momentum: 12-1 return / 12m vol of monthly returns
    vol = ret.rolling(12).std().shift(1)
    report(backtest(mom(12) / vol), "12-1 ajustado por vol")
    res["12-1 (estándar)"].to_csv("xs_mom_12_1_monthly.csv")
