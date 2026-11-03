# Pre-registration: post-earnings announcement drift (PEAD)

Written on 30 October 2026, before building the signal or looking at any returns. If I change anything later, I note it at the end with the date and the reason, and the version here stays the main one.

## Question

After earnings are published, do the stocks with the biggest positive surprise keep rising more than the rest over the next ~3 months, and do the biggest negative surprises keep falling? And if so, is there anything left that I can capture by only buying, after costs?

## Data

- Universe: the 2,609 US companies in the screener backtest (`equity-screener/data/backtest`), with adjusted daily prices from 2010 to October 2026. These are companies listed today, so there's survivorship bias. It mainly affects the negative-surprise leg (companies that later went bust), and I'll keep that in mind when reading that leg.
- Quarterly earnings: `NetIncomeLoss` from XBRL (`sql-analysis/sec.duckdb`). I use the first value filed for each quarter, never the revised one. The fourth quarter is the annual figure minus the nine-month year-to-date, both taken from their first filing.
- Announcement date: the first 8-K with item 2.02 (results) filed between the quarter end and the 10-Q/10-K filing, from `data.sec.gov/submissions`. If there isn't one, I use the 10-Q/10-K date and report that group separately.

## Signal

SUE = (NI_q − NI_{q−4}) / standard deviation of (NI_k − NI_{k−4}) over the previous 8 quarters (k = q−1 … q−8). I require at least 6. It's the seasonal random-walk model from the classic literature, with no analyst estimates.

SUE deciles use the cut-offs from the previous calendar quarter's events, so no information from the same quarter is used.

## Returns

- Day 0 is the announcement date. Many 8-Ks are filed after the close, so the reaction to the announcement is the window [0, 1].
- The drift is the window [2, 61] in trading days, about three months. This means entering at the close of day 1, which a retail investor can do.
- Abnormal return: the stock's return minus the equal-weighted average of the whole universe that day.

## Main test

A calendar-time portfolio. Each day I hold, in equal weights, the decile-10 stocks that are inside their [2, 61] window, and separately the decile-1 stocks. I compound daily returns to monthly and compute the t-stat with Newey-West, 3 lags.

- Development: announcements from 1 January 2012 to 31 December 2023.
- Hold-out: announcements from 1 January 2024 to the last one with 61 days of prices. I don't look at it until development is closed.

## What counts as "it works"

All four at once:

1. In development, decile 10 − decile 1 has a positive monthly mean with t > 2.
2. In development, decile 10 − universe > 0 net of costs (10 bp per side on turnover, as in the rest of the lab).
3. In the hold-out, decile 10 − decile 1 > 0 with t > 1.65 (one-sided, 5%).
4. In the hold-out, decile 10 − universe net > 0.

If any of them fails, the conclusion is "not implementable". Whatever I look at on the side (size terciles, 8-K versus 10-Q date, the [0, 1] reaction, subperiods) is descriptive and doesn't change the verdict.

## What I expect

The same as the recent literature: some drift, more in small caps and in negative surprises, and little or none in my universe of mid and large caps, especially since 2018. I write it down so the opposite doesn't surprise me for no reason.

## Changes after writing this

30 Oct 2026, after seeing development: I change nothing. I note that condition 2 should have asked for significance; as written, +0.8% with t 0.4 meets it. I open the hold-out anyway, as planned.
