# Pre-registration: cloning the best ideas of concentrated managers (13F)

Written on 31 October 2026, before downloading any 13F. If I change anything later, I note it at the end with the date and the reason.

## Question

If every quarter I buy, with the 45-day 13F delay, the stocks that the most concentrated and patient managers hold among their top 5 positions, do I beat the equal-weighted universe after costs?

The literature I found says the managers worth cloning are the concentrated, low-turnover ones. With many positions or high turnover, the 45-day delay eats the information. I couldn't read the results of Schroeder and Posch (2024), which are behind a paywall. The positive results I saw (Faber) are gross and use managers picked after the fact.

## Data

- The SEC's "Form 13F data sets": one ZIP per quarter since Q2 2013, with the information as filed.
- Only original 13F-HR filings (no amendments). If a manager files twice for the same period, I keep the first.
- I only count filings made no more than 45 days after the quarter end.
- Positions: shares (SSHPRNAMTTYPE = SH), no options (PUTCALL empty).
- CUSIP to ticker with OpenFIGI. I only count tickers that are in the screener universe and have a price.
- Prices and universe: those of the screener backtest (US, above $1bn at the end of the month before formation). It carries the same survivorship bias as the rest of the lab.

## Which managers count (decided every quarter, using only information available then)

1. Total 13F value between $200mm and $50bn.
2. Between 10 and 50 equity positions.
3. The top 10 add up to at least 50% of the value.
4. Patient: at least 60% of current value is in stocks they already held in their 13F four quarters earlier.

## Portfolio

- For each selected manager, their 5 largest positions are their "best ideas".
- Each stock's score is the number of selected managers that have it in their top 5. Ties are broken by the sum of their weights.
- I buy the 20 highest-scoring stocks in the universe, in equal weights.
- The portfolio is formed on day 46 after each quarter end. I enter at the close of the first trading day from that date and hold to the next formation, without rebalancing.
- I compare against the equal-weighted universe formed and held the same way (same dates, no rebalancing within the quarter) and against SPY.
- Costs: 10 bp per side on turnover. As a sensitivity, an extra 0.5% per side, which is what a retail broker typically charges a euro account to convert into dollars.

## Periods

- Development: formations from November 2014 to November 2023. The first needs the Q3 2013 13Fs to measure patience, and uses Q3 2014.
- Hold-out: formations from February 2024, with the 13Fs from Q4 2023 onwards, to the last one with returns. I don't look at it until development is closed.

## What counts as "it works"

All at once:

1. In development, the net excess (10 bp) over the equal-weighted universe is > 0, with a Newey-West t (3 lags, monthly returns) > 2.
2. In the hold-out, that net excess is > 0.
3. In development, the net portfolio also beats SPY. If it doesn't beat what I already hold (a global index), it's no use to me even if it beats the equal-weighted universe.

If all three aren't met, I don't use it. Whatever I look at on the side (number of managers, top 10 versus top 20, subperiods, the 0.5% sensitivity) is descriptive.

## What I expect

That it looks a lot like a portfolio of large tech and quality names, because that's what concentrated managers tend to hold. And that it beats the equal-weighted universe but not SPY, or beats neither with a t-stat that means anything.

## Changes after writing this

31 Oct 2026: development fails (+0.09%/yr over the universe, t 0.02; −0.52% against SPY). I don't open the hold-out, as in the profitability filter. The 13F parquet takes 1.4 GB, not the few hundred MB I estimated.
