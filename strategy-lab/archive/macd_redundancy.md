# MACD (MCP native strategy #3)

**Status: archived before 2026-07-14. Evidence rebuilt on 2026-10-11. The zero-line MACD repeats
the EMA trend signal, and in the lab's ML features it was an exact
duplicate. The crossover version the MCP trades is a different signal, but
it adds turnover, not edge.**

The original analysis is not on disk; the evidence below was rebuilt with
`evidence/technical_rules.py`.

## Thesis

MACD = EMA12 − EMA26; its signal line is a 9-day EMA of the MACD. The MCP's
"MACD Crossover" is long while the MACD is above its signal line. The idea
is to catch changes in momentum earlier than a plain moving-average cross.

## What happened

**1. An exact duplicate in the lab's own code.** Strategy #10 used the nine
lab strategies as features for its ML model. Two of those features were:

- `ema_cross_norm`, computed by `ema_cross_features(close, 12, 26)`
  as (EMA12 − EMA26) / close;
- `macd_hist`, computed from MACD(12, 26, 9).

The first is the MACD line divided by the price: the maximum difference
between the two series is 0.0. The "EMA cross" feature was MACD under
another name. The nine strategy-features were fewer than nine signals.

**2. The zero-line MACD is the EMA trend signal.** "MACD above zero" means
EMA12 above EMA26. Over 2006–2026 on SPY, QQQ, NVDA, GDX, GLD and XLE, it
agrees with the MCP's EMA20/50 cross on 86% of days, and their daily
returns correlate 0.85.

**3. The crossover MACD is different, but no better.**

- **A different signal.** The MCP's MACD Crossover (MACD vs signal line)
  agrees with the EMA cross on only 50% of days, with a return correlation
  of 0.45. It is a faster signal, and it trades ~10 times a year against
  ~2 for the EMA cross.
- **No edge.**
  - It never beats buy-and-hold on Sharpe on any of the six assets.
  - It beats its random-timing benchmark (same trades and time in the
    market, random dates) in 4 of 6, significant in none:

| Asset | Sharpe | Random-timing median | p | Buy-and-hold Sharpe |
|---|---|---|---|---|
| SPY | 0.29 | 0.24 | 0.35 | 0.65 |
| QQQ | 0.45 | 0.40 | 0.37 | 0.80 |
| NVDA | 0.44 | 0.57 | 0.79 | 0.89 |
| GDX | 0.23 | 0.14 | 0.27 | 0.33 |
| GLD | 0.34 | 0.21 | 0.19 | 0.58 |
| XLE | 0.13 | 0.15 | 0.55 | 0.39 |

The rule was replicated exactly: it reproduces all 5 recent NVDA trades in
the MCP's own trade log.

## Lessons learned

- **Check what a feature computes, not what it is called.** The duplicate
  sat in plain sight in `indicators.py` because the two functions had
  different names.
- **Count independent signals, not strategies.** The six MCP strategies
  and three custom ones are mostly price trend and price mean reversion.
  The EMA cross, the triple EMA and the zero-line MACD are one signal.
- **A faster version of a weak signal mostly adds costs.** The crossover
  MACD trades more than four times as often as the EMA cross and earns
  less than buy-and-hold on every asset tested.

## Evidence

| File | Content |
|---|---|
| `archive/evidence/technical_rules.py` | Feature identity, agreement and correlations, random-timing test |
| `signal_lab/indicators.py` | `macd()` and `ema_cross_features()`, the duplicated features |
