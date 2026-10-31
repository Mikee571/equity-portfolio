# Portfolio construction: add a quality or a trend sleeve?

October 2026. My round-2 tests found no extra return in quality or in trend following, but they did find some risk control. `portfolio_mix.py` checks whether that risk control improves a whole portfolio: the 70/20/10 structure I use for my own long-term money. The design was fixed before looking at results; the docstring has the details.

## Design

The base portfolio:

- 70% VWRL, the global ETF, in euros.
- 20% the screener's top 10, from the point-in-time backtest.
- 10% tactical. That sleeve is discretionary and can't be reconstructed, so I stand in the equal-weight universe for it: picking stocks with no edge.

Variants add 10% or 20% of quality (MSCI-style) or trend (TSMOM12 on seven commodity ETFs), funded from the core. Everything is in euros with monthly rebalancing. A variant counts as better if it raises the Sharpe with the lower end of the 90% CI (12-month block bootstrap) above zero.

## Each sleeve on its own (June 2012 – September 2026, EUR)

| Sleeve | CAGR | Vol | Sharpe | Max DD | Correlation with VWRL |
|---|---|---|---|---|---|
| VWRL (core) | 10.6% | 13.9% | 0.80 | −26% | 1 |
| Screener top 10 | 17.0% | 21.5% | 0.85 | −27% | 0.61 |
| Equal-weight universe (tactical) | 14.1% | 17.1% | 0.87 | −28% | 0.77 |
| Quality | 14.9% | 15.6% | 0.98 | −20% | 0.75 |
| Commodity trend | 4.2% | 10.0% | 0.46 | −24% | 0.21 |

## Portfolios

| Portfolio | CAGR | Vol | Sharpe | Max DD | Worst 12 months | Sharpe diff [90% CI] |
|---|---|---|---|---|---|---|
| Base 70/20/10 | 12.5% | 14.3% | 0.90 | −20.4% | −13.3% | — |
| + 10% quality | 13.0% | 14.4% | 0.93 | −20.4% | −13.4% | +0.02 [−0.02, 0.07] |
| + 20% quality | 13.4% | 14.5% | 0.95 | −20.4% | −13.5% | +0.04 [−0.03, 0.14] |
| + 10% trend | 12.0% | 13.2% | 0.93 | −18.9% | −10.6% | +0.02 [−0.01, 0.07] |
| + 20% trend | 11.4% | 12.3% | 0.95 | −17.5% | −9.2% | +0.05 [−0.03, 0.15] |

No variant passes. The differences are small; the base is already well diversified for its level of risk.

Quality doesn't reduce this portfolio's risk. On its own it looks defensive (Sharpe 0.98), but it's more volatile than the VWRL it replaces (15.6% vs 13.9%), moves almost exactly with the other equity sleeves (0.95 correlation with the tactical one) and doesn't improve the drawdown or the worst year. Its extra 0.5–0.9 points of return have two explanations that aren't "quality": the US beat the world in 2012–2026 and quality is US-only, and the equity sleeves come from today's US universe, which has survivorship bias that VWRL doesn't. That bias also inflates the screener's 17%.

Trend does diversify (0.21 correlation with VWRL), but it costs return. With a 20% trend sleeve, volatility drops from 14.3% to 12.3%, the maximum drawdown from −20.4% to −17.5% and the worst year from −13.3% to −9.2%, while return falls 1.1 points a year and the Sharpe stays the same within noise. In the COVID drop (February–March 2020) it cut the loss from −20.4% to −17.5%. So it's insurance with a premium, not a free improvement.

Whether ~1 point a year is worth ~4 points less in the worst year depends on how much drawdowns would affect my behaviour, for example whether they'd make me sell. That's a risk preference, not something a backtest can decide. If I ever implement it, there's a practical catch: GLD, USO, DBA and the rest are US ETFs that EU retail investors can't buy, so it would need UCITS ETCs, which I haven't tested.

## Limitations

- Survivorship bias in the equity sleeves (not in VWRL or trend), as above.
- The tactical sleeve is an assumption; the real one depends on my own decisions.
- Monthly rebalancing with no cost between sleeves. In practice I'd rebalance less often.
- Only 172 months, in a single period dominated by the US.

```
# in equity-screener (once, after run_backtest.py):
python -m src.backtest.export_sleeves
# here:
python portfolio_mix.py
```
