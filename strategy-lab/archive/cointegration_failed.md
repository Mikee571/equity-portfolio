# 2b. Statistical Arbitrage, systematic version (cointegrated pairs)

**Status: archived 2026-10-07. Result: loses money after costs in a
2012–2026 walk-forward. A Kalman hedge ratio and Ornstein-Uhlenbeck bands do
not fix it.**

The daily alert task (`Stat Arb Telegram Alerts`) was retired the same day.
Code and evidence stay in `stat_arb/` (see *Evidence* below). The
discretionary paper-trading version of the strategy is documented in
`theoretical/strategies/2_statistical_arbitrage.md`.

## Thesis

Find pairs whose log-prices are cointegrated. Trade the spread when it
stretches (|z| >= 1.5 on a 30-day rolling z-score) and close it when it
reverts (|z| <= 0.5). A pair counts as tradable only if both Engle-Granger
and Johansen confirm cointegration on two years of daily data, and its
half-life of mean reversion is 3 to 60 days.

## What happened

- **Week 1.** The three pairs chosen on thesis all failed the two-stage
  test: GDXJ/GDX (EG p = 0.108, Johansen 13.1 < 15.5), LMT/RHM.DE
  (p = 0.648) and XOM/AAL (p = 0.890).
- **Week 4.** A scan of every combination inside the lab's four sectors
  (37 pairs) found two that passed: GDXJ/KGC (half-life 16.2 days) and
  AEM/GLD (13.2 days). They went into the daily alert script.
- **Live, from 2026-06-21.**
  - GDXJ/KGC tested as cointegrated only on the runs of 21–22 June. It was
    ambiguous from 3 July and not cointegrated from 7 August.
  - AEM/GLD was cointegrated on 5 runs up to 9 August, ambiguous through
    August, and not cointegrated from 31 August.
  - The alert condition (cointegrated and |z| >= 1.5) was met on four days:
    AEM/GLD on 22 June and on 7–9 August, with z ≈ 2.25. The August signals
    came while the relationship was dissolving.
  - No alert was ever delivered: Telegram ran in dry-run mode until
    2026-10-06.
- **October 2026.** A walk-forward backtest asked whether the method had
  ever worked, and whether the two methods from
  cantaro86/Financial-Models-Numerical-Methods could improve it: a Kalman
  hedge ratio (notebook 5.1) and Ornstein-Uhlenbeck bands (notebook 6.1).
  - **Design, fixed before seeing results.** Every quarter, pairs were
    selected with the lab's own rule on the previous two years and traded
    for the next 63 days.
  - **Costs.** 0.15% per side per leg, plus 0.5% a year to borrow the short
    leg.
  - **Capital.** Committed capital: each selected pair gets an equal share,
    traded or not.

| Strategy | Return / yr | Sharpe [90% CI] | Trades | Sharpe before costs |
|---|---|---|---|---|
| Current method (fixed OLS beta, 30-day z) | −1.9% | −0.37 [−0.76, 0.02] | 294 | 0.16 |
| Kalman beta, calibrated as in notebook 5.1 | +0.3% | 0.24 [−0.07, 0.56] | 27 | 0.43 |
| OU bands (notebook 6.1) | −0.4% | −0.07 [−0.47, 0.34] | 134 | 0.15 |
| Kalman beta, joint MLE (added afterwards) | −3.7% | −1.30 [−1.69, −0.92] | 449 | 0.16 |
| Current method without the cointegration filter | −4.4% | −1.02 [−1.49, −0.64] | 6,282 | −0.14 |

The pre-registered criteria had two parts:

- An alternative replaces the current method only if it beats it with
  t > 2. Kalman reached t = 1.8, OU t = 1.0, and the joint-MLE Kalman
  t = −1.3.
- Stat arb stays live only if the lower bound of its net Sharpe's 90% CI is
  above 0.

Nothing met either.

## Lessons learned

- **Scanning finds pairs by chance.** At p < 0.05, 37 candidate pairs
  produce about two false positives under the null of no cointegration.
  Requiring Johansen as well does not change this much, because the two
  tests largely agree. The Week 4 scan found exactly two, and neither
  stayed cointegrated for long. A scan needs a multiple-testing correction
  (Benjamini-Hochberg, or a hold-out period) before any pair is believed.
- **Two years of daily data hold few reversion cycles.** With a 15-day
  half-life, that is about 30 half-lives. Cointegration tests have little
  power on that much data, and their verdict flips as the window rolls.
  GDXJ/KGC went from cointegrated to ambiguous in eleven days.
- **The signal is strongest when the relationship is breaking.** A spread
  that drifts away for good produces a large z-score for weeks. AEM/GLD sat
  above z = 2 for most of August while it lost cointegration. In the
  backtest, 59% of trades won but the average trade lost: many small gains,
  and a few large losses when a pair broke.
- **The gross edge was smaller than the costs.** Before costs, the method
  earned about 0.8% a year with a Sharpe of 0.16, indistinguishable from
  zero. Roughly 20 round trips a year at 0.3% each turned that into −1.9%.
- **A Kalman hedge ratio cannot rescue a pair.** The notebook's calibration
  (measurement noise = OLS residual) assumes regression noise. In a pair,
  the OLS residual is the spread itself, ~2.5 times wider than the real
  noise. The innovations' standard deviation was 0.41 instead of 1, so the
  filter almost never traded. Calibrated properly by joint MLE, the
  innovations become white noise by construction: trading them is trading
  noise, 449 trades of a day and a half each, and the worst result of the
  five. Any adaptive hedge ratio can make a spread look stationary;
  stationarity bought that way is not an edge.
- **Market-neutral is not commodity-neutral.** This was already the
  paper-trading lesson. Gold miners carry operating leverage to gold, so
  miner/gold and junior/senior relationships drift whenever gold trends.
  Both live pairs broke during the 2026 gold move.

## What would justify reopening it

- **A pair with an economic reason to converge** (a merger spread, a share
  class arbitrage, an ETF against its basket), not a statistical scan.
- **If scanning, a much larger universe** with multiple-testing control,
  and a hold-out period the scan never saw.
- **The same walk-forward test passed after costs** (`backtest_walkforward.py`),
  with the criterion written down before running it.

## Evidence

| File | Content |
|---|---|
| `stat_arb/backtest_walkforward.py` | The walk-forward test. Rerun with `python stat_arb/backtest_walkforward.py` |
| `stat_arb/kalman_ou.py` | Kalman hedge ratio and OU fit (cantaro86 notebooks 5.1 and 6.1) |
| `stat_arb/README.md` | Results and their reading, in more detail |
| `stat_arb/data/walkforward_results.csv` | Daily net returns of every variant |
| `logs/stat_arb_*.log` | Live runs, 2026-06-21 → 2026-10-07 |
| `tests/test_stat_arb.py` | Kalman, OU, and no-look-ahead accounting tests |
