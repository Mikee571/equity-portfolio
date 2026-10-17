"""
Quality factor signals (src/backtest/quality.py). No network.

Run with:
    python -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.backtest import quality


def snapshots(n=12, eps_growth=None, cik=1, start='2021-03-31'):
    ends = pd.date_range(start, periods=n, freq='QE')
    growth = np.full(n, 0.10) if eps_growth is None else np.asarray(eps_growth)
    return pd.DataFrame({
        'cik': cik, 'period_end': ends, 'known': ends + pd.Timedelta(days=40),
        'known_quality': ends + pd.Timedelta(days=40),
        'eps': 1.0 + growth, 'eps_prev': 1.0, 'ni': np.nan, 'ni_prev': np.nan,
        'diluted_shares': np.nan, 'diluted_shares_prev': np.nan,
        'gross_profit': np.nan, 'revenue': 100.0, 'cogs': 60.0, 'assets': 200.0,
    })


def test_steady_growth_has_zero_variability():
    var = quality.earnings_variability(snapshots(), '2024-06-30')
    assert var.loc[1] == pytest.approx(0.0)


def test_variability_needs_enough_observations():
    var = quality.earnings_variability(snapshots(n=5), '2022-08-31')
    assert np.isnan(var.loc[1])


def test_variability_ignores_unpublished_snapshots():
    g = np.r_[np.full(11, 0.10), 5.0]                     # last quarter: a huge jump
    s = snapshots(eps_growth=g)
    last_known = s['known'].iloc[-1]
    before = quality.earnings_variability(s, last_known)  # known strictly before: excluded
    after = quality.earnings_variability(s, last_known + pd.Timedelta(days=1))
    assert before.loc[1] == pytest.approx(0.0)
    assert after.loc[1] > 1.0


def test_gross_profitability_falls_back_to_revenue_minus_cogs():
    gp = quality.gross_profitability(snapshots(), '2024-06-30')
    assert gp.loc[1] == pytest.approx((100 - 60) / 200)


def test_tagged_gross_profit_wins():
    s = snapshots().assign(gross_profit=50.0)
    assert quality.gross_profitability(s, '2024-06-30').loc[1] == pytest.approx(0.25)


def test_top_quintile_weights():
    d = pd.Timestamp('2020-01-31')
    df = pd.DataFrame({'date': d, 'cik': range(10), 'msci': np.arange(10.0)})
    w = quality.top_quantile_weights(df, 'msci')
    held = w.loc[d][w.loc[d] > 0]
    assert sorted(held.index) == [8, 9] and held.sum() == pytest.approx(1.0)


def test_zscore_is_winsorised():
    x = pd.Series(np.r_[np.arange(99.0), 1e6])
    z = quality.zscore(x)
    raw = (x - x.mean()) / x.std(ddof=0)
    assert z.iloc[-1] < 2.0 < raw.iloc[-1]                # the outlier is clipped to P95
    assert z.iloc[-1] == pytest.approx(z.iloc[-2])        # ...like the names already at P95
