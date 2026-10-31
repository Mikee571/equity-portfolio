"""
analyze_results.py

Reads the strategy comparison log and produces a ranked summary plus a basic
risk-adjusted view (return per unit of "active risk taken", proxied here by
a manually assigned complexity/risk tier per strategy archetype).

Usage:
    python analyze_results.py
"""

import pandas as pd

# Subjective but documented risk tiers, used only to illustrate the
# return-per-unit-of-risk framing — not a rigorous volatility measure.
RISK_TIER = {
    "Global Macro": 4,             # concentrated directional bets
    "Statistical Arbitrage": 2,    # market neutral, but pair risk if hedge breaks
    "S&P 500 Benchmark": 3,        # full market beta, no hedging
    "70/20/10 Passive": 2,         # diversified, capped speculative sleeve
    "Volatility Arbitrage": 4,     # theta decay + event risk on long-vol legs
    "Trend Following": 3,          # exposed to regime-break reversals
}


def load_log(path: str = "../data/results_log.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["risk_tier"] = df["strategy"].map(RISK_TIER)
    df["return_per_risk_tier"] = (df["return_pct"] / df["risk_tier"]).round(2)
    return df.sort_values("return_pct", ascending=False)


def summarize(df: pd.DataFrame) -> None:
    print("\nRanked by raw return:\n")
    print(df[["strategy", "return_pct", "start_value", "end_value"]]
          .to_string(index=False))

    print("\nRanked by return per unit of risk tier (illustrative, not a real Sharpe ratio):\n")
    ranked = df.sort_values("return_per_risk_tier", ascending=False)
    print(ranked[["strategy", "return_pct", "risk_tier", "return_per_risk_tier"]]
          .to_string(index=False))


if __name__ == "__main__":
    data = load_log()
    summarize(data)
