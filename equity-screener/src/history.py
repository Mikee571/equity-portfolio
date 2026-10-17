"""
Weekly history — one snapshot per run, persistence metrics across weeks.

Storage: data/screener_history.csv, append-only, one row per ticker per run.
Every ranked and quarantined ticker is stored with its factor values,
z-scores, score and rank, plus run_ts, week and model_version.

Week convention: a screening week runs Sunday to Saturday and is labelled by
its Sunday. The scheduled run fires Sunday 20:00; a retry in the early hours
of Monday (as on 2026-09-28) still belongs to the Sunday it replaces. When a
week has several runs, the latest one is that week's snapshot. A week with
no run at all (failed fetch) is skipped: it neither extends nor breaks a
streak.

Why it matters: a cross-sectional z-score says where a stock stands *this
week* relative to *this week's* survivors. A falling score can mean the stock
got worse (price up faster than earnings, lower ROE...) or simply that peers
got better. persistence() splits each score change both ways:

    by factor:   delta_score = sum_f  w_f * (z_f,now - z_f,start)
    own / peers: d_own   = sum_f  w_f * (z*_f - z_f,start)
                 d_peers = delta_score - d_own

where z*_f is the z-score the stock's *current* value would get under the
*start* week's standardisation (same winsorisation bounds, mean and std, see
screener.fit_zscore). d_own is the change the stock would have had if its
peers had not moved; d_peers is the rest. The P/E move is further split
into price change and implied EPS change (EPS = price / P/E).

Scores from different model versions are on different scales (v0.7 changed
the FCF factor and added winsorisation), so the trend window only uses
snapshots scored by the same model as the latest one. Streaks (top-N
membership) do span models and are flagged when they do.

Usage:
    python -m src.history backfill   # load pre-v0.7 Excel outputs once
    python -m src.history report     # persistence table for the latest week
"""

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__, config
from .screener import (FACTOR_COLS, LEGACY_MODEL, apply_zscore, fit_zscore,
                       score_inputs)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

HISTORY_COLS = (['run_ts', 'week', 'model_version', 'status', 'rank',
                 'ticker', 'name', 'exchange', 'country', 'sector',
                 'close', 'market_cap_basic']
                + list(FACTOR_COLS.values())
                + [f'z_{f}' for f in FACTOR_COLS]
                + ['score', 'data_errors', 'data_warnings'])

PERSISTENCE_COLS = (['ticker', 'name', 'rank', 'score',
                     'weeks_ranked', 'weeks_top_n', 'streak', 'streak_since',
                     'window_weeks', 'window_start', 'rank_start', 'score_start',
                     'score_delta', 'score_slope']
                    + [f'd_{f}' for f in FACTOR_COLS]
                    + ['d_own', 'd_peers', 'price_chg_pct', 'eps_chg_pct',
                       'model_version', 'streak_mixed_models'])


def history_path(path=None) -> Path:
    return Path(path) if path else PROJECT_ROOT / config.HISTORY_PATH


def week_label(ts) -> pd.Timestamp:
    """The Sunday on or before ts (see module docstring)."""
    day = pd.Timestamp(ts).normalize()
    return day - pd.Timedelta(days=(day.weekday() + 1) % 7)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def snapshot_rows(ranked: pd.DataFrame, quarantine: pd.DataFrame = None,
                  run_ts=None, model_version: str = __version__) -> pd.DataFrame:
    """History rows for one run. ranked must be sorted by score, best first."""
    run_ts = pd.Timestamp(run_ts or datetime.now()).floor('min')
    parts = []
    if not ranked.empty:
        r = ranked.copy()
        r['status'] = 'ranked'
        r['rank'] = np.arange(1, len(r) + 1)
        parts.append(r)
    if quarantine is not None and not quarantine.empty:
        q = quarantine.copy()
        q['status'] = 'quarantined'
        q['rank'] = np.nan
        parts.append(q)
    if not parts:
        return pd.DataFrame(columns=HISTORY_COLS)

    df = pd.concat(parts, ignore_index=True)
    if 'ticker' not in df.columns:
        df['ticker'] = df['name']
    df['run_ts'] = run_ts.strftime('%Y-%m-%d %H:%M')
    df['week'] = week_label(run_ts).strftime('%Y-%m-%d')
    df['model_version'] = model_version
    return df.reindex(columns=HISTORY_COLS)


def append_snapshot(ranked: pd.DataFrame, quarantine: pd.DataFrame = None,
                    run_ts=None, path=None,
                    model_version: str = __version__) -> int:
    """
    Append one run to the history CSV. Idempotent: a run_ts already in the
    file is not written again. Returns the number of rows written.
    """
    path = history_path(path)
    rows = snapshot_rows(ranked, quarantine, run_ts, model_version)
    if rows.empty:
        return 0
    if path.exists():
        seen = set(pd.read_csv(path, usecols=['run_ts'])['run_ts'])
        if rows['run_ts'].iloc[0] in seen:
            return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, mode='a', header=not path.exists(), index=False)
    return len(rows)


def backfill_from_excel(output_dir=None, path=None) -> int:
    """
    Load past Excel exports (full_ranking sheet) into the history. Only
    pre-v0.7 files are read (no 'quarantine' sheet): v0.7+ runs are recorded
    live by run_weekly.py. Scores are kept exactly as they were produced,
    tagged model_version='pre-0.7'.
    """
    output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / config.OUTPUT_DIR
    total = 0
    for f in sorted(output_dir.glob('five_factor_screener_*.xlsx')):
        if 'quarantine' in pd.ExcelFile(f).sheet_names:
            print(f"  skip {f.name} (v0.7+, recorded live)")
            continue
        run_ts = datetime.strptime(f.stem.replace('five_factor_screener_', ''),
                                   '%Y%m%d_%H%M')
        ranked = pd.read_excel(f, sheet_name='full_ranking')
        n = append_snapshot(ranked, run_ts=run_ts, path=path,
                            model_version='pre-0.7')
        print(f"  {f.name}: {n} rows" + ("" if n else " (already loaded)"))
        total += n
    return total


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def load_history(path=None) -> pd.DataFrame:
    path = history_path(path)
    if not path.exists():
        return pd.DataFrame(columns=HISTORY_COLS)
    df = pd.read_csv(path, parse_dates=['run_ts', 'week'],
                     dtype={'data_errors': str, 'data_warnings': str,
                            'model_version': str})
    df[['data_errors', 'data_warnings']] = df[['data_errors', 'data_warnings']].fillna('')
    return df.sort_values(['run_ts', 'rank']).reset_index(drop=True)


def weekly_snapshots(history: pd.DataFrame) -> pd.DataFrame:
    """Keep only the latest run of each week."""
    if history.empty:
        return history
    latest = history.groupby('week')['run_ts'].transform('max')
    return history[history['run_ts'] == latest].copy()


def persistence(history: pd.DataFrame, top_n: int = None,
                lookback: int = None) -> pd.DataFrame:
    """
    One row per ticker ranked in the latest weekly snapshot:

        weeks_ranked / weeks_top_n   snapshots ranked at all / inside the top N
        streak, streak_since         consecutive snapshots in the top N ending
                                     now (0 if outside the top N), and the week
                                     the streak started
        window_*                     trend window: the last `lookback`
                                     consecutive snapshots in which the ticker
                                     was ranked by the current model, ending now
        score_delta, score_slope     score change over the window, and its OLS
                                     slope per calendar week (>= 3 snapshots)
        d_<factor>                   score change attributed to each factor
        d_own, d_peers               score change from the stock's own factor
                                     values vs from the peer distribution
        price_chg_pct, eps_chg_pct   price and implied-EPS change over the window
        streak_mixed_models          the streak spans more than one model
                                     version, so membership was not decided
                                     the same way throughout
    """
    top_n = top_n or config.TOP_N
    lookback = lookback or config.HISTORY_LOOKBACK

    snaps = weekly_snapshots(history)
    ranked = snaps[snaps['status'] == 'ranked']
    if ranked.empty:
        return pd.DataFrame(columns=PERSISTENCE_COLS)

    weeks = sorted(snaps['week'].unique())
    rank = ranked.pivot(index='ticker', columns='week', values='rank').reindex(columns=weeks)
    by_week = {w: g.set_index('ticker') for w, g in ranked.groupby('week')}
    model_of = {w: g['model_version'].iloc[0] for w, g in by_week.items()}
    current_model = model_of[weeks[-1]]
    legacy = current_model == LEGACY_MODEL

    # Standardisation of each week, refitted from its stored survivors
    fitted = {}
    def week_params(w):
        if w not in fitted:
            fitted[w] = fit_zscore(score_inputs(by_week[w], legacy), legacy)
        return fitted[w]

    rows = []
    for ticker, now in by_week[weeks[-1]].iterrows():
        r = rank.loc[ticker]

        streak = 0
        for w in reversed(weeks):
            if r[w] <= top_n:
                streak += 1
            else:
                break

        window = []
        for w in reversed(weeks):
            if (pd.isna(r[w]) or model_of[w] != current_model
                    or len(window) == lookback):
                break
            window.append(w)
        window = window[::-1]
        start = by_week[window[0]].loc[ticker]

        row = {
            'ticker': ticker, 'name': now['name'],
            'rank': int(now['rank']), 'score': now['score'],
            'weeks_ranked': int(r.notna().sum()),
            'weeks_top_n': int((r <= top_n).sum()),
            'streak': streak,
            'streak_since': weeks[-streak] if streak else pd.NaT,
            'window_weeks': len(window), 'window_start': window[0],
            'rank_start': int(start['rank']), 'score_start': start['score'],
            'score_delta': now['score'] - start['score'],
            'model_version': current_model,
            'streak_mixed_models': len({model_of[w] for w in weeks[len(weeks) - streak:]}) > 1,
        }

        if len(window) >= 3:
            x = np.array([(w - window[0]).days / 7 for w in window])
            y = np.array([by_week[w].loc[ticker, 'score'] for w in window])
            row['score_slope'] = np.polyfit(x, y, 1)[0]

        # Own effect: today's values under the start week's standardisation
        z_own = apply_zscore(score_inputs(now.to_frame().T, legacy),
                             week_params(window[0])).iloc[0]
        d_own = 0.0
        for f in FACTOR_COLS:
            w_f = config.SCORE_WEIGHTS[f]
            row[f'd_{f}'] = w_f * (now[f'z_{f}'] - start[f'z_{f}'])
            d_own += w_f * (z_own[f] - start[f'z_{f}'])
        row['d_own'] = d_own
        row['d_peers'] = row['score_delta'] - d_own

        pe_col = FACTOR_COLS['pe']
        row['price_chg_pct'] = 100 * (now['close'] / start['close'] - 1)
        row['eps_chg_pct'] = 100 * ((now['close'] / now[pe_col])
                                    / (start['close'] / start[pe_col]) - 1)
        rows.append(row)

    return pd.DataFrame(rows).reindex(columns=PERSISTENCE_COLS)


def fading(table: pd.DataFrame, top_n: int = None,
           threshold: float = None) -> pd.DataFrame:
    """Top-N names with a streak of 3+ whose score fell more than threshold."""
    top_n = top_n or config.TOP_N
    threshold = config.FADING_SCORE_DELTA if threshold is None else threshold
    if table.empty:
        return table
    mask = ((table['rank'] <= top_n) & (table['streak'] >= 3)
            & (table['score_delta'] < threshold))
    return table[mask].sort_values('score_delta')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog='python -m src.history',
                                     description='Screener weekly history.')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('backfill', help='load pre-v0.7 Excel outputs into the history')
    rep = sub.add_parser('report', help='persistence table for the latest week')
    rep.add_argument('--all', action='store_true', help='all ranked tickers, not only top N')
    args = parser.parse_args(argv)

    if args.cmd == 'backfill':
        n = backfill_from_excel()
        print(f"{n} rows added to {history_path()}")
        return

    table = persistence(load_history())
    if not args.all:
        table = table[table['rank'] <= config.TOP_N]
    cols = ['rank', 'name', 'score', 'streak', 'streak_since', 'window_weeks',
            'score_delta', 'score_slope', 'd_own', 'd_peers',
            'price_chg_pct', 'eps_chg_pct', 'model_version']
    with pd.option_context('display.width', 200, 'display.max_columns', 20,
                           'display.float_format', '{:,.3f}'.format):
        print(table[cols].to_string(index=False))


if __name__ == '__main__':
    main()
