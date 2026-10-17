"""
Five-factor screener — hard filters + data validation + composite score ranking.

Pipeline:
    1. Drop tickers with missing five-factor data (PEG = 0.00 counts as missing).
    2. Validate: flag internally inconsistent rows (src/validation.py).
    3. Apply the five thresholds.
    4. Quarantine survivors with a data error; they never reach step 5.
    5. Build score inputs (FCF yield, PEG neutral on base effect), winsorise, and z-score
       each factor across the clean survivors.
    6. Combine into a weighted composite score (config.SCORE_WEIGHTS).
    7. Rank descending and return.
"""

import numpy as np
import pandas as pd

from . import config, validation


# Raw TradingView fields behind each factor: required for a ticker to be
# screened, used by the thresholds, and stored in the weekly history.
FACTOR_COLS = {
    'pe': 'price_earnings_ttm',
    'roe': 'return_on_equity_fq',
    'de': 'debt_to_equity',
    'peg': 'price_earnings_growth_ttm',
    'fcf': 'free_cash_flow_ttm',
}

# Factors where a LOWER value is better. Their z-score is inverted before
# weighting so that "higher composite score = better" is uniform.
LOWER_IS_BETTER = {'pe', 'de', 'peg'}

# History rows written before v0.7 were scored on raw values (absolute FCF,
# PEG used as reported, no winsorisation). See src/history.py.
LEGACY_MODEL = 'pre-0.7'


EPS_GROWTH_COL = 'earnings_per_share_diluted_yoy_growth_ttm'


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Copy with PEG = 0.00 turned into NaN: TradingView's code for "no data"."""
    df = df.copy()
    peg = FACTOR_COLS['peg']
    if peg in df.columns:
        df[peg] = df[peg].mask(df[peg] == 0)
    return df


def missing_data_reason(df: pd.DataFrame) -> pd.Series:
    """
    Why a row lacks a five-factor field ('' if it doesn't). Most gaps are
    economic, not data problems:
        loss-making  P/E is undefined for negative TTM earnings
        EPS falling  PEG = P/E / EPS growth is undefined when growth <= 0
        data gap     anything else
    Expects PEG zeros already turned into NaN (see prepare()).
    """
    missing = df[list(FACTOR_COLS.values())].isna().any(axis=1)
    reason = pd.Series('', index=df.index, dtype=object)
    reason[missing] = 'data gap'
    pe, peg = df[FACTOR_COLS['pe']], df[FACTOR_COLS['peg']]
    if EPS_GROWTH_COL in df.columns:
        reason[missing & peg.isna() & pe.notna() & (df[EPS_GROWTH_COL] <= 0)] = 'EPS falling'
    if 'net_income_ttm' in df.columns:
        reason[missing & pe.isna() & (df['net_income_ttm'] <= 0)] = 'loss-making'
    return reason


def threshold_checks(df: pd.DataFrame) -> pd.DataFrame:
    """
    One boolean column per five-factor threshold (True = passes).
    Note: TradingView returns ROE as a percentage (48.67 = 48.67%),
    so ROE_MIN is compared against percent values directly.
    """
    pe, peg = df['price_earnings_ttm'], df['price_earnings_growth_ttm']
    return pd.DataFrame({
        f'P/E < {config.PE_MAX:g}': (pe > 0) & (pe < config.PE_MAX),
        f'ROE > {config.ROE_MIN:g}%': df['return_on_equity_fq'] > config.ROE_MIN,
        f'D/E < {config.DE_MAX:g}': df['debt_to_equity'] < config.DE_MAX,
        f'0 < PEG < {config.PEG_MAX:g}': (peg > 0) & (peg < config.PEG_MAX),
        f'FCF > {config.FCF_MIN:g}': df['free_cash_flow_ttm'] > config.FCF_MIN,
    }, index=df.index)


def apply_hard_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop tickers with any missing five-factor field, validate the rest, then
    apply the thresholds. Returns every row that clears the thresholds, with
    the validation columns attached (data_errors, data_warnings, suspect).
    Rows with suspect=True still have to be split off before scoring; see
    split_quarantine().
    """
    initial = len(df)
    df = prepare(df)

    # Drop rows with any NaN in the required fields, reporting why
    reasons = missing_data_reason(df)
    counts = reasons[reasons != ''].value_counts()
    df = df[reasons == ''].copy()
    detail = ', '.join(f"{n} {r}" for r, n in counts.items())
    print(f"\nHard filters:")
    print(f"  Universe:            {initial:5d}")
    print(f"  Complete data:       {len(df):5d} ({initial - len(df)} dropped"
          f"{': ' + detail if detail else ''})")

    # Data validation — flags, never drops
    df = validation.validate(df)
    n_errors = int(df['suspect'].sum())
    n_warnings = int((df['data_warnings'] != '').sum())
    print(f"  Validation flags:    {n_errors:5d} with errors, {n_warnings} with warnings")

    # Apply five-factor thresholds. Out-of-bounds values are not filtered
    # here: they are flagged OOB_* above and end up in quarantine if they
    # would otherwise have passed.
    survivors = df[threshold_checks(df).all(axis=1)].copy()

    print(f"  After five-factor:   {len(survivors):5d} rejected: "
          f"{len(df) - len(survivors)}")

    return survivors


def split_quarantine(survivors: pd.DataFrame) -> tuple:
    """
    Split threshold survivors into (clean, quarantine). Quarantined rows
    passed every threshold but failed a data check: they would have ranked
    on numbers we have reason to distrust.
    """
    suspect = survivors['suspect'].astype(bool)
    clean = survivors[~suspect].copy()
    quarantine = survivors[suspect].reset_index(drop=True)
    print(f"  Quarantined:         {len(quarantine):5d} -> ranked: {len(clean)}")
    return clean, quarantine


def score_inputs(df: pd.DataFrame, legacy: bool = False) -> pd.DataFrame:
    """
    The value each factor is scored on, one column per factor key.

        fcf: FCF yield = FCF TTM / market cap. Absolute FCF ranks companies
             by size (Alphabet's $53B at a 1.3% yield above CF's $1.9B at
             10.9%) and mixes reporting currencies; the yield is the
             inverse of P/FCF, a standard price multiple, and is
             currency-free because both terms are in the same currency.
        peg: the raw PEG, or NaN when the implied EPS growth (P/E / PEG)
             exceeds PEG_MAX_IMPLIED_GROWTH_PCT. Such growth comes off a
             depressed base; the PEG is not measurable and scores a neutral
             z = 0 (see apply_zscore). A floor at P/E / 100 was tried first
             and rejected: on the full universe it made the floored PEG a
             copy of P/E (z correlation 0.99), crediting cheapness twice.
        others: the raw field.

    legacy=True returns the pre-v0.7 inputs (all raw), used only to
    decompose score changes inside old history windows.
    """
    inputs = pd.DataFrame({f: pd.to_numeric(df[c], errors='coerce').astype(float)
                           for f, c in FACTOR_COLS.items()}, index=df.index)
    if not legacy:
        inputs['fcf'] = (pd.to_numeric(df['free_cash_flow_ttm'], errors='coerce')
                         / pd.to_numeric(df['market_cap_basic'], errors='coerce'))
        implied_growth = inputs['pe'] / inputs['peg']
        inputs['peg'] = inputs['peg'].mask(implied_growth > config.PEG_MAX_IMPLIED_GROWTH_PCT)
    return inputs


def fit_zscore(inputs: pd.DataFrame, legacy: bool = False) -> pd.DataFrame:
    """
    Standardisation parameters per factor: winsorisation bounds (lo, hi)
    from config.WINSOR_QUANTILES, then the mean and population std of the
    winsorised values. Index = factor key, columns = lo, hi, mean, std.
    NaN inputs (non-measurable PEG) are left out of every statistic.
    """
    q = None if legacy else config.WINSOR_QUANTILES
    params = {}
    for f in inputs.columns:
        x = inputs[f]
        lo, hi = (x.quantile(q[0]), x.quantile(q[1])) if q else (-np.inf, np.inf)
        clipped = x.clip(lo, hi)
        params[f] = {'lo': lo, 'hi': hi,
                     'mean': clipped.mean(), 'std': clipped.std(ddof=0)}
    return pd.DataFrame(params).T


def apply_zscore(inputs: pd.DataFrame, params: pd.DataFrame) -> pd.DataFrame:
    """
    Signed z-scores (higher = better) of inputs under fitted params.
    A NaN input gets z = 0: neutral, neither credited nor penalised.
    """
    z = {}
    for f in inputs.columns:
        p = params.loc[f]
        x = inputs[f].clip(p['lo'], p['hi'])
        zf = (x - p['mean']) / p['std'] if p['std'] > 0 else x * 0
        z[f] = (-zf if f in LOWER_IS_BETTER else zf).fillna(0.0)
    return pd.DataFrame(z, index=inputs.index)


def compute_composite_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute z-scored composite ranking. Adds columns:
        - fcf_yield, peg_scored: the FCF and PEG values actually scored
          (peg_scored is NaN where the PEG was treated as neutral)
        - z_<factor>: signed z-score (already inverted for lower-is-better)
        - score: weighted composite (higher = better)

    z-score (standardisation, CFA Level I Quantitative Methods):
        z = (x - mean) / std
    The mean and std are taken across the survivors being ranked, with the
    population std (ddof=0): the survivors are the whole cross-section being
    compared, not a sample drawn from a larger one. A factor with zero
    dispersion carries no ranking information and gets z = 0.

    Winsorisation (CFA Level I, measures of central tendency): before the
    mean and std are computed, values beyond the 5th/95th percentiles are
    set to those percentiles. The extreme ticker keeps the best (or worst)
    z, but no longer stretches the scale for everyone else: until v0.7,
    WDC's 131% ROE cut GTT's ROE z from 4.3 to 2.5 with GTT's ROE unchanged.

    Because mean and std are shared, one bad value moves every ticker's z,
    which is why quarantined rows are removed before this step.
    """
    if df.empty:
        df['score'] = []
        return df

    df = df.copy()
    inputs = score_inputs(df)
    z = apply_zscore(inputs, fit_zscore(inputs))

    df['fcf_yield'] = inputs['fcf']
    df['peg_scored'] = inputs['peg']
    for factor in FACTOR_COLS:
        df[f'z_{factor}'] = z[factor]

    # Weighted sum
    df['score'] = sum(
        df[f'z_{factor}'] * config.SCORE_WEIGHTS[factor]
        for factor in FACTOR_COLS
    )

    return df.sort_values('score', ascending=False).reset_index(drop=True)


def run_screener(universe: pd.DataFrame) -> tuple:
    """
    End-to-end: filter -> validate -> quarantine -> score -> rank.

    Returns:
        ranked:     clean survivors, ranked by composite score
        quarantine: survivors held back by a data error (see src/validation.py)
    """
    survivors = apply_hard_filters(universe)
    clean, quarantine = split_quarantine(survivors)
    ranked = compute_composite_score(clean)
    return ranked, quarantine
