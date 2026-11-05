"""Variance risk premium on the S&P 500, 1990-2026, and a delta-hedged short straddle that tries to harvest it.

1. VRP: the VIX (30-day implied vol) against the volatility the index actually realised over the next 21 trading days.
2. Strategy: on the first trading day of each month, sell a 1-month at-the-money straddle on the S&P 500 and
   delta-hedge it daily with the index until expiry (Black-Scholes delta at the implied vol). Its P&L is
   approximately the gap between implied and realised variance, weighted by gamma along the path.

No historical option prices are available here, so the straddle is priced with an implied vol of k x VIX.
The VIX includes the put skew, so it sits above at-the-money vol (on 2026-10-16: VIX 20.0, 1-month ATM 14.4,
a ratio of 0.72). Results are shown for k = 1.00, 0.85 and 0.72. Transaction costs are ignored, as is the index
dividend (price index and q = 0). Both flatter the strategy.

Run from research/derivatives/:  python variance_premium.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import options as o

HERE = Path(__file__).parent
DAYS = 21


def load():
    cache = HERE / "data" / "spx_vix.csv"
    if cache.exists():
        return pd.read_csv(cache, index_col=0, parse_dates=True)
    px = yf.download(["^GSPC", "^VIX", "^IRX"], start="1990-01-01", auto_adjust=True, progress=False)["Close"]
    px = px.rename(columns={"^GSPC": "spx", "^VIX": "vix", "^IRX": "irx"}).dropna(subset=["spx", "vix"])
    px["irx"] = px["irx"].ffill()
    cache.parent.mkdir(exist_ok=True)
    px.to_csv(cache)
    return px


def vrp_table(px):
    r = np.log(px.spx).diff()
    rv_next = np.sqrt((r ** 2).rolling(DAYS).sum().shift(-DAYS) * 252 / DAYS) * 100
    d = pd.DataFrame({"vix": px.vix, "rv_next": rv_next}).dropna()
    d["spread"] = d.vix - d.rv_next
    return d


def straddle_month(S, sigma_imp, r):
    """Sell one ATM straddle at S[0], hedge daily, return P&L as a fraction of the starting index level."""
    n = len(S) - 1
    T0 = n / 252
    K = S[0]
    premium = o.bs_price(S[0], K, T0, r, sigma_imp, "call") + o.bs_price(S[0], K, T0, r, sigma_imp, "put")
    cash = premium
    hedge = 0.0
    for i in range(n):
        T = (n - i) / 252
        g_c = o.bs_greeks(S[i], K, T, r, sigma_imp, "call")["delta"]
        delta = 2 * g_c - 1                       # straddle delta = call delta + put delta
        cash -= (delta - hedge) * S[i]            # short straddle => hold +delta of the index
        hedge = delta
        cash *= np.exp(r / 252)
    cash += hedge * S[-1]
    payoff = abs(S[-1] - K)
    return (cash - payoff) / S[0], premium / S[0], (premium - payoff) / S[0]


def backtest(px, k):
    starts = px.groupby(px.index.to_period("M")).head(1).index
    rows = []
    for t0 in starts:
        i = px.index.get_loc(t0)
        if i + DAYS >= len(px):
            break
        S = px.spx.values[i: i + DAYS + 1]
        sigma = k * px.vix.iloc[i] / 100
        r = np.log(1 + (px.irx.iloc[i] if np.isfinite(px.irx.iloc[i]) else 3.0) / 100)
        hedged, prem, naked = straddle_month(S, sigma, r)
        rows.append({"month": t0, "vix": px.vix.iloc[i], "premium": prem, "hedged_pnl": hedged, "naked_pnl": naked})
    return pd.DataFrame(rows).set_index("month")


def stats(x):
    m = x.mean()
    s = x.std()
    return {"mean_month": m, "vol_month": s, "sharpe_ann": m / s * np.sqrt(12), "hit_rate": (x > 0).mean(),
            "skew": x.skew(), "worst_month": x.min(), "worst_month_date": x.idxmin().strftime("%Y-%m"),
            "best_month": x.max()}


def main():
    px = load()
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "figures").mkdir(exist_ok=True)
    d = vrp_table(px)
    v = {"days": len(d), "mean_vix": d.vix.mean(), "mean_realised_next_21d": d.rv_next.mean(),
         "mean_spread_vol_pts": d.spread.mean(), "median_spread": d.spread.median(),
         "share_days_vix_above_realised": (d.spread > 0).mean(), "worst_spread": d.spread.min(),
         "worst_spread_date": d.spread.idxmin().strftime("%Y-%m-%d")}
    pd.Series(v).to_csv(HERE / "results" / "vrp_summary.csv")
    print("VRP 1990-2026:", {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items()})

    rows, curves = [], {}
    for k in (1.00, 0.85, 0.72):
        bt = backtest(px, k)
        for col, lab in (("hedged_pnl", "delta-hedged"), ("naked_pnl", "unhedged")):
            rows.append({"implied_vol": f"{k:.2f} x VIX", "version": lab, "months": len(bt), **stats(bt[col])})
        curves[k] = bt
        bt.to_csv(HERE / "results" / f"straddle_k{int(k * 100)}.csv")
    res = pd.DataFrame(rows)
    res.to_csv(HERE / "results" / "straddle_summary.csv", index=False)
    pd.set_option("display.width", 220)
    print(res.round(4).to_string(index=False))
    plot(d, curves)


def plot(d, curves):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4), facecolor="#fcfcfb")
    m = d.resample("ME").mean()
    a1.plot(m.index, m.vix, color="#2a78d6", lw=1.3, label="VIX (implied, 30-day)")
    a1.plot(m.index, m.rv_next, color="#eb6834", lw=1.3, label="Realised over the next 21 days")
    a1.set_ylabel("Annualised volatility (%), monthly average", color="#52514e")
    a1.set_title(f"Implied above realised {(d.spread > 0).mean():.0%} of days", loc="left", fontweight="bold",
                 color="#0b0b0b")
    a1.legend(frameon=False, fontsize=8.5, loc="upper left")
    colors = {1.00: "#86b6ef", 0.85: "#2a78d6", 0.72: "#104281"}
    for k, bt in curves.items():
        a2.plot(bt.index, bt.hedged_pnl.cumsum() * 100, color=colors[k], lw=1.6, label=f"priced at {k:.2f} x VIX")
    a2.axhline(0, color="#c3c2b7", lw=1)
    a2.set_ylabel("Cumulative P&L (% of index, summed monthly)", color="#52514e")
    a2.set_title("Short 1-month ATM straddle, delta-hedged daily", loc="left", fontweight="bold", color="#0b0b0b")
    a2.legend(frameon=False, fontsize=8.5, loc="upper left")
    for ax in (a1, a2):
        ax.set_facecolor("#fcfcfb")
        ax.grid(color="#e1e0d9", lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors="#52514e", labelsize=9)
    fig.tight_layout()
    fig.savefig(HERE / "figures" / "variance_premium.png", dpi=160)


if __name__ == "__main__":
    main()
