"""
Export the monthly net returns of the backtest portfolios that the
portfolio-construction study in strategy-lab combines (USD):

    screener_top10   the live screener's top 10, equal-weighted
    universe_ew      US non-financials above $1B, equal-weighted
    quality_msci     top quintile of the MSCI-style quality signal

Written to data/backtest/sleeves.csv, indexed by the month the return belongs to.

Usage:  python -m src.backtest.export_sleeves   (needs the run_backtest.py caches)
"""

import pandas as pd

from . import analysis, prices, quality

SLEEVES_CSV = 'sleeves.csv'


def main():
    import run_backtest as rb

    data = rb.load_all(False)
    px, sym2cik = data['prices'], data['sym2cik']
    dates = analysis.month_ends(px['close'].index)
    adj_m = rb.by_cik(prices.month_end(px['adj_close']), sym2cik).loc[:dates[-1]]
    fwd = analysis.forward_returns(adj_m)
    pan = pd.read_parquet(rb.CACHE / 'panel.parquet')
    pan = analysis.attach_returns(pan[pan['date'].isin(dates)], fwd)

    uni, ranked, _ = analysis.screen_history(pan)
    hold = analysis.holdings(ranked, uni)
    hist = quality.quality_history(pan, data['snapshots'])
    sleeves = pd.DataFrame({
        'screener_top10': analysis.portfolio_returns(hold['screen_top10'], fwd['1m'])['net'],
        'universe_ew': analysis.portfolio_returns(hold['universe_ew'], fwd['1m'])['net'],
        'quality_msci': analysis.portfolio_returns(quality.top_quantile_weights(hist, 'msci'), fwd['1m'])['net'],
    }).dropna()
    path = rb.CACHE / SLEEVES_CSV
    sleeves.to_csv(path)
    print(f"Saved {len(sleeves)} months ({sleeves.index.min():%Y-%m} -> {sleeves.index.max():%Y-%m}): {path}")


if __name__ == '__main__':
    main()
