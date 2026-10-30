"""Portfolio risk for a 70/20/10 equity portfolio held by a euro investor: VaR / CVaR by five methods,
a VaR backtest with Kupiec and Christoffersen tests, historical stress tests and risk contributions.

Portfolio (ETF proxies with daily history from 2004, so 2008, 2011, 2020 and 2022 are all in the sample):
  70% global core   = 42% SPY + 21% EFA + 7% EEM   (roughly the US / developed ex-US / emerging split of ACWI)
  20% value sleeve  = IJS (S&P 600 small-cap value): the factor regression showed the screener is a
                      small, value, high-profitability tilt
  10% tactical      = RSP (S&P 500 equal weight)
Daily VaR and its backtest are in USD, the currency the ETFs trade in. Converting daily returns to EUR with
Yahoo's EURUSD=X adds noise, because the FX close and the NYSE close are hours apart (daily EUR vol 21% vs 17%
implied by weekly data). Stress tests run over weeks or months, where that timing doesn't matter, so they are
shown in both EUR and USD. Daily rebalancing to fixed weights (a simplification).

Run from research/portfolio-risk/:  python portfolio_risk.py   (downloads prices from Yahoo Finance)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

HERE = Path(__file__).parent
WEIGHTS = {"SPY": 0.42, "EFA": 0.21, "EEM": 0.07, "IJS": 0.20, "RSP": 0.10}
SLEEVE = {"SPY": "Global core", "EFA": "Global core", "EEM": "Global core", "IJS": "Value sleeve", "RSP": "Tactical"}
STRESS = {"Global financial crisis": ("2007-10-09", "2009-03-09"),
          "Euro debt crisis": ("2011-07-22", "2011-10-03"),
          "China / oil sell-off": ("2015-07-20", "2016-02-11"),
          "Q4 2018": ("2018-09-20", "2018-12-24"),
          "COVID crash": ("2020-02-19", "2020-03-23"),
          "2022 rates shock": ("2022-01-03", "2022-10-12")}


def load_returns():
    cache = HERE / "data" / "prices.csv"
    if cache.exists():
        px = pd.read_csv(cache, index_col=0, parse_dates=True)
    else:
        px = yf.download(list(WEIGHTS) + ["EURUSD=X"], start="2003-12-01", auto_adjust=True, progress=False)["Close"]
        cache.parent.mkdir(exist_ok=True)
        px.to_csv(cache)
    fx = px["EURUSD=X"].ffill()                        # USD per EUR
    usd = px[list(WEIGHTS)].pct_change(fill_method=None).dropna()
    eur = px[list(WEIGHTS)].div(fx, axis=0).pct_change(fill_method=None).dropna()
    return usd[usd.index >= "2004-01-01"], eur[eur.index >= "2004-01-01"]


# ------------------------------------------------------------------ one-day VaR / CVaR, five ways
def var_table(port, rets, w, level):
    a = 1 - level
    x = port.values
    mu, sd = x.mean(), x.std(ddof=1)
    out = {}
    # 1. historical
    q = np.quantile(x, a)
    out["Historical"] = (-q, -x[x <= q].mean())
    # 2. parametric normal
    z = stats.norm.ppf(a)
    out["Normal"] = (-(mu + z * sd), -(mu - sd * stats.norm.pdf(z) / a))
    # 3. Cornish-Fisher: adjust the normal quantile for skewness and kurtosis
    s, k = stats.skew(x), stats.kurtosis(x)
    zcf = z + (z ** 2 - 1) * s / 6 + (z ** 3 - 3 * z) * k / 24 - (2 * z ** 3 - 5 * z) * s ** 2 / 36
    out["Cornish-Fisher"] = (-(mu + zcf * sd), np.nan)
    # 4. EWMA (RiskMetrics, lambda 0.94): today's conditional volatility, normal quantile
    lam, var_t = 0.94, x[:250].var()
    for v in x:
        var_t = lam * var_t + (1 - lam) * v ** 2
    sd_t = np.sqrt(var_t)
    out["EWMA (today)"] = (-(z * sd_t), -(-sd_t * stats.norm.pdf(z) / a))
    # 5. Monte Carlo: 100,000 draws from a multivariate Student-t (5 d.o.f.) fitted to the asset covariance
    rng = np.random.default_rng(7)
    cov = rets.cov().values * (5 - 2) / 5
    g = rng.chisquare(5, 100_000) / 5
    sims = rng.multivariate_normal(rets.mean().values, cov, 100_000) / np.sqrt(g)[:, None]
    ps = sims @ w
    qm = np.quantile(ps, a)
    out["Monte Carlo (Student-t)"] = (-qm, -ps[ps <= qm].mean())
    return pd.DataFrame(out, index=[f"VaR {level:.0%}", f"CVaR {level:.0%}"]).T


# ------------------------------------------------------------------ VaR backtest
def kupiec(n, x, p):
    """Proportion-of-failures likelihood-ratio test: is the exception rate x/n consistent with p?"""
    phat = x / n
    lr = -2 * ((n - x) * np.log(1 - p) + x * np.log(p) - (n - x) * np.log(1 - phat) - x * np.log(phat))
    return lr, 1 - stats.chi2.cdf(lr, 1)


def christoffersen(hits):
    """Independence test: does an exception today make one tomorrow more likely (clustering)?"""
    h = hits.astype(int)
    n00 = ((h[:-1] == 0) & (h[1:] == 0)).sum(); n01 = ((h[:-1] == 0) & (h[1:] == 1)).sum()
    n10 = ((h[:-1] == 1) & (h[1:] == 0)).sum(); n11 = ((h[:-1] == 1) & (h[1:] == 1)).sum()
    p01, p11 = n01 / (n00 + n01), n11 / max(n10 + n11, 1)
    p = (n01 + n11) / (n00 + n01 + n10 + n11)
    ll0 = (n00 + n10) * np.log(1 - p) + (n01 + n11) * np.log(p)
    ll1 = n00 * np.log(1 - p01) + n01 * np.log(p01) + n10 * np.log(1 - p11) + (n11 * np.log(p11) if n11 else 0)
    lr = -2 * (ll0 - ll1)
    return lr, 1 - stats.chi2.cdf(lr, 1), n11


def backtest(port, level=0.99, window=250):
    """Each day, forecast tomorrow's VaR with information up to today only, then count exceptions."""
    a = 1 - level
    z = stats.norm.ppf(a)
    x = port
    hist = -x.rolling(window).quantile(a).shift(1)
    normal = -(x.rolling(window).mean() + z * x.rolling(window).std()).shift(1)
    ewma_var = (x ** 2).ewm(alpha=0.06, adjust=False).mean()
    ewma = -(z * np.sqrt(ewma_var)).shift(1)
    # filtered historical simulation: scale by EWMA vol, use the empirical quantile of past standardised returns
    sd = np.sqrt((x ** 2).ewm(alpha=0.06, adjust=False).mean())
    std_resid = x / sd.shift(1)
    fhs = -(std_resid.rolling(1000, min_periods=500).quantile(a).shift(1) * sd.shift(1))
    rows, series = [], {}
    for name, v in (("Historical, 1-year window", hist), ("Normal, 1-year window", normal),
                    ("EWMA (RiskMetrics)", ewma), ("Filtered historical simulation", fhs)):
        d = pd.concat([x, v], axis=1, keys=["r", "var"]).dropna()
        d = d[d.index >= "2005-01-01"]
        hits = (d.r < -d["var"]).values
        n, k = len(d), hits.sum()
        lr_uc, p_uc = kupiec(n, k, a)
        lr_ind, p_ind, clustered = christoffersen(hits)
        worst = d[hits].assign(excess=lambda t: -t.r / t["var"]).excess.max()
        rows.append({"method": name, "days": n, "expected_exceptions": round(n * a), "exceptions": int(k),
                     "exception_rate": k / n, "kupiec_p": p_uc, "christoffersen_p": p_ind,
                     "back_to_back_exceptions": int(clustered), "worst_loss_vs_var": worst})
        series[name] = d
    return pd.DataFrame(rows), series


# ------------------------------------------------------------------ stress tests and risk contributions
def stress(rets, w, rets_usd):
    port_level = (1 + rets @ w).cumprod()
    rows = []
    for name, (a, b) in STRESS.items():
        seg = rets.loc[a:b]
        row = {"scenario": name, "from": a, "to": b, "trading_days": len(seg),
               "portfolio": (1 + seg @ w).prod() - 1,
               "portfolio_usd": (1 + rets_usd.loc[a:b] @ w).prod() - 1}
        for t in WEIGHTS:
            row[t] = (1 + seg[t]).prod() - 1
        peak = port_level.loc[:b].iloc[-1]
        start = port_level.loc[:a].iloc[-1]
        after = port_level.loc[b:]
        rec = after[after >= start]
        row["days_to_recover"] = (rec.index[0] - pd.Timestamp(b)).days if len(rec) else None
        rows.append(row)
    return pd.DataFrame(rows)


def risk_contributions(rets, w):
    """Euler decomposition of portfolio volatility: each sleeve's share of total risk."""
    cov = rets.cov().values * 252
    sigma = np.sqrt(w @ cov @ w)
    contrib = w * (cov @ w) / sigma
    df = pd.DataFrame({"ticker": list(WEIGHTS), "sleeve": [SLEEVE[t] for t in WEIGHTS], "weight": w,
                       "vol": np.sqrt(np.diag(cov)), "risk_contribution": contrib / sigma})
    by_sleeve = df.groupby("sleeve", sort=False)[["weight", "risk_contribution"]].sum()
    return df, by_sleeve, sigma


# ------------------------------------------------------------------ figures
def fig_backtest(series, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = series["Filtered historical simulation"]
    hits = d[d.r < -d["var"]]
    fig, ax = plt.subplots(figsize=(10, 3.8), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.plot(d.index, d.r * 100, color="#c3c2b7", lw=0.5, label="Daily return")
    ax.plot(d.index, -d["var"] * 100, color="#2a78d6", lw=1.2, label="99% one-day VaR (filtered historical simulation)")
    ax.scatter(hits.index, hits.r * 100, color="#eb6834", s=14, zorder=3, label=f"Exceptions ({len(hits)})")
    ax.set_ylabel("% per day (USD)", color="#52514e")
    ax.set_title("VaR backtest, 2005-2026: the forecast widens after shocks, but the first days of a shock still break it",
                 loc="left", fontsize=10.5, fontweight="bold", color="#0b0b0b")
    ax.legend(frameon=False, loc="lower left", fontsize=9, ncol=3)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#e1e0d9", lw=0.6)
    ax.tick_params(colors="#52514e", labelsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_stress(st, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s = st.sort_values("portfolio")
    fig, ax = plt.subplots(figsize=(7.5, 3.6), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.barh(s.scenario, s.portfolio * 100, color="#2a78d6", height=0.6, zorder=3)
    for y, (v, d) in enumerate(zip(s.portfolio * 100, s.days_to_recover)):
        rec = f"back to the start {d / 365:.1f} yrs after the low" if pd.notna(d) else "not yet recovered"
        ax.text(v - 0.8, y, f"{v:.0f}%  ·  {rec}", va="center", ha="right", fontsize=8.5, color="#0b0b0b")
    ax.set_xlim(s.portfolio.min() * 100 * 2.3, 0)
    ax.set_xlabel("Portfolio return over the episode, in EUR (%)", color="#52514e")
    ax.set_title("Historical stress tests", loc="left", fontweight="bold", color="#0b0b0b")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors="#52514e", labelsize=9, left=False)
    ax.grid(axis="x", color="#e1e0d9", lw=0.6, zorder=0)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    rets, rets_eur = load_returns()
    w = np.array([WEIGHTS[t] for t in rets.columns])
    port = rets @ w
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "figures").mkdir(exist_ok=True)
    pd.set_option("display.width", 220)

    print(f"Sample {rets.index[0]:%Y-%m-%d} to {rets.index[-1]:%Y-%m-%d}, {len(rets)} days (USD). "
          f"Annualised vol {port.std() * np.sqrt(252):.1%}, skew {stats.skew(port):.2f}, excess kurtosis {stats.kurtosis(port):.1f}")
    vt = pd.concat([var_table(port, rets, w, 0.95), var_table(port, rets, w, 0.99)], axis=1)
    vt.to_csv(HERE / "results" / "var_cvar.csv")
    print("\nOne-day VaR / CVaR (loss as a share of the portfolio):\n", (vt * 100).round(2))

    bt, series = backtest(port)
    bt.to_csv(HERE / "results" / "var_backtest.csv", index=False)
    print("\nVaR 99% backtest:\n", bt.round(4).to_string(index=False))

    st = stress(rets_eur, w, rets)
    st.to_csv(HERE / "results" / "stress_tests.csv", index=False)
    print("\nStress tests:\n", st.round(3).to_string(index=False))

    rc, by_sleeve, sigma = risk_contributions(rets, w)
    rc.to_csv(HERE / "results" / "risk_contributions.csv", index=False)
    print(f"\nRisk contributions (portfolio vol {sigma:.1%}):\n", by_sleeve.round(3))

    fig_backtest(series, HERE / "figures" / "var_backtest.png")
    fig_stress(st, HERE / "figures" / "stress_tests.png")


if __name__ == "__main__":
    main()
