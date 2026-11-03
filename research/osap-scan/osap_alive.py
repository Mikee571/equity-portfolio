"""Which published signals still deliver something in mid and large caps since 2015.

Uses the size-filtered OSAP portfolios (ME > NYSE 20th percentile) downloaded by
osap-check/compare.py. For each signal: long-short and long leg (long quintile or decile
minus the average of all), before publication, after it and in 2015-2025. Corrects for
multiple testing with Benjamini-Hochberg and with the Harvey, Liu and Zhu t > 3 threshold.
Usage: python osap_alive.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

HERE = Path(__file__).parent
OSAP = HERE.parent / "osap-check" / "data"


def nw(x, lags=3):
    x = x.dropna()
    if len(x) < 36:
        return np.nan, np.nan
    fit = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return x.mean() * 12, fit.tvalues[0]


def main():
    d = pd.read_parquet(OSAP / "ex_nyse_p20_me.parquet")
    d["date"] = pd.to_datetime(d.date) + pd.offsets.MonthEnd(0)
    d["ret"] = d.ret / 100
    doc = pd.read_parquet(OSAP / "doc.parquet").set_index("Acronym") if (OSAP / "doc.parquet").exists() else None
    rows = []
    for sig, g in d.groupby("signalname"):
        p = g.pivot(index="date", columns="port", values="ret")
        if "LS" not in p:
            continue
        qs = sorted(c for c in p.columns if c != "LS")
        top, bot = p[qs[-1]], p[qs[0]]
        avg = p[qs].mean(axis=1)
        # the long leg is the one in the direction of the long-short
        long_leg = (top - avg) if (p.LS - (top - bot)).abs().mean() < (p.LS + (top - bot)).abs().mean() else (bot - avg)
        end = int(doc.loc[sig, "SampleEndYear"]) if doc is not None and sig in doc.index else 2000
        pub = int(doc.loc[sig, "Year"]) if doc is not None and sig in doc.index else 2000
        r = {"signal": sig, "pub": pub, "cat": doc.loc[sig, "Cat.Data"] if doc is not None and sig in doc.index else ""}
        for lbl, x in [("ls_in", p.LS.loc[:str(end)]), ("ls_post", p.LS.loc[str(pub + 1):]),
                       ("ls_15", p.LS.loc["2015":]), ("long_15", long_leg.loc["2015":])]:
            r[lbl], r["t_" + lbl] = nw(x)
        rows.append(r)
    t = pd.DataFrame(rows).dropna(subset=["t_ls_15"])
    for c in ["ls_15", "long_15"]:
        pv = 2 * (1 - __import__("scipy").stats.norm.cdf(t["t_" + c].abs()))
        t["bh_" + c] = multipletests(pv, alpha=0.05, method="fdr_bh")[0]
    t["decay"] = 1 - t.ls_post / t.ls_in
    t.to_csv(HERE / "osap_alive.csv", index=False)
    n = len(t)
    print(f"signals {n} | median long-short in sample {t.ls_in.median():.1%}, post-publication "
          f"{t.ls_post.median():.1%}, 2015-25 {t.ls_15.median():.1%}")
    for c in ["ls_15", "long_15"]:
        print(f"{c}: t>2 {(t['t_'+c] > 2).sum()} | t>3 {(t['t_'+c] > 3).sum()} | BH 5% {t['bh_'+c].sum()} "
              f"(by chance I'd expect ~{0.025*n:.0f} with t>2)")
    cols = ["signal", "pub", "cat", "ls_in", "ls_15", "t_ls_15", "long_15", "t_long_15"]
    pd.set_option("display.width", 200)
    print("\nTop 25 by long-leg t-stat, 2015-25:")
    print(t.sort_values("t_long_15", ascending=False)[cols].head(25).to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
