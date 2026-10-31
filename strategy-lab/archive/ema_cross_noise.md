# EMA Cross (MCP native strategy #4)

**Status: archived before 2026-07-14. Evidence rebuilt on 2026-10-11: over 20 years and six
assets, its timing is not distinguishable from random.**

The original analysis is not on disk. What survives is a comment in
`signal_lab/indicators.py`: "100% win rate en solo 3 trades en el backtest
real = ruido, no edge confirmado". The evidence below was rebuilt with
`evidence/technical_rules.py`.

## Thesis

The MCP's "EMA 20/50 Golden/Death Cross": long while the 20-day EMA is above
the 50-day EMA, flat otherwise. It is a slow trend-following rule that aims
to sit through rises and step aside in falls.

## What happened

The rule was archived after a backtest of three trades, all winners. That
sample says nothing: three fair coin flips all come up heads one time in
eight.

The rebuilt test replicates the MCP's rule exactly: it reproduces 5 of the
6 NVDA trades in the MCP's own log, and the sixth differs only because the
MCP starts its averages in October 2024. It runs from June 2006 to
October 2026 on SPY, QQQ, NVDA, GDX, GLD and XLE, net of 0.15% per side.

**The benchmark is the right null for a timing rule.** For each asset,
1,000 strategies take the rule's own holding periods and waiting periods,
shuffled to random dates: same number of trades, same time in the market,
same costs, random timing.

| Asset | Trades / year | Time in market | Sharpe | Random-timing median | p | Buy-and-hold Sharpe |
|---|---|---|---|---|---|---|
| SPY | 1.8 | 76% | 0.75 | 0.53 | 0.05 | 0.65 |
| QQQ | 2.3 | 74% | 0.58 | 0.66 | 0.79 | 0.80 |
| NVDA | 2.3 | 69% | 0.80 | 0.72 | 0.32 | 0.89 |
| GDX | 2.8 | 51% | 0.08 | 0.22 | 0.84 | 0.33 |
| GLD | 2.4 | 60% | 0.41 | 0.42 | 0.52 | 0.58 |
| XLE | 2.4 | 62% | 0.15 | 0.29 | 0.85 | 0.39 |

The rule beats its random-timing median in 2 of 6 assets. It is
significant in none (SPY sits exactly at p = 0.05, one test in six), and it
beats buy-and-hold only on SPY. Whatever it earns comes from being in the
market most of the time, not from when it enters or leaves.

## Lessons learned

- **Three trades are not a sample.** A 100% win rate on three trades was
  the right reason to distrust the rule, but not enough to judge it.
  Twenty years and six assets were.
- **Test a timing rule against random timing with the same exposure, not
  against zero.** A rule that is long 70% of the time inherits 70% of the
  market's return. Only the comparison with random dates isolates the
  timing.
- **The EMA family is one signal, not several.** The lab's TRIPLE_EMA
  (EMA20/50 filtered by SMA200) agrees with this rule on 82% of days, and
  the zero-line MACD (EMA12/26) on 86%. Their returns correlate 0.83–0.85.
  Counting them as separate strategies overstated the lab's
  diversification (see `macd_redundancy.md`).
- **Slow trend rules work better as risk control on a diversified basket
  than as timing on a single asset.** The trend test of October 2026
  (`trend_following/README.md`) found the same: drawdowns halved on a
  commodity basket, no reliable gain on one or two assets.

## Evidence

| File | Content |
|---|---|
| `archive/evidence/technical_rules.py` | Replication against the MCP, random-timing test, redundancy |
| `signal_lab/indicators.py` | The original comment ("100% win rate in only 3 trades = noise") |
