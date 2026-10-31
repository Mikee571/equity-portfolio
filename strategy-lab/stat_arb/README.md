# Stat arb: cointegrated pairs

Archived on 2026-10-07. The walk-forward backtest below loses money after costs, and neither a Kalman filter nor OU bands fix it. Lessons are in [`../archive/cointegration_failed.md`](../archive/cointegration_failed.md). I keep the code as evidence.

This was the systematic version of strategy #2 in my paper-trading lab. `stat_arb_pairs.py` tests each configured pair with Engle-Granger and Johansen on two years of log prices, estimates the hedge ratio by OLS and builds a 30-day rolling z-score. It enters at |z| ≥ 1.5 and exits at |z| ≤ 0.5. `pair_scanner.py` searches for pairs across four sectors (37 combinations), and `telegram_alerts.py` used to send me a morning alert when a cointegrated pair crossed the threshold.

## Walk-forward backtest, 2012–2026: do Kalman or OU help?

`backtest_walkforward.py` answers two questions: does the current method make money out of sample after costs, and do the two methods from cantaro86/Financial-Models-Numerical-Methods (`kalman_ou.py`) improve it? I fixed the design before looking at any result; the script's docstring has the details.

- Every quarter I select pairs with the lab's rule on the previous two years (EG + Johansen, half-life between 3 and 60 days, positive beta) and trade them for the next 63 days.
- Costs: 0.15% per side per leg, which also covers Kalman's daily re-hedging, plus 0.5% a year to borrow the short leg.
- Each selected pair gets 1/N of the capital even if it never opens a position.
- Pass criteria, written down beforehand: a variant replaces the current method only if its net return beats it with t > 2, and stat arb deserves to stay live only if the lower end of the 90% CI of its net Sharpe is above zero.

Net results, January 2012 to October 2026 (3,712 sessions; on average 1.6 pairs selected per quarter, none in 29% of quarters):

| Strategy | Return/yr | Sharpe [90% CI] | Max DD | Trades | Avg days | Gross Sharpe |
|---|---|---|---|---|---|---|
| STATIC_Z (current) | −1.9% | −0.37 [−0.76, 0.02] | −32% | 294 | 11 | 0.16 [−0.25, 0.57] |
| KALMAN_Z (notebook 5.1 recipe) | +0.3% | 0.24 [−0.07, 0.56] | −3% | 27 | 6 | 0.43 [0.10, 0.77] |
| STATIC_OU (notebook 6.1 bands) | −0.4% | −0.07 [−0.47, 0.34] | −19% | 134 | 30 | 0.15 [−0.26, 0.56] |
| KALMAN_Z_MLE (added later, see below) | −3.7% | −1.30 [−1.69, −0.92] | −43% | 449 | 1.5 | 0.16 [−0.23, 0.53] |
| STATIC_Z with no selection (all 37 pairs) | −4.4% | −1.02 [−1.49, −0.64] | −49% | 6,282 | 11 | −0.14 [−0.54, 0.27] |

Against STATIC_Z, the net return difference is +2.2% a year for KALMAN_Z (t = 1.8), +1.5% for STATIC_OU (t = 1.0) and −1.8% for KALMAN_Z_MLE (t = −1.3). Nothing meets either criterion.

How I read each row:

- The current method has a small gross edge (0.8% a year, with a Sharpe CI that includes zero), and costs turn it into a loss in 12 of 15 years. 59% of trades win, but the average is negative: lots of small gains and a few big losses when the cointegration breaks. Selecting by cointegration does help, since without it the loss doubles, but not enough.
- KALMAN_Z, calibrated the way the notebook does it, barely trades. It sets the measurement noise to the OLS residual, but for a pair that residual *is* the spread: persistent and about 2.5 times wider than the real measurement noise. So the normalised innovation has a standard deviation of 0.41 instead of 1, |z| ≥ 1.5 means roughly 3.6 sigmas, and there are only 27 trades in 15 years. Its gross Sharpe CI excludes zero, but 27 trades and +0.3% a year net is not something I could trade.
- KALMAN_Z_MLE fixes that calibration by estimating both noise terms jointly by maximum likelihood, so z has a standard deviation of 1.00 in the formation window. I added it after the first backtest. The diagnosis came from the formation data, not from returns, but it is still a post-design variant. The result is 449 trades of 1.5 days each and the worst net number. This is the well-known Kalman trap in pairs trading: if the beta adapts enough for the model to be well specified, the innovations are white noise by construction, so you end up trading noise and paying costs on it.
- The OU bands trade less and hold longer (30 days on average). They do slightly better than the current method, but not distinguishably from luck.

## Limitations

- Small sample: 19 tickers, 37 pairs, 1.6 active pairs per quarter. A wider universe would add power, and also more chances of finding pairs by accident.
- Pairs are selected quarterly. The live script re-tested daily, but the formation beta barely moves in 63 days.
- Retail-broker costs. They could be lower on very liquid ETFs, but even with zero costs only KALMAN_Z (27 trades) has a gross Sharpe CI above zero.

```
python backtest_walkforward.py   # several minutes; downloads prices to data/walkforward_prices.csv
```

Tests (offline), from `strategy-lab/`: `python -m unittest discover tests -v`.
