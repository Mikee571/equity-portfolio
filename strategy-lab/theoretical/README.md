# Multi-Strategy Paper Trading Lab

CFA Level I Candidate | Financial Analyst | Equity Research & Valuation

## What this is

A research log comparing six systematic investment strategy archetypes against
identical starting capital and market conditions, to build intuition about how
different approaches behave across market regimes.

**This is a paper trading exercise — no real capital was deployed.** It exists to
stress-test investment logic, document the reasoning behind each strategy, and be
honest about what worked and what didn't. It is not a track record and not
investment advice.

## Why this exists

Anyone can describe a strategy in the abstract. The interesting (and harder) part
is writing down a thesis *before* the outcome is known, then comparing it against
what actually happened — including the strategies that lost. That discipline is
the point of this repository, not the returns themselves.

## The six strategies

| # | Strategy | Core idea |
|---|---|---|
| 1 | Global Macro | Directional bets on macro catalysts (rates, geopolitics, commodities) |
| 2 | Statistical Arbitrage | Market-neutral pairs trading on temporary divergences |
| 3 | Volatility Arbitrage | Long/short implied volatility around binary events |
| 4 | Trend Following | Momentum-based positioning across FX, commodities, rates |
| 5 | 70/20/10 Passive | 70% global ETF (VWRL) / 20% value stocks / 10% speculative |
| 6 | S&P 500 Benchmark | Passive index exposure, no active management |

## Test window 1 — 12 Apr 2026 → 14 May 2026 (32 days)

**Market backdrop:** an active geopolitical conflict (Iran/Strait of Hormuz)
disrupted oil markets and pushed gold and defense equities higher through most
of the window, before a ceasefire and a strong Nvidia earnings report drove a
14% S&P 500 rally into mid-May.

### Results

| Strategy | Return | $1,000 → |
|---|---|---|
| **Global Macro** | **+23.0%** | **$1,230** |
| Statistical Arbitrage | +14.7% | $1,147 |
| S&P 500 (benchmark) | +14.0% | $1,140 |
| 70/20/10 Passive | +8.2% | $1,082 |
| Volatility Arbitrage | +5.3% | $1,053 |
| Trend Following | +2.7% | $1,027 |

See `strategies/` for the thesis, position composition and lessons learned for
each strategy in this window.

### Headline takeaway

Global Macro won, but mostly because of a single concentrated bet on gold
miners (GDX/GDXJ, +53% over the window) that happened to align with the
regime. Stripped of that one position, the strategy would have returned only
+5.2% — the worst of the group. Statistical Arbitrage came close to matching
the S&P 500 (+14.7% vs +14.0%) with far less directional risk, which is the
more reproducible result of the two. The full reasoning per strategy is in
`strategies/`.

## Structure

```
.
├── strategies/      # One file per strategy: thesis, positions, result, lessons
├── data/             # results_log.csv — machine-readable version of the table above
├── scripts/          # analyze_results.py — basic return/volatility comparison
└── README.md
```

## Methodology notes

- All six strategies started with the same hypothetical $1,000 and were
  evaluated over the same calendar window, to isolate strategy behavior from
  timing luck as much as possible.
- Position-level reasoning was written down at entry, before outcomes were
  known, and is preserved as-is in `strategies/` — including the parts that
  turned out to be wrong.
- Review cadence varied by strategy: volatility and statistical arbitrage
  positions were reviewed daily given time-decay and convergence dynamics;
  the passive 70/20/10 sleeve was deliberately reviewed monthly to avoid
  emotional rebalancing.

## Disclaimer

This is a personal research project using simulated capital. Nothing here is
investment advice, and past paper-trading results do not predict future
performance — simulated or otherwise.

## Contact

- LinkedIn: [marcelo-renere](https://www.linkedin.com/in/marcelo-renere/)
- Email: mrenere@student.eae.es
