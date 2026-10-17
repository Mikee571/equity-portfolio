"""
Backtest universe: US common stocks listed today, as the live screener sees
them, mapped to their SEC CIK.

The live universe floor is $1B today. Here the floor is applied month by
month on the historical market cap, so the fetch goes much lower
(HIST_MCAP_MIN) to include companies that were above $1B in the past and
are smaller now. Companies that delisted (bankruptcy, acquisition) are not
in TradingView or yfinance any more: that is the survivorship bias measured
in src/backtest/analysis.py.
"""

import pandas as pd
from tradingview_screener import Query, col

from .. import universe as live_universe

HIST_MCAP_MIN = 50_000_000
US_EXCHANGES = ['NASDAQ', 'NYSE', 'AMEX']
PAGE_SIZE = 5000


def fetch_current_us(min_mcap: float = HIST_MCAP_MIN) -> pd.DataFrame:
    """All US domestic-exchange listings above min_mcap, with the live FIELDS."""
    frames, start = [], 0
    while True:
        count, page = (Query()
                       .set_markets('america')
                       .select(*live_universe.FIELDS)
                       .where(col('market_cap_basic') > min_mcap,
                              col('exchange').isin(US_EXCHANGES))
                       .order_by('market_cap_basic', ascending=False)
                       .offset(start)
                       .limit(start + PAGE_SIZE)
                       .get_scanner_data())
        frames.append(page)
        start += PAGE_SIZE
        if page.empty or start >= count:
            break
    df = pd.concat(frames, ignore_index=True).drop_duplicates('ticker')
    df['market'] = 'america'
    return df.reset_index(drop=True)


def yahoo_symbol(tv_name: str) -> str:
    """TradingView symbol -> yfinance / SEC symbol (BRK.B -> BRK-B)."""
    return tv_name.replace('.', '-').replace('/', '-')


def build_universe(sec_tickers: pd.DataFrame, min_mcap: float = HIST_MCAP_MIN) -> pd.DataFrame:
    """
    Current US universe after the live screener's cleaning (financials,
    preferreds, units, secondary lines, share-class duplicates removed),
    with a `symbol` (yfinance) and `cik` column. Rows without a CIK
    (no SEC filings under that ticker) are dropped.
    """
    raw = fetch_current_us(min_mcap)
    clean = live_universe.clean_universe(raw)
    clean['symbol'] = clean['name'].map(yahoo_symbol)
    ciks = sec_tickers.drop_duplicates('ticker').set_index('ticker')['cik']
    clean['cik'] = clean['symbol'].map(ciks)
    mapped = clean[clean['cik'].notna()].copy()
    mapped['cik'] = mapped['cik'].astype(int)
    print(f"  Mapped to a SEC CIK: {len(mapped)} of {len(clean)}")
    return mapped.drop_duplicates('cik').reset_index(drop=True)
