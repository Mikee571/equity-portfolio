"""
Report generator — Excel export and console summary.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

from . import config


TOP_COLS = ['name', 'description', 'exchange', 'country', 'sector',
            'close', 'market_cap_basic',
            'price_earnings_ttm', 'return_on_equity_fq', 'debt_to_equity',
            'price_earnings_growth_ttm', 'free_cash_flow_ttm', 'fcf_yield',
            'score', 'data_warnings']

# Quarantine sheet: the factor values plus the evidence behind each flag
QUARANTINE_COLS = ['name', 'description', 'exchange', 'country', 'sector',
                   'close', 'market_cap_basic',
                   'price_earnings_ttm', 'return_on_equity_fq', 'debt_to_equity',
                   'price_earnings_growth_ttm', 'free_cash_flow_ttm',
                   'net_income_ttm', 'total_equity_fq',
                   'pe_earnings_check', 'roe_equity_check', 'implied_growth_pct',
                   'data_errors', 'data_warnings']


def _present(df: pd.DataFrame, cols: list) -> list:
    return [c for c in cols if c in df.columns]


def export_excel(ranked: pd.DataFrame, output_dir: str = None,
                 quarantine: pd.DataFrame = None,
                 persistence: pd.DataFrame = None) -> Path:
    """
    Write the screener output to a timestamped Excel file.
    Sheets:
        - top_n: top-N tickers with core factors, formatted for review
        - full_ranking: complete ranked list with z-scores and check ratios
        - quarantine: rows that passed the thresholds but failed a data
          check (always written, empty if none, so the file shape is stable)
        - persistence: streaks and score trend from the weekly history
          (only when provided; see src/history.py)
    """
    output_dir = Path(output_dir or config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    filepath = output_dir / f'five_factor_screener_{timestamp}.xlsx'

    top_n = ranked.head(config.TOP_N)[_present(ranked, TOP_COLS)].copy()
    if quarantine is None:
        quarantine = pd.DataFrame(columns=QUARANTINE_COLS)

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        top_n.to_excel(writer, sheet_name='top_n', index=False)
        ranked.to_excel(writer, sheet_name='full_ranking', index=False)
        quarantine[_present(quarantine, QUARANTINE_COLS)].to_excel(
            writer, sheet_name='quarantine', index=False)
        if persistence is not None:
            persistence.to_excel(writer, sheet_name='persistence', index=False)

    print(f"\nExcel written: {filepath}")
    return filepath


def print_top_n(ranked: pd.DataFrame, quarantine: pd.DataFrame = None) -> None:
    """
    Print top-N with the five factors and composite score for console review.
    Tickers carrying a data warning are marked with '*'.
    """
    if ranked.empty:
        print("\n[!] No tickers survived the filters. Loosen thresholds in config.py.")
    else:
        top = ranked.head(config.TOP_N)
        print(f"\n{'=' * 78}")
        print(f"TOP {config.TOP_N} — Five-Factor Screener")
        print(f"{'=' * 78}")
        print(f"{'#':>2}  {'Ticker':<12} {'PE':>6} {'ROE':>6} {'D/E':>6} "
              f"{'PEG':>6} {'FCF yld':>8} {'Score':>7}  Flags")
        print('-' * 78)
        for i, row in top.iterrows():
            flags = row.get('data_warnings', '') or ''
            ticker = f"{row['name']}{'*' if flags else ''}"
            print(f"{i+1:>2}  {ticker:<12} "
                  f"{row['price_earnings_ttm']:>6.1f} "
                  f"{row['return_on_equity_fq']:>5.1f}% "
                  f"{row['debt_to_equity']:>6.2f} "
                  f"{row['price_earnings_growth_ttm']:>6.2f} "
                  f"{100 * row['fcf_yield']:>7.1f}% "
                  f"{row['score']:>+7.2f}  {flags}")
        print('=' * 78)

    if quarantine is not None and not quarantine.empty:
        print(f"\nQUARANTINE — {len(quarantine)} passed the thresholds but failed "
              f"a data check (not ranked):")
        for _, row in quarantine.iterrows():
            print(f"  {row['name']:<12} {row['exchange']:<9} "
                  f"PE {row['price_earnings_ttm']:>6.1f}  {row['data_errors']}")
