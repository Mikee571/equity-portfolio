# What I tested, and what I learned (October 2026)

Between 7 and 12 October 2026 I went back over every systematic idea I had been playing with and tested each one properly. At the end of October I did a second round with pre-registered tests and information that doesn't come from prices. This page pulls everything together.

The method was the same for all of them:

- rules fixed before seeing results;
- out-of-sample or walk-forward testing;
- costs included;
- a fair comparison (buy and hold, the equal-weight universe, the same exposure without timing, or random entries);
- a pass criterion decided in advance, usually t > 2 or a Sharpe CI above zero.

## The scorecard

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| [ML direction predictor](strategy-lab/archive/ml_predictor_lessons.md) | 4 assets, 2018–24 | AUC 0.43–0.52; worse than buy and hold on all 4 | No (archived) |
| [Cointegrated pairs](strategy-lab/stat_arb) | 37 pairs, walk-forward 2012–26 | −1.9%/yr; Kalman and OU don't fix it | No (archived) |
| [EMA cross, MACD](strategy-lab/archive) | 6 assets, 2006–26 | Not better than random timing on any | No |
| [Five-factor screener (top 10)](equity-screener) | US point-in-time, 2012–26 | +3.2%/yr over its universe, t 1.0 | Not proven |
| Quality factor | US, 2012–26 | +0.3–0.6%/yr, t 0.2–0.3 (but +4%, t 2.0, in CRSP data; see [OSAP check](research/osap-check)) | No |
| [Commodity trend following](strategy-lab/trend_following) | ETFs, 2006–26 | Sharpe +0.18–0.23 with CI touching zero; drawdown −73% → −35% | Almost |
| [Sector TAA by Fed regime](strategy-lab/taa_sectorial) | 2000–26 | +2.3%/yr, t 1.98, mostly 2000 and 2020 | No |
| [Quality/trend sleeves in a 70/20/10](strategy-lab/portfolio_construction) | 2012–26 | No reliable Sharpe gain | No |
| [Volatility targeting (HAR)](research/realised-vol) | SPY 2003–26, global ETF 2014–26 | SPY drawdown −55% → −30%; global ETF ≈ fixed exposure | Risk yes, return no |
| [Cross-sectional momentum](research/momentum) | US stocks 2013–26; ETFs 1999–26 | Stocks +6%/yr winners − losers, t 1.7; ETFs ≈ 0 | No |
| [Short-term reversal, RSI(2)](research/mean-reversion) | 6 ETFs, 1993–26 | +0.80% → +0.12% per trade; nothing since 2018 | Not any more |

None of the eleven in the first round passed. A later [factor regression](research/factor-models) adds context. The screener's top 10 loads mainly on profitability, small size and value, leaving ~3% a year of alpha with t ≈ 1. The momentum backtest is almost entirely the published momentum factor (R² 0.89). The closest ones (the screener, the TAA and stock momentum) have t-stats between 1 and 2, and each depends on one or two specific periods.

## Round 2: pre-registered tests (30–31 October 2026)

For these I wrote the question, the data, the test and the pass criterion in a `PREREGISTRATION.md` before building anything, and kept 2024–26 as a hold-out I didn't open until development was closed.

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| [Post-earnings drift (PEAD)](research/pead) | 86,000 announcements, 2012–26, real 8-K dates | Development D10 − D1 t 2.2; hold-out t 1.0; buyable long leg ≈ 0 | No |
| [13F clone of concentrated managers](research/clone-13f) | SEC 13F data sets, 2014–23 | +0.09%/yr over the universe (t 0.02), −0.5% against SPY | No |
| [Cash profitability filter](research/profitability-filter) | US point-in-time, 2012–23 | +0.43%/yr, t 0.77 | No |
| [Intraday momentum on SPY](research/intraday-momentum) (replication) | 1-minute bars, 2016–26 | Replica matches the paper (0.99 correlation); +0.9%/yr since publication vs SPY +20% | No |

Two checks frame these. The [OSAP check](research/osap-check) compares my backtests with Open Source Asset Pricing, which is built on CRSP and includes delisted companies: survivorship bias costs my momentum backtest about 2 points a year, only in the loser leg. The [OSAP scan](research/osap-scan) looks at 207 published signals in mid and large caps since 2015: none survives a multiple-testing correction, and the only family with some coherence is operating profitability.

That makes fifteen ideas tested and none passed.

## What I learned

Published edges fade. RSI(2) is the cleanest example: its edge has shrunk by about 85% since 2008. ETF momentum and one-month reversal don't show up in this data at all any more.

What works reduces risk, not adds return. Trend following and vol targeting cut drawdowns, from −52% to −30% on ACWI including 2008. But they cost 1–3 points a year and only pay off in slow bear markets like 2008. In fast V-shaped sell-offs like 2020 or 2025 they arrive late and get in the way.

"Almost significant" usually means one or two episodes. The TAA lives on 2000 and 2020, momentum on 2022–26, vol targeting on 2008. Before I believe a t of 1.7–2.0 I now check the subperiods.

A better forecast is not a better strategy. HAR forecasts volatility 22% better than a trailing average, and the strategy built on it performs exactly the same.

Data fails silently. Three examples from this round:

- Yahoo has bad VWRL.AS prices in 2013.
- A third-party backtesting tool reported Sharpe ratios inflated 5–10×, sometimes with the wrong sign.
- Stock universes built from today's listings drop every company that died.

Trading costs more than the backtest says. In Spain every sale realises a taxable gain (ETFs can't be switched tax-free like mutual funds), so anything that rotates pays more than the model charges.

Small baskets are a lottery on names. In one five-stock "quality" paper portfolio, MSFT explained 76% of the return.

## What it means in practice

For a long-term investor holding a global index ETF, none of these rules improved on simply holding it after costs. The levers that matter are elsewhere: how much you contribute, costs, taxes, and not selling in a drawdown. The one genuine choice left is a risk preference: whether to pay roughly 1 point a year for insurance against slow bear markets.

## If I come back to this

It's only worth it with information that doesn't come from price: fund flows, real sentiment data, insider buying, earnings surprises. It would also need:

- a written hypothesis before testing;
- a hold-out sample I don't touch until the end;
- for stocks, a universe that includes delisted companies.

The second round did exactly that for earnings surprises and 13F holdings, and the answer was the same: what's left is in shorts and microcaps, which I can't trade, and what I can buy is already in the index. The OSAP comparison also gave me a bound on survivorship bias that I didn't have before.

I won't retest variations of what's already discarded: pairs with Kalman, RSI(2), ETF momentum, or re-fitting the screener's weights.
