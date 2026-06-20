"""
fundamental_screener.py

A lightweight fundamental screening framework for equity selection.
Applies five criteria to a list of tickers and returns a scored watchlist.

This is the same methodology used to select and monitor positions in my
personal equity portfolio (see ../stock_pitches/ for full investment theses).

Requirements:
    pip install yfinance pandas --break-system-packages

Usage:
    python fundamental_screener.py
"""

import pandas as pd
import yfinance as yf
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Screening thresholds — adjust to taste, but document any change in README
# ---------------------------------------------------------------------------
@dataclass
class Thresholds:
    max_pe_value: float = 15.0       # P/E ceiling for value names
    max_pe_growth: float = 25.0      # P/E ceiling for growth names
    min_roe: float = 0.15            # Return on Equity floor
    max_debt_to_equity: float = 1.0  # Leverage ceiling
    max_peg: float = 1.5             # PEG ratio ceiling


THRESHOLDS = Thresholds()


def fetch_fundamentals(ticker: str) -> dict:
    """Pull the core fundamental fields needed for screening from Yahoo Finance."""
    t = yf.Ticker(ticker)
    info = t.info

    return {
        "ticker": ticker,
        "name": info.get("longName"),
        "pe_ratio": info.get("trailingPE"),
        "peg_ratio": info.get("trailingPegRatio") or info.get("pegRatio"),
        "roe": info.get("returnOnEquity"),
        "debt_to_equity": (info.get("debtToEquity") or 0) / 100 if info.get("debtToEquity") else None,
        "free_cash_flow": info.get("freeCashflow"),
        "net_margin": info.get("profitMargins"),
        "sector": info.get("sector"),
    }


def score_row(row: dict, thresholds: Thresholds = THRESHOLDS) -> dict:
    """Apply pass/fail screening logic and return a readable verdict per metric."""
    pe = row.get("pe_ratio")
    pe_ceiling = thresholds.max_pe_growth if row.get("sector") in ("Technology", "Consumer Cyclical") else thresholds.max_pe_value

    checks = {
        "pe_pass": pe is not None and pe < pe_ceiling,
        "roe_pass": row.get("roe") is not None and row.get("roe") >= thresholds.min_roe,
        "debt_pass": row.get("debt_to_equity") is not None and row.get("debt_to_equity") <= thresholds.max_debt_to_equity,
        "fcf_pass": row.get("free_cash_flow") is not None and row.get("free_cash_flow") > 0,
        "peg_pass": row.get("peg_ratio") is not None and row.get("peg_ratio") <= thresholds.max_peg,
    }

    row.update(checks)
    row["score"] = sum(1 for v in checks.values() if v)
    row["verdict"] = "WATCH" if row["score"] >= 4 else "PASS" if row["score"] >= 3 else "REJECT"
    return row


def run_screen(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        try:
            data = fetch_fundamentals(ticker)
            rows.append(score_row(data))
        except Exception as exc:
            print(f"[warning] could not fetch {ticker}: {exc}")

    df = pd.DataFrame(rows)
    cols = ["ticker", "name", "pe_ratio", "roe", "debt_to_equity",
            "free_cash_flow", "peg_ratio", "score", "verdict"]
    return df[cols].sort_values("score", ascending=False)


if __name__ == "__main__":
    watchlist = ["JPM", "XOM", "BMW.DE"]
    result = run_screen(watchlist)
    print(result.to_string(index=False))
    result.to_csv("../data/watchlist.csv", index=False)
