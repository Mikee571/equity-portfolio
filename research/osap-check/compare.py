"""Compares my momentum and quality backtests with the Open Source Asset Pricing portfolios.

OSAP uses CRSP (delisted companies included). My backtests only use companies listed today.
Usage: python compare.py   (downloads OSAP's default release to ./data the first time)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

HERE = Path(__file__).parent
DATA = HERE / "data"
MOM = HERE.parent / "momentum" / "xs_mom_12_1_monthly.csv"
COST = 0.0010  # the same as in xs_momentum_us.py; I add it back to compare gross
FILES = ["quintiles_ew", "quintiles_vw", "ex_nyse_p20_me"]


def download():
    import openassetpricing as oap
    DATA.mkdir(exist_ok=True)
    o = oap.OpenAP()
    for n in FILES:
        if not (DATA / f"{n}.parquet").exists():
            o.dl_port(n, "pandas").to_parquet(DATA / f"{n}.parquet")


def load(name):
    d = pd.read_parquet(DATA / f"{name}.parquet")
    d["date"] = pd.to_datetime(d.date) + pd.offsets.MonthEnd(0)
    return d.pivot_table(index="date", columns=["signalname", "port"], values="ret") / 100


def nw(x, lags=3):
    x = x.dropna()
    t = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags}).tvalues[0]
    return x.mean() * 12, t


def top_bottom(p, sig):
    q = p[sig].drop(columns="LS").dropna(how="all", axis=1)
    avg = q.mean(axis=1)
    return q.iloc[:, -1] - avg, q.iloc[:, 0] - avg, p[sig]["LS"]


def main():
    download()
    ports = {n: load(n) for n in FILES}
    m = pd.read_csv(MOM, parse_dates=["date"]).set_index("date")
    m.index = m.index + pd.offsets.MonthEnd(0)
    g = {k: m[f"Q{k}"] + m[f"tov{k}"] * COST for k in (1, 5)}
    mine = {"top": g[5] - m.univ, "bottom": g[1] - m.univ, "LS": g[5] - g[1]}

    rows = []
    periods = [("full", None, "2025-12"), ("2012-16", None, "2016-12"),
               ("2017-21", "2017-01", "2021-11"), ("2021-25", "2021-12", "2025-12")]

    def add(sig, version, leg, x, ref=None):
        start = "2013-02" if sig == "Mom12m" else "2012-02"
        for lbl, a, b in periods:
            v, t = nw(x.loc[a or start:b])
            r = {"signal": sig, "version": version, "leg": leg, "period": lbl, "annual": v, "t": t}
            if ref is not None and lbl == "full":
                r["corr_mine"] = x.corr(ref)
            rows.append(r)

    for leg in mine:
        add("Mom12m", "mine (>$1bn, survivors)", leg, mine[leg].loc[:"2025-12"])
    for sig in ["Mom12m", "GP", "RoE"]:
        for n, p in ports.items():
            for leg, x in zip(["top", "bottom", "LS"], top_bottom(p, sig)):
                add(sig, f"OSAP {n}", leg, x, mine[leg] if sig == "Mom12m" else None)

    out = pd.DataFrame(rows)
    out.to_csv(HERE / "comparison.csv", index=False)
    full = out[out.period == "full"].drop(columns="period")
    pd.set_option("display.width", 200)
    print(full.to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
