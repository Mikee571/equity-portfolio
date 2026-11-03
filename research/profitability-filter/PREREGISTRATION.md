# Pre-registration: cash profitability filter

Written on 30 October 2026, before computing the signal. If I change anything later, I note it at the end with the date and the reason.

## Where it comes from

In the scan of 207 OSAP signals ([`osap-scan`](../osap-scan)), the only family that holds up in mid and large caps since 2015 is operating profitability. In the [OSAP check](../osap-check), the only thing my data and CRSP agreed on was that companies with the lowest gross profit do worse than average. The idea is to use it to exclude, not to pick: remove the least profitable companies from the universe.

Contamination warning: I've already looked at gross profit over assets in my data up to 2026, so it can't be a clean test. I use a signal I've never computed: cash profitability.

## Signal

Cash profitability = trailing 12-month operating cash flow / total assets, using the last figure published before each month end (`cfo` and `assets` from the XBRL snapshots, with their `known` and `known_quality` dates). It's the "cash" part of the measure in Ball, Gerakos, Linnainmaa and Nikolaev (2016). I don't have SG&A or working-capital items in XBRL, so I can't reproduce their exact definition.

Each month I rank the universe companies that have the signal and flag the bottom quintile.

## Universe and portfolios

The same universe as the screener backtest: US companies above $1bn at each month end, rebalanced monthly, with 10 bp per side on turnover.

1. Main test: the equal-weighted universe without the bottom quintile, against the full equal-weighted universe.
2. Secondary test: the screener top 10 chosen only from companies outside the bottom quintile, against the current top 10.

## Periods

- Development: February 2012 to December 2023.
- Hold-out: January 2024 to the last month with returns. I don't look at it until development is closed.

## What counts as "it works"

For the main test, all at once:

1. In development, the net excess over the universe is > 0 with a Newey-West t (3 lags) > 2.
2. In the hold-out, the net excess is > 0.
3. The bottom quintile on its own underperforms the universe in development, with t < −2. That checks the improvement comes from what I remove.

The hold-out has about 33 months and doesn't have the power to produce a high t-stat. That's why I only ask it for the sign. I say so now so I don't reinterpret it later.

The secondary test is descriptive. With 10 names the noise is huge (I already saw t ≈ 1 in the screener) and it doesn't decide anything.

If it passes, I add it to the screener as an exclusion, without touching the weights. If it fails, I don't.

## What I expect

A small improvement, around +0.5–1% a year, because removing 20% of the universe that returns some 3–5 points less gives about that. The t-stat will probably be between 1.5 and 2.5. I'm not sure it passes.

## Changes after writing this

30 Oct 2026: development fails (t 0.77 and t −0.86). I decide not to open the hold-out, which the pre-registration didn't cover for this case: without an approved development there's nothing to confirm, and this way 2024–26 stays clean.
