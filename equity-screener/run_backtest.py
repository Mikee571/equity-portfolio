"""
Point-in-time backtest of the five-factor screener (US only).

Stages, cached under data/backtest/ (--refresh rebuilds them all):
    1. universe   US listings on TradingView today, cleaned like the live
                  screener (no financials, preferreds...), mapped to SEC CIKs
    2. facts      SEC companyfacts.zip, those CIKs only
    3. prices     yfinance daily close, adjusted close and splits since 2010
    4. snapshots  point-in-time fundamentals per fiscal period
    5. screen     the live screener at every month-end since 2012
    6. report     portfolios, ICs, survivorship -> output/backtest_YYYYMMDD.xlsx

Usage:
    python run_backtest.py               # cached data where present
    python run_backtest.py --refresh     # download everything again
    python run_backtest.py --calibrate   # reconstructed factors vs TradingView today
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config
from src.backtest import analysis, fundamentals, panel, prices, sec, universe

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'data' / 'backtest'
OUTPUT = ROOT / config.OUTPUT_DIR
BENCHMARK = 'SPY'


def stage(name, path: Path, build, refresh: bool, read=pd.read_parquet, write='to_parquet'):
    if path.exists() and not refresh:
        return read(path)
    t = time.time()
    print(f"[{name}] building...", flush=True)
    obj = build()
    getattr(obj, write)(path)
    print(f"[{name}] done in {time.time() - t:.0f}s", flush=True)
    return obj


def load_all(refresh: bool) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    tickers = sec.load_tickers()
    uni = stage('universe', CACHE / 'universe.pkl', lambda: universe.build_universe(tickers),
                refresh, read=pd.read_pickle, write='to_pickle')
    facts = stage('facts', CACHE / 'facts.parquet', lambda: sec.extract_facts(set(uni['cik'])), refresh)
    px = prices.load_prices(sorted(uni['symbol']) + [BENCHMARK], refresh=refresh)
    sym2cik = uni.set_index('symbol')['cik']
    splits = {sym2cik[s]: prices.split_events(px['splits'][s])
              for s in px['splits'].columns if s in sym2cik.index}
    snaps = stage('snapshots', CACHE / 'snapshots.parquet',
                  lambda: fundamentals.build_snapshots(facts, splits), refresh)
    return {'tickers': tickers, 'universe': uni, 'prices': px, 'snapshots': snaps, 'sym2cik': sym2cik}


def by_cik(frame: pd.DataFrame, sym2cik: pd.Series) -> pd.DataFrame:
    """Columns renamed symbol -> cik, keeping symbols of the universe only."""
    frame = frame[[s for s in frame.columns if s in sym2cik.index]]
    return frame.rename(columns=sym2cik)


def calibrate(data: dict) -> pd.DataFrame:
    close = data['prices']['close'].ffill().iloc[-1]
    close = by_cik(close.to_frame().T, data['sym2cik']).iloc[0]
    return panel.calibrate(data['snapshots'], data['universe'], close,
                           pd.Timestamp.today().normalize() + pd.Timedelta(days=1))


def run(data: dict, refresh: bool) -> dict:
    px, sym2cik = data['prices'], data['sym2cik']
    # Complete months only: resample('ME') labels the current month with
    # its latest close, which is not a month-end price.
    dates = analysis.month_ends(px['close'].index)
    close_m = by_cik(prices.month_end(px['close']), sym2cik).loc[:dates[-1]]
    adj_m = by_cik(prices.month_end(px['adj_close']), sym2cik).loc[:dates[-1]]
    # The last month-end has no forward return yet; it stays in the screen
    # history (it is the latest point-in-time screen) but not in returns.
    pan = stage('panel', CACHE / 'panel.parquet',
                lambda: analysis.build_panel(data['snapshots'], close_m, data['universe'], dates),
                refresh)
    pan = pan[pan['date'].isin(dates)]
    fwd = analysis.forward_returns(adj_m)
    pan = analysis.attach_returns(pan, fwd)
    uni, ranked, quar = analysis.screen_history(pan)

    hold = analysis.holdings(ranked, uni)
    port = {name: analysis.portfolio_returns(w, fwd['1m']) for name, w in hold.items()}
    spy = prices.month_end(px['adj_close'][[BENCHMARK]])[BENCHMARK].loc[:dates[-1]].pct_change()
    last = min(p.index.max() for p in port.values())
    port = {k: v[v.index <= last] for k, v in port.items()}
    port['spy'] = pd.DataFrame({'gross': spy, 'net': spy}).loc[port['universe_ew'].index.min():last]

    perf_rows, period_rows = [], []
    bench = port['universe_ew']['net']
    for name, p in port.items():
        perf_rows.append({'portfolio': name, **analysis.performance(p['net']),
                          'avg_holdings': p['n_holdings'].mean() if 'n_holdings' in p else None,
                          'turnover_monthly': p['turnover'].mean() if 'turnover' in p else None,
                          **({} if name == 'universe_ew' else analysis.excess_stats(p['net'], bench))})
    for label, (a, b) in analysis.periods(bench.index).items():
        for name, p in port.items():
            if name == 'universe_ew':
                continue
            r = p['net'].loc[a:b]
            period_rows.append({'period': label, 'portfolio': name,
                                'cagr': analysis.performance(r).get('cagr'),
                                'cagr_universe': analysis.performance(bench.loc[a:b]).get('cagr'),
                                **analysis.excess_stats(r, bench.loc[a:b])})

    ic_uni = analysis.ic_table(uni, analysis.UNIVERSE_SIGNALS)
    ic_surv = analysis.ic_table(ranked, analysis.SURVIVOR_SIGNALS)

    pf = stage('public_float', CACHE / 'public_float.parquet', sec.extract_public_float, refresh)
    listed = set(data['tickers'].loc[data['tickers']['exchange'].isin(['NYSE', 'Nasdaq', 'CBOE']), 'cik'])
    surv = analysis.survivorship(pf, listed)

    coverage = pd.DataFrame({
        'universe_gt_1b': uni.groupby('date').size(),
        'complete_data': uni.dropna(subset=list(analysis.screener.FACTOR_COLS.values())).groupby('date').size(),
        'ranked': ranked.groupby('date').size(),
        'quarantined': quar.groupby('date').size() if not quar.empty else 0,
    }).fillna(0).astype(int)

    return {
        'portfolios': pd.DataFrame(perf_rows),
        'subperiods': pd.DataFrame(period_rows),
        'ic_universe': ic_uni,
        'ic_survivors': ic_surv,
        'monthly_returns': pd.DataFrame({k: v['net'] for k, v in port.items()}),
        'top_holdings': ranked[ranked['rank'] <= config.TOP_N][
            ['date', 'rank', 'name', 'description', 'sector', 'score', 'market_cap_basic',
             'price_earnings_ttm', 'return_on_equity_fq', 'debt_to_equity',
             'price_earnings_growth_ttm', 'fcf_yield', 'fwd_1m', 'fwd_12m']],
        'coverage': coverage,
        'survivorship': surv,
    }


def report(results: dict, calibration: pd.DataFrame) -> Path:
    pd.set_option('display.width', 220)
    pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
    for key in ('portfolios', 'subperiods', 'ic_universe', 'ic_survivors'):
        print(f"\n=== {key} ===")
        print(results[key].to_string(index=False))
    print("\n=== survivorship (companies with public float > $1B, share still listed today) ===")
    print(results['survivorship'].to_string())

    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / f"backtest_{datetime.now():%Y%m%d_%H%M}.xlsx"
    with pd.ExcelWriter(path) as xl:
        for key, frame in results.items():
            frame.to_excel(xl, sheet_name=key[:31], index=key in ('monthly_returns', 'coverage', 'survivorship'))
        calibration.to_excel(xl, sheet_name='calibration', index=False)
    print(f"\nSaved: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--refresh', action='store_true', help='download and rebuild every stage')
    parser.add_argument('--calibrate', action='store_true', help='only compare with TradingView today')
    args = parser.parse_args()

    data = load_all(args.refresh)
    cal = calibrate(data)
    print("\n=== calibration: reconstructed factors vs TradingView today ===")
    print(cal.to_string(index=False))
    if args.calibrate:
        return
    report(run(data, args.refresh), cal)


if __name__ == '__main__':
    main()
