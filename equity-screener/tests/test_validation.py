"""
Tests for data validation (src/validation.py) and the quarantine step.

Fixtures reproduce real rows from the 2026-10-06 TradingView pull, so the
thresholds are tested against the anomalies that motivated them.

Run with:
    python -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src import screener, validation


def make_row(**overrides):
    """Internally consistent row: mcap / PE = NI, NI / equity = ROE, growth 15%."""
    row = dict(name='CLEAN', exchange='NYSE',
               price_earnings_ttm=15.0, return_on_equity_fq=20.0,
               debt_to_equity=0.5, price_earnings_growth_ttm=1.0,
               free_cash_flow_ttm=5e8,
               market_cap_basic=15e9, net_income_ttm=1e9, total_equity_fq=5e9)
    row.update(overrides)
    return row


# Real values, 2026-10-06. LISPE is a SIX temporary line that carried the
# registered share's EPS (3,179 CHF) against a participation-certificate price.
LINDT = dict(market_cap_basic=17_470_594_208, net_income_ttm=730_500_000,
             return_on_equity_fq=15.965119, total_equity_fq=4_393_200_000,
             debt_to_equity=0.42024, price_earnings_growth_ttm=0.183,
             free_cash_flow_ttm=775_300_000)
LISPE = make_row(name='LISPE', exchange='SIX', price_earnings_ttm=2.388861, **LINDT)
LISP = make_row(name='LISP', exchange='SIX', price_earnings_ttm=23.621262, **LINDT)


def flags_of(row, column='data_errors'):
    return validation.validate(pd.DataFrame([row])).iloc[0][column]


def test_clean_row_has_no_flags():
    out = validation.validate(pd.DataFrame([make_row()])).iloc[0]
    assert out['data_errors'] == ''
    assert out['data_warnings'] == ''
    assert not out['suspect']
    assert out['pe_earnings_check'] == pytest.approx(1.0)
    assert out['roe_equity_check'] == pytest.approx(1.0)
    assert out['implied_growth_pct'] == pytest.approx(15.0)


def test_pe_from_wrong_share_line_is_an_error():
    out = validation.validate(pd.DataFrame([LISPE, LISP]))
    lispe, lisp = out.iloc[0], out.iloc[1]
    assert lispe['data_errors'] == 'PE_VS_EARNINGS'
    assert lispe['suspect']
    assert lispe['pe_earnings_check'] == pytest.approx(10.0, rel=0.01)
    # Same company on its regular line is consistent
    assert lisp['data_errors'] == ''
    assert lisp['pe_earnings_check'] == pytest.approx(1.0, abs=0.02)


def test_roe_on_average_equity_is_not_flagged():
    # HOC, 2026-10-06. Reported ROE 37.4% vs 26.9% on closing total equity.
    # Verified against the statements: 300.7M USD / avg(651.6M, 957.7M) = 37.4%.
    # The gap comes from average vs closing equity plus minorities in total equity.
    hoc = make_row(name='HOC', price_earnings_ttm=12.003216,
                   return_on_equity_fq=37.415734, debt_to_equity=0.27513,
                   price_earnings_growth_ttm=0.128741, free_cash_flow_ttm=245_447_160,
                   market_cap_basic=2_749_780_227, net_income_ttm=223_948_091,
                   total_equity_fq=831_939_725)
    out = validation.validate(pd.DataFrame([hoc])).iloc[0]
    assert out['data_errors'] == ''
    assert 'ROE_VS_EQUITY' not in out['data_warnings']
    assert out['roe_equity_check'] == pytest.approx(1.39, abs=0.01)


def test_gross_roe_gap_warns_but_is_not_quarantined():
    # CQP, 2026-10-06: reported 91.3% vs 356.6% on closing equity (ratio 0.26)
    cqp = make_row(name='CQP', return_on_equity_fq=91.322805,
                   net_income_ttm=2.689e9, total_equity_fq=7.54e8,
                   market_cap_basic=15.0 * 2.689e9)
    out = validation.validate(pd.DataFrame([cqp])).iloc[0]
    assert out['data_warnings'] == 'ROE_VS_EQUITY'
    assert not out['suspect']


def test_small_roe_gap_below_minimum_pp_is_ignored():
    # Ratio 0.33x but only 4 pp apart: noise on a low-ROE company, not a flag
    row = make_row(return_on_equity_fq=2.0, net_income_ttm=3e8, total_equity_fq=5e9,
                   market_cap_basic=15.0 * 3e8)
    assert flags_of(row, 'data_warnings') == ''


def test_roe_sign_mismatch_is_an_error():
    # Lonza-like: ROE +12.6% reported while TTM net income is negative
    row = make_row(return_on_equity_fq=12.64, net_income_ttm=-1.1e8)
    assert flags_of(row) == 'ROE_SIGN'
    # The sign error is not double-reported as an ROE/equity warning
    assert flags_of(row, 'data_warnings') == ''


def test_peg_base_effect_warns():
    # VLO, 2026-10-06: P/E 16.1 with PEG 0.018 implies ~909% EPS growth
    row = make_row(price_earnings_ttm=16.060762, price_earnings_growth_ttm=0.017653,
                   market_cap_basic=16.060762 * 1e9)
    out = validation.validate(pd.DataFrame([row])).iloc[0]
    assert out['data_warnings'] == 'PEG_BASE_EFFECT'
    assert out['implied_growth_pct'] == pytest.approx(909.8, abs=0.5)
    assert not out['suspect']


def test_out_of_bounds_is_flagged_not_dropped():
    rows = [make_row(), make_row(name='TINY_PE', price_earnings_ttm=0.05,
                                 market_cap_basic=0.05 * 1e9)]
    out = validation.validate(pd.DataFrame(rows))
    assert len(out) == 2
    assert out.iloc[1]['data_errors'] == 'OOB_PE'


def test_multiple_errors_are_joined():
    row = make_row(price_earnings_ttm=0.05, return_on_equity_fq=600.0)
    codes = set(flags_of(row).split(';'))
    assert {'OOB_PE', 'OOB_ROE', 'PE_VS_EARNINGS'} <= codes


def test_missing_inputs_skip_checks():
    # Without NI / equity fields the cross-checks cannot run: no flag, no crash
    row = make_row()
    del row['net_income_ttm'], row['total_equity_fq']
    out = validation.validate(pd.DataFrame([row])).iloc[0]
    assert out['data_errors'] == '' and out['data_warnings'] == ''
    assert np.isnan(out['pe_earnings_check'])

    # Same with the fields present but NaN
    out = validation.validate(pd.DataFrame([make_row(net_income_ttm=np.nan)])).iloc[0]
    assert out['data_errors'] == ''


def test_empty_frame():
    empty = pd.DataFrame(columns=list(make_row()))
    out = validation.validate(empty)
    assert out.empty and 'suspect' in out.columns


def test_flag_counts():
    out = validation.validate(pd.DataFrame([LISPE, make_row(return_on_equity_fq=12.0,
                                                           net_income_ttm=-1e8)]))
    assert validation.flag_counts(out) == {'PE_VS_EARNINGS': 1, 'ROE_SIGN': 1}


# ---------------------------------------------------------------------------
# Quarantine inside the screener pipeline
# ---------------------------------------------------------------------------

@pytest.fixture
def universe_with_lispe():
    clean_rows = [
        make_row(name='A'),
        make_row(name='B', price_earnings_ttm=10.0, return_on_equity_fq=25.0,
                 market_cap_basic=10e9, total_equity_fq=4e9),
        make_row(name='C', price_earnings_ttm=18.0, return_on_equity_fq=14.0,
                 debt_to_equity=0.8, market_cap_basic=18e9, net_income_ttm=1e9,
                 total_equity_fq=1e9 / 0.14),
    ]
    return pd.DataFrame(clean_rows + [LISPE])


def test_quarantined_row_is_not_ranked(universe_with_lispe):
    ranked, quarantine = screener.run_screener(universe_with_lispe)
    assert set(ranked['name']) == {'A', 'B', 'C'}
    assert list(quarantine['name']) == ['LISPE']
    assert quarantine.iloc[0]['data_errors'] == 'PE_VS_EARNINGS'


def test_quarantined_row_does_not_contaminate_zscores(universe_with_lispe):
    # The core reason for quarantine: LISPE's P/E of 2.4 would shift the P/E
    # mean and std that A, B and C are scored against.
    ranked, _ = screener.run_screener(universe_with_lispe)
    clean_only = universe_with_lispe[universe_with_lispe['name'] != 'LISPE']
    expected, _ = screener.run_screener(clean_only)
    pd.testing.assert_series_equal(ranked['score'], expected['score'])

    # ...and scoring with LISPE included gives different scores
    contaminated = screener.compute_composite_score(
        validation.validate(universe_with_lispe))
    contaminated = contaminated[contaminated['name'] != 'LISPE']
    assert not np.allclose(
        contaminated.set_index('name')['score'].sort_index(),
        ranked.set_index('name')['score'].sort_index())
