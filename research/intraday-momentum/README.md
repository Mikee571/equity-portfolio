# Beat the Market: SPY intraday momentum after publication

30 October 2026. Zarattini, Aziz and Barbon published "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)" (SFI 24-97) in May 2024. With data from 2007 to April 2024 they report 19.6% a year net and a Sharpe of 1.33. I wanted to know what has happened since it was published, which is exactly the period the authors couldn't look at when they designed it.

I copied the paper's rules without touching any parameter, and the design was written in the docstring of `btm.py` before running it. Each day the strategy defines a noise zone around the open using the average move over the previous 14 days at that same time of day. If the price leaves the zone, it enters in the direction of the move. It exits on a stop at the band or at VWAP, and closes everything at the end of the day. Position size targets 2% daily volatility with a 4x cap. Costs are the paper's: $0.0035 commission and $0.001 slippage per share.

## Data: first hourly bars, then 1-minute bars

The first version used 1-hour bars from yfinance, the only free option since December 2023, and checked the position every hour. It followed the original's direction (0.86 monthly correlation with what the authors publish), but it lost return. From May to December 2024 they had +16.9% and I had +1.7%.

Then I downloaded 1-minute SPY bars from Alpaca from January 2016 (SIP feed, free account, `fetch_alpaca.py`). `run_1min.py` builds 30-minute bars, computes VWAP minute by minute and checks every 30 minutes, as in the paper. The rules are the same as in `btm.py`.

To validate it, I compared month by month with the table the authors publish (FAQ Q24 of the paper):

| Period | Months | Monthly correlation | My mean | Authors' mean |
|---|---|---|---|---|
| 2016–2023 | 96 | 0.99 | +1.49% | +1.55% |
| Jan 2024 to Aug 2025 | 20 | 0.98 (hourly: 0.86) | +1.49% | +1.54% |

So the replica is practically the same strategy. By year the difference is 1 to 3 points (for example 2018: +59.2% against +60.9%). The gap in my first version came from the hourly data, not from the rules.

## Results (1-minute bars, checked every 30 minutes)

| Period | Strategy | With 1 bp per side | SPY |
|---|---|---|---|
| 2016 – Apr 2024, inside the paper's sample | +19.0% a year, Sharpe 1.27 | +5.0% a year, Sharpe 0.40 | +14.4% a year, Sharpe 0.83 |
| May–Dec 2024 | +17.2% (authors +16.9%) | +8.1% | +17.9% |
| 2025 | −1.8% | −12.4% | +17.7% |
| 2026 to 29 Oct | −11.1% | −20.8% | +13.7% |
| All post-publication (May 2024 – Oct 2026) | +2.2%, +0.9% a year, Sharpe 0.13 | −25.0% | +57.8% |

The 90% interval for the post-publication Sharpe runs from −0.68 to 1.08 (block bootstrap with 21-day blocks). Since September 2025, the stretch the authors no longer report, the strategy has lost 14.6% while SPY gained 20.9%. In 2026, 7 of 10 months are negative.

## What I take from it

This changes what I had written with the hourly version. That "−6.1% a year after publication" was wrong because of the data. With 1-minute data the strategy worked well for the eight months after publication, as the authors say, and since 2025 it has stopped making money. In total, since publication, it's flat (+0.9% a year) while SPY is up 20% a year.

Two and a half years isn't enough to say it's dead: the Sharpe interval still includes values close to 1, and its own history already had two bad years in a row (2016 and 2017, −15% and −10% in my replica). What can be said is that the post-publication period doesn't look like the one before, and that 2025–26 is its worst run since 2016–17.

For me it still isn't tradable. At 1 bp per side, roughly what a retail CFD on the S&P 500 costs, even inside the paper's sample the strategy returns less than SPY (+5.0% against +14.4% a year), and after publication it loses 25%. It also uses 2.7x average leverage and needs someone in front of the screen for the whole US session.

## Files

- `btm.py`: rules, the hourly version, validation and a 30- against 60-minute test. `python btm.py`
- `fetch_alpaca.py`: 1-minute SPY bars since 2016. Needs `ALPACA_KEY_ID` and `ALPACA_SECRET_KEY` in `.env` (not in the repo).
- `run_1min.py`: the 1-minute version, validation against the authors' monthly table since 2016, years and periods. `python run_1min.py`
- `test_btm.py`: 8 offline tests of the bands, the gap adjustment, the stops, the costs and that no same-day information is used. `python -m unittest test_btm -v`
- `data/`: daily returns of both versions (`btm_daily_1h.csv`, `btm_daily_30m_alpaca.csv`). The bars and the Alpaca parquet (~34 MB) aren't in the repo.
