"""
Monthly cross-sections in the live screener's format.

Each month-end, every company's latest public snapshot (fundamentals.as_of)
is combined with that day's price into the TradingView columns that
src/screener.py reads, so the backtest runs the live screener unchanged:
same thresholds, validation, quarantine and scoring.

Definitions (TradingView's, as far as XBRL allows; see calibrate()):
    price_earnings_ttm       close / diluted EPS TTM (NI / diluted shares where EPS
                             is not tagged); NaN when EPS <= 0
    earnings_per_share_diluted_yoy_growth_ttm
                             EPS TTM vs one year earlier, in %; NaN when the
                             earlier EPS <= 0
    price_earnings_growth_ttm  P/E / that growth; NaN when growth <= 0
    return_on_equity_fq      net income TTM / average equity (now and one
                             year earlier), in %
    debt_to_equity           total debt / equity, total debt per DEBT_VARIANT
    free_cash_flow_ttm       operating cash flow TTM - capex TTM
    market_cap_basic         close x shares outstanding (cover page, else
                             diluted weighted average)
"""

import numpy as np
import pandas as pd

from . import fundamentals

# Chosen by calibrate() on 2026-10-07: TradingView's total debt includes
# operating lease liabilities (median ratio to TradingView 1.00 with them,
# ~0.6 without). They are on the balance sheet only since 2019 (ASC 842).
DEBT_VARIANT = 'debt_oplease'
DEBT_VARIANTS = ('debt', 'debt_oplease')

ID_COLS = ['name', 'description', 'sector', 'industry', 'country', 'exchange', 'type',
           'ticker', 'symbol', 'cik']


def debt_total(snap: pd.DataFrame, variant: str = DEBT_VARIANT) -> pd.Series:
    """Total debt (fundamentals.debt_by_date), plus operating leases under 'debt_oplease'."""
    return snap['debt'] + (snap['oplease'] if variant == 'debt_oplease' else 0)


def tradingview_columns(snap: pd.DataFrame, close: pd.Series,
                        debt_variant: str = DEBT_VARIANT) -> pd.DataFrame:
    """
    The screener's input columns from snapshots (index = cik) and a close
    price per cik (today's share basis).
    """
    close = close.reindex(snap.index)
    # EPS from net income / diluted shares where the company does not tag
    # EPS (multi-class issuers report it per class, a dimension the SEC's
    # company facts leave out; some tag it in the 10-K only).
    eps = snap['eps'].fillna(snap['ni'] / snap['diluted_shares'])
    eps_prev = snap['eps_prev'].fillna(snap['ni_prev'] / snap['diluted_shares_prev'])
    pe = (close / eps).where(eps > 0)
    growth = ((eps / eps_prev - 1) * 100).where(eps_prev > 0)
    peg = (pe / growth).where(growth > 0)
    avg_equity = (snap['equity'] + snap['equity_prev'].fillna(snap['equity'])) / 2
    shares = snap['cover_shares'].fillna(snap['diluted_shares'])
    return pd.DataFrame({
        'close': close,
        'market_cap_basic': close * shares,
        'price_earnings_ttm': pe,
        'return_on_equity_fq': snap['ni'] / avg_equity * 100,
        'debt_to_equity': debt_total(snap, debt_variant) / snap['equity'],
        'price_earnings_growth_ttm': peg,
        'free_cash_flow_ttm': snap['cfo'] - snap['capex'],
        'net_income_ttm': snap['ni'],
        'total_equity_fq': snap['equity_total'],
        'earnings_per_share_diluted_yoy_growth_ttm': growth,
        'period_end': snap['period_end'],
        'known': snap['known'],
        'capex_reported': snap['capex_reported'],
    }, index=snap.index)


def cross_section(snapshots: pd.DataFrame, date, close_by_cik: pd.Series,
                  universe: pd.DataFrame, debt_variant: str = DEBT_VARIANT) -> pd.DataFrame:
    """One date's cross-section: identity columns + screener inputs, one row per company."""
    snap = fundamentals.as_of(snapshots, date)
    cols = tradingview_columns(snap, close_by_cik, debt_variant)
    ident = universe[ID_COLS].set_index('cik')
    out = ident.join(cols, how='inner')
    out = out[out['close'].notna()]
    return out.reset_index()


def calibrate(snapshots: pd.DataFrame, universe: pd.DataFrame, close_by_cik: pd.Series,
              date) -> pd.DataFrame:
    """
    Reconstructed factors vs TradingView's current values for the same
    companies (universe holds TradingView's fields as fetched today).
    One row per factor: coverage, rank correlation, median ratio, share of
    companies within 10% and 25%, and agreement on the screener threshold.
    """
    from .. import config  # thresholds of the live screener
    tv = universe.set_index('cik')
    rows = []
    for variant in DEBT_VARIANTS:
        rec = tradingview_columns(fundamentals.as_of(snapshots, date), close_by_cik, variant)
        both = rec.join(tv, how='inner', rsuffix='_tv')
        checks = {
            'market_cap_basic': lambda x: x > config.MARKET_CAP_MIN,
            'price_earnings_ttm': lambda x: (x > 0) & (x < config.PE_MAX),
            'return_on_equity_fq': lambda x: x > config.ROE_MIN,
            'debt_to_equity': lambda x: x < config.DE_MAX,
            'price_earnings_growth_ttm': lambda x: (x > 0) & (x < config.PEG_MAX),
            'free_cash_flow_ttm': lambda x: x > config.FCF_MIN,
        }
        for field, passes in checks.items():
            if variant != DEBT_VARIANTS[0] and field != 'debt_to_equity':
                continue
            a, b = both[field], both[f'{field}_tv']
            ok = a.notna() & b.notna()
            ratio = (a[ok] / b[ok]).replace([np.inf, -np.inf], np.nan)
            rows.append({
                'factor': field if field != 'debt_to_equity' else f'debt_to_equity [{variant}]',
                'n_tv': int(b.notna().sum()),
                'coverage': ok.sum() / max(b.notna().sum(), 1),
                'rank_corr': a[ok].rank().corr(b[ok].rank()),
                'median_ratio': ratio.median(),
                'within_10pct': ((ratio - 1).abs() <= 0.10).mean(),
                'within_25pct': ((ratio - 1).abs() <= 0.25).mean(),
                'threshold_agree': (passes(a[ok]) == passes(b[ok])).mean(),
            })
    return pd.DataFrame(rows)
