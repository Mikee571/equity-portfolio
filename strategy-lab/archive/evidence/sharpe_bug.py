"""
Evidence for archive/sharpe_bug_x52.md (2026-10-11)
===================================================
Reproduces the Sharpe ratio reported by tradingview-mcp-server's
backtest_strategy from its own trade logs, and the corrected value from
shared/corrected_sharpe.py.

Trade returns (net, % per trade) were copied from the MCP's trade logs on
2026-10-11 (include_trade_log=True, default costs 0.1% + 0.05% per side).

Usage:  python sharpe_bug.py
"""
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shared"))
from corrected_sharpe import corrected_sharpe  # noqa: E402

RUNS = {
    "NVDA ema_cross, 2y, 1d": {"reported": -0.77, "years": 2.0, "candles_per_year": 252,
                               "trades": [-17.268, 33.777, -8.65, -3.058, -2.261, -7.589]},
    "NVDA macd, 2y, 1d": {"reported": -1.30, "years": 2.0, "candles_per_year": 252,
                          "trades": [-5.285, -16.213, -2.014, -8.549, -10.21, 33.901, 7.943, -4.497, 1.602,
                                     -2.081, -5.975, 0.854, -4.639, -6.32, 11.572, 1.703, -4.028, 1.012, -4.717]},
    "SPY ema_cross, 1y, 1h": {"reported": 0.53, "years": 1.0, "candles_per_year": 1512,
                              "trades": [-1.952, 0.583, -0.715, -0.955, -1.215, -1.893, -1.392, 11.698, 0.532,
                                         -2.627, -0.222, 2.715, -0.963, -1.71, -1.14]},
}


def mcp_sharpe(trades_pct, candles_per_year, rf=0.04):
    """The MCP's formula: per-trade statistics annualised by candles per year."""
    r = [t / 100 for t in trades_pct]
    return (statistics.mean(r) - rf / candles_per_year) / statistics.stdev(r) * math.sqrt(candles_per_year)


def main():
    print(f"{'run':24s} {'reported':>9} {'MCP formula':>12} {'corrected':>10} {'trades/yr':>10} {'distortion':>11}")
    for name, d in RUNS.items():
        tpy = len(d["trades"]) / d["years"]
        print(f"{name:24s} {d['reported']:>+9.2f} {mcp_sharpe(d['trades'], d['candles_per_year']):>+12.2f} "
              f"{corrected_sharpe(d['trades'], d['years']):>+10.2f} {tpy:>10.1f} "
              f"{math.sqrt(d['candles_per_year'] / tpy):>10.1f}x")


if __name__ == "__main__":
    main()
