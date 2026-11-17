# What I tested, and what I learned (October–November 2026)

Between 7 October and 14 November 2026 I tested every systematic idea I had been playing with, in three rounds. The first was a pass over everything in early October. The second, at the end of October, used pre-registered tests and information that doesn't come from prices. The third, in November, added more markets, more non-price data and a harder question: can I actually buy it? This page pulls everything together.

The method was the same for all of them:

- rules fixed before seeing results;
- out-of-sample or walk-forward testing;
- costs included;
- a fair comparison (buy and hold, the equal-weight universe, the same exposure without timing, or random entries);
- a pass criterion decided in advance, usually t > 2 or a Sharpe CI above zero.

From the end of October every test has a pre-registration written before running it, and if development fails the hold-out stays closed.

## Round 1: the first pass (7–12 October)

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

## Round 2: pre-registered tests (30–31 October)

For these I wrote the question, the data, the test and the pass criterion in a `PREREGISTRATION.md` before building anything, and kept 2024–26 as a hold-out I didn't open until development was closed.

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| [Post-earnings drift (PEAD)](research/pead) | 86,000 announcements, 2012–26, real 8-K dates | Development D10 − D1 t 2.2; hold-out t 1.0; buyable long leg ≈ 0 | No |
| [13F clone of concentrated managers](research/clone-13f) | SEC 13F data sets, 2014–23 | +0.09%/yr over the universe (t 0.02), −0.5% against SPY | No |
| [Cash profitability filter](research/profitability-filter) | US point-in-time, 2012–23 | +0.43%/yr, t 0.77 | No |
| [Intraday momentum on SPY](research/intraday-momentum) (replication) | 1-minute bars, 2016–26 | Replica matches the paper (0.99 correlation); +0.9%/yr since publication vs SPY +20% | No |
| Earnings announcement premium (predicted dates, [−5, +5]) | US, 74,692 announcements, 2012–23 | +3.4%/yr gross (t 1.4), −1.7% net; only works in ~$170M microcaps | No |
| Long-only small value tilt (Ken French data) | Developed and Europe 1990–2026, US 1926–2026 | Developed +1.7%/yr net (t 1.1); 2014–26 −1.9%; without 2000–04, −0.7%; US from +6% to +2.3% after 1992 | No |

Two checks frame these. The [OSAP check](research/osap-check) compares my backtests with Open Source Asset Pricing, which is built on CRSP and includes delisted companies: survivorship bias costs my momentum backtest about 2 points a year, only in the loser leg. The [OSAP scan](research/osap-scan) looks at 207 published signals in mid and large caps since 2015: 16 long-shorts have t > 2 where chance would give about 5, none survives a multiple-testing correction, and the only family with some coherence is operating profitability.

After two rounds: seventeen ideas, none passed.

## Round 3: more markets, more data, and can I buy it? (November)

All pre-registered except the global macro study and the descriptive first parts of the overnight and bubble studies. Rows without a link live in my private research folder; their code isn't in this repository yet.

Rules that only use prices:

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| Systematic global macro: oil, Fed, curve, credit and gold | US equities monthly 1985–2026; then a global ETF in euros from 2014 | Only cutting exposure after large oil spikes helps (ΔSharpe +0.08–0.11), but none of 28 rules survives a multiple-testing correction (deflated Sharpe 0.06). On the global ETF in euros, going from 100% to 75% gives ΔSharpe 0.00 | No |
| Overnight vs intraday returns (Knuteson) and its family: Gao's intraday momentum, Akbas's tug of war, overnight only when the VIX is high | ETFs and indices 1993–2026, SPY 1-minute 2016–26, top 1,000 US stocks | The night/day gap was real before 2020 and is gone in SPY, QQQ and Europe. Gao: −5.6%/yr net at 1 bp a side (t −3.7). Akbas: +0.15%/month, t 0.45 since 2018. The VIX filter fails too | No |
| Sector bubbles (Greenwood, Shleifer and You) and Burry's AI thesis | 49 French industries; out of sample 19 STOXX 600 and 16 TOPIX-17 sectors, 2008–26 | After running up more than 100% over the market, 46% end in a crash, but the median net return is −1%. The best variant (stay in, leave on a 10-month average break) gives −1.7%/yr, t −0.86, out of sample. Buying puts: −1.6%/yr, t −2.5 | No |
| Rolling Candle Profile and other TradingView indicators | 12 index ETFs, 2000–17 | −0.27% per signal, t −1.85 (wrong sign); against a plain EMA21 rule, +0.08%, t 0.51 | No |
| Kronos, a time-series foundation model for markets, zero-shot | S&P 500, 59 dates from Jul-2024 to Oct-2026, after its training data | RankIC 0.011, t 0.49; worse volatility forecasts than HAR. Its signal has a −0.71 correlation with last month's return: it's reversal | No |
| Opening range breakout from a popular day-trading repository | 150 S&P 500 stocks, 5-minute bars, 2016–22 | −9.5 bp/day net (t −17), worse than entering at 9:45 with no signal; negative every year | No |

Trend following:

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| Diversified trend with micro futures (TSMOM12, 23 markets in four asset classes, long and short) | ETF proxies for the futures, 2008 – Oct 2026 | Standalone: +5.6%/yr over bills, Sharpe 0.57, t 2.67; since 2013 t 2.2. As an overlay on a global ETF: Sharpe from 0.66 to 0.90, ΔSharpe CI [−0.07, 0.51]. Without 2008 and 2022, t 1.87 | Yes standalone; the overlay misses narrowly; needs an account of about $100k |
| Hedging-pressure (COT) filter on the trend | CFTC Legacy reports, 2008–26 | Commodity leg Sharpe from 0.50 to 0.51, ΔSharpe CI [−0.24, 0.28]; the whole strategy doesn't change | No |
| 80% global ETF + 20% real managed-futures funds, in euros | AQMIX, PQTIX, ASFYX, DBMF and KMLM, Feb-2010 – Oct 2026 | Sharpe from 0.79 to 0.88, ΔSharpe CI [−0.035, 0.208]. Max drawdown from −25.9% to −21.4% and worst year from −13.6% to −8.4%, for 0.6 points a year (1.2 currency-hedged). The UCITS version tracks the US fund poorly (weekly correlation 0.78) | Insurance yes; Sharpe gain and vehicle no |

Equity factors:

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| Global factors (Jensen, Kelly and Pedersen data) | All JKP factors, US and world ex-US, to Dec 2025 | In the US the premium dies after publication (0.07%/month, t 1.0); outside it survives (0.24%/month, t 4.7). Long-only, the most profitable third ex-US gives +1.2%/yr, t 3.7. But UCITS quality ETFs against a global ETF give +0.65%/yr, t 0.7 | On paper yes; with ETFs I can buy, no |
| Eurozone momentum | 929 eurozone stocks 2004–26 and UCITS momentum ETFs | Top 20% over the universe +0.21%/month, t 1.2; the ETFs t 0.96 and 0.18. In the JKP data the gross long-short does work in Germany, Italy and Spain | No |
| Fama-MacBeth of gross profitability with controls | The screener's point-in-time panel, US >$1B, 2012–23 | GP/A +0.055%/month per standard deviation, t 0.71; CFO/A the same. Only one-month reversal is significant | No |
| Screener exclusions: low cash conversion (CFO / net income < 0.8) or peak-cycle earnings | The screener's point-in-time backtest, 2012–23 | Cash conversion −0.55%/yr, t −1.13; peak cycle t 0.14 and −1.09 depending on the version | No; both stay as warnings in the screener |

Earnings and other events:

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| PEAD in the eurozone and Japan | yfinance dates and surprises, 2006–18; 442 eurozone and 625 Japanese stocks | Eurozone D10 − D1 +0.65%/month, t 2.3; buying D10, −0.07%/month net, t −0.28. Japan t 1.7 in development and in the hold-out | Long-short yes; long-only no |
| Long-only microcaps with delisted names (earnings premium and PEAD D10) | US $50–500M, 2016–23, Alpaca and SEC data, estimated spreads | Earnings premium +20.7% gross, −9.4% net (costs of 30% a year); PEAD D10 +7.8% net, t 1.97 against a 2.24 bar, mostly 2020–23 | No |
| Cash merger arbitrage | 340 deals from EDGAR, 2016–21, delisted names included | Net alpha −3.8%/yr, t −0.96; eleven broken deals eat a third of the gains | No |
| Spin-offs | 50 spincos from EDGAR (Form 10-12B), 2016–21 | CAPM alpha −14.8%/yr, t −1.95; the CSD ETF also lags SPY | No |
| Odd-lot tender offers | 18 US self-tenders, 2016–21 | +1.75% per trade, t 0.97, $67 on average; 22% lose, and the price doesn't converge to the tender price | No |

Information that isn't price:

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| Lazy Prices: changes in 10-K text | 26,613 10-Ks from EDGAR, top 1,000 US, 2015–26 | v1 (cosine on word counts) +0.09%/month, t 1.0; v2 (TF-IDF, bar raised to t > 2.5) +0.10%/month, t 0.9. What's left is profitability, value and low beta | No |
| Fortune's Best Companies to Work For | 2012–20 lists, held April to April, 0.55% a side | FF5 + momentum alpha +2.0%/yr, t 1.6; CAPM alpha 0.6% | No |
| An LLM scoring earnings releases | Forward only: every 8-K item 2.02 release from Nov-2026 to Nov-2027 | Running; evaluation in February 2028 | Pending |

Risk:

| Idea | Data | Net result | Passes? |
|---|---|---|---|
| [GJR-GARCH filter in a filtered-historical-simulation VaR](research/portfolio-risk) | 2007 – Oct 2026, 4,785 days | Same exception count (51, with 48 expected), Christoffersen p from 0.002 to 0.58, lower average VaR, Diebold-Mariano t −2.9 | Yes, as a risk model; most of it is the GARCH, not the asymmetry |

Across the three rounds that's more than 40 tests. Four things pass, fully or in part, and none adds return with what I can actually buy: diversified trend with futures (standalone, and it needs an account of about $100k), the ex-US profitability premium in the JKP data (which real ETFs don't capture), the insurance part of the managed-futures sleeve (no Sharpe gain, and the UCITS vehicle tracks poorly) and the GJR filter, which is a risk model.

The trend result isn't a new idea: it's the CTA version of something I had already tested badly (commodities only, long only). The difference is breadth, going short and not having to put up the capital. Even so, my backtest has a higher Sharpe than AQR's factor (0.65 against 0.41 gross) and most real funds, and a good part of the return comes from 2008 and 2022. Live, I'd expect something closer to 0.3–0.4.

With this many tests you have to count. If nothing worked, with 40-odd tests and a bar of t > 2 I'd expect about one pass by luck, and a Bonferroni bar would be around t 3. Trend with futures (t 2.67) doesn't clear it. What makes me believe it isn't my t but decades of evidence outside my data: AQR's work and the real funds I used in the sleeve test. The ex-US profitability premium does clear it (t 4.7 long-short), but that one I can't buy.

## Pass, ruled out or inconclusive

In mid-November I went back over the tables with a different question. A "No" can mean that the effect isn't there, or that the test couldn't have seen it. To separate them, for each test with a comparable measure I took the 95% interval of its main number and compared it with the smallest effect I would care about: 1 point a year for a long-only portfolio against its benchmark, 2 for a long-short, 0.10 of Sharpe difference, the round-trip cost for a per-trade measure, and so on.

- Pass: it met its own bar.
- Ruled out: the top of the interval is below that minimum. If there is something, it's too small to use.
- Inconclusive: neither.

Of 44 tests, 2 pass, 9 are ruled out and 33 are inconclusive. Some I had treated as dead aren't, strictly: the 13F clone runs from −7 to +7 points a year, merger arbitrage from −11.6 to +4.0 and the earnings announcement premium from −6.7 to +3.3. It's not that they work. The tests couldn't tell them apart from zero or from something useful. The ruled-out ones are of three kinds: tests with a lot of data relative to their noise (the breakout rule, with 139,000 trades, and Gao's intraday momentum, with 2,710 days), results with clearly the wrong sign (spin-offs, puts, cointegrated pairs and the TradingView indicator) and small changes to a portfolio I already know well (adding a 10% sleeve, the oil rule on the global ETF, dropping low cash conversion from the screener).

One caveat: I set those minimums after seeing all of these results, so for the old tests the line between ruled out and inconclusive is drawn after the fact. It only really counts for new tests, which now write down the effect they expect, its noise and the smallest effect that matters before running. That also explains why so little passes. With 10–15 years of data and a 6% tracking error, a long-only tilt needs to earn about 3.5 points a year just to have even odds of reaching t 2. And with 40-odd tests, one or two passes is what I'd expect both if nothing worked (about 0.9 by chance) and if eight ideas had a real but small effect (about 2). My tests can't tell those two worlds apart.

## What I learned

Published edges fade. RSI(2) is the cleanest example: its edge has shrunk by about 85% since 2008. ETF momentum doesn't show up in this data any more, and neither does one-month reversal in a portfolio (t 0.2 in my universe); it only appears in the Fama-MacBeth regression with controls (t −2.4), and Kronos, which is essentially that, doesn't pass.

What works reduces risk, not adds return. Trend following and vol targeting cut drawdowns, from −52% to −30% on ACWI including 2008. But they cost 1–3 points a year and only pay off in slow bear markets like 2008. In fast V-shaped sell-offs like 2020 or 2025 they arrive late and get in the way.

"Almost significant" usually means one or two episodes. The TAA lives on 2000 and 2020, momentum on 2022–26, vol targeting on 2008. Before I believe a t of 1.7–2.0 I now check the subperiods.

Some strategies work for an institution and not for me. Diversified trend is the clearest case: with $25k you can only hold 3–4 of the 22 positions in micro contracts, and you need around $100k for the rounded book to look like the continuous one. Long-short strategies need cheap stock borrow. Before calling an idea dead, it's worth separating whether the signal fails or my way of trading it does.

What's dead in the US is often alive abroad, but only on paper. The JKP factors, PEAD in the eurozone and momentum in Germany, Italy and Spain all give gross long-shorts with t > 2. As soon as I make them long-only and add costs, almost nothing is left, because the drift sits in the short leg.

Many new ideas are old factors with a new name. Kronos is one-month reversal, Lazy Prices loads on profitability and value, and the 13F clone is a mega-cap basket. Before spending days on something new, it's worth checking how it correlates with what I already know.

Costs bind before signals do. A stock strategy that turns over 30% of the portfolio a month pays about 3.5 points a year to a 0.5% currency conversion each way, before any spread or tax.

A long-only factor tilt can't be proven on a personal horizon. To detect +1.6 points a year with a 6% tracking error at t 2 you need about 55 years of data.

"Sure profits" rarely are. In odd-lot tender offers one trade in five loses money, and the price doesn't end at the tender price.

A better forecast is not a better strategy. HAR forecasts volatility 22% better than a trailing average, and the strategy built on it performs exactly the same.

Test the method on data where you know the answer. In the puts test, estimating implied volatility from realised volatility produced +9% a year buying fairly priced puts in simulated data, where the right answer is zero. Without the simulation I would have believed it.

Data fails silently. Some examples:

- Yahoo has bad VWRL.AS prices in 2013, negative adjusted prices for a Japanese ETF (1629.T), unadjusted splits in another (1306.T), and repeated opening prices in many indices (77% of days for ^FTSE).
- A third-party backtesting tool reported Sharpe ratios inflated 5–10×, sometimes with the wrong sign.
- Stock universes built from today's listings drop every company that died.
- Dividend-adjusted prices invent tender-offer spreads that don't exist. Raw prices are the right ones there.
- The Ken French industry files mark missing data with −999. Without cleaning them, the share of bubbles that end in a crash came out at 41% instead of 46%.

Trading costs more than the backtest says. In Spain every sale realises a taxable gain (ETFs can't be switched tax-free like mutual funds), so anything that rotates pays more than the model charges.

Small baskets are a lottery on names. In one five-stock "quality" paper portfolio, MSFT explained 76% of the return.

## What it means in practice

For a long-term investor holding a global index ETF, none of these rules improved on simply holding it after costs. The levers that matter are elsewhere: how much you contribute, costs, taxes, and not selling in a drawdown.

The one genuine choice left is a risk preference: whether to pay for insurance against slow bear markets. November made it concrete. Diversified trend with futures works, but needs an account of about $100k. The accessible version, a 20% sleeve in real managed-futures funds, would have cut the worst year from −13.6% to −8.4% for about 0.6 points a year, partly thanks to the dollar, and the UCITS vehicle didn't track the original well. Whether that's worth paying is a question about how much risk I want to carry, not something a test can decide.

## What's still open

Some of this now runs forward, which is the only way to get data nobody has looked at yet: a paper book of the diversified trend strategy with real futures contracts (December 2026 to November 2027), the LLM earnings-release test (evaluation in February 2028) and a couple of paper-trading experiments that I'll write up when they finish.

For a new idea I still ask for the same things: information that doesn't come from price, a written hypothesis, a hold-out I don't touch until the end and, for stocks, a universe that includes delisted companies. Insider buying and short interest I left untested on purpose. The replications I found say most of the insider effect was 2008, and in microcaps it lasts two or three days. The short-interest evidence is old and concentrated in stocks that are expensive to borrow.

I won't rerun these with the same data or test variations of them: pairs with Kalman, RSI(2), ETF momentum, re-fitting the screener's weights, opening-range breakouts and other intraday rules, price-only TradingView indicators, PEAD outside the US, US large-cap profitability with another method, spin-offs, merger arbitrage without announcement dates, or a third version of Lazy Prices.
