# 10. ML Direction Signal (XGBoost)

**Status: archived 2026-10-07. Result: no predictive skill out of sample.**

The daily production run (scheduled task `Estrategia10_SignalDiaria`) was
retired the same day. Code and evidence stay in `signal_lab/` (see
*Evidence* below).

## Thesis

Predict whether an asset will rise more than 1% (1.5% for NVDA) over the
next 10 trading days. The features are built from the lab's nine technical
strategies plus news sentiment, so that a model learns how to combine the
rules instead of trading each one on its own. Universe: USDJPY=X, HG=F
(copper), GDX, NVDA. XGBoost and Random Forest, with ARIMA as the benchmark.

## What was built (June 2026)

- 15 technical features (RSI, Bollinger, MACD, Supertrend, Donchian, Keltner,
  triple EMA, RSI pullback, 1- and 5-day returns, 10-day volatility) and 4
  sentiment features (VADER on RSS headlines).
- Walk-forward validation on 2 years of data: expanding window, retrained
  every 21 days.
- Per-asset tuning: horizon × threshold (9 combinations), XGBoost
  hyperparameters (4 sets), sigmoid calibration on or off. About 15
  configurations per asset, chosen by F1 of the positive class.
- A daily production run that retrains on the last 2 years and logs one
  signal per asset. 195 signals between 2026-06-18 and 2026-10-07.

The June evaluation reported F1 gains in all four assets after tuning (GDX
0.47 → 0.74, USDJPY 0.22 → 0.32, NVDA 0.49 → 0.54, HG=F 0.51 → 0.54), and an
ARIMA benchmark that predicted "no rise" 100% of the time.

## What the October audit found

Three flaws in the evaluation, all in the model's favour:

1. **F1 had no baseline.** F1 of the positive class is maximised by a
   classifier that always says "up": its recall is 1 and its F1 is
   2p / (1 + p), about 0.67 when half the days are positive. The only
   benchmark, ARIMA, did the opposite (never "up", F1 = 0), so any model with
   some recall looked good next to it. In a replication with the tuned
   parameters (2 and 5 years, four assets), "always up" beat the model's F1
   in 8 cases out of 8.
2. **Leakage between train and test.** The target looks 10 days ahead and
   the walk-forward left no gap, so the last 10 training labels depended on
   prices inside the test window. Purging them lowered AUC by up to 0.06.
3. **Selection bias.** Each asset's configuration was picked on the same two
   years that were then reported.

The audit (`signal_lab/evaluate_strategy10.py`) replicates production over
10 years: rolling 2-year window, retrained every 21 days, a gap equal to the
horizon, and the tuned configuration. It then splits the predictions by what
the tuning saw. Nothing before June 2024 was seen by the grid search:

| Asset | AUC 2018 – Jun 2024 [90% CI] | AUC in tuning window | Brier skill score 2018–2024 | Sharpe signal / buy-and-hold 2018–2024 |
|---|---|---|---|---|
| USDJPY=X | 0.49 [0.44, 0.56] | 0.54 | −0.48 | −0.01 / 0.76 |
| HG=F | 0.52 [0.46, 0.57] | 0.44 | −0.04 | 0.46 / 0.49 |
| GDX | 0.45 [0.40, 0.50] | 0.52 | −0.15 | 0.06 / 0.49 |
| NVDA | 0.43 [0.39, 0.49] | 0.52 | −0.55 | 0.76 / 1.22 |

- **AUC** (0.5 = a coin flip): no confidence interval clears 0.5, not even
  inside the tuning window. GDX and NVDA score below 0.5 before 2024.
  Flipping the signal would be one more choice made after seeing the answer.
- **Brier skill score** against the up-move frequency known at training
  time: negative in every asset and period. The probabilities are worse than
  repeating the historical base rate.
- **Returns**: trading the signal long/flat, each entry held 10 days, 0.3%
  round-trip cost, gives a lower Sharpe ratio than buy-and-hold in all four
  assets.
- **Live** (signals resolved through 2026-09-23, about 40 per asset): AUC
  0.36–0.55, Brier skill score −0.19 to −1.45. That is too few independent
  observations to conclude anything alone, but nothing in it contradicts the
  backtest.

Production also differed from what had been validated:

- **Calibration was fitted on data the model had trained on.** In GDX and
  HG=F, 67–80% of live probabilities were below 0.1 or above 0.9, against
  11–24% in the uncalibrated assets.
- **Sentiment never reached the model.** RSS covers about 5 days, and those
  rows have no label yet with a 10-day horizon, so every training row had
  sentiment = 0.
- **Warm-up.** With a 2-year download and a 200-day moving average, the
  trend features were 0 in about 40% of the training rows.
- **Inflated equity curves.** The notebook v1 equity curve compounded the
  full 10-day return every day, counting each price move about 10 times.
  This is fixed in `ml_pipeline.simulate_equity_curve`.

## Lessons learned

- **Compare against both trivial classifiers before reading any metric.**
  "Always up" and "always down" bracket what a model with no information
  scores. A metric that one of them wins (F1 here, accuracy with imbalanced
  classes) means nothing on its own. AUC, which needs no threshold, and the
  Brier skill score against the base rate are much harder to fool.
- **"Accuracy fell while F1 rose, as expected" was the warning sign.** The
  June write-up read it as a better precision/recall balance. It was the
  model drifting towards always "up".
- **Overlapping labels need a gap.** With a target h days ahead, leave at
  least h rows between train and test, and between fitting and calibration.
- **Count independent observations, not rows.** Two consecutive days share 9
  of their 10 days of return. Two years of daily rows hold about 50
  independent outcomes, and confidence intervals have to reflect that
  (block bootstrap).
- **Tuning is a test too.** Fifteen configurations per asset, each judged on
  the period it was then reported on, guarantee an optimistic number. Keep
  data the tuning never touches, and record how many configurations were
  tried.
- **Production has to be the validated procedure, not something close to
  it.** A one-line difference in where calibration was fitted made the live
  probabilities useless.
- **A feature that is constant in training does nothing.** Sentiment was the
  only input carrying information beyond the price itself, and it never
  reached the model.
- **Write the promotion criterion so that a trivial model fails it.** The
  original one ("consistent accuracy/F1 for 3–6 months, reasonable recall")
  would have promoted a classifier that always says "up".
- **Recombining price-based rules did not create information.** Indicators
  computed from an asset's own price did not predict its 10-day direction in
  any of the four assets over six years. A non-linear model can only use
  information the rules already carry.

## What would justify reopening it

- A source of information not derived from the asset's own price (sentiment
  with real history, positioning, fundamentals), rather than another
  configuration of the same features.
- The configuration fixed before looking at results, then tested on data it
  never saw: `evaluate_strategy10.py`, `pre_seleccion` period, with the
  criteria in `evaluation.PROMOTION_CRITERIA`.

## Evidence

| File | Content |
|---|---|
| `signal_lab/evaluate_strategy10.py` | The audit. Rerun with `python signal_lab/evaluate_strategy10.py` |
| `signal_lab/data/strategy10_evaluation.csv` | Audit output of 2026-10-07 |
| `signal_lab/data/estrategia_10_signal_history.csv` | Live track record, 2026-06-18 → 2026-10-07 |
| `signal_lab/evaluation.py`, `tests/test_evaluation.py` | Metrics against trivial baselines, and tests for the purge |
| `README.md` | Original v1/v2 results as written, and the audit section |
| `signal_lab/*.ipynb` | Original June analysis, before the audit (v1 equity curves inflated) |
