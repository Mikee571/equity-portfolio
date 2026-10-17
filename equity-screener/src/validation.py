"""
Data validation — flag rows whose fundamentals contradict each other.

Why it matters: a P/E computed on the wrong per-share base does more than
plant a false positive in the top 10. The composite score z-scores every
factor across survivors, so one bad P/E also shifts the mean and standard
deviation that every *other* ticker is scored against. Flagged rows are
therefore taken out before scoring and reported in a quarantine list,
instead of being ranked or silently dropped.

Severities:
    error -> quarantined: excluded from the ranking and the z-score statistics
    warn  -> ranked normally; the flag travels with the row to Excel/Telegram

Checks (thresholds in config.SANITY_BOUNDS and config.VALIDATION):
    OOB_<factor>     error  Value outside config.SANITY_BOUNDS.
    PE_VS_EARNINGS   error  Market cap / P/E must reproduce TTM net income:
                            both are company-level and in the same currency.
                            A 10x gap means the P/E was built from another
                            share line's EPS (SIX:LISPE, 2026-09: P/E 2.4x
                            vs 23.6x on LISP, the same company).
    ROE_SIGN         error  Reported ROE and TTM net income have opposite
                            signs, so ROE and P/E describe different earnings.
    ROE_VS_EQUITY    warn   Reported ROE vs net income TTM / closing equity.
                            The CFA definition is ROE = net income / *average*
                            shareholders' equity, and TradingView's total
                            equity includes minority interests, so a moderate
                            gap is expected (HOC: 37.4% reported vs 26.9%
                            on closing total equity, and the 37.4% is right).
                            Only gross gaps are flagged, for review.
    PEG_BASE_EFFECT  warn   Implied EPS growth (P/E / PEG) above
                            config.PEG_MAX_IMPLIED_GROWTH_PCT: growth
                            measured off a depressed base, so the PEG looks
                            cheap without the stock being cheap. The scoring
                            treats this PEG as neutral (src/screener.py); the
                            flag says so.

A check whose inputs are missing is skipped, not flagged: missing data is
handled by the hard filters, and absence of evidence is not an error.

Limitation: these are internal-consistency checks. An error that is
consistent across fields (e.g. every fundamental stale by a year) passes.
"""

import numpy as np
import pandas as pd

from . import config


# Short labels for OOB_<factor> codes
_LABELS = {
    'price_earnings_ttm': 'PE',
    'return_on_equity_fq': 'ROE',
    'debt_to_equity': 'DE',
    'price_earnings_growth_ttm': 'PEG',
    'free_cash_flow_ttm': 'FCF',
}


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Numeric column, or all-NaN if the field was not fetched."""
    if name in df.columns:
        return pd.to_numeric(df[name], errors='coerce').astype(float)
    return pd.Series(np.nan, index=df.index, dtype=float)


def _ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num / den, NaN wherever the result is not finite."""
    with np.errstate(divide='ignore', invalid='ignore'):
        r = num / den
    return r.where(np.isfinite(r))


def _outside(x: pd.Series, bounds: tuple) -> pd.Series:
    """True where x is known and outside [low, high]."""
    low, high = bounds
    return x.notna() & ((x < low) | (x > high))


def _join(flags: dict, index: pd.Index) -> pd.Series:
    """Collapse {code: bool Series} into one ';'-joined string per row."""
    codes = list(flags)
    hits = [flags[c].to_numpy(dtype=bool, na_value=False) for c in codes]
    return pd.Series(
        [';'.join(c for c, h in zip(codes, row) if h) for row in zip(*hits)]
        if codes else [''] * len(index),
        index=index, dtype=object,
    )


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of df with diagnostic columns added:
        pe_earnings_check   (market cap / P/E) / net income TTM; ~1.0 if consistent
        roe_equity_check    reported ROE / (100 * NI TTM / total equity); ~1.0
        implied_growth_pct  P/E / PEG, the EPS growth the PEG assumes (%)
        data_errors         ';'-joined error codes, '' if none
        data_warnings       ';'-joined warning codes, '' if none
        suspect             True if any error -> goes to quarantine
    """
    out = df.copy()
    cfg = config.VALIDATION
    errors, warnings = {}, {}

    pe = _col(out, 'price_earnings_ttm')
    roe = _col(out, 'return_on_equity_fq')
    peg = _col(out, 'price_earnings_growth_ttm')
    mcap = _col(out, 'market_cap_basic')
    ni = _col(out, 'net_income_ttm')
    equity = _col(out, 'total_equity_fq')

    # 1. Sanity bounds
    for colname, bounds in config.SANITY_BOUNDS.items():
        if colname in out.columns:
            code = f"OOB_{_LABELS.get(colname, colname)}"
            errors[code] = _outside(_col(out, colname), bounds)

    # 2. P/E vs earnings. Only defined for profitable companies.
    implied_ni = _ratio(mcap, pe.where(pe > 0))
    out['pe_earnings_check'] = _ratio(implied_ni, ni.where(ni > 0))
    errors['PE_VS_EARNINGS'] = _outside(out['pe_earnings_check'],
                                        cfg['pe_earnings_ratio'])

    # 3. ROE sign vs net income sign
    roe_sign = roe.notna() & ni.notna() & (np.sign(roe) * np.sign(ni) < 0)
    errors['ROE_SIGN'] = roe_sign

    # 4. ROE vs NI / closing equity (warning only, see module docstring)
    roe_closing = 100 * _ratio(ni, equity.where(equity > 0))
    out['roe_equity_check'] = _ratio(roe, roe_closing)
    gap = (roe - roe_closing).abs()
    warnings['ROE_VS_EQUITY'] = (
        _outside(out['roe_equity_check'], cfg['roe_equity_ratio'])
        & (gap >= cfg['roe_min_gap_pp'])
        & ~roe_sign
    )

    # 5. PEG base effect
    out['implied_growth_pct'] = _ratio(pe.where(pe > 0), peg.where(peg > 0))
    warnings['PEG_BASE_EFFECT'] = (
        out['implied_growth_pct'] > config.PEG_MAX_IMPLIED_GROWTH_PCT
    )

    out['data_errors'] = _join(errors, out.index)
    out['data_warnings'] = _join(warnings, out.index)
    out['suspect'] = out['data_errors'] != ''
    return out


def flag_counts(df: pd.DataFrame) -> dict:
    """Count occurrences of each flag code across data_errors and data_warnings."""
    counts = {}
    for colname in ('data_errors', 'data_warnings'):
        if colname not in df.columns:
            continue
        for cell in df[colname]:
            for code in filter(None, str(cell).split(';')):
                counts[code] = counts.get(code, 0) + 1
    return counts
