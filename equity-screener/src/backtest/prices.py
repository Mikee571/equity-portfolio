"""
Daily prices and splits from yfinance, cached to data/backtest/.

Close is split-adjusted to today's share basis (yfinance always does this)
but not dividend-adjusted: it is the price behind P/E and market cap.
Adj Close also reinvests dividends: it is the price behind returns.

XBRL per-share values and share counts are reported on the share basis of
the day they were filed. split_factor_after() converts them to today's
basis, the one Close is on.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / 'data' / 'backtest'
FIELDS = {'Close': 'close', 'Adj Close': 'adj_close', 'Stock Splits': 'splits', 'Volume': 'volume'}


def download_prices(symbols: list, start: str = '2010-01-01', chunk: int = 200) -> dict:
    """
    {field: DataFrame (date x symbol)} for FIELDS, downloaded in chunks.
    Symbols yfinance does not know come back as all-NaN columns.
    """
    parts = {name: [] for name in FIELDS.values()}
    for i in range(0, len(symbols), chunk):
        batch = symbols[i:i + chunk]
        raw = yf.download(batch, start=start, auto_adjust=False, actions=True,
                          group_by='column', threads=True, progress=False)
        for field, name in FIELDS.items():
            frame = raw[field] if field in raw.columns.get_level_values(0) else pd.DataFrame(index=raw.index)
            parts[name].append(frame.reindex(columns=batch))
        print(f"  prices: {min(i + chunk, len(symbols))}/{len(symbols)}", flush=True)
    return {name: pd.concat(frames, axis=1).sort_index() for name, frames in parts.items()}


def load_prices(symbols: list, refresh: bool = False) -> dict:
    """Cached download_prices (one parquet per field)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    paths = {name: CACHE_DIR / f'prices_{name}.parquet' for name in FIELDS.values()}
    if not refresh and all(p.exists() for p in paths.values()):
        return {name: pd.read_parquet(p) for name, p in paths.items()}
    data = download_prices(symbols)
    for name, frame in data.items():
        frame.to_parquet(paths[name])
    return data


def split_events(splits: pd.Series) -> pd.Series:
    """Non-trivial split ratios of one symbol, indexed by ex-date (4.0 = 4-for-1)."""
    s = splits.dropna()
    return s[(s > 0) & (s != 1)]


def split_factor_after(events: pd.Series, dates) -> np.ndarray:
    """
    For each date, the product of the split ratios with ex-date strictly
    after it: how many of today's shares one share of that date became.
    A per-share value reported that day is divided by it; a share count is
    multiplied by it.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(dates))
    if events.empty:
        return np.ones(len(dates))
    ex = events.index.values
    # cumulative product from the latest split backwards
    tail = np.cumprod(events.values[::-1])[::-1]
    pos = np.searchsorted(ex, dates.values, side='right')
    return np.where(pos < len(ex), tail[np.minimum(pos, len(ex) - 1)], 1.0)


def month_end(frame: pd.DataFrame) -> pd.DataFrame:
    """Last available value of each calendar month, indexed by month end."""
    return frame.resample('ME').last()
