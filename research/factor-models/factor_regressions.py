"""Fama-French factor regressions of my backtested portfolios: is the screener's excess return alpha, or just
exposure to market, size, value, profitability, investment and momentum?

Portfolios (monthly, USD, net of costs):
  - screener top 10, equal-weight universe, MSCI-style quality quintile  (equity-screener point-in-time backtest)
  - 12-1 momentum winners quintile and winners-minus-losers              (research/momentum)
Factors: Kenneth French data library, US, monthly (downloaded on first run into data/, not redistributed).
Models: CAPM, FF3, FF5, FF5 + momentum (Carhart-style). OLS with Newey-West standard errors (3 lags).

Run from research/factor-models/:  python factor_regressions.py
(inputs/sleeves.csv is written by `python -m src.backtest.export_sleeves` in equity-screener.)
"""
import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

HERE = Path(__file__).parent
BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {"ff5": "F-F_Research_Data_5_Factors_2x3_CSV.zip", "mom": "F-F_Momentum_Factor_CSV.zip"}
MODELS = {"CAPM": ["Mkt-RF"], "FF3": ["Mkt-RF", "SMB", "HML"], "FF5": ["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
          "FF5+Mom": ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]}


def french_monthly(name):
    """Monthly table of a Ken French CSV (the part before the annual block), in decimals, month-end index."""
    cache = HERE / "data" / FILES[name]
    if not cache.exists():
        cache.parent.mkdir(exist_ok=True)
        req = urllib.request.Request(BASE_URL + FILES[name], headers={"User-Agent": "Mozilla/5.0"})
        cache.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    with zipfile.ZipFile(cache) as zf:
        text = zf.read(zf.namelist()[0]).decode("latin-1")
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith(","))   # header row, e.g. ",Mkt-RF,SMB,..."
    end = next(i for i in range(start + 1, len(lines)) if not lines[i].strip() or not lines[i].strip()[:6].isdigit())
    df = pd.read_csv(io.StringIO("\n".join(lines[start:end])), index_col=0)
    df.columns = [c.strip() for c in df.columns]
    df.index = pd.to_datetime(df.index.astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
    return df / 100


def regress(y, X):
    X = sm.add_constant(X)
    m = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    out = {"alpha_ann": m.params["const"] * 12, "alpha_t": m.tvalues["const"], "r2": m.rsquared, "months": int(m.nobs)}
    for f in X.columns[1:]:
        out[f] = m.params[f]
        out[f"t_{f}"] = m.tvalues[f]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sleeves", default=str(HERE / "inputs" / "sleeves.csv"))   # from equity-screener export_sleeves
    ap.add_argument("--momentum", default=str(HERE.parent / "momentum/xs_mom_12_1_monthly.csv"))
    a = ap.parse_args()

    factors = french_monthly("ff5").join(french_monthly("mom"), how="inner")
    sleeves = pd.read_csv(a.sleeves, index_col=0, parse_dates=True)
    mom = pd.read_csv(a.momentum, index_col=0, parse_dates=True)
    sleeves.index = sleeves.index + pd.offsets.MonthEnd(0)
    mom.index = mom.index + pd.offsets.MonthEnd(0)

    # long-only portfolios are regressed in excess of the T-bill; long-short ones are already excess returns
    ports = {
        "Screener top 10": (sleeves["screener_top10"], True),
        "Equal-weight universe": (sleeves["universe_ew"], True),
        "Top 10 minus universe": (sleeves["screener_top10"] - sleeves["universe_ew"], False),
        "Quality quintile (MSCI-style)": (sleeves["quality_msci"], True),
        "Momentum winners (Q5)": (mom["Q5"], True),
        "Momentum winners minus losers": (mom["WML"], False),
    }
    rows = []
    for pname, (r, long_only) in ports.items():
        d = pd.concat([r.rename("r"), factors], axis=1, join="inner").dropna()
        y = d["r"] - d["RF"] if long_only else d["r"]
        for mname, cols in MODELS.items():
            rows.append({"portfolio": pname, "model": mname, "start": d.index[0].strftime("%Y-%m"),
                         "end": d.index[-1].strftime("%Y-%m"), **regress(y, d[cols])})
    res = pd.DataFrame(rows)
    (HERE / "results").mkdir(exist_ok=True)
    res.to_csv(HERE / "results" / "factor_regressions.csv", index=False)

    pd.set_option("display.width", 250)
    show = ["portfolio", "model", "alpha_ann", "alpha_t", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom", "r2"]
    print(res[show].round(3).to_string(index=False))
    fig_alphas(res)


def fig_alphas(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pick = res[res.portfolio.isin(["Top 10 minus universe", "Screener top 10", "Momentum winners minus losers"])]
    order = ["CAPM", "FF3", "FF5", "FF5+Mom"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True, facecolor="#fcfcfb")
    for ax, (pname, g) in zip(axes, pick.groupby("portfolio", sort=False)):
        g = g.set_index("model").loc[order]
        se = (g.alpha_ann / g.alpha_t).abs()
        ax.set_facecolor("#fcfcfb")
        ax.bar(order, g.alpha_ann * 100, color="#2a78d6", width=0.6, zorder=3)
        ax.errorbar(order, g.alpha_ann * 100, yerr=1.96 * se * 100, fmt="none", ecolor="#0b0b0b", capsize=4, lw=1, zorder=4)
        ax.axhline(0, color="#c3c2b7", lw=1)
        ax.set_xticks(range(4), [f"{m}\nt = {t:.1f}" for m, t in zip(order, g.alpha_t)])
        ax.set_title(pname, fontsize=10, loc="left", color="#0b0b0b", fontweight="bold")
        ax.grid(axis="y", color="#e1e0d9", lw=0.6, zorder=0)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors="#52514e", labelsize=9)
    axes[0].set_ylabel("Annual alpha (%), 95% CI", color="#52514e")
    fig.text(0.01, 0.01, "Monthly returns net of costs, Newey-West standard errors. Factors: Kenneth French data library (US).",
             fontsize=7.5, color="#898781")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    (HERE / "figures").mkdir(exist_ok=True)
    fig.savefig(HERE / "figures" / "alphas.png", dpi=160)


if __name__ == "__main__":
    main()
