"""Reruns my gross profitability backtest (gross profit / assets) value-weighted,
to see whether the gap with OSAP comes from weighting or from survivorship bias.

Same universe, signal and dates as equity-screener/src/backtest/quality.py. Only the weights
change: month-end market cap instead of equal weights. I compare gross, as OSAP does.
Usage: python gp_vw.py   (needs the run_backtest.py caches and data/ from compare.py)
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
SCREENER = HERE.parent.parent / "equity-screener"
sys.path.insert(0, str(SCREENER))
os.chdir(SCREENER)

import run_backtest as rb  # noqa: E402
from src.backtest import analysis, prices, quality  # noqa: E402

SIG = "gross_profitability"


def quintile_weights(hist, weight_col=None):
    """{1..5: weights date x cik}. Quintile 5 = highest gross profitability."""
    h = hist[hist[SIG].notna()].copy()
    h["q"] = h.groupby("date")[SIG].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1)
    h["w"] = 1.0 if weight_col is None else h[weight_col]
    out = {}
    for q, g in h.groupby("q"):
        w = g.pivot_table(index="date", columns="cik", values="w", aggfunc="first")
        out[int(q)] = w.div(w.sum(axis=1), axis=0).fillna(0.0)
    return out


def all_weights(hist, weight_col=None):
    h = hist.assign(w=1.0 if weight_col is None else hist[weight_col])
    w = h.pivot_table(index="date", columns="cik", values="w", aggfunc="first")
    return w.div(w.sum(axis=1), axis=0).fillna(0.0)


def main():
    data = rb.load_all(False)
    px, sym2cik = data["prices"], data["sym2cik"]
    dates = analysis.month_ends(px["close"].index)
    adj_m = rb.by_cik(prices.month_end(px["adj_close"]), sym2cik).loc[:dates[-1]]
    fwd = analysis.forward_returns(adj_m)
    pan = pd.read_parquet(rb.CACHE / "panel.parquet")
    pan = analysis.attach_returns(pan[pan["date"].isin(dates)], fwd)
    hist = quality.quality_history(pan, data["snapshots"])
    ret = fwd["1m"]

    series, conc = {}, []
    for lbl, col in [("ew", None), ("vw", "market_cap_basic")]:
        qs = {q: analysis.portfolio_returns(w, ret) for q, w in quintile_weights(hist, col).items()}
        avg = pd.concat([p["gross"] for p in qs.values()], axis=1).mean(axis=1)
        uni = analysis.portfolio_returns(all_weights(hist, col), ret)["gross"]
        series[f"{lbl}_top_minus_avg"] = qs[5]["gross"] - avg
        series[f"{lbl}_bottom_minus_avg"] = qs[1]["gross"] - avg
        series[f"{lbl}_top_minus_universe"] = qs[5]["gross"] - uni
        series[f"{lbl}_top_minus_universe_net"] = qs[5]["net"] - analysis.portfolio_returns(all_weights(hist, col), ret)["net"]
        if col:
            w5 = quintile_weights(hist, col)[5]
            conc = pd.DataFrame({"top5_weight": w5.apply(lambda r: r.nlargest(5).sum(), axis=1),
                                 "n": (w5 > 0).sum(axis=1)})
    s = pd.DataFrame(series)

    # OSAP, same leg (top quintile − average), size-filtered and VW
    o = pd.read_parquet(HERE / "data" / "ex_nyse_p20_me.parquet")
    o = o[o.signalname == "GP"]
    o["date"] = pd.to_datetime(o.date) + pd.offsets.MonthEnd(0)
    op = o.pivot(index="date", columns="port", values="ret").drop(columns="LS") / 100
    s["osap_top_minus_avg"] = op["05"] - op.mean(axis=1)
    s["osap_bottom_minus_avg"] = op["01"] - op.mean(axis=1)
    s = s.loc["2012-02":]

    rows = []
    for lbl, a, b in [("2012-02..2025-12", "2012-02", "2025-12"), ("2012-02..2016-12", "2012-02", "2016-12"),
                      ("2017-01..2021-11", "2017-01", "2021-11"), ("2021-12..2025-12", "2021-12", "2025-12"),
                      ("2012-02..2026-09 (no OSAP)", "2012-02", "2026-09")]:
        for c in s.columns:
            x = s[c].loc[a:b].dropna()
            if len(x) > 12:
                rows.append({"series": c, "period": lbl, "annual": x.mean() * 12, "t": analysis.newey_west_t(x, 3)})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(out.pivot(index="series", columns="period", values="annual").round(3).to_string())
    print(out.pivot(index="series", columns="period", values="t").round(2).to_string())
    ov = s.loc[:"2025-12"].dropna()
    print("\ncorrelation with OSAP (top quintile − average):",
          f"EW {ov.ew_top_minus_avg.corr(ov.osap_top_minus_avg):.2f}  VW {ov.vw_top_minus_avg.corr(ov.osap_top_minus_avg):.2f}")
    print("VW top-quintile concentration: weight of the 5 largest, mean by year")
    print(conc.groupby(conc.index.year).mean().round(2).T.to_string())
    last = hist[(hist.date == hist.date.max()) & hist[SIG].notna()]
    top = last[last[SIG] >= last[SIG].quantile(0.8)].nlargest(8, "market_cap_basic")
    print("\nlargest weights today:", ", ".join(top["name"]))
    out.to_csv(HERE / "gp_vw.csv", index=False)
    s.to_csv(HERE / "gp_vw_monthly.csv")


if __name__ == "__main__":
    main()
