"""
Basic unit tests for the screener logic.

Run with:
    python -m pytest tests/ -v
"""
import sys
from pathlib import Path

# Make src importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src import screener, config


@pytest.fixture
def sample_universe():
    """A small hand-crafted universe covering pass/fail cases."""
    # ROE in percent (TradingView convention: 20.0 = 20%)
    df = pd.DataFrame([
        # PASS: all factors within thresholds
        {'name': 'PASS1', 'price_earnings_ttm': 15, 'return_on_equity_fq': 20.0,
         'debt_to_equity': 0.5, 'price_earnings_growth_ttm': 1.0,
         'free_cash_flow_ttm': 5e9},
        # PASS: good but different profile
        {'name': 'PASS2', 'price_earnings_ttm': 10, 'return_on_equity_fq': 15.0,
         'debt_to_equity': 0.3, 'price_earnings_growth_ttm': 0.8,
         'free_cash_flow_ttm': 2e9},
        # FAIL: PE too high
        {'name': 'FAIL_PE', 'price_earnings_ttm': 50, 'return_on_equity_fq': 20.0,
         'debt_to_equity': 0.5, 'price_earnings_growth_ttm': 1.0,
         'free_cash_flow_ttm': 5e9},
        # FAIL: ROE too low (5% < 12% threshold)
        {'name': 'FAIL_ROE', 'price_earnings_ttm': 15, 'return_on_equity_fq': 5.0,
         'debt_to_equity': 0.5, 'price_earnings_growth_ttm': 1.0,
         'free_cash_flow_ttm': 5e9},
        # FAIL: negative FCF
        {'name': 'FAIL_FCF', 'price_earnings_ttm': 15, 'return_on_equity_fq': 20.0,
         'debt_to_equity': 0.5, 'price_earnings_growth_ttm': 1.0,
         'free_cash_flow_ttm': -1e9},
        # FAIL: missing data (NaN)
        {'name': 'FAIL_NAN', 'price_earnings_ttm': 15, 'return_on_equity_fq': None,
         'debt_to_equity': 0.5, 'price_earnings_growth_ttm': 1.0,
         'free_cash_flow_ttm': 5e9},
        # FAIL: PEG = 0 (missing, not a real 0)
        {'name': 'FAIL_PEG0', 'price_earnings_ttm': 15, 'return_on_equity_fq': 20.0,
         'debt_to_equity': 0.5, 'price_earnings_growth_ttm': 0.0,
         'free_cash_flow_ttm': 5e9},
    ])
    df['market_cap_basic'] = 50e9
    return df


def test_hard_filters_reject_failures(sample_universe):
    survivors = screener.apply_hard_filters(sample_universe)
    survivor_names = set(survivors['name'])
    assert survivor_names == {'PASS1', 'PASS2'}


def test_composite_score_higher_is_better(sample_universe):
    survivors = screener.apply_hard_filters(sample_universe)
    ranked = screener.compute_composite_score(survivors)
    assert 'score' in ranked.columns
    # Scores should be monotonically non-increasing (already sorted desc)
    scores = ranked['score'].values
    assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))


def test_zscore_matches_definition():
    # With two observations the population z-scores are exactly +1 and -1
    # (winsorisation clips both ends symmetrically, so this still holds).
    # BEST beats WORST on every factor (incl. the lower-is-better ones), so
    # after inversion every z_ is +1 for BEST and the composite equals the
    # sum of weights (1.0); WORST mirrors it at -1.0.
    df = pd.DataFrame([
        {'name': 'BEST', 'price_earnings_ttm': 10, 'return_on_equity_fq': 30.0,
         'debt_to_equity': 0.2, 'price_earnings_growth_ttm': 0.5,
         'free_cash_flow_ttm': 4e9, 'market_cap_basic': 40e9},     # 10% yield
        {'name': 'WORST', 'price_earnings_ttm': 18, 'return_on_equity_fq': 14.0,
         'debt_to_equity': 0.9, 'price_earnings_growth_ttm': 1.4,
         'free_cash_flow_ttm': 1e9, 'market_cap_basic': 50e9},     # 2% yield
    ])
    ranked = screener.compute_composite_score(df).set_index('name')
    for factor in screener.FACTOR_COLS:
        assert ranked.loc['BEST', f'z_{factor}'] == pytest.approx(1.0)
        assert ranked.loc['WORST', f'z_{factor}'] == pytest.approx(-1.0)
    assert ranked.loc['BEST', 'score'] == pytest.approx(1.0)
    assert ranked.loc['WORST', 'score'] == pytest.approx(-1.0)


def test_zscore_zero_dispersion_is_neutral(sample_universe):
    survivors = screener.apply_hard_filters(sample_universe)
    survivors['debt_to_equity'] = 0.5          # identical for everyone
    ranked = screener.compute_composite_score(survivors)
    assert (ranked['z_de'] == 0).all()


def spread_universe(n=40, **col_overrides):
    """n survivors with evenly spread factor values; overrides replace a column."""
    df = pd.DataFrame({
        'name': [f'T{i}' for i in range(n)],
        'price_earnings_ttm': np.linspace(6, 19, n),
        'return_on_equity_fq': np.linspace(13, 60, n),
        'debt_to_equity': np.linspace(0.05, 0.95, n),
        'price_earnings_growth_ttm': np.linspace(0.3, 1.4, n),
        'free_cash_flow_ttm': np.linspace(1e8, 5e9, n),
        'market_cap_basic': np.linspace(2e9, 9e10, n)[::-1],
    })
    for col, values in col_overrides.items():
        df[col] = values
    return df


def test_fcf_is_scored_as_yield():
    # BIG has 25x the FCF of SMALL but a 1.25% yield vs 10%: SMALL must win
    df = spread_universe(n=10)
    df.loc[0, ['name', 'free_cash_flow_ttm', 'market_cap_basic']] = ['BIG', 50e9, 4000e9]
    df.loc[1, ['name', 'free_cash_flow_ttm', 'market_cap_basic']] = ['SMALL', 2e9, 20e9]
    ranked = screener.compute_composite_score(df).set_index('name')
    assert ranked.loc['BIG', 'fcf_yield'] == pytest.approx(0.0125)
    assert ranked.loc['SMALL', 'z_fcf'] > ranked.loc['BIG', 'z_fcf']


def test_base_effect_peg_is_neutral():
    # VLO, 2026-10-06: P/E 16.06 with PEG 0.0177 (909% implied growth).
    # Its PEG is not measurable: z = 0, and it does not enter the PEG mean/std
    # (any other base-effect PEG gives everyone identical z-scores).
    df = spread_universe(n=10)
    df.loc[0, ['price_earnings_ttm', 'price_earnings_growth_ttm']] = [16.06, 0.0177]
    ranked = screener.compute_composite_score(df).set_index('name')
    assert np.isnan(ranked.loc['T0', 'peg_scored'])
    assert ranked.loc['T0', 'z_peg'] == 0.0
    assert ranked.loc['T5', 'peg_scored'] == ranked.loc['T5', 'price_earnings_growth_ttm']

    df.loc[0, 'price_earnings_growth_ttm'] = 0.05      # 321% implied growth
    other = screener.compute_composite_score(df).set_index('name')
    pd.testing.assert_series_equal(ranked['z_peg'].sort_index(), other['z_peg'].sort_index())


def test_base_effect_peg_does_not_double_count_pe():
    # The rejected alternative, a floor at P/E / 100, made the PEG of every
    # base-effect name proportional to its P/E. Neutral z avoids that.
    df = spread_universe(n=20)
    df['price_earnings_growth_ttm'] = df['price_earnings_ttm'] / 300   # all 300% growth
    ranked = screener.compute_composite_score(df)
    assert (ranked['z_peg'] == 0).all()


def test_winsorised_zscores_ignore_outlier_magnitude():
    # n=40: the 95th percentile sits between the 38th and 39th values, so
    # the size of the single maximum no longer reaches anyone else's z.
    roe = np.linspace(13, 60, 40)
    moderate = screener.compute_composite_score(
        spread_universe(return_on_equity_fq=np.r_[roe[:-1], 131.0])).set_index('name')
    extreme = screener.compute_composite_score(
        spread_universe(return_on_equity_fq=np.r_[roe[:-1], 5000.0])).set_index('name')
    others = [f'T{i}' for i in range(39)]
    pd.testing.assert_series_equal(moderate.loc[others, 'z_roe'],
                                   extreme.loc[others, 'z_roe'])


def test_without_winsorisation_outlier_compresses_everyone(monkeypatch):
    # The pre-v0.7 behaviour, kept as documentation of why winsorisation exists
    monkeypatch.setattr(config, 'WINSOR_QUANTILES', None)
    roe = np.linspace(13, 60, 40)
    moderate = screener.compute_composite_score(
        spread_universe(return_on_equity_fq=np.r_[roe[:-1], 131.0])).set_index('name')
    extreme = screener.compute_composite_score(
        spread_universe(return_on_equity_fq=np.r_[roe[:-1], 5000.0])).set_index('name')
    others = [f'T{i}' for i in range(39)]
    spread_moderate = np.ptp(moderate.loc[others, 'z_roe'])
    spread_extreme = np.ptp(extreme.loc[others, 'z_roe'])
    assert spread_extreme < spread_moderate / 5


def test_empty_input_handled():
    empty = pd.DataFrame(columns=list(screener.FACTOR_COLS.values()) + ['name'])
    survivors = screener.apply_hard_filters(empty)
    ranked = screener.compute_composite_score(survivors)
    assert ranked.empty


def test_weights_sum_to_one():
    assert abs(sum(config.SCORE_WEIGHTS.values()) - 1.0) < 1e-9
