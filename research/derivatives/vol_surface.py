"""Implied volatility smile and term structure of SPY options, from a snapshot of the option chain.

Uses out-of-the-money options only (puts below the forward, calls above), mid prices with a positive bid, and
my own Black-Scholes implied-vol solver (options.py). The forward of each expiry is backed out of put-call
parity on near-the-money strikes (F = K + e^(rT)(C - P)), which also gives the implied dividend yield. SPY options are American; for OTM options the early-exercise
premium is small, so the European formula is a reasonable approximation (noted in the README).

Run from research/derivatives/:  python vol_surface.py   -> results/spy_iv_snapshot.csv, figures/spy_smile.png
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import options as o

HERE = Path(__file__).parent
TARGET_DAYS = [7, 30, 60, 91, 182, 365]


def main():
    spy = yf.Ticker("SPY")
    hist = spy.history(period="5d")
    spot = float(hist["Close"].iloc[-1])
    asof = hist.index[-1].tz_localize(None).normalize() + pd.Timedelta(hours=16)     # last close, 4pm New York
    r = float(yf.Ticker("^IRX").history(period="5d")["Close"].iloc[-1]) / 100        # 13-week T-bill
    r = np.log(1 + r)                                                                  # continuous compounding
    vix = float(yf.Ticker("^VIX").history(period="5d")["Close"].iloc[-1])

    expiries = pd.to_datetime(spy.options)
    days = (expiries - asof.normalize()).days
    chosen = sorted({expiries[np.argmin(np.abs(days - d))] for d in TARGET_DAYS})

    rows = []
    for ex in chosen:
        T = ((ex + pd.Timedelta(hours=16)) - asof).total_seconds() / (365 * 24 * 3600)
        chain = spy.option_chain(ex.strftime("%Y-%m-%d"))
        # forward from put-call parity on the strikes nearest the spot that have both a call and a put quote
        mids = {}
        for kind, tbl in (("call", chain.calls), ("put", chain.puts)):
            t = tbl[(tbl.bid > 0) & (tbl.ask > tbl.bid)]
            mids[kind] = ((t.bid + t.ask) / 2).set_axis(t.strike)
        both = pd.concat(mids, axis=1).dropna()
        near = both.iloc[(both.index.to_series() - spot).abs().argsort()[:6]]
        F = float(np.median(near.index + np.exp(r * T) * (near["call"] - near["put"])))
        q = r - np.log(F / spot) / T                                                   # implied dividend yield
        for kind, tbl in (("call", chain.calls), ("put", chain.puts)):
            t = tbl[(tbl.bid > 0) & (tbl.ask > tbl.bid)].copy()
            t["mid"] = (t.bid + t.ask) / 2
            t = t[(t.ask - t.bid) / t.mid < 0.5]
            t = t[t.strike > F] if kind == "call" else t[t.strike <= F]          # out of the money only
            for _, x in t.iterrows():
                iv = o.implied_vol(x.mid, spot, x.strike, T, r, kind, q)
                if np.isfinite(iv):
                    rows.append(dict(expiry=ex.date(), days=round(T * 365), T=T, forward=F, implied_q=q,
                                     kind=kind, strike=x.strike,
                                     moneyness=np.log(x.strike / F), mid=x.mid, iv=iv, yahoo_iv=x.impliedVolatility,
                                     open_interest=x.openInterest))
    df = pd.DataFrame(rows)
    df = df[(df.moneyness > -0.35) & (df.moneyness < 0.15)].sort_values(["expiry", "moneyness"])
    # drop stale or illiquid quotes: points more than 2 vol points away from the median of their neighbours
    med = df.groupby("expiry").iv.transform(lambda s: s.rolling(7, center=True, min_periods=3).median())
    df = df[(df.iv - med).abs() < 0.02]
    (HERE / "results").mkdir(exist_ok=True)
    df.to_csv(HERE / "results" / "spy_iv_snapshot.csv", index=False)

    # summary per expiry: ATM vol, 25-delta-ish skew proxy (IV at -10% vs +5% log-moneyness)
    summ = []
    for ex, g in df.groupby("expiry"):
        g = g.sort_values("moneyness")
        atm = np.interp(0.0, g.moneyness, g.iv)
        down = np.interp(-0.10, g.moneyness, g.iv) if g.moneyness.min() <= -0.10 else np.nan
        up = np.interp(0.05, g.moneyness, g.iv) if g.moneyness.max() >= 0.05 else np.nan
        summ.append(dict(expiry=ex, days=int(g.days.iloc[0]), forward=g.forward.iloc[0], implied_q=g.implied_q.iloc[0],
                         atm_iv=atm, iv_minus10pct=down, iv_plus5pct=up,
                         skew_10pct_down_minus_atm=down - atm, n_quotes=len(g)))
    summ = pd.DataFrame(summ)
    summ.to_csv(HERE / "results" / "spy_iv_term_structure.csv", index=False)
    print(f"SPY {spot:.2f} at {asof:%Y-%m-%d %H:%M}, r = {r:.2%}, VIX = {vix:.2f}")
    print(summ.round(4).to_string(index=False))
    print(f"\nMy IV vs Yahoo's IV column: median abs difference {np.median(np.abs(df.iv - df.yahoo_iv)):.3f}")
    plot(df, summ, spot, asof, vix)


def plot(df, summ, spot, asof, vix):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("b", ["#86b6ef", "#2a78d6", "#104281"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1.6, 1]}, facecolor="#fcfcfb")
    exps = sorted(df.expiry.unique())
    for i, ex in enumerate(exps):
        g = df[df.expiry == ex].sort_values("moneyness")
        a1.plot(g.moneyness * 100, g.iv * 100, color=cmap(i / max(len(exps) - 1, 1)), lw=1.6,
                label=f"{int(g.days.iloc[0])} days")
    a1.axvline(0, color="#c3c2b7", lw=1)
    a1.set_xlabel("Strike vs forward, log-moneyness (%)", color="#52514e")
    a1.set_ylabel("Implied volatility (%)", color="#52514e")
    a1.set_title(f"SPY volatility smile, close of {asof:%Y-%m-%d}", loc="left", fontweight="bold", color="#0b0b0b")
    a1.legend(frameon=False, fontsize=8.5, title="Expiry", title_fontsize=8.5, loc="upper right")
    a2.plot(summ.days, summ.atm_iv * 100, color="#2a78d6", lw=2, marker="o", label="At the money")
    a2.plot(summ.days, summ.iv_minus10pct * 100, color="#eb6834", lw=2, marker="o", label="10% below the forward")
    a2.axhline(vix, color="#52514e", lw=1, ls="--")
    a2.text(summ.days.max(), vix + 0.3, f"VIX {vix:.1f}", ha="right", fontsize=8.5, color="#52514e")
    a2.set_xlabel("Days to expiry", color="#52514e")
    a2.set_title("Term structure", loc="left", fontweight="bold", color="#0b0b0b")
    a2.legend(frameon=False, fontsize=8.5)
    for ax in (a1, a2):
        ax.set_facecolor("#fcfcfb")
        ax.grid(color="#e1e0d9", lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors="#52514e", labelsize=9)
    fig.tight_layout()
    (HERE / "figures").mkdir(exist_ok=True)
    fig.savefig(HERE / "figures" / "spy_smile.png", dpi=160)


if __name__ == "__main__":
    main()
