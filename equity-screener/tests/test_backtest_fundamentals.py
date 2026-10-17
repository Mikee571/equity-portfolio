"""
Point-in-time fundamentals (src/backtest/fundamentals.py), on hand-built
XBRL facts. No network.

Run with:
    python -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.backtest import fundamentals as fu
from src.backtest import prices


def fact(concept, start, end, val, filed, form='10-Q'):
    return {'cik': 1, 'concept': concept, 'unit': 'USD',
            'start': pd.Timestamp(start) if start else pd.NaT, 'end': pd.Timestamp(end),
            'val': float(val), 'accn': f'a-{filed}', 'form': form, 'filed': pd.Timestamp(filed)}


@pytest.fixture
def calendar_year_company():
    """Calendar fiscal year. Net income FY2022 = 100; H1 2022 = 45; H1 2023 = 60."""
    ni = 'NetIncomeLoss'
    return pd.DataFrame([
        fact(ni, '2022-01-01', '2022-03-31', 20, '2022-05-05'),
        fact(ni, '2022-01-01', '2022-06-30', 45, '2022-08-05'),
        fact(ni, '2022-04-01', '2022-06-30', 25, '2022-08-05'),
        fact(ni, '2022-01-01', '2022-12-31', 100, '2023-02-15', '10-K'),
        fact(ni, '2023-01-01', '2023-03-31', 30, '2023-05-05'),
        fact(ni, '2023-01-01', '2023-06-30', 60, '2023-08-05'),
        fact(ni, '2023-04-01', '2023-06-30', 30, '2023-08-05'),
        # Comparative restated in the 2023 10-Q: the backtest keeps 45
        fact(ni, '2022-01-01', '2022-06-30', 50, '2023-08-05'),
        fact('StockholdersEquity', None, '2022-06-30', 400, '2022-08-05'),
        fact('StockholdersEquity', None, '2023-06-30', 500, '2023-08-05'),
    ])


# ---------------------------------------------------------------- TTM

def test_ttm_at_fiscal_year_end_is_the_annual_figure(calendar_year_company):
    ttm = fu.ttm_series(fu.first_reported(calendar_year_company))
    assert ttm.loc['2022-12-31', 'val'] == 100
    assert ttm.loc['2022-12-31', 'known'] == pd.Timestamp('2023-02-15')


def test_ttm_from_year_to_date(calendar_year_company):
    ttm = fu.ttm_series(fu.first_reported(calendar_year_company))
    # YTD(H1 2023) + FY2022 - YTD(H1 2022), with the first-reported 45
    assert ttm.loc['2023-06-30', 'val'] == 60 + 100 - 45
    assert ttm.loc['2023-03-31', 'val'] == 30 + 100 - 20


def test_ttm_known_on_latest_input(calendar_year_company):
    ttm = fu.ttm_series(fu.first_reported(calendar_year_company))
    assert ttm.loc['2023-06-30', 'known'] == pd.Timestamp('2023-08-05')


def test_ttm_needs_prior_year():
    # No FY or prior-year YTD before H1 2022: no TTM can be built there
    rows = pd.DataFrame([fact('NetIncomeLoss', '2022-01-01', '2022-06-30', 45, '2022-08-05')])
    assert fu.ttm_series(rows).empty


def test_ttm_52_53_week_fiscal_year():
    """Apple-style calendar: FY ends on the last Saturday of September, Q1 FY23 had 14 weeks."""
    ni = 'NetIncomeLoss'
    rows = pd.DataFrame([
        fact(ni, '2022-09-25', '2022-12-31', 30, '2023-02-03'),           # 98 days
        fact(ni, '2022-09-25', '2023-09-30', 97, '2023-11-03', '10-K'),   # 371 days
        fact(ni, '2023-10-01', '2023-12-30', 34, '2024-02-02'),           # 91 days
    ])
    ttm = fu.ttm_series(rows)
    assert ttm.loc['2023-12-30', 'val'] == 34 + 97 - 30


def test_first_reported_ignores_restatements(calendar_year_company):
    first = fu.first_reported(calendar_year_company)
    h1_2022 = first[(first['start'] == '2022-01-01') & (first['end'] == '2022-06-30')]
    assert h1_2022['val'].tolist() == [45]


# ---------------------------------------------------------------- splits

def test_split_factor_after():
    events = pd.Series([4.0, 10.0], index=pd.to_datetime(['2021-07-20', '2024-06-10']))
    f = prices.split_factor_after(events, ['2020-01-01', '2021-07-20', '2022-01-01', '2025-01-01'])
    # A split on its ex-date already applies to that day's reports
    np.testing.assert_allclose(f, [40, 10, 10, 1])


def test_to_current_basis_restates_per_share_and_counts():
    events = pd.Series([4.0], index=pd.to_datetime(['2021-07-20']))
    rows = pd.DataFrame([
        fact('EarningsPerShareDiluted', '2020-01-01', '2020-12-31', 8.0, '2021-02-15', '10-K'),
        fact('EarningsPerShareDiluted', '2021-01-01', '2021-06-30', 1.0, '2021-08-01'),
        fact('WeightedAverageNumberOfDilutedSharesOutstanding', '2020-01-01', '2020-12-31', 100, '2021-02-15'),
        fact('NetIncomeLoss', '2020-01-01', '2020-12-31', 800, '2021-02-15', '10-K'),
    ])
    out = fu.to_current_basis(rows, events)
    assert out['val'].tolist() == [2.0, 1.0, 400.0, 800.0]


# ---------------------------------------------------------------- snapshots

def test_snapshot_columns_and_known(calendar_year_company):
    snap = fu.company_snapshots(calendar_year_company)
    row = snap.loc['2023-06-30']
    assert row['ni'] == 115
    assert row['equity'] == 500 and row['equity_prev'] == 400
    assert row['known'] == pd.Timestamp('2023-08-05')
    assert not row['capex_reported'] and row['capex'] == 0


def test_cover_shares_taken_after_period_end():
    rows = pd.DataFrame([
        fact('NetIncomeLoss', '2022-01-01', '2022-12-31', 100, '2023-02-15', '10-K'),
        fact('EntityCommonStockSharesOutstanding', None, '2023-02-01', 50, '2023-02-15', '10-K'),
    ])
    snap = fu.company_snapshots(rows)
    assert snap.loc['2022-12-31', 'cover_shares'] == 50


def snapshots_table():
    return pd.DataFrame({
        'cik': [1, 1, 2],
        'period_end': pd.to_datetime(['2023-03-31', '2023-06-30', '2021-12-31']),
        'known': pd.to_datetime(['2023-05-05', '2023-08-05', '2022-02-15']),
        'ni': [110.0, 115.0, 7.0],
    })


def test_as_of_uses_only_filings_already_public():
    s = snapshots_table()
    assert fu.as_of(s, '2023-08-05').loc[1, 'ni'] == 110     # filed that day: not yet usable
    assert fu.as_of(s, '2023-08-06').loc[1, 'ni'] == 115


def test_as_of_drops_stale_snapshots():
    s = snapshots_table()
    assert 2 in fu.as_of(s, '2022-06-30').index
    assert 2 not in fu.as_of(s, '2023-08-06').index          # period ended 19 months earlier


# ---------------------------------------------------------------- debt

def debt_company(extra):
    ni = 'NetIncomeLoss'
    base = [
        fact(ni, '2025-01-01', '2025-12-31', 100, '2026-02-13', '10-K'),
        fact(ni, '2025-01-01', '2025-03-31', 20, '2025-05-06'),
        fact(ni, '2026-01-01', '2026-03-31', 30, '2026-05-06'),
    ]
    return pd.DataFrame(base + extra)


def test_debt_carried_from_last_complete_balance_sheet():
    # Caterpillar-style: standard debt tags in the 10-K only
    snap = fu.company_snapshots(debt_company([
        fact('LongTermDebtNoncurrent', None, '2025-12-31', 30, '2026-02-13', '10-K'),
        fact('ShortTermBorrowings', None, '2025-12-31', 5, '2026-02-13', '10-K'),
    ]))
    assert snap.loc['2025-12-31', 'debt'] == 35
    assert snap.loc['2026-03-31', 'debt'] == 35


def test_debt_takes_most_complete_candidate():
    snap = fu.company_snapshots(debt_company([
        fact('DebtAndCapitalLeaseObligations', None, '2025-12-31', 17.7, '2026-02-13', '10-K'),
        fact('LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities', None, '2025-12-31',
             17.66, '2026-02-13', '10-K'),
        fact('OperatingLeaseLiability', None, '2025-12-31', 2, '2026-02-13', '10-K'),
    ]))
    assert snap.loc['2025-12-31', 'debt'] == pytest.approx(17.7)
    assert snap.loc['2025-12-31', 'oplease'] == 2


def test_no_debt_tags_means_debt_free():
    snap = fu.company_snapshots(debt_company([]))
    assert snap.loc['2025-12-31', 'debt'] == 0


def test_cover_shares_from_a_later_filing_are_not_used():
    rows = pd.DataFrame([
        fact('NetIncomeLoss', '2022-01-01', '2022-12-31', 100, '2023-02-15', '10-K'),
        # Next filing's cover page, dated within 150 days but public only in May
        fact('EntityCommonStockSharesOutstanding', None, '2023-04-28', 50, '2023-05-05'),
    ])
    snap = fu.company_snapshots(rows)
    assert np.isnan(snap.loc['2022-12-31', 'cover_shares'])
