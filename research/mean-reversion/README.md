# Short-term mean reversion

October 2026. One-month reversal in single stocks gave nothing (see the momentum project), so here I looked at the few-day version on index ETFs, which is where it usually shows up. I used Connors' rules exactly as published in 2008, without tuning a single parameter. That makes everything from 2009 onwards a genuine out-of-sample test.

![RSI(2) decay](figures/rsi2_decay.png)

## What I tested (`short_term_mr.py`)

Three long-only rules:

- RSI(2) < 10 with price above the 200-day average; exit when it closes above the 5-day average.
- 5-day z-score < −1.5 with the same filter; exit when it gets back to 0.
- RSI(2) < 10 with no trend filter.

ETFs: SPY, QQQ, IWM, DIA, EFA and EEM from 1993 (or inception), plus VWRL.AS from 2014. The signal is computed at the close. I tried two fills: at that same close, which is optimistic, and at the next day's open, which is realistic and what the conclusions use. Costs are 5 bp per side.

To judge whether the average trade is any good I compare it with random entries of the same number and length. Otherwise a strategy that is only long during a bull market always looks good.

## What came out (`decay.py`)

Pooling the six ETFs with the filtered RSI(2) rule, the excess per trade over random entries went like this:

| Period | Trades | Excess per trade | approx. t |
|---|---|---|---|
| 1993–2000 | 94 | +0.80% | 3.4 |
| 2001–2008 | 275 | +0.35% | 3.3 |
| 2009–2017 | 434 | +0.28% | 3.3 |
| 2018–2026 | 422 | +0.12% | 1.3 |

The real t is a bit lower, because trades on different ETFs often fall on the same days.

So it worked, and it has faded more or less since it became popular. Over the last eight years I can't tell it apart from noise.

Other details (full table in `summary_open_fill.csv`):

- After 2009 the excess is positive in 16 of 19 combinations, but only SPY and QQQ reach p < 0.05.
- 60–70% of trades win, but the losers hurt: single trades of −8% to −16%, mostly without the 200-day filter.
- On VWRL.AS: +0.19% per trade, p = 0.17, about 7 trades a year.
- It's invested only about 10% of the time, so on its own it returns 1–3% a year, far below just staying invested.

## Conclusion

What's left (roughly 0.1% per trade × 7 trades a year) doesn't survive short-term capital gains tax or a couple of bad fills. I won't use it. At most it could help pick the day for a monthly contribution, and even then the effect would be tiny.
