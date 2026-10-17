"""
Universe fetcher — pulls the raw investable universe from TradingView.

Responsibilities:
    - Build the Query for each market (US + Europe)
    - Fetch all fields needed for the five-factor screener
    - Return a clean pandas DataFrame with normalized columns
    - Exclude financials, ADRs, preferred shares, listed debt, temporary
      trading lines, and duplicated classes
"""

import logging

import pandas as pd
from tradingview_screener import Query, col

from . import config

log = logging.getLogger(__name__)


# Fields to fetch. Names verified against tradingview-screener 3.2.1.
FIELDS = [
    'name',
    'description',
    'close',
    'market_cap_basic',
    'sector',
    'industry',
    'country',
    'exchange',
    'type',
    'price_earnings_ttm',
    'return_on_equity_fq',
    'debt_to_equity',
    'price_earnings_growth_ttm',
    'free_cash_flow_ttm',
    # Cross-check inputs for src/validation.py
    'net_income_ttm',
    'total_equity_fq',
    # Explains a missing PEG: TradingView's PEG = P/E / this growth, so it
    # is undefined when EPS fell (screener.missing_data_reason)
    'earnings_per_share_diluted_yoy_growth_ttm',
    # Liquidity, used to pick one line per company in clean_universe
    'Value.Traded',
]

# Description patterns for listings that are not common equity, matched
# case-insensitively. Word boundaries matter: a bare 'Unit' or 'Right'
# substring removed UnitedHealth, UPS, United Airlines, Unity,
# Curtiss-Wright, BrightSpring and Rightmove until v0.7.
# 'Pref' alone is NOT excluded: German Vorzugsaktien (VOW3, HEN3) and
# Swiss participation certificates (SCHP) are real equity.
NON_EQUITY_PATTERNS = [
    r'Depositary', r'Preferred', r'Convertible',
    r'\bWarrants?\b', r'\bRights\b', r'\bUnits\b',
    # Exchange-listed debt (e.g. CMS Energy Junior Subordinated Notes on NYSE)
    r'\bNotes\b', r'\bDebentures?\b', r'\bSubordinated\b',
    # Fixed-dividend preference shares (e.g. Croda 6.6% Cum Pref)
    r'\bCum(?:ulative)?\.? Pref',
]

# SIX opens temporary trading lines (description ending in 'TEMP', ticker
# usually suffixed 'E') around corporate actions. Their per-share data can
# belong to another line: SIX:LISPE carried LISN's EPS (3,179 CHF) against
# a LISP-level price, giving a P/E of 2.4x instead of ~24x.
TEMP_LINE_PATTERN = r'\bTEMP$'


# Rows per request. Above every market's current count, so one request per
# market in practice; pagination is only a fallback.
PAGE_SIZE = 5000


def market_exchanges(market: str) -> list:
    """Domestic exchanges for a market, from config.EXCHANGE_COUNTRY."""
    country = config.MARKET_COUNTRY[market]
    return [ex for ex, countries in config.EXCHANGE_COUNTRY.items()
            if country in countries]


def fetch_market(market: str) -> tuple:
    """
    Fetch one market's investable universe with all five-factor fields.

    Only the market's domestic exchanges are requested, and results are
    paginated until TradingView's reported count is reached. Rows can
    reorder between requests when market caps tie (share classes of one
    issuer), so pages are de-duplicated by ticker.

    Returns (df, count): count is the number of rows TradingView reports as
    matching. len(df) < count means the fetch was incomplete.
    """
    frames, start, count = [], 0, 0
    while True:
        query = (Query()
                 .set_markets(market)
                 .select(*FIELDS)
                 .where(col('market_cap_basic') > config.MARKET_CAP_MIN,
                        col('exchange').isin(market_exchanges(market)))
                 .order_by('market_cap_basic', ascending=False)
                 .offset(start)
                 .limit(start + PAGE_SIZE))   # TradingView range = [start, end)
        count, page = query.get_scanner_data()
        frames.append(page)
        start += PAGE_SIZE
        if page.empty or start >= count:
            break

    df = pd.concat(frames, ignore_index=True).drop_duplicates('ticker')
    df['market'] = market
    return df.reset_index(drop=True), count


def fetch_universe() -> pd.DataFrame:
    """Fetch the combined US + Europe universe."""
    frames = []
    for market in config.MARKETS:
        try:
            df, count = fetch_market(market)
            frames.append(df)
            print(f"  {market:15s}: {len(df):5d} tickers")
            if len(df) < count:
                # logging, not print: run_weekly.py only keeps the log file
                log.warning(f"{market}: incomplete fetch, {len(df)} of {count} matching rows")
        except Exception as e:
            print(f"  {market:15s}: FAILED ({e})")
            log.error(f"{market}: fetch FAILED ({e})")

    if not frames:
        raise RuntimeError("No markets returned data. Check network / TradingView status.")

    return pd.concat(frames, ignore_index=True)


# Plain-language reason for each cleaning stage (used by src/diagnose.py)
CLEANING_REASONS = {
    'common_stock_only': 'not common stock (TradingView type)',
    'no_preferred': 'preferred share ticker (/P)',
    'no_financials': 'financial sector, excluded by design',
    'no_derivatives': 'not common equity (depositary, preferred, notes, units...)',
    'no_temp_lines': 'temporary trading line (SIX TEMP)',
    'primary_listing': 'secondary listing: exchange is not domestic for its country',
    'dedup_by_company': 'another share class of the same company was kept',
    'dedup_same_mcap': 'another line of the same company was kept',
}


def clean_universe(df: pd.DataFrame, return_dropped: bool = False):
    """
    Filter to primary exchanges, remove ADR duplicates, preferred shares,
    non-common-stock, and financials.

    With return_dropped=True, also returns the removed rows with a
    `drop_reason` column (a CLEANING_REASONS key) and, for de-duplicated
    lines, `kept_instead` (the ticker kept for that company).
    """
    initial = len(df)
    stages = {}
    dropped = []
    ident = 'ticker' if 'ticker' in df.columns else 'name'

    def keep(frame, mask, stage):
        mask = pd.Series(mask, index=frame.index).astype(bool)
        dropped.append(frame.loc[~mask].assign(drop_reason=stage))
        out = frame.loc[mask].copy()
        stages[stage] = len(out)
        return out

    def dedup(frame, key, stage):
        kept = frame.groupby(key, sort=False)[ident].transform('first')
        is_dup = frame.duplicated(subset=key, keep='first')
        dropped.append(frame.loc[is_dup].assign(drop_reason=stage,
                                                kept_instead=kept[is_dup]))
        out = frame.loc[~is_dup].copy()
        stages[stage] = len(out)
        return out

    # 1. Keep only common stock
    if 'type' in df.columns:
        df = keep(df, df['type'] == 'stock', 'common_stock_only')

    # 2. Drop preferred shares (tickers with /P, /PA, /PB, /PK, etc.)
    df = keep(df, ~df['name'].str.contains(r'/P', regex=True, na=False), 'no_preferred')

    # 3. Drop excluded sectors
    df = keep(df, ~df['sector'].isin(config.EXCLUDED_SECTORS), 'no_financials')

    # 3b. Drop preferred/convertible/depositary structures and listed debt
    # detected by description keywords. TradingView labels these as
    # type=stock but they are not common equity (e.g. GOOGN = Alphabet
    # Series B convertible preferred depositary shares).
    pattern = '|'.join(NON_EQUITY_PATTERNS)
    df = keep(df, ~df['description'].str.contains(pattern, case=False, na=False, regex=True),
              'no_derivatives')

    # 3c. Drop temporary trading lines (see TEMP_LINE_PATTERN)
    df = keep(df, ~df['description'].str.contains(TEMP_LINE_PATTERN, na=False, regex=True),
              'no_temp_lines')

    # 4. Primary listing only: exchange must be a domestic venue for the
    # ticker's country of incorporation. Eliminates all secondary listings
    # (Alphabet on LSE, Teradata on LSE, US ADRs in Xetra, etc.)
    primary = [config.EXCHANGE_COUNTRY.get(ex) is not None
               and country in config.EXCHANGE_COUNTRY[ex]
               for ex, country in zip(df['exchange'], df['country'])]
    df = keep(df, primary, 'primary_listing')

    # 5. Deduplicate share classes of the same company. Multiple classes
    # (e.g. GOOGL vs GOOG, both "Alphabet Inc.") share the exact same
    # description root. Keep the highest market-cap class per company,
    # and among equal market caps the most traded line.
    sort_cols = ['market_cap_basic'] + (['Value.Traded'] if 'Value.Traded' in df.columns else [])
    df = df.sort_values(sort_cols, ascending=False).copy()
    # Company root = description up to first comma, "Class", or " - "
    df['_company_root'] = (df['description']
                           .str.split(r',| Class | - ', n=1, regex=True).str[0]
                           .str.strip().str.upper())
    df = dedup(df, ['_company_root'], 'dedup_by_company')

    # 6. Same issuer, differently worded descriptions (LISN "...AG" vs LISP
    # "...AG Partizipsch.", UHR "Bearer" vs UHRN "Registered", WBD vs WBDR
    # savings shares). TradingView reports market cap at company level, so
    # every line of one issuer carries the identical figure. Keep the first
    # (= most traded, given the sort above).
    df = dedup(df, ['country', 'market_cap_basic'], 'dedup_same_mcap')
    df = df.drop(columns=['_company_root'])

    print(f"\nCleaning stages:")
    print(f"  Initial:                {initial:5d}")
    for stage, n in stages.items():
        print(f"  {stage:22s}  {n:5d}")

    clean = df.reset_index(drop=True)
    if not return_dropped:
        return clean
    parts = [d for d in dropped if not d.empty]
    removed = (pd.concat(parts, ignore_index=True) if parts
               else df.iloc[0:0].assign(drop_reason=pd.Series(dtype=object)))
    return clean, removed.drop(columns=['_company_root'], errors='ignore')
