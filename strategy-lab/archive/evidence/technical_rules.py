"""
Evidence for archive/ema_cross_noise.md and archive/macd_redundancy.md (2026-10-11)
===================================================================================
The original analyses behind archiving EMA Cross and MACD are not on disk.
What survives are two code comments: EMA cross "100% win rate in only 3
trades = noise", and the lab's `ema_cross_features` (EMA12 - EMA26) / close.
This script rebuilds the evidence with 20 years of data.

Rules, replicated as tradingview-mcp-server runs them (long-only; decision
at the close of the cross day; 0.15% per side, the lab's validated cost):
    EMA_CROSS  long while EMA20 > EMA50 (MCP label: "EMA 20/50 Golden/Death Cross")
    MACD       long while MACD(12,26) > signal(9) (MCP label: "MACD Crossover")
    MACD_ZERO  long while MACD(12,26) > 0, i.e. EMA12 > EMA26
    TRIPLE_EMA the lab's custom rule (EMA20/50 cross filtered by SMA200), long side

1. Replication: entry and exit dates against the MCP's NVDA trade log.
2. Noise test: each rule against 1,000 strategies with random timing,
   built by shuffling the rule's own holding periods and waiting periods.
   Same number of trades, same time in the market, same costs; only the
   timing changes. p = share of random Sharpes >= the rule's.
3. Redundancy: how often the rules agree, and correlation of their returns.

Usage:  python technical_rules.py
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(LAB, "stat_arb"))
sys.path.insert(0, os.path.join(LAB, "signal_lab"))

from custom_strategies import triple_ema_position  # noqa: E402
from indicators import ema_cross_features, macd  # noqa: E402

ASSETS = ["SPY", "QQQ", "NVDA", "GDX", "GLD", "XLE"]
START = "2006-06-01"
COST_PER_SIDE = 0.0015
N_RANDOM = 1000

# MCP trade log, NVDA, period 2y, 1d (captured 2026-10-11): (entry, exit)
MCP_NVDA = {
    "EMA_CROSS": [("2025-01-24", "2025-01-27"), ("2025-05-14", "2025-12-02"), ("2025-12-30", "2026-02-05"),
                  ("2026-02-10", "2026-03-05"), ("2026-04-15", "2026-06-29"), ("2026-07-15", "2026-07-28")],
    "MACD": [("2026-04-02", "2026-05-01"), ("2026-05-08", "2026-05-21"), ("2026-07-08", "2026-07-27"),
             ("2026-08-04", "2026-08-21"), ("2026-09-03", "2026-09-10")],
}


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def positions(close: pd.Series) -> pd.DataFrame:
    """Position decided at each close (1 = long). Not yet shifted."""
    line, signal, _ = macd(close)
    tri = triple_ema_position(close).shift(-1).fillna(0)        # the lab's function is pre-shifted
    return pd.DataFrame({
        "EMA_CROSS": (ema(close, 20) > ema(close, 50)).astype(float),
        "MACD": (line > signal).astype(float),
        "MACD_ZERO": (line > 0).astype(float),
        "TRIPLE_EMA": (tri > 0).astype(float),
    })


def strategy_returns(pos: pd.Series, r: pd.Series) -> pd.Series:
    """Hold from the close of the decision day; pay COST_PER_SIDE on each change."""
    return pos.shift(1).fillna(0) * r - pos.diff().abs().fillna(pos.iloc[0]) * COST_PER_SIDE


def sharpe(x) -> float:
    x = np.asarray(x)
    return x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else np.nan


def run_lengths(p: np.ndarray) -> list:
    change = np.flatnonzero(np.diff(p)) + 1
    bounds = np.r_[0, change, len(p)]
    return [(p[a], b - a) for a, b in zip(bounds[:-1], bounds[1:])]


def random_timing(p: np.ndarray, rng) -> np.ndarray:
    """Same holding and waiting periods as `p`, shuffled: same trades and exposure, random dates."""
    runs = run_lengths(p)
    ones = [n for v, n in runs if v == 1]
    zeros = [n for v, n in runs if v == 0]
    rng.shuffle(ones)
    rng.shuffle(zeros)
    out, it1, it0 = [], iter(ones), iter(zeros)
    for v, _ in runs:
        out.extend([v] * next(it1 if v == 1 else it0))
    return np.array(out, dtype=float)


def trades(pos: pd.Series) -> list:
    d = pos.diff().fillna(pos.iloc[0])
    entries = list(pos.index[d == 1])
    exits = list(pos.index[d == -1])
    return list(zip(entries, exits + [None] * (len(entries) - len(exits))))


def main():
    px = yf.download(ASSETS, start=START, auto_adjust=True, progress=False)["Close"].dropna(how="all")
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda x: f"{x:,.2f}")

    # 1. Replication (NVDA, recent trades; the MCP's EMAs start in Oct-2024, ours in 2006)
    nv = positions(px["NVDA"].dropna())
    print("=== 1. Replication against the MCP's NVDA trade log ===")
    for rule, mcp in MCP_NVDA.items():
        ours = {(e.strftime("%Y-%m-%d"), x.strftime("%Y-%m-%d") if x is not None else None)
                for e, x in trades(nv[rule]) if e >= pd.Timestamp("2025-01-01")}
        hit = sum(t in ours for t in mcp)
        print(f"  {rule}: {hit} of {len(mcp)} MCP trades reproduced exactly (same entry and exit day)")

    # 2. Noise test
    rng = np.random.default_rng(7)
    rows = []
    rets = {}
    for a in ASSETS:
        c = px[a].dropna()
        r = c.pct_change().fillna(0)
        pos = positions(c)
        rets[a] = {k: strategy_returns(pos[k], r) for k in pos}
        bh = r.iloc[1:]
        for rule in ("EMA_CROSS", "MACD"):
            p = pos[rule].to_numpy()
            s = sharpe(rets[a][rule].iloc[1:])
            sims = np.array([sharpe(strategy_returns(pd.Series(random_timing(p, rng), index=c.index), r).iloc[1:])
                             for _ in range(N_RANDOM)])
            n_tr = int((np.diff(p) == 1).sum())
            years = len(c) / 252
            rows.append({"asset": a, "rule": rule, "since": c.index[0].date(), "trades_per_year": n_tr / years,
                         "time_in_market": p.mean(), "sharpe": s, "random_median": np.median(sims),
                         "p_value": (sims >= s).mean(), "sharpe_buy_hold": sharpe(bh)})
    res = pd.DataFrame(rows)
    print("\n=== 2. Noise test: rule vs 1,000 random-timing strategies (net of costs) ===")
    print(res.to_string(index=False))
    for rule in ("EMA_CROSS", "MACD"):
        sub = res[res.rule == rule]
        print(f"  {rule}: beats its random median in {(sub.sharpe > sub.random_median).sum()} of {len(sub)} assets; "
              f"p < 0.05 in {(sub.p_value < 0.05).sum()}; beats buy-and-hold Sharpe in "
              f"{(sub.sharpe > sub.sharpe_buy_hold).sum()}")

    # 3. Redundancy
    print("\n=== 3. Redundancy ===")
    c = px["SPY"].dropna()
    line, _, _ = macd(c)
    diff = (ema_cross_features(c) - line / c).abs().max()
    print(f"  Lab feature ema_cross_features(12,26) vs MACD line / close: max abs difference {diff:.1e} (identical)")
    red = []
    for a in ASSETS:
        pos = positions(px[a].dropna())
        rr = pd.DataFrame(rets[a]).iloc[1:]
        red.append({"asset": a,
                    "agree_MACD_vs_EMA_CROSS": (pos.MACD == pos.EMA_CROSS).mean(),
                    "agree_MACD_ZERO_vs_EMA_CROSS": (pos.MACD_ZERO == pos.EMA_CROSS).mean(),
                    "agree_TRIPLE_vs_EMA_CROSS": (pos.TRIPLE_EMA == pos.EMA_CROSS).mean(),
                    "corr_ret_MACD_EMA": rr.MACD.corr(rr.EMA_CROSS),
                    "corr_ret_MACD_ZERO_EMA": rr.MACD_ZERO.corr(rr.EMA_CROSS),
                    "corr_ret_TRIPLE_EMA": rr.TRIPLE_EMA.corr(rr.EMA_CROSS),
                    "trades_yr_MACD": (pos.MACD.diff() == 1).sum() / (len(pos) / 252),
                    "trades_yr_EMA": (pos.EMA_CROSS.diff() == 1).sum() / (len(pos) / 252)})
    red = pd.DataFrame(red)
    print(red.to_string(index=False))
    print("  mean:", red.drop(columns="asset").mean().round(2).to_dict())
    return res, red


if __name__ == "__main__":
    main()
