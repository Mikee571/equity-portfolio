"""Does a GJR-GARCH filter fix what EWMA gets wrong in the 99% VaR backtest?

In portfolio_risk.py the filtered historical simulation (FHS) scales returns by an EWMA volatility (RiskMetrics,
lambda 0.94). It gets the exception count right (55 vs 50, Kupiec p 0.51) but fails Christoffersen (p 0.003):
exceptions bunch at the start of crises. GJR-GARCH should help on paper, for two reasons. Volatility rises more
after a down day than after an up day (the leverage term), so the forecast reacts faster when a sell-off starts.
And it mean-reverts, where EWMA is an IGARCH that never does.

Pre-registered before running (2026-11-03). The 2005-26 sample was already used for the EWMA version, so there is
no untouched hold-out. This is a model comparison on known data, not a new-signal test.
  Primary: FHS with a GJR-GARCH(1,1) Student-t filter vs FHS with the EWMA filter, same 1000-day window of
           standardised residuals, same evaluation days. GJR passes if Kupiec p > 0.05 AND its Christoffersen p is
           higher than the EWMA version's. A clear fix would need Christoffersen p > 0.05 too.
  Secondary, descriptive only: parametric GJR-t and GARCH-t VaR (GARCH-t isolates the leverage term), FHS-GARCH,
           and a Diebold-Mariano test on the quantile (tick) loss of FHS-GJR vs FHS-EWMA.
  Estimation is walk-forward: parameters are refitted every 21 trading days on an expanding window and only data
  up to the day before is used. No parameter is tuned on the full sample.

Run from research/portfolio-risk/:  python gjr_garch.py   (needs the arch package; reuses data/prices.csv)
"""
import warnings

import numpy as np
import pandas as pd
from arch import arch_model
from scipy import stats

from portfolio_risk import HERE, WEIGHTS, christoffersen, kupiec, load_returns

LEVEL, REFIT, START = 0.99, 21, "2005-01-01"


def walk_forward_sigma(r, start, o):
    """One-day-ahead conditional vol, refitting a GARCH(1,o,1)-t every REFIT days on data up to the day before.
    Returns the sigma series, the mean and the t degrees of freedom in force each day."""
    first = r.index.searchsorted(pd.Timestamp(start))
    sig, mu, nu = (pd.Series(np.nan, index=r.index) for _ in range(3))
    x = r.values
    for k in range(first, len(x), REFIT):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = arch_model(x[:k], mean="Constant", vol="GARCH", p=1, o=o, q=1, dist="t").fit(disp="off")
        p = res.params
        m, w, a, b = p["mu"], p["omega"], p["alpha[1]"], p["beta[1]"]
        g = p["gamma[1]"] if o else 0.0
        end = min(k + REFIT, len(x))
        # run the recursion from the start with these parameters, keep the forecasts for days k..end-1
        e = x[:end] - m
        s2 = np.empty(end)
        s2[0] = e[:k].var()
        for t in range(1, end):
            s2[t] = w + (a + g * (e[t - 1] < 0)) * e[t - 1] ** 2 + b * s2[t - 1]
        sig.iloc[k:end] = np.sqrt(s2[k:end])
        mu.iloc[k:end], nu.iloc[k:end] = m, p["nu"]
    return sig, mu, nu


def fhs(r, sig, mu=0.0):
    """Filtered historical simulation: empirical quantile of past standardised residuals times today's sigma."""
    z = (r - mu) / sig
    q = z.rolling(1000, min_periods=500).quantile(1 - LEVEL).shift(1)
    return -(mu + q * sig)


def tick_loss(r, var):
    a = 1 - LEVEL
    q = -var
    return (a - (r < q)) * (r - q)


def diebold_mariano(l1, l2, lags=10):
    """DM test on loss differential l1 - l2 with a Newey-West variance. Negative t = model 1 has lower loss."""
    d = (l1 - l2).values
    n, m = len(d), d.mean()
    u = d - m
    v = u @ u / n
    for j in range(1, lags + 1):
        v += 2 * (1 - j / (lags + 1)) * (u[j:] @ u[:-j]) / n
    t = m / np.sqrt(v / n)
    return t, 2 * (1 - stats.norm.cdf(abs(t)))


def evaluate(r, var, days):
    d = pd.concat([r, var], axis=1, keys=["r", "var"]).loc[days]
    hits = (d.r < -d["var"]).values
    n, k = len(d), int(hits.sum())
    _, p_uc = kupiec(n, k, 1 - LEVEL)
    _, p_ind, n11 = christoffersen(hits)
    return {"days": n, "expected": round(n * (1 - LEVEL)), "exceptions": k, "kupiec_p": p_uc,
            "christoffersen_p": p_ind, "back_to_back": int(n11), "mean_var_pct": d["var"].mean(),
            "tick_loss": tick_loss(d.r, d["var"]).mean()}


def main():
    rets, _ = load_returns()
    w = np.array([WEIGHTS[t] for t in rets.columns])
    r = (rets @ w) * 100                                   # percent, which GARCH estimation prefers

    # baseline, identical to portfolio_risk.py
    sd_ewma = np.sqrt((r ** 2).ewm(alpha=0.06, adjust=False).mean()).shift(1)
    var = {"FHS, EWMA filter (baseline)": fhs(r, sd_ewma)}

    a = 1 - LEVEL
    for name, o in (("GJR", 1), ("GARCH", 0)):
        sig, mu, nu = walk_forward_sigma(r, START, o)
        tq = stats.t.ppf(a, nu) * np.sqrt((nu - 2) / nu)   # standardised-t quantile
        var[f"{name}-t, parametric"] = -(mu + tq * sig)
        var[f"FHS, {name} filter"] = fhs(r, sig, mu)
        if o:
            sig_gjr = sig

    days = pd.concat(var, axis=1).dropna().index
    days = days[days >= START]
    rows = {k: evaluate(r, v, days) for k, v in var.items()}
    tab = pd.DataFrame(rows).T
    (HERE / "results").mkdir(exist_ok=True)
    tab.to_csv(HERE / "results" / "gjr_backtest.csv")
    pd.set_option("display.width", 200)
    print(f"Evaluation {days[0]:%Y-%m-%d} to {days[-1]:%Y-%m-%d}, {len(days)} days, 99% one-day VaR (% of portfolio)")
    print(tab.astype(float).round(4).to_string())

    base, gjr = "FHS, EWMA filter (baseline)", "FHS, GJR filter"
    l_base = tick_loss(r.loc[days], var[base].loc[days])
    l_gjr = tick_loss(r.loc[days], var[gjr].loc[days])
    t, p = diebold_mariano(l_gjr, l_base)
    print(f"\nDiebold-Mariano, tick loss FHS-GJR minus FHS-EWMA: t {t:.2f}, p {p:.3f} (negative = GJR better)")

    b, g = rows[base], rows[gjr]
    passed = g["kupiec_p"] > 0.05 and g["christoffersen_p"] > b["christoffersen_p"]
    print(f"\nPre-registered rule: Kupiec p {g['kupiec_p']:.3f} > 0.05 and Christoffersen p "
          f"{g['christoffersen_p']:.3f} > baseline {b['christoffersen_p']:.3f}  ->  {'PASS' if passed else 'FAIL'}"
          f"{'  (clear fix: Christoffersen > 0.05)' if g['christoffersen_p'] > 0.05 else ''}")

    # where do the exceptions fall? first day of each cluster vs later days
    for name in (base, gjr):
        d = pd.concat([r, var[name]], axis=1, keys=["r", "var"]).loc[days]
        h = d[d.r < -d["var"]].index
        print(f"{name}: exceptions by year", pd.Series(h.year).value_counts().sort_index().to_dict())

    # today's numbers, for the README
    last = r.index[-1]
    print(f"\nLatest ({last:%Y-%m-%d}): EWMA vol {sd_ewma.iloc[-1] * np.sqrt(252):.1f}%/yr, "
          f"GJR vol {sig_gjr.iloc[-1] * np.sqrt(252):.1f}%/yr; 99% VaR EWMA-FHS {var[base].iloc[-1]:.2f}%, "
          f"GJR-FHS {var[gjr].iloc[-1]:.2f}%")


if __name__ == "__main__":
    main()
