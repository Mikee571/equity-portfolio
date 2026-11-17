"""Scorecard of the systematic strategy research (see SYNTHESIS.md)."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import ROOT  # noqa: E402

st.set_page_config(page_title="Strategy research", layout="wide")
st.title("Strategy research: 40+ ideas, one strategy passes")
st.caption("Each idea was tested with rules fixed in advance, realistic costs, out-of-sample data and a fair "
           "benchmark; from round 2 on, pre-registered. The one strategy that passes, diversified trend with futures, "
           "needs an account of about $100k. Full write-up in SYNTHESIS.md.")

st.caption("Round 1: early October. Round 2: end of October, pre-registered. Round 3: November, pre-registered.")
R1, R2, R3 = "1", "2", "3"
score = pd.DataFrame([
    (R1, "ML direction predictor (XGBoost)", "4 assets, 2018-24", "AUC 0.43-0.52, worse than buy and hold on all 4", "No"),
    (R1, "Cointegrated pairs (stat arb)", "37 pairs, walk-forward 2012-26", "−1.9%/yr net; Kalman/OU don't fix it", "No"),
    (R1, "EMA cross, MACD", "6 assets, 2006-26", "No better than random timing", "No"),
    (R1, "Five-factor screener, top 10", "US point-in-time, 2012-26", "+3.2%/yr vs universe, t = 1.0", "Not proven"),
    (R1, "Quality factor", "US, 2012-26", "+0.3-0.6%/yr, t = 0.2-0.3", "No"),
    (R1, "Commodity trend following", "ETFs, 2006-26", "Halves drawdowns; Sharpe gain CI touches zero", "Almost"),
    (R1, "Sector rotation by Fed regime", "2000-26", "+2.3%/yr, t = 1.98, mostly 2000 and 2020", "No"),
    (R1, "Quality / trend sleeves in a 70/20/10", "2012-26", "No reliable Sharpe gain", "No"),
    (R1, "Volatility targeting (HAR-RV)", "SPY 2003-26, global ETF 2014-26", "Cuts drawdowns, not returns", "Risk only"),
    (R1, "Cross-sectional momentum", "US stocks 2013-26, ETFs 1999-26", "Stocks t = 1.7; ETFs ≈ 0", "No"),
    (R1, "Short-term reversal, RSI(2)", "6 ETFs, 1993-2026", "Edge fell from 0.80% to 0.12% per trade", "Not any more"),
    (R2, "Post-earnings drift (PEAD)", "86,000 announcements, 2012-26", "Development t = 2.2, hold-out t = 1.0; long leg ≈ 0", "No"),
    (R2, "13F clone of concentrated managers", "SEC 13F data sets, 2014-23", "+0.09%/yr vs universe, t = 0.02", "No"),
    (R2, "Cash profitability filter", "US point-in-time, 2012-23", "+0.43%/yr, t = 0.77", "No"),
    (R2, "Intraday momentum on SPY (replication)", "1-minute bars, 2016-26", "+0.9%/yr since publication vs SPY +20%", "No"),
    (R2, "Earnings announcement premium", "US, 74,692 announcements, 2012-23", "+3.4%/yr gross, −1.7% net", "No"),
    (R2, "Long-only small value tilt", "Developed 1990-2026, US 1926-2026", "Developed +1.7%/yr net, t = 1.1; negative since 2014", "No"),
    (R3, "Systematic global macro (oil, Fed, curve, credit, gold)", "US equities 1985-2026; global ETF in euros",
     "None of 28 rules survives multiple testing; ΔSharpe 0.00 on the global ETF", "No"),
    (R3, "Overnight vs intraday (Knuteson, Gao, Akbas, VIX filter)", "ETFs and indices 1993-2026, SPY 1-minute",
     "Night/day gap gone after 2020; Gao −5.6%/yr net, t = −3.7", "No"),
    (R3, "Sector bubbles and Burry's AI thesis", "49 US industries; EU and Japan sectors out of sample",
     "Best variant −1.7%/yr out of sample; puts −1.6%/yr", "No"),
    (R3, "TradingView indicators (Rolling Candle Profile)", "12 index ETFs, 2000-17", "−0.27% per signal, t = −1.85 (wrong sign)", "No"),
    (R3, "Kronos foundation model, zero-shot", "S&P 500, 2024-26", "RankIC 0.011, t = 0.49; it's one-month reversal", "No"),
    (R3, "Opening range breakout", "150 S&P 500 stocks, 5-minute bars, 2016-22", "−9.5 bp/day net, t = −17", "No"),
    (R3, "Diversified trend with micro futures", "23 markets, 2008-26", "Sharpe 0.57, t = 2.67; needs about $100k", "Yes, standalone"),
    (R3, "Hedging-pressure (COT) filter on the trend", "CFTC reports, 2008-26", "Commodity leg Sharpe 0.50 to 0.51", "No"),
    (R3, "20% managed-futures funds next to a global ETF", "Real funds in euros, 2010-26",
     "Worst year −13.6% to −8.4% for 0.6 points a year; the UCITS vehicle tracks poorly", "Insurance only"),
    (R3, "Global factors (Jensen, Kelly and Pedersen data)", "US and world ex-US, to 2025",
     "Ex-US profitability +1.2%/yr long-only, t = 3.7; real ETFs t = 0.7", "On paper only"),
    (R3, "Eurozone momentum", "929 stocks 2004-26, UCITS ETFs", "+0.21%/month vs universe, t = 1.2", "No"),
    (R3, "Fama-MacBeth of gross profitability", "US >$1B, 2012-23", "t = 0.71 with controls", "No"),
    (R3, "Screener exclusions: low cash conversion, peak cycle", "Screener backtest, 2012-23", "−0.55%/yr, t = −1.13; t = 0.14", "No"),
    (R3, "PEAD in the eurozone and Japan", "2006-18, 1,067 stocks", "Eurozone long-short t = 2.3; long-only −0.07%/month net", "Long-short only"),
    (R3, "Long-only microcaps with delisted names", "US $50-500M, 2016-23", "PEAD D10 +7.8% net, t = 1.97 < 2.24", "No"),
    (R3, "Cash merger arbitrage", "340 deals, 2016-21", "Net alpha −3.8%/yr, t = −0.96", "No"),
    (R3, "Spin-offs", "50 spincos, 2016-21", "CAPM alpha −14.8%/yr, t = −1.95", "No"),
    (R3, "Odd-lot tender offers", "18 US self-tenders, 2016-21", "+1.75% per trade, t = 0.97; 22% lose", "No"),
    (R3, "Lazy Prices (changes in 10-K text)", "26,613 10-Ks, 2015-26", "+0.10%/month, t = 0.9", "No"),
    (R3, "Best Companies to Work For", "Fortune lists, 2012-20", "FF5 + momentum alpha +2.0%/yr, t = 1.6", "No"),
    (R3, "An LLM scoring earnings releases", "Forward only, Nov-2026 to Nov-2027", "Evaluation in February 2028", "Pending"),
    (R3, "GJR-GARCH filter in the VaR", "2007-26, 4,785 days", "Christoffersen p from 0.002 to 0.58", "Yes, as a risk model"),
], columns=["Round", "Idea", "Data", "Net result", "Passes?"])
st.dataframe(score, hide_index=True, width="stretch", height=35 * len(score) + 38,  # every row, no inner scroll
             column_config={"Round": st.column_config.TextColumn(width="small")})

st.subheader("Pass, ruled out or inconclusive")
st.markdown("A \"No\" can mean the effect isn't there or that the test couldn't have seen it. For each test with a "
            "comparable measure I compared the 95% interval with the smallest effect worth having (1 point a year "
            "long-only, 0.10 of Sharpe, the round-trip cost per trade). I set those minimums after seeing the "
            "results, so for these tests the split is a reading after the fact.")
m1, m2, m3 = st.columns(3)
m1.metric("Pass", "2 of 44")
m2.metric("Ruled out", "9 of 44")
m3.metric("Inconclusive", "33 of 44")

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
- **What's dead in the US is often alive abroad, but only on paper.** Ex-US factors, eurozone PEAD and momentum
  work as gross long-shorts; long-only and after costs, almost nothing is left.
- **Many new ideas are old factors renamed.** Kronos is one-month reversal, Lazy Prices loads on profitability
  and value, and the 13F clone is a mega-cap basket.
- **Most "No"s are really "can't tell".** With 10-15 years and a 6% tracking error, a long-only tilt needs about
  3.5 points a year to have even odds of reaching t = 2.
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
