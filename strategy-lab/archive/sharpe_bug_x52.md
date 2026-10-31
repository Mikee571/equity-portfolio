# The Sharpe ratio bug in tradingview-mcp-server

**Status: documented. Corrected in `shared/corrected_sharpe.py`. Still
present in the MCP server on 2026-10-11.**

The original analysis that named this file (the ×52) is not on disk. The
bug itself is described in `shared/corrected_sharpe.py`, and it was
reproduced on 2026-10-11 with the MCP's own trade logs
(`evidence/sharpe_bug.py`).

## The bug

The MCP's `backtest_strategy` computes the Sharpe ratio from per-trade
returns, but annualises it with the number of candles per year (252 daily,
1,512 hourly):

```
sharpe = (mean(trade returns) - 0.04 / candles_per_year) / stdev(trade returns) * sqrt(candles_per_year)
```

Per-trade statistics have to be annualised by trades per year. Two things
go wrong at once:

1. **The magnitude is inflated** by √(candles per year ÷ trades per year).
2. **The risk-free hurdle shrinks** by the same ratio. Each trade is charged
   4% ÷ 252 instead of 4% ÷ trades per year, so a strategy that earns less
   than cash per trade can still show a positive Sharpe.

## Reproduced on 2026-10-11

| Run | Reported by the MCP | Formula above | Corrected | Trades / year | Distortion |
|---|---|---|---|---|---|
| NVDA, ema_cross, 2y, daily | −0.77 | −0.77 | −0.21 | 3.0 | 9.2× |
| NVDA, macd, 2y, daily | −1.30 | −1.30 | −0.37 | 9.5 | 5.2× |
| SPY, ema_cross, 1y, hourly | **+0.53** | +0.53 | **−0.24** | 15.0 | 10.0× |

The formula reproduces the reported figure to the second decimal in all
three runs. The hourly SPY run shows the worse half of the bug: a strategy
that loses to cash is reported with a positive Sharpe.

**Where a factor of 52 comes from.** The distortion is √(candles ÷ trades),
so in Sharpe terms a factor of 52 needs about 0.56 trades a year on hourly
data: about one trade in a two-year backtest, which happens with slow
rules. If the 52 recorded the ratio of candles to trades instead, the
Sharpe distortion was √52 ≈ 7.2×, within the range measured here. Which
of the two the original measured is not recorded.

## Lessons learned

- **Reproduce a metric's formula before ranking anything with it.** Any
  comparison built on these figures mixes strategies distorted by 5× with
  others distorted by 10×.
- **The annualisation must match the frequency of the returns being
  measured,** not the frequency of the data they came from.
- **A wrong hurdle can flip the sign,** which is worse than inflating the
  size. A strategy that loses to cash should never look profitable.
- **Even the corrected figure is not the right comparison.** A per-trade
  Sharpe ignores the time spent out of the market. The lab's later tests
  (`stat_arb/backtest_walkforward.py`, `trend_following/backtest_trend.py`,
  `evidence/technical_rules.py`) compute Sharpe on daily or monthly
  portfolio returns, with cash earning the bill rate when flat. Only that
  figure is comparable to buy-and-hold.

## Evidence

| File | Content |
|---|---|
| `shared/corrected_sharpe.py` | Description of the bug and the corrected per-trade Sharpe |
| `archive/evidence/sharpe_bug.py` | Reproduction of the three MCP runs above |
