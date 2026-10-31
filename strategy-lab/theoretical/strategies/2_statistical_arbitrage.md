# 2. Statistical Arbitrage

**Result (12 Apr – 14 May 2026): +14.7%**

## Thesis

Market-neutral pairs trading: identify two correlated assets whose price
ratio has diverged for reasons unrelated to fundamentals, go long the
relatively cheap leg and short the relatively expensive leg, and profit when
the ratio reverts — independent of overall market direction.

## Key positions

| Pair | Direction | Divergence thesis |
|---|---|---|
| AMD / NVDA | Long AMD, Short NVDA | NVDA +420% vs AMD +70% over 18 months — ratio historically compressed |
| GDX / GLD | Long GDX, Short GLD | Gold miners trading at a discount to physical gold (P/E ~10.85x) |
| GDXJ / GDX | Long GDXJ, Short GDX | Junior miners at historical lows vs seniors despite higher operating leverage to gold price |
| IAG (or Ryanair) / Delta | Long European carrier, Short Delta | European carriers more exposed to jet fuel costs; asymmetric benefit if Hormuz reopens |

## What happened

The AMD/NVDA pair worked as intended: NVDA's earnings-day move created a
temporary divergence that the pair captured. The airline pair (IAG/Delta)
also worked, benefiting from a relative improvement in fuel-cost exposure as
oil eased. The two gold-miner pairs (GDX/GLD and GDXJ/GDX) moved against the
position — gold's broader decline hit both legs in the same direction rather
than converging, the opposite of what a market-neutral pair is supposed to do.

## Lessons learned

- **"Market neutral" is not the same as "commodity neutral."** Both
  gold-miner pairs were neutral to the broader market but still had shared
  directional exposure to the price of gold itself. A genuine pairs trade
  needs the *shared* risk factor identified and hedged, not assumed away.
- **The pairs that worked had a real, named catalyst** (NVDA earnings, a fuel
  cost differential) rather than just a statistically stretched ratio. A
  cheap/expensive ratio alone is not a thesis — there has to be a reason the
  ratio reverts within the time horizon.
- **The result (+14.7%) nearly matched the S&P 500 (+14.0%) with much less
  directional risk** — but this was partly because the period's shock (an
  active war, then a ceasefire) created unusually large temporary
  dislocations between correlated assets. That magnitude of opportunity is
  not the steady-state condition for this strategy.

## Later: the systematic version (archived 2026-10-07)

The lab then built a systematic version of this strategy: cointegrated
pairs, daily z-score alerts. It was tested in a 2012–2026 walk-forward and
lost 1.9% a year after costs. A Kalman hedge ratio and Ornstein-Uhlenbeck
bands did not fix it, and it was archived. See
`archive/cointegration_failed.md`. That result is consistent with the second
lesson above: the pairs that worked here had a named catalyst, not just a
stretched ratio.
