# Sector TAA: rotating between XLF, XLE, XLK and XLB

October 2026. In my round-2 paper trades (entered 2026-05-14) this strategy was described only as "quarterly rotation by Fed regime" across four sector ETFs. There was no written rule. `backtest_taa.py` writes one down before looking at results and tests it from 1999; the docstring has the design.

## Rules

- FED_REGIME. If the 3-month T-bill yield (^IRX) rises more than 0.25 pp over six months, that's tightening: hold XLF + XLE. If it falls more than 0.25 pp, that's easing: hold XLK + XLB. Otherwise hold all four equally. The mapping is my reading of the literature (Conover et al., 2008); the original description didn't specify it.
- MOMENTUM_TOP2. Hold the two sectors with the best 12-month return.

Both rebalance quarterly with 0.15% per side. The benchmark is the four ETFs at equal weight. The pass criterion, fixed beforehand: excess return over the benchmark with t > 2.

## Results, January 2000 – September 2026 (net, 321 months)

| Strategy | CAGR | Vol | Sharpe | Max DD | Excess vs equal weight (t) | By thirds |
|---|---|---|---|---|---|---|
| Equal weight (benchmark) | 8.8% | 18.1% | 0.45 | −57% | — | — |
| FED_REGIME | 11.2% | 18.7% | 0.56 | −52% | +2.3%/yr (1.98) | +4.9 / +0.3 / +1.6 |
| MOMENTUM_TOP2 | 9.0% | 18.2% | 0.46 | −52% | +0.2%/yr (0.16) | +2.6 / −2.1 / +0.2 |
| SPY (context) | 8.2% | 15.1% | 0.47 | −51% | — | — |

Neither passes. Sector momentum adds nothing. FED_REGIME stops at t = 1.98, and when I looked closer the evidence is weaker than that number suggests:

- The real sample is Fed cycles, not months, because regimes last years. Of 11 regime episodes lasting three months or more, the "right" basket won in 6. That's a coin flip.
- Two episodes explain almost everything. In 2000 the Fed was hiking while tech collapsed (+26% excess that year). In 2020 the Fed was cutting while tech soared (+25%). Without the three most extreme years the excess is +0.4% a year (t = 0.46).
- The mapping itself is contaminated by those same episodes. The idea that financials and energy win when the Fed hikes was formed largely by watching 2000, 2004–06 and 2022, so using it to judge those years isn't a clean test, even though no parameter was fitted.

At the end of September 2026 the T-bill had risen more than 0.25 pp in six months, so the rule would switch to XLF + XLE for Q4. That's what the rule says, not something I'd follow with money on this evidence.

## Limitations

- Only four sectors, all cyclical. A typical sector TAA includes defensives (utilities, staples, health care), which is where the literature puts the tightening effect.
- One regime definition. The 3-month bill with a 0.25 pp band over six months is the one I fixed beforehand; trying others now would just be searching for the one that works.

```
python backtest_taa.py      # downloads prices on the first run (data/prices.csv)
```

Tests (offline), from `strategy-lab/`: `python -m unittest discover tests -v`.
