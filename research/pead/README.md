# Post-earnings announcement drift (PEAD)

October 2026. This is the first idea I tested with information that doesn't come from prices: how much earnings surprise. I wrote the rules down in [`PREREGISTRATION.md`](PREREGISTRATION.md) before building anything, and left 2024–26 unopened until the development part was closed.

## How I did it

- `build_sue.py` takes quarterly net income from my XBRL database ([`sql-analysis/sec.duckdb`](../../sql-analysis)), always using the first value filed. The fourth quarter is the annual figure minus the nine-month year-to-date. The surprise (SUE) is the change from the same quarter a year earlier, divided by the standard deviation of those changes over the previous 8 quarters. No analyst estimates.
- `fetch_filings.py` downloads the filing history of the ~2,600 companies in the screener universe from the SEC. That gives the real announcement date: the first 8-K with item 2.02 after the quarter ends. 91–93% of events have one; for the rest I use the 10-Q/10-K date.
- `run_pead.py` sorts events into SUE deciles using the previous quarter's cut-offs. It buys at the close of day 1 after the announcement and holds to day 61, and measures it as a calendar-time portfolio against the equal-weighted universe.

That's 64,884 announcements in development (2012–23) and 21,339 in the hold-out (2024 to July 2026).

## Results

The signal makes sense: the two-day reaction to the announcement rises steadily from −1.9% in decile 1 to +2.3% in decile 10. What matters is whether the price keeps moving afterwards.

| Pre-registered condition | Development 2012–23 | Hold-out 2024–26 | Pass? |
|---|---|---|---|
| 1. D10 − D1, t > 2 | +6.9%/yr, t 2.20 | | Yes |
| 2. D10 − universe, net > 0 | +0.8%/yr, t 0.39 | | Yes, barely |
| 3. D10 − D1, t > 1.65 | | +8.8%/yr, t 0.98 | No |
| 4. D10 − universe, net > 0 | | −0.8%/yr, t −0.20 | No |

It fails. In the hold-out the spread between deciles points the same way, but with 33 months it isn't significant, and the part I could actually buy gives nothing.

I wrote the second condition badly: it asked for "greater than zero" without asking for significance. +0.8% with a t of 0.4 isn't evidence of anything. I don't change it after the fact, but I don't count it as a result in favour either.

## Where the drift is

Almost all of the effect comes from two places I can't use.

The short side. Companies with the worst surprises do 5.1% a year worse than the universe in development (t −2.3) and 8.6% worse in the hold-out. Using that means shorting, and survivorship bias works in the effect's favour here: the companies that collapsed completely aren't in my data, so the real effect is probably stronger.

Microcaps. By size terciles, D10 − D1 over days [2, 61]:

| Tercile | Median market cap | Development | Hold-out |
|---|---|---|---|
| Small | ~$200mm | +4.7% | +3.3% |
| Mid | ~$1.7bn | +1.6% | +0.4% |
| Large | ~$14bn | +1.1% | +1.6% |

On the buy side, decile 10 of the small tercile beats the universe by 4.6% (development) and 4.2% (hold-out) over three months. In mid and large caps it's −0.4% to −1.9%: buying after a good surprise adds nothing. That's what the 2025 papers say too: the drift lives in microcaps.

By subperiod, the drift was bigger in 2018–23 (+11% a year in calendar time, t 2.1) than in 2012–17 (+2.4%, t 0.8). It looks more tied to 2020–22 than to a trend, and it doesn't hold up strongly in the hold-out.

## What I take from it

I'm not using it. What can be captured by buying the companies I can actually trade doesn't survive costs, in development or in the hold-out. The drift that does show up is in shorts and in $200mm companies, where real costs (spreads, market impact) are well above the 10 bp in the model.

As a method, this is the cleanest test I've done: rules written first, the real announcement date, point-in-time first-filed data and a hold-out I didn't look at. The result is negative, but the process is the part I'd want someone to look at.

To rerun it: `fetch_filings.py`, `build_sue.py`, `run_pead.py`, then `run_pead.py --holdout`. The SEC data (about 5,000 JSON files in `data/raw`) isn't in the repo.
