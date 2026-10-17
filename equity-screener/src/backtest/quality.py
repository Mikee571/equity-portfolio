"""
Has buying quality paid? Point-in-time backtest of two standard definitions
of the quality factor (US non-financials above $1B, 2012-2026).

Both definitions were fixed before looking at any result:

    msci     Equal-weighted z-scores of high ROE, low debt/equity and low
             earnings variability (std of year-on-year growth of TTM EPS over
             the last 5 years), after the MSCI Quality Index methodology.
             Each descriptor is winsorised at 5/95 and z-scored across the
             month's universe; all three are required.
    gross_profitability
             Gross profit TTM / total assets (Novy-Marx, 2013), the quality
             measure with the strongest published evidence. Gross profit is
             the tagged figure, else revenue - cost of revenue.

Test: at every month-end, the top quintile of each signal, equal-weighted,
against the equal-weighted universe of run_backtest.py, net of 10 bp per
side. Quality "worked" if the excess return has a Newey-West t > 2. Rank ICs
with forward returns are reported as well.

Usage:  python -m src.backtest.quality   (needs the run_backtest.py caches)
"""

import numpy as np
import pandas as pd

from .. import config
from . import analysis

QUANTILE = 0.2
VARIABILITY_YEARS = 5
VARIABILITY_MIN_OBS = 8


def _eps(s: pd.DataFrame, now: bool = True) -> pd.Series:
    """TTM EPS (or one year earlier), NI / diluted shares where EPS is not tagged."""
    if now:
        return s['eps'].fillna(s['ni'] / s['diluted_shares'])
    return s['eps_prev'].fillna(s['ni_prev'] / s['diluted_shares_prev'])


def earnings_variability(snapshots: pd.DataFrame, date) -> pd.Series:
    """
    Std of year-on-year TTM EPS growth over the snapshots known before `date`
    with a period end in the last VARIABILITY_YEARS years. Growth is only
    defined when the earlier EPS is positive. NaN with fewer than
    VARIABILITY_MIN_OBS observations.
    """
    date = pd.Timestamp(date)
    s = snapshots[(snapshots['known'] < date)
                  & (snapshots['period_end'] > date - pd.DateOffset(years=VARIABILITY_YEARS))]
    prev = _eps(s, now=False)
    growth = (_eps(s) / prev - 1).where(prev > 0)
    g = growth.groupby(s['cik'])
    return g.std().where(g.count() >= VARIABILITY_MIN_OBS)


def gross_profitability(snapshots: pd.DataFrame, date) -> pd.Series:
    """Gross profit TTM / total assets from the latest snapshot whose quality inputs are public."""
    date = pd.Timestamp(date)
    s = snapshots[(snapshots['known_quality'] < date)
                  & (snapshots['period_end'] >= date - pd.Timedelta(days=456))]
    s = s.sort_values(['cik', 'period_end']).drop_duplicates('cik', keep='last').set_index('cik')
    gp = s['gross_profit'].fillna(s['revenue'] - s['cogs'])
    return (gp / s['assets']).where(s['assets'] > 0)


def zscore(x: pd.Series, q=config.WINSOR_QUANTILES) -> pd.Series:
    """Winsorised (5/95) z-score across one cross-section."""
    lo, hi = x.quantile(q[0]), x.quantile(q[1])
    c = x.clip(lo, hi)
    return (c - c.mean()) / c.std(ddof=0)


def signals(cs: pd.DataFrame, snapshots: pd.DataFrame, date) -> pd.DataFrame:
    """Both quality signals (higher = better quality) for one month's universe."""
    cs = cs.set_index('cik')
    var = earnings_variability(snapshots, date).reindex(cs.index)
    de = cs['debt_to_equity'].where(cs['debt_to_equity'] >= 0)      # negative equity: undefined
    parts = pd.DataFrame({'roe': zscore(cs['return_on_equity_fq']),
                          'low_de': -zscore(de), 'low_var': -zscore(var)})
    out = pd.DataFrame({
        'msci': parts.mean(axis=1).where(parts.notna().all(axis=1)),
        'gross_profitability': gross_profitability(snapshots, date).reindex(cs.index),
        'earnings_variability': var,
    })
    return out.reset_index()


def quality_history(pan: pd.DataFrame, snapshots: pd.DataFrame) -> pd.DataFrame:
    """Monthly universe (> $1B) with both signals and forward returns attached."""
    frames = []
    for d, cs in pan.groupby('date', sort=True):
        cs = cs[cs['market_cap_basic'] > config.MARKET_CAP_MIN]
        frames.append(cs.merge(signals(cs, snapshots, d), on='cik', how='left'))
    return pd.concat(frames, ignore_index=True)


def top_quantile_weights(df: pd.DataFrame, signal: str, q: float = QUANTILE) -> pd.DataFrame:
    """Equal weights on the top q of `signal` each month (date x cik)."""
    picks = df[df[signal].notna()]
    cut = picks.groupby('date')[signal].transform(lambda s: s.quantile(1 - q))
    picks = picks[picks[signal] >= cut]
    w = picks.assign(w=1.0).pivot_table(index='date', columns='cik', values='w', aggfunc='first')
    return w.div(w.sum(axis=1), axis=0).fillna(0.0)


def equal_weights(df: pd.DataFrame) -> pd.DataFrame:
    w = df.assign(w=1.0).pivot_table(index='date', columns='cik', values='w', aggfunc='first')
    return w.div(w.sum(axis=1), axis=0).fillna(0.0)


def study(hist: pd.DataFrame, ret_1m: pd.DataFrame) -> dict:
    bench = analysis.portfolio_returns(equal_weights(hist), ret_1m)['net']
    rows, sub_rows, coverage = [], [], {}
    for sig in ('msci', 'gross_profitability'):
        has = hist[hist[sig].notna()]
        coverage[sig] = (hist[sig].notna().groupby(hist['date']).mean()).mean()
        port = analysis.portfolio_returns(top_quantile_weights(hist, sig), ret_1m)
        # coverage-neutral benchmark: the names that have the signal
        bench_cov = analysis.portfolio_returns(equal_weights(has), ret_1m)['net']
        rows.append({'signal': sig, 'coverage': coverage[sig], **analysis.performance(port['net']),
                     'avg_holdings': port['n_holdings'].mean(), 'turnover_monthly': port['turnover'].mean(),
                     **{f'{k}_vs_universe': v for k, v in analysis.excess_stats(port['net'], bench).items()
                        if k in ('excess_ann', 't_stat', 'tracking_error')},
                     **{f'{k}_vs_covered': v for k, v in analysis.excess_stats(port['net'], bench_cov).items()
                        if k in ('excess_ann', 't_stat')}})
        for label, (a, b) in analysis.periods(bench.index).items():
            ex = analysis.excess_stats(port['net'].loc[a:b], bench.loc[a:b])
            sub_rows.append({'signal': sig, 'period': label, 'excess_ann': ex['excess_ann'], 't_stat': ex['t_stat']})
    rows.append({'signal': 'universe_ew', **analysis.performance(bench)})
    ic = analysis.ic_table(hist, {
        'msci': lambda g: g['msci'],
        'gross_profitability': lambda g: g['gross_profitability'],
        'roe': lambda g: g['return_on_equity_fq'],
        'low_debt_to_equity': lambda g: -g['debt_to_equity'].where(g['debt_to_equity'] >= 0),
        'low_earnings_variability': lambda g: -g['earnings_variability'],
    })
    return {'portfolios': pd.DataFrame(rows), 'subperiods': pd.DataFrame(sub_rows), 'ic': ic}


def main():
    from datetime import datetime

    import run_backtest as rb
    from . import prices

    data = rb.load_all(False)
    px, sym2cik = data['prices'], data['sym2cik']
    dates = analysis.month_ends(px['close'].index)
    adj_m = rb.by_cik(prices.month_end(px['adj_close']), sym2cik).loc[:dates[-1]]
    fwd = analysis.forward_returns(adj_m)
    pan = pd.read_parquet(rb.CACHE / 'panel.parquet')
    pan = analysis.attach_returns(pan[pan['date'].isin(dates)], fwd)
    hist = quality_history(pan, data['snapshots'])
    out = study(hist, fwd['1m'])
    spy = prices.month_end(px['adj_close'][[rb.BENCHMARK]])[rb.BENCHMARK].loc[:dates[-1]].pct_change()
    pd.set_option('display.width', 220)
    pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
    for key, frame in out.items():
        print(f"\n=== {key} ===")
        print(frame.to_string(index=False))
    first_return = pd.Timestamp(analysis.START) + pd.offsets.MonthEnd(1)
    print(f"\nSPY CAGR over the same months: {analysis.performance(spy.loc[first_return:])['cagr']:.3f}")
    path = rb.OUTPUT / f"quality_{datetime.now():%Y%m%d_%H%M}.xlsx"
    with pd.ExcelWriter(path) as xl:
        for key, frame in out.items():
            frame.to_excel(xl, sheet_name=key, index=False)
        last = hist[hist['date'] == hist['date'].max()]
        for sig in ('msci', 'gross_profitability'):
            top = last.nlargest(int(len(last[last[sig].notna()]) * QUANTILE), sig)
            top[['name', 'description', 'sector', sig, 'return_on_equity_fq', 'debt_to_equity',
                 'earnings_variability', 'market_cap_basic']].to_excel(xl, sheet_name=f'latest_{sig}'[:31], index=False)
    print(f"Saved: {path}")
    return hist, out


if __name__ == '__main__':
    main()
