"""
Backtest analysis: the live screener run every month-end on point-in-time
data, and three questions asked of it.

1. Does the screen beat its own universe? Equal-weighted portfolios of the
   ranked survivors (all, and the top N by score) against the equal-weighted
   universe they were drawn from (US non-financials above $1B). Both carry
   the same survivorship bias, so it largely cancels in the difference.
   SPY is shown for reference only (cap-weighted, no survivorship bias).
2. Does each factor predict returns? Monthly rank IC (Spearman) of each
   factor against forward returns across the whole universe.
3. Does the score add anything among survivors? Rank IC of the composite
   score and of each factor's z-score within the survivors: this is the
   evidence on the weights.

Nothing here is tuned on the results: thresholds, weights and scoring are
the live screener's (src/config.py), run unchanged.
"""

import contextlib
import io

import numpy as np
import pandas as pd

from .. import config, screener
from . import panel

HORIZONS = {'1m': 1, '3m': 3, '12m': 12}
COST_PER_SIDE = 0.001       # 10 bp per side on traded weight
START = '2012-01-31'        # XBRL coverage is complete from mid-2011


# ------------------------------------------------------------------ panel

def month_ends(daily_index: pd.DatetimeIndex, start: str = START) -> pd.DatetimeIndex:
    """Complete calendar month-ends covered by a daily price index."""
    return pd.date_range(start, daily_index.max(), freq='ME')


def build_panel(snapshots, close_m, universe, dates) -> pd.DataFrame:
    """Stacked monthly cross-sections (panel.cross_section) with a `date` column."""
    frames = []
    for d in dates:
        cs = panel.cross_section(snapshots, d, close_m.loc[d], universe)
        frames.append(cs.assign(date=d))
    return pd.concat(frames, ignore_index=True)


def forward_returns(adj_m: pd.DataFrame) -> dict:
    """{horizon: DataFrame month x cik} of total returns from month-end t to t + h."""
    return {h: adj_m.shift(-n) / adj_m - 1 for h, n in HORIZONS.items()}


def attach_returns(df: pd.DataFrame, fwd: dict) -> pd.DataFrame:
    for h, frame in fwd.items():
        s = frame.stack()
        s.index.names = ['date', 'cik']
        df = df.join(s.rename(f'fwd_{h}'), on=['date', 'cik'])
    return df


# ------------------------------------------------------------------ screen

def run_screen(cross_section: pd.DataFrame) -> tuple:
    """The live screener on one month, silently: (ranked, quarantine)."""
    with contextlib.redirect_stdout(io.StringIO()):
        return screener.run_screener(cross_section)


def screen_history(pan: pd.DataFrame) -> tuple:
    """
    Run the screener every month on companies above the live market-cap floor.
    Returns (universe rows, ranked survivors with rank and score, quarantine).
    """
    uni, ranked, quar = [], [], []
    for d, cs in pan.groupby('date', sort=True):
        cs = cs[cs['market_cap_basic'] > config.MARKET_CAP_MIN]
        r, q = run_screen(cs)
        uni.append(cs)
        ranked.append(r.assign(date=d, rank=np.arange(1, len(r) + 1)))
        quar.append(q.assign(date=d))
    return (pd.concat(uni, ignore_index=True), pd.concat(ranked, ignore_index=True),
            pd.concat(quar, ignore_index=True))


# ------------------------------------------------------------------ statistics

def rank_ic(x: pd.Series, y: pd.Series) -> float:
    ok = x.notna() & y.notna()
    if ok.sum() < 10:
        return np.nan
    return x[ok].rank().corr(y[ok].rank())


def newey_west_t(series: pd.Series, lags: int) -> float:
    """t-statistic of the mean with Newey-West (Bartlett) standard errors."""
    x = series.dropna().to_numpy()
    n = len(x)
    if n < 3:
        return np.nan
    e = x - x.mean()
    var = e @ e / n
    for k in range(1, min(lags, n - 1) + 1):
        var += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(var / n) if var > 0 else np.nan


def ic_table(df: pd.DataFrame, signals: dict) -> pd.DataFrame:
    """
    Mean monthly rank IC of each signal against each forward horizon, with a
    Newey-West t-stat (lags = horizon - 1, overlapping returns) and the share
    of months with IC > 0.
    """
    rows = []
    for name, fn in signals.items():
        for h, n in HORIZONS.items():
            ics = df.groupby('date').apply(lambda g: rank_ic(fn(g), g[f'fwd_{h}']),
                                           include_groups=False).dropna()
            rows.append({'signal': name, 'horizon': h, 'months': len(ics),
                         'mean_ic': ics.mean(), 't_stat': newey_west_t(ics, max(n - 1, 0)),
                         'pct_positive': (ics > 0).mean()})
    return pd.DataFrame(rows)


# Factor signals across the universe, oriented so that higher = the
# direction the screener prefers. Earnings and FCF yields replace P/E and
# P/FCF so that loss-makers rank instead of dropping out.
UNIVERSE_SIGNALS = {
    'earnings_yield (P/E)': lambda g: g['net_income_ttm'] / g['market_cap_basic'],
    'roe': lambda g: g['return_on_equity_fq'],
    '-debt_to_equity': lambda g: -g['debt_to_equity'].where(g['debt_to_equity'] >= 0),
    '-peg': lambda g: -g['price_earnings_growth_ttm'],
    'fcf_yield': lambda g: g['free_cash_flow_ttm'] / g['market_cap_basic'],
}
SURVIVOR_SIGNALS = {'score': lambda g: g['score'],
                    **{f'z_{f}': (lambda f: lambda g: g[f'z_{f}'])(f) for f in screener.FACTOR_COLS}}


# ------------------------------------------------------------------ portfolios

def holdings(ranked: pd.DataFrame, uni: pd.DataFrame, top_n: int = config.TOP_N) -> dict:
    """{portfolio: DataFrame date x cik of equal weights}."""
    def weights(frame):
        w = frame.assign(w=1.0).pivot_table(index='date', columns='cik', values='w', aggfunc='first')
        return w.div(w.sum(axis=1), axis=0).fillna(0.0)
    return {
        f'screen_top{top_n}': weights(ranked[ranked['rank'] <= top_n]),
        'screen_all': weights(ranked),
        'universe_ew': weights(uni),
    }


def portfolio_returns(w: pd.DataFrame, ret_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Monthly gross and net return of rebalancing to `w` at each month-end.
    A holding with no next-month return (suspended) earns 0; a month-end
    with no next-month return for any holding (the last one) is dropped.
    """
    r = ret_1m.reindex(index=w.index, columns=w.columns)
    has_next = r.notna().any(axis=1)
    w, r = w[has_next], r[has_next].fillna(0.0)
    gross = (w * r).sum(axis=1)
    # weights drift during the month; turnover = distance to next target
    drifted = (w * (1 + r)).div((w * (1 + r)).sum(axis=1), axis=0).fillna(0.0)
    turnover = (w - drifted.shift(1)).abs().sum(axis=1)
    turnover.iloc[0] = w.iloc[0].abs().sum()
    net = gross - turnover * COST_PER_SIDE
    # the return earned after date t belongs to month t + 1
    out = pd.DataFrame({'gross': gross, 'net': net, 'turnover': turnover / 2,
                        'n_holdings': (w > 0).sum(axis=1)})
    out.index = out.index + pd.offsets.MonthEnd(1)
    return out


def performance(r: pd.Series) -> dict:
    r = r.dropna()
    if r.empty:
        return {}
    equity = (1 + r).cumprod()
    years = len(r) / 12
    return {
        'cagr': equity.iloc[-1] ** (1 / years) - 1,
        'ann_vol': r.std() * np.sqrt(12),
        'sharpe_0rf': r.mean() / r.std() * np.sqrt(12),
        'max_drawdown': (equity / equity.cummax() - 1).min(),
        'months': len(r),
    }


def excess_stats(r: pd.Series, bench: pd.Series) -> dict:
    ex = (r - bench).dropna()
    return {
        'excess_ann': ex.mean() * 12,
        'tracking_error': ex.std() * np.sqrt(12),
        'info_ratio': ex.mean() / ex.std() * np.sqrt(12) if ex.std() > 0 else np.nan,
        't_stat': newey_west_t(ex, 3),
        'pct_months_ahead': (ex > 0).mean(),
    }


def periods(index: pd.DatetimeIndex) -> dict:
    """Full sample and three roughly equal sub-periods."""
    out = {'full': (index.min(), index.max())}
    for pos in np.array_split(np.arange(len(index)), 3):
        part = index[pos]
        out[f'{part[0]:%Y-%m}..{part[-1]:%Y-%m}'] = (part[0], part[-1])
    return out


# ------------------------------------------------------------------ survivorship

def survivorship(public_float: pd.DataFrame, listed_ciks: set, min_float: float = 1e9) -> pd.DataFrame:
    """
    Of the companies whose annual report showed a public float above
    min_float in a given year, the share still listed on a US exchange today.
    yfinance has prices only for those, so the rest are missing from the
    backtest universe.
    """
    pf = public_float[public_float['val'] > min_float].copy()
    pf['year'] = pf['filed'].dt.year
    per_year = pf.drop_duplicates(['cik', 'year'])
    out = per_year.groupby('year').agg(companies=('cik', 'nunique'),
                                       still_listed=('cik', lambda c: c.isin(listed_ciks).sum()))
    out['share_still_listed'] = out['still_listed'] / out['companies']
    return out
