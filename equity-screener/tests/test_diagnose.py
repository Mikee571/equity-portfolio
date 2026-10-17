"""
Tests for src/diagnose.py: each listing is attributed to the stage where it
drops out. No network: explain() gets a hand-built universe.

Run with:
    python -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src import diagnose


def listing(name, pe=10.0, roe=25.0, de=0.3, peg=0.8, fcf=1e9, mcap=20e9,
            ni=None, growth=12.0, exchange='NYSE', country='United States',
            sector='Producer Manufacturing', description=None):
    ni = mcap / pe if ni is None and pe == pe else ni
    return {'ticker': f'{exchange}:{name}', 'name': name, 'description': description or f'{name} Inc.',
            'exchange': exchange, 'country': country, 'type': 'stock', 'sector': sector,
            'close': 100.0, 'market_cap_basic': mcap, 'Value.Traded': 1e7,
            'price_earnings_ttm': pe, 'return_on_equity_fq': roe, 'debt_to_equity': de,
            'price_earnings_growth_ttm': peg, 'free_cash_flow_ttm': fcf,
            'net_income_ttm': ni, 'total_equity_fq': ni / (roe / 100) if ni else None,
            'earnings_per_share_diluted_yoy_growth_ttm': growth}


def test_explain_attributes_each_stage():
    raw = pd.DataFrame([
        listing('GOOD'), listing('ALSO', pe=12.0, mcap=24e9),
        listing('PLTR', pe=163.7, peg=0.56, mcap=4.6e11),                    # threshold
        listing('CAT', pe=37.1, de=2.33, peg=2.0, mcap=4.0e11),              # threshold x3
        listing('LOSS', pe=float('nan'), peg=0.0, ni=-5e8, mcap=5e9),        # loss-making
        listing('FALL', peg=0.0, growth=-20.0, mcap=6e9),                    # EPS falling
        listing('BAD', pe=2.4, mcap=17e9, ni=7e8),                           # quarantine
        listing('BANK', sector='Finance'),                                   # cleaning
    ])
    listings = pd.DataFrame([
        {'name': 'TINY', 'exchange': 'NASDAQ', 'country': 'United States', 'market_cap_basic': 4e8},
        {'name': 'ADR', 'exchange': 'OTC', 'country': 'Japan', 'market_cap_basic': 5e10},
    ])
    table = diagnose.explain(['GOOD', 'PLTR', 'CAT', 'LOSS', 'FALL', 'BAD', 'BANK', 'TINY', 'ADR', 'NONE'],
                             raw, listings).set_index('name')

    assert table.loc['GOOD', 'stage'] == 'ranked'
    assert table.loc['GOOD', 'detail'].startswith('#')
    assert table.loc['PLTR', 'stage'] == 'threshold'
    assert table.loc['PLTR', 'detail'] == 'P/E < 20 (is 163.7)'
    assert table.loc['CAT', 'detail'].count(';') == 2                    # P/E, D/E, PEG
    assert table.loc['LOSS', 'detail'].startswith('loss-making')
    assert table.loc['FALL', 'detail'].startswith('EPS falling')
    assert table.loc['BAD', 'stage'] == 'quarantine'
    assert 'PE_VS_EARNINGS' in table.loc['BAD', 'detail']
    assert table.loc['BANK', 'stage'] == 'cleaning'
    assert 'financial' in table.loc['BANK', 'detail']
    assert table.loc['TINY', 'stage'] == 'not fetched'
    assert 'below the 1B floor' in table.loc['TINY', 'detail']
    assert 'no domestic listing' in table.loc['ADR', 'detail']
    assert table.loc['NONE', 'detail'] == 'not found in the screened markets'
