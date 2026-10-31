# 3. Volatility Arbitrage

**Result (12 Apr – 14 May 2026): +5.3%**

## Thesis

Trade implied volatility rather than direction: be long volatility ahead of
binary events where a large price move is likely in either direction, and be
short volatility where the market is overpricing uncertainty in an otherwise
calm regime — collecting premium (carry) while it stays calm.

## Key positions

| Position | Type | Rationale |
|---|---|---|
| Petroleum (WTI) straddle | Long volatility | Hormuz could resolve (oil down) or escalate (oil up) — both directions profit a straddle |
| Short VIX (via short-vol instrument) | Short volatility | If geopolitical risk eases, VIX compresses and the position collects carry |

## What happened

The oil straddle delivered a modest, unremarkable result — the move in oil
prices over the window wasn't large enough in either direction to clearly
beat the cost of holding the position (theta decay). The short-VIX leg was
the more reliable contributor: as the ceasefire held and risk sentiment
calmed, VIX compressed and the position collected carry as designed.

## Lessons learned

- **Long-volatility positions need a real binary catalyst, not just
  "elevated uncertainty."** Geopolitical tension alone doesn't guarantee a
  large realized move within the position's time horizon — it guarantees
  elevated *implied* volatility, which is exactly what you're paying for.
- **Theta decay is not optional to manage.** A long-volatility position that
  doesn't get its catalyst on schedule bleeds value every day, independent
  of the underlying. This strategy demands the most active management of the
  six, by design.
- **Short volatility worked here mainly because the regime cooperated.**
  That is the structural risk of carry strategies: they look reliable until
  a single spike erases multiple periods of accumulated gains. A later,
  separate test (logged informally but not yet written up here) showed this
  risk materialize when a long-volatility position around an earnings event
  suffered a sharp IV crush — a reminder that this strategy's risk is
  asymmetric to the downside on the long-vol leg specifically.
