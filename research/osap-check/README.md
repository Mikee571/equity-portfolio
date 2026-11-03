# My backtests against Open Source Asset Pricing

30 October 2026. My equity backtests only have companies that are listed today, and I never knew how much that biases them. Open Source Asset Pricing (Chen and Zimmermann) publishes portfolios for more than 200 signals built with CRSP, which does include the companies that stopped trading. They're free to download with `pip install openassetpricing`. I use the October 2026 release, with data up to December 2025.

`compare.py` downloads three versions of the portfolios and compares them with my results over the same months:

- `quintiles_ew`: quintiles of all of CRSP, microcaps included.
- `quintiles_vw`: quintiles of all of CRSP, value-weighted.
- `ex_nyse_p20_me`: the original paper's construction, dropping companies below the 20th percentile of NYSE market cap. It's the closest thing to my $1bn filter.

The numbers are gross (I add the costs back to my momentum), annualised, with Newey-West t-stats with 3 lags. "Top" and "bottom" are the extreme quintile (or decile) minus the average of all of them, the same as my comparison with the universe.

## 12-1 momentum (Feb 2013 to Dec 2025)

| Version | Winners − average | Losers − average | Winners − losers | Correlation with mine |
|---|---|---|---|---|
| Mine (>$1bn, survivors, EW quintiles) | +2.8% (t 1.5) | −2.9% (t −1.2) | +5.7% (t 1.6) | |
| OSAP with size filter (EW deciles) | +3.5% (t 1.3) | −5.0% (t −1.2) | +8.5% (t 1.8) | 0.84 |
| OSAP VW quintiles | +0.6% (t 0.2) | −3.3% (t −0.8) | +3.9% (t 0.6) | 0.77 |
| OSAP EW quintiles, all of CRSP | +3.1% (t 1.9) | −9.3% (t −2.1) | +12.4% (t 2.3) | 0.59 |

The size-filtered version moves almost exactly like mine (correlation 0.84). The difference is where I expected it: among the winners there's hardly any gap (0.7 points), and among the losers OSAP comes out about 2 points a year worse. That's survivorship bias. The companies that sink and disappear are in the loser quintile, and they aren't in my data. Part of those 2 points is because OSAP uses deciles, which are more extreme than my quintiles, so the real bias is a little smaller.

The conclusion of the [momentum project](../momentum) doesn't change. In mid and large caps no version reaches t = 2. Only the one with microcaps passes, and almost all of that comes from 2022–25 (+29% a year, against +1% in 2017–21). For what I would buy, which is the winners, my data wasn't misleading me.

## Quality: gross profitability (gross profit / assets) and ROE (Feb 2012 to Dec 2025)

Here there's a difference I didn't expect.

| Signal | Version | Top quintile − average | By subperiod (2012–16 / 2017–21 / 2021–25) |
|---|---|---|---|
| Gross profitability | Mine (EW, survivors, XBRL) | +0.6% (t 0.3) | −0.4 / +6.0 / −3.8 |
| Gross profitability | OSAP with size filter (VW) | +4.0% (t 2.0) | +1.5 / +6.7 / +3.9 |
| Gross profitability | OSAP all of CRSP (VW) | +4.5% (t 2.3) | +1.3 / +6.8 / +5.6 |
| ROE | OSAP with size filter | +1.4% (t 1.5) | +0.2 / +2.5 / +1.6 |

The definition is the same (sales minus cost of sales, over total assets, no financials). Even so, OSAP gets +4% a year in the top quintile, with t of 2 to 2.3. It also works better after publication than before: the long-short gives +9.6% a year in 2012–25 against +3.8% in 1963–2011.

The gap with my results is almost entirely in Dec 2021 to 2025: I get −3.8% a year and OSAP +3.9%. I see three possible explanations, and with this data I can't separate them:

1. Weighting. OSAP value-weights this signal, as in Novy-Marx's paper, and doesn't publish the equal-weighted version (the EW and VW files are identical for GP). Since 2022, large companies with high gross margins (tech) have done very well. A VW portfolio of that quintile can be dominated by four or five names.
2. Survivorship. Unprofitable companies that went bust or were sold cheaply aren't in my universe. That flatters my bottom quintile and the average, and narrows the spread. The strength of OSAP's losing leg (−5.6%, t −3.4) points to this.
3. Data. My numbers come from XBRL with filing dates, and OSAP uses Compustat with a standard lag.

This fits the [Fama-French regressions](../factor-models): the screener's edge came from its profitability loading (RMW 0.68). The profitability factor exists in good data. What I don't know is whether an equal-weighted, long-only, large-cap portfolio like mine captures it.

## What changes

In momentum, nothing. I now have a bound on survivorship bias (about 2 points a year, only in the losers) and I know the conclusion holds.

In quality, my "doesn't work" was too strong. It would be more accurate to say it doesn't show up in my version (equal-weighted, long-only, survivors), but it does in the standard CRSP version, if only just (t ≈ 2) and concentrated in 2017–21. To find out whether the difference was the weighting, I reran my backtest value-weighted (below).

## Value-weighted gross profitability (`gp_vw.py`, `gp_annual.py`)

Same universe, same signal and same months as `equity-screener/src/backtest/quality.py`. I only change the weights, from equal to market cap. Then I also try OSAP's construction: portfolios formed at the end of June and held 12 months, instead of rebuilt every month. All gross, top (or bottom) quintile minus the average of the five quintiles, as in OSAP.

| Version | Top quintile − average | Bottom quintile − average | 2012–16 / 2017–21 / 2021–25 (top) | Correlation with OSAP |
|---|---|---|---|---|
| Mine, EW, monthly | +0.8% (t 0.6) | −2.0% (t −1.4) | −0.6 / +4.8 / −2.2 | 0.33 |
| Mine, VW, monthly | −2.9% (t −0.9) | −0.9% (t −0.4) | −9.6 / +4.8 / −4.2 | 0.46 |
| Mine, EW, annual in June (from Jul 2013) | +0.1% (t 0.1) | −2.3% (t −1.4) | −1.7 / +3.0 / −1.9 | 0.40 |
| Mine, VW, annual in June (from Jul 2013) | −4.1% (t −1.2) | −2.8% (t −1.0) | −13.8 / +3.8 / −5.2 | 0.39 |
| OSAP with size filter (VW, annual) | +4.0% (t 2.0) | −5.6% (t −3.4) | +1.5 / +6.7 / +3.9 | |

Weighting doesn't explain it. Value-weighted it comes out worse, not better, and none of my four versions looks like OSAP: the monthly correlation stays at 0.33–0.46, when for momentum it was 0.84. My VW version is also very concentrated. The five largest weights add up to half the quintile until 2021 and three quarters since 2024 (today NVDA, AAPL, MU, WMT, LRCX...). What happens to two or three names decides the result: in June 2023 NVDA dropped to quintile 3 and missed its whole 2023–24 rise.

With the same definition, the same size filter and the same construction, my data and CRSP's don't measure the same thing. What's left is the universe (companies that disappeared and those between ~$500mm and $1bn) and the data source (XBRL with filing dates against Compustat with a six-month lag). Without CRSP/Compustat I can't separate the two. I can't blame it all on survivorship either, because the biggest difference is in 2021–25, the period where it should matter least.

The only thing both sources agree on is the low leg: companies with the least gross profitability do worse than average. Strongly in OSAP (−5.6%, t −3.4). In my data in the same direction but not significant (−2.0%, t −1.4), except in 2017–21 (−5.6%, t −2.8). If I ever use gross profitability, it would be to drop the bottom quintile in the screener, not to buy the top one. That also fits the literature's view that the quality premium comes mostly from avoiding "junk".

Decision: I don't change anything in the screener. The conclusion on quality goes from "doesn't work" to "the factor exists in CRSP, but my implementation doesn't capture it, and I don't know whether because of the data or the universe". Testing the bottom-quintile filter in the screener would be a new idea, and I'd have to pre-register it before looking. That became the [profitability filter](../profitability-filter).

## Files

`comparison.csv` has every OSAP version and its subperiods, and `gp_vw.csv` / `gp_vw_monthly.csv` those of my VW backtest. The OSAP parquet files are saved in `data/` (about 50 MB; not in the repo).

`openassetpricing` depends on `wrds`, which pins pandas < 2.3. Installing it in my main Python downgraded pandas from 3.x to 2.2.3, and the screener's caches stopped loading. I keep it separately in `.venv` (to download: `.venv/Scripts/python compare.py`). The `gp_*.py` scripts run with the normal Python.
