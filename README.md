This repository documents the analytical framework I use to manage my personal equity
portfolio and a tactical macro allocation sleeve. It is built to be transparent and
reproducible: every stock pitch is backed by the same screening methodology, and every
number in the model can be traced back to its source.

## Why this repository exists

Most of what I do in equity analysis doesn't show up on a CV bullet point. This is the
evidence layer: the actual screening code, the actual valuation models, and the actual
investment theses behind the "Personal Equity Portfolio Management" line on my resume.

## Structure

```
.
├── models/
│   └── fundamental_screener.py     # P/E, ROE, FCF, Debt/Equity, PEG screening framework
├── stock_pitches/
│   └── TEMPLATE_stock_pitch.md     # Format used for every position in the portfolio
├── data/
│   └── watchlist.csv               # Tracked tickers and current screening scores
└── README.md
```

## Methodology

Every position in the portfolio is screened against five criteria before entry:

| Metric | What it measures | Threshold I look for |
|---|---|---|
| P/E | Price paid per unit of earnings | < 15x value names, < 25x growth names |
| ROE | Profitability relative to equity capital | > 15% |
| Debt/Equity | Balance sheet leverage | < 1.0, ideally < 0.5 |
| Free Cash Flow | Real cash generated after capex | Positive and growing |
| PEG ratio | P/E adjusted for growth | < 1.5 |

No position is added without a written thesis (see `stock_pitches/`) covering the bull
case, the bear case, and the specific catalysts that would change my position size.

## Current focus

Active names under coverage: JPMorgan Chase (JPM), ExxonMobil (XOM), BMW (BMW.DE).
See `data/watchlist.csv` for the latest screening output and `stock_pitches/` for
full writeups.

## Disclaimer

This repository reflects personal research and is not investment advice. Figures are
based on publicly available data at the time of writing and may not reflect current
market conditions.
