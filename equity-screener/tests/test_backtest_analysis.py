"""
Backtest statistics and portfolio accounting (src/backtest/analysis.py,
src/backtest/panel.py). No network.

Run with:
    python -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.backtest import analysis, panel


def test_rank_ic_is_spearman():
    x = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10.0])
    assert analysis.rank_ic(x, x ** 3) == pytest.approx(1.0)
    assert analysis.rank_ic(x, -x) == pytest.approx(-1.0)
    assert np.isnan(analysis.rank_ic(x[:5], x[:5]))      # fewer than 10 names


def test_newey_west_matches_plain_t_without_lags():
    rng = np.random.default_rng(0)
    s = pd.Series(rng.normal(0.01, 0.05, 200))
    plain = s.mean() / (s.std(ddof=0) / np.sqrt(len(s)))
    assert analysis.newey_west_t(s, 0) == pytest.approx(plain)


def test_newey_west_penalises_autocorrelation():
    # Overlapping 12-month sums of iid noise: lags shrink the t-stat
    rng = np.random.default_rng(1)
    s = pd.Series(rng.normal(0.01, 0.05, 400)).rolling(12).sum().dropna()
    assert abs(analysis.newey_west_t(s, 11)) < abs(analysis.newey_west_t(s, 0))


def test_portfolio_returns_equal_weight_and_turnover():
    dates = pd.date_range('2020-01-31', periods=3, freq='ME')
    w = pd.DataFrame({1: [0.5, 0.5, 0.0], 2: [0.5, 0.5, 1.0]}, index=dates)
    r = pd.DataFrame({1: [0.10, 0.0, 0.0], 2: [-0.10, 0.0, 0.0]}, index=dates)
    out = analysis.portfolio_returns(w, r)
    # Return earned after Jan 31 is booked at Feb end
    assert out.index[0] == pd.Timestamp('2020-02-29')
    assert out['gross'].iloc[0] == pytest.approx(0.0)
    # Feb: drifted to 0.55 / 0.45, rebalanced back to 0.5 / 0.5 -> 10% traded, 5% one-way
    assert out['turnover'].iloc[1] == pytest.approx(0.05)
    # First month: buying the whole portfolio costs one side on 100%
    assert out['net'].iloc[0] == pytest.approx(-analysis.COST_PER_SIDE)


def test_holdings_top_n_and_universe_weights():
    d = pd.Timestamp('2020-01-31')
    ranked = pd.DataFrame({'date': d, 'cik': [1, 2, 3], 'rank': [1, 2, 3]})
    uni = pd.DataFrame({'date': d, 'cik': [1, 2, 3, 4]})
    h = analysis.holdings(ranked, uni, top_n=2)
    assert h['screen_top2'].loc[d].tolist() == [0.5, 0.5]
    assert h['universe_ew'].loc[d].sum() == pytest.approx(1.0)


def test_survivorship_share():
    pf = pd.DataFrame({'cik': [1, 2, 3, 1], 'val': [2e9, 3e9, 5e8, 2e9],
                       'filed': pd.to_datetime(['2014-03-01', '2014-03-01', '2014-03-01', '2014-09-01']),
                       'end': pd.to_datetime(['2013-06-30'] * 4)})
    out = analysis.survivorship(pf, listed_ciks={1})
    assert out.loc[2014, 'companies'] == 2            # cik 3 below $1B; cik 1 counted once
    assert out.loc[2014, 'share_still_listed'] == 0.5


def test_tradingview_columns_definitions():
    snap = pd.DataFrame({
        'eps': [2.0, -1.0], 'eps_prev': [1.6, 1.0], 'ni': [200.0, -100.0],
        'equity': [1000.0, 500.0], 'equity_prev': [600.0, np.nan], 'equity_total': [1100.0, 500.0],
        'debt': [300.0, 0.0], 'oplease': [100.0, 0.0], 'cfo': [250.0, 10.0], 'capex': [50.0, 20.0],
        'cover_shares': [100.0, np.nan], 'diluted_shares': [101.0, 100.0],
        'ni_prev': [160.0, 100.0], 'diluted_shares_prev': [100.0, 100.0],
        'period_end': pd.Timestamp('2025-12-31'), 'known': pd.Timestamp('2026-02-01'),
        'capex_reported': True,
    }, index=[10, 20])
    out = panel.tradingview_columns(snap, pd.Series({10: 30.0, 20: 5.0}))
    a = out.loc[10]
    assert a['price_earnings_ttm'] == 15
    assert a['earnings_per_share_diluted_yoy_growth_ttm'] == pytest.approx(25)
    assert a['price_earnings_growth_ttm'] == pytest.approx(0.6)
    assert a['return_on_equity_fq'] == pytest.approx(25)          # 200 / avg(1000, 600)
    assert a['debt_to_equity'] == pytest.approx(0.4)              # (300 + 100) / 1000
    assert a['free_cash_flow_ttm'] == 200
    assert a['market_cap_basic'] == 3000                          # cover-page shares
    b = out.loc[20]
    assert np.isnan(b['price_earnings_ttm'])                      # loss-making
    assert b['market_cap_basic'] == 500                           # falls back to diluted shares


def test_eps_falls_back_to_net_income_per_diluted_share():
    snap = pd.DataFrame({
        'eps': [np.nan], 'eps_prev': [np.nan], 'ni': [200.0], 'ni_prev': [100.0],
        'diluted_shares': [100.0], 'diluted_shares_prev': [100.0],
        'equity': [1000.0], 'equity_prev': [1000.0], 'equity_total': [1000.0],
        'debt': [0.0], 'oplease': [0.0], 'cfo': [1.0], 'capex': [0.0],
        'cover_shares': [100.0], 'period_end': pd.Timestamp('2025-12-31'),
        'known': pd.Timestamp('2026-02-01'), 'capex_reported': True,
    }, index=[1])
    out = panel.tradingview_columns(snap, pd.Series({1: 20.0}))
    assert out.loc[1, 'price_earnings_ttm'] == 10                 # 20 / (200 / 100)
    assert out.loc[1, 'earnings_per_share_diluted_yoy_growth_ttm'] == pytest.approx(100)


def test_periods_split_in_three():
    idx = pd.date_range('2012-02-29', periods=12, freq='ME')
    p = analysis.periods(idx)
    assert list(p)[1:] == ['2012-02..2012-05', '2012-06..2012-09', '2012-10..2013-01']
    assert p['full'] == (idx[0], idx[-1])


def test_month_ends_exclude_the_current_partial_month():
    daily = pd.bdate_range('2026-08-03', '2026-10-07')
    assert analysis.month_ends(daily, start='2026-08-31')[-1] == pd.Timestamp('2026-09-30')


def test_last_month_without_returns_is_dropped():
    dates = pd.date_range('2020-01-31', periods=2, freq='ME')
    w = pd.DataFrame({1: [1.0, 1.0]}, index=dates)
    r = pd.DataFrame({1: [0.05, np.nan]}, index=dates)
    out = analysis.portfolio_returns(w, r)
    assert len(out) == 1 and out['gross'].iloc[0] == pytest.approx(0.05)


# ---------------------------------------------------------------- weights study

from src.backtest import weights


def test_top_n_ranks_by_weighted_z():
    z = np.array([[1.0, 0, 0, 0, 0], [0, 2.0, 0, 0, 0], [0, 0, 0, 0, 3.0]])
    groups = [(pd.Timestamp('2020-01-31'), z, np.array([0.1, 0.2, 0.3]), np.array([1, 2, 3]))]
    w = np.array([1.0, 0, 0, 0, 0])
    ret, picks = weights.top_n(groups, w, n=1)
    assert picks == [{1}] and ret.iloc[0] == pytest.approx(0.1)
    ret, picks = weights.top_n(groups, np.full(5, 0.2), n=2)
    assert picks == [{2, 3}] and ret.iloc[0] == pytest.approx(0.25)


def test_no_roe_alternative_sums_to_one():
    w = weights.ALTERNATIVES['no_roe']
    assert w.sum() == pytest.approx(1.0)
    assert w[weights.FACTORS.index('roe')] == 0
