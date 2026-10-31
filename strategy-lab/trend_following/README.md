# Trend following in commodities

October 2026. My paper "Trend Following commodities" strategy (round 2, entered 2026-05-14) was gold and copper at 50/50, which is really just buy and hold, with no trend rule at all. `backtest_trend.py` measures what a real rule would have added. I wrote the rules before seeing results; the docstring has the full design.

## Design

I use ETFs rather than continuous futures, because yfinance's `=F` series jump at every contract roll.

- Basket A, the one I actually held on paper: GLD + CPER.
- Basket B, diversified: GLD, SLV, CPER, USO, UNG, DBA, DBB.
- Each ETF joins once it has 12 months of history, so basket A is gold only until 2012 (CPER starts at the end of 2011).

Two rules straight from the literature, with nothing tuned to this data:

- SMA10 (Faber, 2007): long if the month-end close is above the 10-month average.
- TSMOM12 (Moskowitz, Ooi and Pedersen, 2012): long if the 12-month return is positive.

Without a signal the money sits in cash earning the 3-month T-bill. Rebalancing is monthly at equal weights, with 0.15% per side. The benchmark is buy and hold of the same basket. The pass criterion, fixed beforehand: the rule must improve buy-and-hold's Sharpe with the lower end of the 90% CI (12-month block bootstrap) above zero.

## Results, January 2006 – September 2026 (net)

| Basket | Rule | CAGR | Vol | Sharpe | Max DD | Time invested | Sharpe diff [90% CI] |
|---|---|---|---|---|---|---|---|
| A gold+copper | Buy & hold | 9.7% | 16.5% | 0.55 | −45% | 100% | — |
| A gold+copper | SMA10 | 7.0% | 13.2% | 0.45 | −38% | 66% | −0.10 [−0.29, 0.07] |
| A gold+copper | TSMOM12 | 9.7% | 14.1% | 0.61 | −26% | 67% | +0.07 [−0.12, 0.26] |
| B diversified | Buy & hold | 2.3% | 17.2% | 0.12 | −73% | 100% | — |
| B diversified | SMA10 | 5.1% | 11.3% | 0.34 | −34% | 53% | +0.23 [−0.04, 0.44] |
| B diversified | TSMOM12 | 4.6% | 12.0% | 0.30 | −35% | 53% | +0.18 [−0.03, 0.36] |

None of the four tests passes.

On gold and copper the rule doesn't reliably help. SMA10 makes the Sharpe worse. TSMOM12 cuts the maximum drawdown from −45% to −26%, but its Sharpe gain (+0.07) is noise.

The diversified basket is where a trend rule makes sense. Buying and holding commodities was a bad investment there: 2.3% a year with a −73% drawdown, mostly from the roll cost of USO and UNG. Both rules halve the drawdown and add 0.18–0.23 to the Sharpe, and TSMOM12 improves it in all three thirds of the sample (+0.11, +0.15, +0.12). Still, the CI touches zero without crossing it. That matches what the literature says: trend is mainly drawdown control. And even with the rule, 5% a year at a Sharpe of 0.3 is far below equities, so it works as a diversifier, not as a core holding.

In the live round, neither rule would have avoided gold's June drop (−7.3% that month), because both were still long at the end of May. SMA10 then sold gold at the end of June and missed the July–August rebound: −4.4% from June to September against −3.1% for buy and hold. That's the known weakness of monthly rules: they are late at sharp turns.

## Limitations

- Few assets and short ETF histories. Basket A is gold only until 2012, and basket B isn't complete until 2012 either.
- Long/cash only. The academic version also goes short and diversifies across bonds, currencies and equities, which is where much of its return comes from. This tests the version a retail investor can build with ETFs.
- I didn't test the portfolio role here. That's in [`../portfolio_construction`](../portfolio_construction).

```
python backtest_trend.py      # downloads prices on the first run (data/prices.csv)
```

Tests (offline), from `strategy-lab/`: `python -m unittest discover tests -v`.
