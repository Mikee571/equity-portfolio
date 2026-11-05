"""Scorecard of the systematic strategy research (see SYNTHESIS.md)."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import ROOT  # noqa: E402

st.set_page_config(page_title="Strategy research", layout="wide")
st.title("Strategy research: 11 ideas, 0 survivors")
st.caption("Each idea was tested with rules fixed in advance, realistic costs, out-of-sample data and a fair "
           "benchmark. Full write-up in SYNTHESIS.md.")

score = pd.DataFrame([
    ("ML direction predictor (XGBoost)", "4 assets, 2018-24", "AUC 0.43-0.52, worse than buy and hold on all 4", "No"),
    ("Cointegrated pairs (stat arb)", "37 pairs, walk-forward 2012-26", "−1.9%/yr net; Kalman/OU don't fix it", "No"),
    ("EMA cross, MACD", "6 assets, 2006-26", "No better than random timing", "No"),
    ("Five-factor screener, top 10", "US point-in-time, 2012-26", "+3.2%/yr vs universe, t = 1.0", "Not proven"),
    ("Quality factor", "US, 2012-26", "+0.3-0.6%/yr, t = 0.2-0.3", "No"),
    ("Commodity trend following", "ETFs, 2006-26", "Halves drawdowns; Sharpe gain CI touches zero", "Almost"),
    ("Sector rotation by Fed regime", "2000-26", "+2.3%/yr, t = 1.98, mostly 2000 and 2020", "No"),
    ("Quality / trend sleeves in a 70/20/10", "2012-26", "No reliable Sharpe gain", "No"),
    ("Volatility targeting (HAR-RV)", "SPY 2003-26, global ETF 2014-26", "Cuts drawdowns, not returns", "Risk only"),
    ("Cross-sectional momentum", "US stocks 2013-26, ETFs 1999-26", "Stocks t = 1.7; ETFs ≈ 0", "No"),
    ("Short-term reversal, RSI(2)", "6 ETFs, 1993-2026", "Edge fell from 0.80% to 0.12% per trade", "Not any more"),
], columns=["Idea", "Data", "Net result", "Passes?"])
st.dataframe(score, hide_index=True, use_container_width=True)

st.subheader("What I learned")
st.markdown(
    """
- **Published edges fade.** RSI(2) lost about 85% of its edge after it became popular in 2008.
- **What works reduces risk, it doesn't add return.** Trend following and volatility targeting cut drawdowns
  but cost 1-3 points a year, and they only pay off in slow bear markets like 2008.
- **"Almost significant" usually means one or two episodes.** Before believing a t of 1.7, check the subperiods.
- **A better forecast is not a better strategy.** HAR forecasts volatility 22% better than a trailing average;
  the strategy built on it performs the same.
- **Data fails silently:** bad prices in Yahoo, a third-party tool's Sharpe ratio inflated 5-10×, and universes
  that drop every company that died.
"""
)

st.subheader("Alpha or factor exposure?")
st.markdown("Fama-French five-factor + momentum regressions of the backtested portfolios. The screener's edge over its "
            "universe is mostly a **profitability tilt** (RMW loading 0.68); the leftover ~3%/yr alpha has t ≈ 1. "
            "My momentum backtest is 89% explained by the published momentum factor, which is a useful check that the code is right.")
st.image(str(ROOT / "research/factor-models/figures/alphas.png"))

st.subheader("Portfolio risk: which VaR survives a backtest?")
st.markdown("A 70/20/10 equity portfolio (ETF proxies, 2004-2026). Daily 99% VaR forecast with four methods and "
            "checked against what happened: the normal model is broken 2.6% of the time instead of 1%; only "
            "**filtered historical simulation** gets the count right (55 vs 50 expected), and even it misses the first "
            "days of each crisis. For a euro investor the dollar halved the 2022 loss (−10% vs −21%).")
c1, c2 = st.columns([1.4, 1])
c1.image(str(ROOT / "research/portfolio-risk/figures/var_backtest.png"))
c2.image(str(ROOT / "research/portfolio-risk/figures/stress_tests.png"))

st.subheader("Derivatives: is selling volatility a free lunch?")
st.markdown("The VIX was above subsequent realised volatility on 86% of days since 1990. But a delta-hedged short "
            "ATM straddle only profits if you assume you can sell at the VIX; at a realistic at-the-money vol "
            "(0.72 x VIX, today's ratio, because the VIX includes the put skew) it loses money. The premium sits "
            "in the downside puts, and so does the crash risk.")
c1, c2 = st.columns(2)
c1.image(str(ROOT / "research/derivatives/figures/spy_smile.png"))
c2.image(str(ROOT / "research/derivatives/figures/variance_premium.png"))

st.subheader("Three charts from the research")
c1, c2 = st.columns(2)
c1.image(str(ROOT / "research/mean-reversion/figures/rsi2_decay.png"),
         caption="The RSI(2) edge, before and after publication")
c2.image(str(ROOT / "research/momentum/figures/quintiles_12_1.png"),
         caption="12-1 momentum quintiles: the right shape, not significant")
st.image(str(ROOT / "research/realised-vol/figures/spy_vol_target.png"),
         caption="Volatility targeting on SPY: lower drawdowns, lower returns")
