# Cloning the best ideas of concentrated managers (13F)

31 October 2026. This was the second idea from my [scan of published anomalies](../osap-scan): information that doesn't come from prices, that a retail investor can buy (long only, large companies, quarterly turnover), and that gets sold a lot as "copy the best managers". The rules are in [`PREREGISTRATION.md`](PREREGISTRATION.md), written before downloading anything.

## How I did it

- `fetch_13f.py` downloads the SEC's 54 "Form 13F data sets" (Q2 2013 to August 2026, about 3.3 GB) and keeps only the original 13F-HR filings and their equity positions (1.4 GB of parquet, not in the repo).
- `build_clone.py` applies the rules every quarter:
  - Managers with $200mm to $50bn, 10 to 50 positions, at least 50% of the value in the top 10, and at least 60% of the value in stocks they already held a year earlier.
  - Only filings made within 45 days.
  - Take each manager's 5 largest positions and buy the 20 stocks that appear in the most portfolios.
  - Form the portfolio on day 46 and hold it to the next quarter.
- CUSIPs are mapped to tickers with OpenFIGI (about 5,000).

Each quarter between 163 and 528 managers qualify (median 282).

## Development result (formations Nov 2014 to Nov 2023, 110 months)

| | Annual excess | t |
|---|---|---|
| Clone − equal-weighted universe, net of 10 bp | +0.09% | 0.02 |
| Clone − SPY, net of 10 bp | −0.52% | −0.22 |
| Clone − universe, with a 0.5% currency conversion | −1.33% | −0.36 |
| Clone − SPY, with a 0.5% currency conversion | −1.94% | −0.82 |

In CAGR terms: clone 10.5%, clone with conversion 8.9%, universe 10.3% and SPY 11.7%. By subperiod the clone trails both the universe and SPY in 2014–18 and in 2019–23.

None of the conditions is met. In practice the clone is a portfolio of the usual giants: in 2023 its top five ideas were MSFT, AMZN, AAPL, NVDA and META. It does the same as the market, with 20 names instead of 500, 36% turnover per quarter and, for a euro investor, 0.5% of currency conversion on every buy and sell.

That's what I expected in the pre-registration. What concentrated managers have in common is the same mega-caps a global index fund already holds. The part that might carry information (what only one manager owns) gets diluted when you vote across hundreds of them, and what arrives late is eaten by the 45-day delay.

## What I do with it

I'm not using it, and I don't open the 2024–26 hold-out, for the same reason as in the [profitability filter](../profitability-filter).

Some variants could come out differently and are left untested: a single manager chosen in advance, new positions instead of held ones, or conviction weighting. I'm not testing them now. Each would be another attempt on the same data, and picking the "good" manager after the fact is exactly the bias in Faber-style backtests.

`python fetch_13f.py`, then `python build_clone.py`. `build_clone.py --holdout` is written but I haven't run it.
