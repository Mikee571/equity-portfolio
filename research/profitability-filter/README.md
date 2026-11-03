# Cash profitability filter

30 October 2026. Operating profitability was the only lead that showed up in three different places: the [OSAP scan](../osap-scan), the low leg in the [OSAP check](../osap-check) and my [Fama-French regressions](../factor-models). So I tried using it to exclude rather than to pick: drop the 20% of the universe with the lowest operating cash flow over assets. The rules are in [`PREREGISTRATION.md`](PREREGISTRATION.md), written before computing the signal. I chose cash profitability precisely because I had already looked at gross profitability.

## Development result (Feb 2012 to Dec 2023, 143 months, net of costs)

| | Excess over the universe | t | Tracking error |
|---|---|---|---|
| Universe without the bottom quintile | +0.43%/yr | 0.77 | 1.8% |
| The bottom quintile on its own | −1.92%/yr | −0.86 | 7.2% |
| Screener top 10 with the filter | +3.63%/yr | 1.00 | 12.3% |
| Screener top 10 without the filter | +3.66%/yr | 1.02 | 11.8% |

Neither development condition is met: I asked for t > 2 on the improvement and t < −2 on the bottom quintile. The direction is the expected one (the bottom quintile returns 9.9% a year against 13.0% for the universe), but the noise is bigger than the effect. Almost all of it comes from 2020–23. In 2012–16 and 2016–20 the difference is practically zero.

In the screener the filter changes nothing (−0.03% a year). The top 10 almost never includes companies from the bottom cash-profitability quintile, because ROE and the other factors already keep them out.

## What I do with it

I'm not using it. I don't open the 2024–26 hold-out either: since development fails there's nothing to confirm, and I'd rather keep those months unseen in case I ever test something else with this signal.

This fits the OSAP scan: the profitability family has t-stats of 2 to 2.7 in CRSP portfolios with hundreds of names, and in my universe of survivors above $1bn it stays at t 0.8. If the effect exists, it's too small for my data, and the screener already picks it up through ROE.

`python run_filter.py` reproduces development. `run_filter.py --holdout` is written but I haven't run it.
