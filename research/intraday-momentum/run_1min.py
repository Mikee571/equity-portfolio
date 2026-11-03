"""Beat the Market with 1-minute Alpaca bars and checks every 30 minutes, as in the paper.

Same rules and parameters as btm.py. Only the data changes: the 30-minute bars are built
from 1-minute bars, and the session VWAP is computed minute by minute.
Periods fixed before looking: inside the paper's sample (2016 – Apr 2024) and
post-publication (May 2024 – today).
Usage: python fetch_alpaca.py && python run_1min.py
"""
import pandas as pd

import btm

DATA = btm.DATA

# The authors' monthly table, FAQ Q24 of the paper (Feb 2025 version, p. 42), 2016–2023, in %.
# 2024 onwards comes from btm.PAPER_MONTHLY (Feb 2026 version).
_PAPER_ROWS = {
    2016: [-1.0, -1.9, 1.3, -1.4, 0.4, -7.3, -3.1, -5.2, 8.4, -5.0, 1.4, 0.7],
    2017: [-3.3, 0.9, 1.7, -3.3, -2.4, 0.4, -1.8, 3.6, -1.1, 2.9, -2.2, -2.3],
    2018: [3.5, 8.9, 7.2, 3.5, -4.7, 2.0, 6.2, -1.7, -3.5, 13.4, 3.0, 12.5],
    2019: [0.9, -0.7, 2.9, 0.9, -5.1, -0.5, 1.4, 6.8, -1.4, 2.6, -1.7, 1.0],
    2020: [5.3, 1.9, -0.5, -1.8, -0.2, 8.0, 0.1, -1.8, 14.3, 2.8, -1.1, -1.9],
    2021: [7.8, 3.1, 0.7, 6.1, 2.6, -1.0, 2.8, 1.7, 2.8, 3.3, -3.2, 4.1],
    2022: [-5.5, 2.8, 0.2, 9.0, 2.1, 0.5, 0.2, 6.3, -1.0, 5.8, 1.6, 0.7],
    2023: [2.9, -1.3, 7.8, 1.8, 2.9, 4.1, 2.2, 6.0, 2.9, -1.1, 0.5, 3.8],
}
PAPER = {f"{y}-{m:02d}": v for y, row in _PAPER_ROWS.items() for m, v in enumerate(row, 1)}
PAPER.update(btm.PAPER_MONTHLY)


def bars_30(m1: pd.DataFrame) -> pd.DataFrame:
    tp = (m1.High + m1.Low + m1.Close) / 3
    out = []
    for _, g in m1.groupby(m1.index.date):
        vw = (tp.loc[g.index] * g.Volume).cumsum() / g.Volume.cumsum().clip(lower=1)
        r = g.resample("30min", origin="start").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        r["VWAP"] = vw.resample("30min", origin="start").last()
        out.append(r.dropna())
    return pd.concat(out)


def daily_closes() -> pd.Series:
    f = DATA / "spy_daily_2015.csv"
    if f.exists():
        return pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
    import yfinance as yf
    s = yf.download("SPY", start="2015-06-01", interval="1d", progress=False,
                    auto_adjust=True, multi_level_index=False)["Close"].rename("close")
    s.to_csv(f)
    return s


def main() -> None:
    m1 = pd.read_parquet(DATA / "spy_1m_alpaca.parquet")
    b30 = bars_30(m1)
    # days with an incomplete session (half days): the paper keeps them, and so do I
    daily = daily_closes()
    res = btm.backtest(b30, daily)
    res_cost = btm.backtest(b30, daily, btm.Params(cost_bps=1.0))
    res.to_csv(DATA / "btm_daily_30m_alpaca.csv")
    spy = daily.pct_change().reindex(res.index)

    print("== Validation against the authors' monthly returns (2016 to Aug 2025) ==")
    mine = btm.monthly(res["ret"])
    comp = pd.DataFrame({"mine_1min": mine, "paper": pd.Series(PAPER)}).dropna()
    hourly = pd.read_csv(DATA / "btm_daily_1h.csv", index_col=0, parse_dates=True)["ret"]
    comp["mine_hourly"] = btm.monthly(hourly)
    print(comp.loc["2024-01":].round(1).to_string())
    for a, b in [("2016-01", "2023-12"), ("2024-01", "2025-08")]:
        c = comp.loc[a:b]
        print(f"correlation {a}..{b} ({len(c)} months): 1 min {c.mine_1min.corr(c.paper):.2f} | "
              f"mean 1 min {c.mine_1min.mean():+.2f}% vs authors {c.paper.mean():+.2f}% a month"
              + (f" | hourly {c.mine_hourly.corr(c.paper):.2f}" if a >= "2024" else ""))
    yr_p = pd.Series(PAPER).groupby(lambda k: k[:4]).apply(lambda s: ((1 + s / 100).prod() - 1) * 100)
    for a, b in [("2024-05", "2024-12"), ("2025-01", "2025-08")]:
        c = comp.loc[a:b] / 100
        print(f"  {a} to {b}: authors {(1 + c.paper).prod() - 1:+.1%} | 1 min {(1 + c.mine_1min).prod() - 1:+.1%}")

    print("\n== By year (to compare with the paper's annual table) ==")
    yr = (1 + res["ret"]).groupby(res.index.year).prod() - 1
    yr_spy = (1 + spy).groupby(spy.index.year).prod() - 1
    yr_p.index = yr_p.index.astype(int)
    print(pd.DataFrame({"strategy": yr * 100, "authors": yr_p, "SPY": yr_spy * 100}).round(1).to_string())

    today = str(pd.Timestamp.now().date())
    periods = {
        "Inside the paper's sample (2016 – Apr 2024)": ("2016-01-01", "2024-04-30"),
        "Post-publication (May 2024 – today)": ("2024-05-01", today),
        "  of which May–Dec 2024": ("2024-05-01", "2024-12-31"),
        "  of which 2025": ("2025-01-01", "2025-12-31"),
        "  of which 2026 to today": ("2026-01-01", today),
    }
    for name, (a, b) in periods.items():
        sl = slice(a, b)
        print(f"\n== {name} ==")
        print("strategy        ", btm.fmt(btm.stats(res["ret"][sl])))
        print("with 1 bp/side  ", btm.fmt(btm.stats(res_cost["ret"][sl])))
        print("SPY buy & hold  ", btm.fmt(btm.stats(spy[sl])))
        if not name.startswith("  "):
            lo, hi = btm.sharpe_ci(res["ret"][sl])
            print(f"90% CI Sharpe: {lo:.2f} to {hi:.2f}")


if __name__ == "__main__":
    main()
