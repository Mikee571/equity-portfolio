"""
Tests for universe cleaning (src/universe.py). No network: clean_universe
is fed a hand-built frame that mirrors real TradingView rows.

Run with:
    python -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src import universe


def row(name, description, exchange, country, mcap, traded=1e6,
        sector='Technology Services', type_='stock'):
    return {'name': name, 'description': description, 'exchange': exchange,
            'country': country, 'market_cap_basic': mcap, 'Value.Traded': traded,
            'sector': sector, 'type': type_}


@pytest.fixture
def cleaned():
    raw = pd.DataFrame([
        # Regression: 'Unit' / 'Right' substrings used to drop these
        row('UNH', 'UnitedHealth Group Incorporated', 'NYSE', 'United States', 3.4e11),
        row('UPS', 'United Parcel Service, Inc.', 'NYSE', 'United States', 7.9e10),
        row('CW', 'Curtiss-Wright Corporation', 'NYSE', 'United States', 2.0e10),
        row('RMV', 'Rightmove plc', 'LSE', 'United Kingdom', 3.2e9),
        # Non-equity structures
        row('FOOU', 'Foo Acquisition Corp - Units', 'NASDAQ', 'United States', 1.1e9),
        row('FOOR', 'Foo Acquisition Corp - Rights', 'NASDAQ', 'United States', 1.2e9),
        row('CMSD', 'CMS Energy Corporation 5.875% Junior Subordinated Notes due 2079',
            'NYSE', 'United States', 2.0e10),
        row('DTK', 'DTE Energy Company 2025 Series H 6.25% Junior Subordinated '
                   'Debentures due 2085', 'NYSE', 'United States', 2.6e10),
        row('49GP', 'Croda International PLC 6.6 % Cum Pref', 'LSE', 'United Kingdom',
            4.6e9, traded=0),
        row('CRDA', 'Croda International Plc', 'LSE', 'United Kingdom', 4.6e9, traded=2.9e7),
        # Lindt: three lines, one temporary, identical company-level market cap
        row('LISN', 'Chocoladefabriken Lindt & Spruengli AG', 'SIX', 'Switzerland',
            1.747e10, traded=1.7e7),
        row('LISP', 'Chocoladefabriken Lindt & Spruengli AG Partizipsch.', 'SIX',
            'Switzerland', 1.747e10, traded=2.97e7),
        row('LISPE', 'Chocoladefabriken Lindt & Spruengli AG TEMP', 'SIX',
            'Switzerland', 1.747e10, traded=1.6e6),
        # Logitech: TEMP line with the same description root
        row('LOGN', 'Logitech International S.A.', 'SIX', 'Switzerland', 1.19e10,
            traded=3.9e7),
        row('LOGNE', 'Logitech International S.A. TEMP', 'SIX', 'Switzerland', 1.19e10,
            traded=2.5e6),
        # German preference shares are real equity: keep the more liquid line
        row('VOW3', 'Volkswagen AG Pref', 'XETR', 'Germany', 5.0e10, traded=1.5e8),
        row('VOW', 'Volkswagen AG', 'XETR', 'Germany', 5.0e10, traded=5e6),
        # Existing rules still apply
        row('UNH_DE', 'UnitedHealth Group Incorporated', 'XETR', 'United States', 3.0e11),
        row('JPM', 'JPMorgan Chase & Co.', 'NYSE', 'United States', 6e11, sector='Finance'),
    ])
    return set(universe.clean_universe(raw)['name'])


@pytest.mark.parametrize('name', ['UNH', 'UPS', 'CW', 'RMV'])
def test_word_substrings_do_not_drop_real_companies(cleaned, name):
    assert name in cleaned


@pytest.mark.parametrize('name', ['FOOU', 'FOOR', 'CMSD', 'DTK', '49GP'])
def test_non_equity_listings_dropped(cleaned, name):
    assert name not in cleaned


def test_temp_lines_dropped(cleaned):
    assert 'LISPE' not in cleaned
    assert 'LOGNE' not in cleaned
    assert 'LOGN' in cleaned


def test_one_line_per_company_most_traded_kept(cleaned):
    assert {'LISN', 'LISP'} & cleaned == {'LISP'}
    assert {'VOW', 'VOW3'} & cleaned == {'VOW3'}
    assert 'CRDA' in cleaned


def test_secondary_listing_and_financials_dropped(cleaned):
    assert 'UNH_DE' not in cleaned
    assert 'JPM' not in cleaned


def test_dropped_rows_carry_reasons():
    raw = pd.DataFrame([
        row('LISN', 'Chocoladefabriken Lindt & Spruengli AG', 'SIX', 'Switzerland', 1.747e10, traded=1.7e7),
        row('LISP', 'Chocoladefabriken Lindt & Spruengli AG Partizipsch.', 'SIX', 'Switzerland',
            1.747e10, traded=2.97e7),
        row('LISPE', 'Chocoladefabriken Lindt & Spruengli AG TEMP', 'SIX', 'Switzerland', 1.747e10),
        row('UNH_DE', 'UnitedHealth Group Incorporated', 'XETR', 'United States', 3.0e11),
        row('JPM', 'JPMorgan Chase & Co.', 'NYSE', 'United States', 6e11, sector='Finance'),
    ])
    clean, dropped = universe.clean_universe(raw, return_dropped=True)
    assert list(clean['name']) == list(universe.clean_universe(raw)['name']) == ['LISP']
    why = dropped.set_index('name')
    assert why.loc['LISPE', 'drop_reason'] == 'no_temp_lines'
    assert why.loc['UNH_DE', 'drop_reason'] == 'primary_listing'
    assert why.loc['JPM', 'drop_reason'] == 'no_financials'
    assert why.loc['LISN', 'drop_reason'] == 'dedup_same_mcap'
    assert why.loc['LISN', 'kept_instead'] == 'LISP'
    assert set(why['drop_reason']) <= set(universe.CLEANING_REASONS)


def test_market_exchanges():
    assert universe.market_exchanges('america') == ['NASDAQ', 'NYSE', 'AMEX']
    assert universe.market_exchanges('germany') == ['XETR', 'FWB']
    assert universe.market_exchanges('netherlands') == ['EURONEXT']


class FakeQuery:
    """Stands in for tradingview_screener.Query: serves `rows` by range."""
    rows, calls = [], []

    def __init__(self):
        self.start, self.end = 0, 50

    def set_markets(self, *a): return self
    def select(self, *a): return self
    def where(self, *a): return self
    def order_by(self, *a, **k): return self

    def offset(self, n):
        self.start = n
        return self

    def limit(self, n):
        self.end = n
        return self

    def get_scanner_data(self):
        FakeQuery.calls.append((self.start, self.end))
        page = FakeQuery.rows[self.start:self.end]
        return len(FakeQuery.rows), pd.DataFrame(page, columns=['ticker', 'name'])


def test_fetch_market_paginates_until_count(monkeypatch):
    FakeQuery.rows = [(f'X:T{i}', f'T{i}') for i in range(12)]
    FakeQuery.calls = []
    monkeypatch.setattr(universe, 'Query', FakeQuery)
    monkeypatch.setattr(universe, 'PAGE_SIZE', 5)
    df, count = universe.fetch_market('america')
    assert count == 12 and len(df) == 12
    assert FakeQuery.calls == [(0, 5), (5, 10), (10, 15)]    # range = [start, end)
    assert (df['market'] == 'america').all()


def test_fetch_market_dedups_rows_repeated_across_pages(monkeypatch):
    # Tied market caps can reorder between requests, repeating a row
    rows = [(f'X:T{i}', f'T{i}') for i in range(6)]
    FakeQuery.rows = rows[:5] + [rows[4]] + rows[5:]          # T4 served twice
    monkeypatch.setattr(universe, 'Query', FakeQuery)
    monkeypatch.setattr(universe, 'PAGE_SIZE', 5)
    df, count = universe.fetch_market('america')
    assert df['ticker'].is_unique and len(df) == 6 and count == 7
