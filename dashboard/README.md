# Dashboard

A small Streamlit app that works as the front door to this repository. It has four pages:

- Valuations: the five company models (Micron, GTT, JPMorgan, Adobe, Deckers) with sliders for the discount rate and the key drivers: normalised margins, orders per year, long-run ROTE, and your own growth and margin case for Adobe and Deckers. A reverse DCF recalculates as you move them.
- Screener: the latest five-factor ranking (snapshot of the weekly run on 2026-10-11) with filters and each stock's factor profile.
- Research: the scorecard of the eleven strategy tests and three charts from them.
- SQL insights: the results of the SEC filings analysis.

The valuation page doesn't read the Excel files. [`valuation/models.py`](../valuation/models.py) re-implements the models in Python so the sliders respond instantly; the Monte Carlo uses the same code. `valuation/test_models.py` checks that, with the default inputs, the Python versions give exactly the same values as Excel:

```
cd valuation
python -m unittest test_models -v
```

## Running it

```
pip install -r dashboard/requirements.txt
streamlit run dashboard/Home.py
```

## Publishing it (free)

1. Push the repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub and choose **Create app**.
3. Pick the repository, branch `main` and main file `dashboard/Home.py`.

The app reads only files that are already in the repository: the screener snapshot, `valuation/*/data`, `sql-analysis/results` and the research figures. The theme is in `.streamlit/config.toml` at the repository root.
