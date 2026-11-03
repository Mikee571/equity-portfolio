"""Cash profitability filter (TTM CFO / assets), as set out in PREREGISTRATION.md.

Usage:
    python run_filter.py            development (Feb 2012 to Dec 2023)
    python run_filter.py --holdout  hold-out (Jan 2024 onwards); only once development is closed
"""
import os
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SCREENER = HERE.parent.parent / "equity-screener"
sys.path.insert(0, str(SCREENER))
os.chdir(SCREENER)

import run_backtest as rb  # noqa: E402
from src import config  # noqa: E402
from src.backtest import analysis, prices  # noqa: E402

DEV = ("2012-02", "2023-12")
HOLDOUT = "2024-01"
QUANTILE = 0.2


def cash_profitability(snapshots: pd.DataFrame, date) -> pd.Series:
    """TTM CFO / assets from the latest snapshot with both figures published before `date`."""
    date = pd.Timestamp(date)
    s = snapshots[(snapshots["known"] < date) & (snapshots["known_quality"] < date)
                  & (snapshots["period_end"] >= date - pd.Timedelta(days=456))
                  & snapshots["cfo"].notna() & (snapshots["assets"] > 0)]
    s = s.sort_values(["cik", "period_end"]).drop_duplicates("cik", keep="last").set_index("cik")
    return s["cfo"] / s["assets"]


def weights(frame: pd.DataFrame) -> pd.DataFrame:
    w = frame.assign(w=1.0).pivot_table(index="date", columns="cik", values="w", aggfunc="first")
    return w.div(w.sum(axis=1), axis=0).fillna(0.0)


def main(holdout: bool):
    data = rb.load_all(False)
    px, sym2cik, snaps = data["prices"], data["sym2cik"], data["snapshots"]
    dates = analysis.month_ends(px["close"].index)
    adj_m = rb.by_cik(prices.month_end(px["adj_close"]), sym2cik).loc[:dates[-1]]
    fwd = analysis.forward_returns(adj_m)
    pan = pd.read_parquet(rb.CACHE / "panel.parquet")
    pan = analysis.attach_returns(pan[pan["date"].isin(dates)], fwd)
    uni, ranked, _ = analysis.screen_history(pan)

    flags = []
    for d, cs in uni.groupby("date"):
        sig = cash_profitability(snaps, d).reindex(cs["cik"].unique()).dropna()
        low = sig[sig <= sig.quantile(QUANTILE)].index
        flags.append(pd.DataFrame({"date": d, "cik": sig.index, "cashprof": sig.values,
                                   "low": sig.index.isin(low)}))
    flags = pd.concat(flags, ignore_index=True)
    uni = uni.merge(flags, on=["date", "cik"], how="left")
    ranked = ranked.merge(flags[["date", "cik", "low"]], on=["date", "cik"], how="left")
    coverage = uni.cashprof.notna().groupby(uni.date).mean().mean()

    keep_r = ranked[ranked["low"] != True].copy()  # noqa: E712  (no data: stays in)
    keep_r["rank"] = keep_r.groupby("date").cumcount() + 1
    ports = {
        "universe": weights(uni),
        "universe_ex_low": weights(uni[uni["low"] != True]),  # noqa: E712
        "low_quintile": weights(uni[uni["low"] == True]),  # noqa: E712
        "top10": weights(ranked[ranked["rank"] <= config.TOP_N]),
        "top10_filtered": weights(keep_r[keep_r["rank"] <= config.TOP_N]),
    }
    r = {k: analysis.portfolio_returns(w, fwd["1m"]) for k, w in ports.items()}
    net = pd.DataFrame({k: v["net"] for k, v in r.items()})
    turn = pd.DataFrame({k: v["turnover"] for k, v in r.items()})

    a, b = (HOLDOUT, None) if holdout else DEV
    net, turn = net.loc[a:b], turn.loc[a:b]
    print(f"\n=== {'HOLD-OUT' if holdout else 'DEVELOPMENT'} {net.index[0]:%Y-%m}..{net.index[-1]:%Y-%m} "
          f"({len(net)} months) | signal coverage {coverage:.0%} ===")
    tests = [("1. universe ex low quintile − universe", "universe_ex_low", "universe"),
             ("3. low quintile − universe", "low_quintile", "universe"),
             ("   filtered top 10 − top 10", "top10_filtered", "top10"),
             ("   filtered top 10 − universe", "top10_filtered", "universe"),
             ("   top 10 − universe", "top10", "universe")]
    for name, x, y in tests:
        e = analysis.excess_stats(net[x], net[y])
        print(f"  {name:42s} {e['excess_ann']:+.2%}/yr  t {e['t_stat']:5.2f}  TE {e['tracking_error']:.1%}")
    print("\n  net CAGR:", {k: f"{analysis.performance(net[k])['cagr']:.1%}" for k in net})
    print("  average monthly turnover:", {k: f"{turn[k].mean():.0%}" for k in turn})
    if not holdout:
        for lbl, (p, q) in analysis.periods(net.index).items():
            if lbl == "full":
                continue
            e = analysis.excess_stats(net.loc[p:q, "universe_ex_low"], net.loc[p:q, "universe"])
            e2 = analysis.excess_stats(net.loc[p:q, "low_quintile"], net.loc[p:q, "universe"])
            print(f"  {lbl}: ex low − universe {e['excess_ann']:+.2%} (t {e['t_stat']:.2f}) | "
                  f"low quintile − universe {e2['excess_ann']:+.2%} (t {e2['t_stat']:.2f})")
    net.to_csv(HERE / f"monthly_{'holdout' if holdout else 'dev'}.csv")


if __name__ == "__main__":
    main("--holdout" in sys.argv)
