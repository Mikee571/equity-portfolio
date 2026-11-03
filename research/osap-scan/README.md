# What's still alive among published anomalies, and what's worth testing

30 October 2026. After testing a dozen ideas with none approved, I went looking for more papers and repositories. Before writing down loose ideas I wanted the whole picture: how many of the published anomalies still work in the kind of companies I can buy.

## What OSAP says about 207 published signals (`osap_alive.py`)

I used the Open Source Asset Pricing portfolios with a size filter (companies above the NYSE 20th percentile), which are the closest to what I would buy. The same data is behind my [OSAP check](../osap-check).

| | Long-short, median annual |
|---|---|
| In the original paper's sample | +4.1% |
| After publication | +2.0% |
| 2015–2025 | +1.4% |

In 2015–2025, 16 signals have a long-short with t > 2 and 8 have a long leg (the only part I can buy) with t > 2. By pure chance I'd expect about 5 in each case. None passes t > 3 (the Harvey, Liu and Zhu threshold) or Benjamini-Hochberg at 5%.

The only thing with some coherence is that three of the top eight are variants of operating profitability: cash-based operating profitability (Ball et al., 2016), operating profitability with R&D, and gross profit over assets. All three give +5–7% a year on the long leg with t between 2.0 and 2.7. It's the same family that showed up in my [Fama-French regressions](../factor-models) (RMW) and the only one that agrees in the OSAP check. One by one they don't survive the correction, but a whole family showing up is harder to put down to luck than a single signal.

The overall conclusion is the same as in the [synthesis](../../SYNTHESIS.md), but now with 207 signals and CRSP data instead of mine: in mid and large caps there's almost nothing left to buy.

A practical note that matters more than any of this: for a euro investor buying US stocks, the currency conversion a retail broker charges (often 0.5% each way) is larger than any edge I've measured after costs in the whole lab.

## New ideas, ranked by how well they fit me

1. Profitability filter in the screener. Drop the quintile with the lowest cash-based operating profitability or gross profit. It's supported by the OSAP scan, the OSAP check and the FF regressions. I have the data in XBRL, and it's long-only and large-cap. It needs pre-registering before looking, with the hold-out from 2024. I tested it: [profitability filter](../profitability-filter).
2. Cloning fund portfolios with 13Fs. The SEC publishes 13F data in tabular form for free every quarter. There's a recent paper by Schroeder and Posch (2024) with 13,035 funds from 1998 to 2023 that I haven't read. It fits what I can do: long only, large companies, quarterly turnover, with a 45-day delay. The practical evidence is mixed: the good results (Faber, 9.8% against SPY's 6.6%) are gross and use managers chosen after the fact. I tested it: [13F clone](../clone-13f).
3. The earnings announcement premium. Stocks tend to rise in the days before reporting (Gao, Hu and Zhang: 0.31% over the 10 days before). One paper says it has disappeared in the US since the 8-K brought the information forward. Testing it is cheap because I already have the 8-K dates from the [PEAD study](../pead). But it needs a lot of turnover, and with a 0.5% conversion nothing would be left even if it existed.
4. The turn-of-the-month effect in a global index. It would only help me choose which day to make a monthly contribution. A 2025 paper says it has disappeared (Han, Han and Tian, "The disappearing turn-of-month effect"). It's five minutes with daily prices, but the most it could be worth is a few tenths of a percent a year on one contribution.

## What I looked at and dropped

- Volatility smile slope (Xing, Zhang and Zhao). It ranks high in OSAP (t 3.0 on the long-short), but Muravyev, Pearson and Pollet (2025) show that two thirds of the prediction disappears when hard-to-borrow stocks are removed. It's a signal for shorts.
- Factor momentum (Ehsani and Linnainmaa). The replications are mixed outside the US, and it's traded with long-short factor portfolios that I can't replicate.
- Insider purchases (Form 4). I had already ranked it low: the reaction lasts two or three days and then there's no alpha left.
- More variations of momentum or reversal. Already dropped in the synthesis.

## Sources

- Open Source Asset Pricing: https://github.com/OpenSourceAP/CrossSection
- 13F, summary of Schroeder and Posch (CXO Advisory): https://www.cxoadvisory.com/miscellaneous/form-13f-clone-portfolio-performance/ and Faber: https://www.etf.com/sections/news/meb-fabers-hedge-fund-replication-101
- The 13F delay: https://arkolith.com/blog/copy-trading-hedge-funds
- Earnings announcement premium: https://www.iimb.ac.in/ARC2020/Papers/The_Disappearing_Earnings_Announcement_Premium.pdf, https://quantpedia.com/pre-announcement-returns/ and https://www.aqr.com/Insights/Research/Working-Paper/The-Earnings-Announcement-Premium-and-Trading-Volume
- Turn of the month: https://www.cxoadvisory.com/calendar-effects/turn-of-the-month-effect-persistence-and-robustness and McConnell and Xu (2008): https://ideas.repec.org/a/taf/ufajxx/v64y2008i2p49-64.html
- Volatility smile: https://ideas.repec.org/a/cup/jfinqa/v45y2010i03p641-662_00.html and Muravyev, Pearson and Pollet: https://data.mendeley.com/datasets/n73cyx89gs
- Factor momentum: https://arxiv.org/pdf/2009.04824
