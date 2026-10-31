# Strategy lab

This is where I test trading ideas before they can touch real money. It started in April 2026 as a paper-trading comparison of six strategy archetypes (`theoretical/`). It turned into a set of proper backtests once I realised a one-month paper result says almost nothing.

Most of what's here is archived, and the archive is the point: each folder records what I expected, how I tested it and why it failed.

| Folder | What it is | Outcome |
|---|---|---|
| [`theoretical/`](theoretical) | Paper-trading log: six strategies, same $1,000, same 32-day window (Apr–May 2026), with the thesis written before the outcome | Global Macro "won" +23%, almost entirely from one gold-miner bet |
| [`stat_arb/`](stat_arb) | Cointegrated pairs: Engle-Granger + Johansen selection, z-score trading, Kalman and OU variants, quarterly walk-forward 2012–2026 | −1.9%/yr net; Kalman/OU don't fix it. Archived |
| [`signal_lab/`](signal_lab) | "Strategy 10": XGBoost / random forest predicting 10-day direction from technical features, with purged CV and a promotion criterion | AUC 0.43–0.52 out of sample, no skill. Archived ([lessons](archive/ml_predictor_lessons.md)) |
| [`trend_following/`](trend_following) | SMA10 and TSMOM12 on commodity ETFs, 2006–2026 | Halves drawdowns; Sharpe gain not significant |
| [`taa_sectorial/`](taa_sectorial) | Fed-regime sector rotation vs sector momentum, 2000–2026 | t = 1.98, driven by 2000 and 2020 |
| [`portfolio_construction/`](portfolio_construction) | Does a quality or trend sleeve improve a 70/20/10 portfolio? | No; trend is insurance with a ~1 pt/yr premium |
| [`archive/`](archive) | Write-ups of failed or retired ideas: cointegration, ML predictor, EMA cross, MACD, and a bug I found in a third-party tool's Sharpe ratio (inflated 5–10×) | — |
| [`shared/`](shared) | `corrected_sharpe.py`, the Sharpe calculation I use instead | — |

Every backtest follows the same rules:

- The design and pass criterion are fixed before I look at results (usually t > 2, or a 90% CI on the Sharpe difference above zero).
- Costs are included.
- The benchmark is something fair: buy and hold of the same assets, equal weight, or random timing.

Tests run offline:

```
pip install -r ../requirements.txt
python -m unittest discover tests -v
```

Some modules (`stat_arb/telegram_alerts.py`, `signal_lab/telegram_alerts_signal10.py`) sent me daily alerts when these strategies were live. They read credentials from a `.env` file (see `.env.example`) and aren't needed for the backtests.
