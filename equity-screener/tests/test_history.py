"""
Tests for the weekly history (src/history.py): week convention, idempotent
storage, streaks across missing weeks, and the score-change decomposition.

Run with:
    python -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src import history, screener


def raw_universe(**overrides):
    """Five tickers; overrides = {name: {column: value}} for this week."""
    base = {
        'A': (12, 30.0, 0.2, 0.6, 3e9, 30e9, 100.0),
        'B': (15, 20.0, 0.4, 0.9, 2e9, 30e9, 50.0),
        'C': (18, 15.0, 0.6, 1.2, 1e9, 20e9, 20.0),
        'D': (10, 14.0, 0.8, 1.0, 5e8, 10e9, 30.0),
        'E': (19, 13.0, 0.9, 1.4, 2e8, 8e9, 10.0),
    }
    rows = []
    for name, (pe, roe, de, peg, fcf, mcap, close) in base.items():
        row = {'ticker': f'X:{name}', 'name': name, 'exchange': 'X', 'close': close,
               'price_earnings_ttm': pe, 'return_on_equity_fq': roe,
               'debt_to_equity': de, 'price_earnings_growth_ttm': peg,
               'free_cash_flow_ttm': fcf, 'market_cap_basic': mcap}
        row.update(overrides.get(name, {}))
        rows.append(row)
    return pd.DataFrame(rows)


def universe(**overrides):
    """This week's survivors scored by the current model."""
    return screener.compute_composite_score(raw_universe(**overrides))


def legacy_universe(**overrides):
    """Same, scored the pre-v0.7 way (raw FCF, PEG as reported, no winsorisation)."""
    df = raw_universe(**overrides)
    inputs = screener.score_inputs(df, legacy=True)
    z = screener.apply_zscore(inputs, screener.fit_zscore(inputs, legacy=True))
    for f in screener.FACTOR_COLS:
        df[f'z_{f}'] = z[f]
    df['score'] = sum(z[f] * w for f, w in screener.config.SCORE_WEIGHTS.items())
    return df.sort_values('score', ascending=False).reset_index(drop=True)


@pytest.fixture
def hist_path(tmp_path):
    return tmp_path / 'history.csv'


def test_week_label_sunday_convention():
    assert history.week_label('2026-10-04 20:10') == pd.Timestamp('2026-10-04')  # Sunday
    assert history.week_label('2026-09-28 01:24') == pd.Timestamp('2026-09-27')  # Monday retry
    assert history.week_label('2026-08-05 00:51') == pd.Timestamp('2026-08-02')  # Wednesday


def test_append_is_idempotent_and_round_trips(hist_path):
    ranked = universe()
    assert history.append_snapshot(ranked, run_ts='2026-10-04 20:10', path=hist_path) == 5
    assert history.append_snapshot(ranked, run_ts='2026-10-04 20:10', path=hist_path) == 0
    h = history.load_history(hist_path)
    assert len(h) == 5
    assert list(h['rank']) == [1, 2, 3, 4, 5]
    assert (h['week'] == pd.Timestamp('2026-10-04')).all()
    assert h.loc[h['rank'] == 1, 'score'].iloc[0] == pytest.approx(ranked['score'].iloc[0])


def test_quarantined_rows_stored_but_not_ranked(hist_path):
    q = pd.DataFrame([{'ticker': 'X:Q', 'name': 'Q', 'price_earnings_ttm': 2.4,
                       'data_errors': 'PE_VS_EARNINGS'}])
    history.append_snapshot(universe(), q, run_ts='2026-10-04 20:10', path=hist_path)
    h = history.load_history(hist_path)
    quarantined = h[h['status'] == 'quarantined']
    assert list(quarantined['name']) == ['Q'] and quarantined['rank'].isna().all()
    assert 'X:Q' not in set(history.persistence(h)['ticker'])


def test_latest_run_of_the_week_is_the_snapshot(hist_path):
    history.append_snapshot(universe(), run_ts='2026-09-27 20:00', path=hist_path)
    later = universe(A={'price_earnings_ttm': 19.5})
    history.append_snapshot(later, run_ts='2026-09-28 01:24', path=hist_path)
    snaps = history.weekly_snapshots(history.load_history(hist_path))
    assert snaps['run_ts'].nunique() == 1
    assert snaps['run_ts'].iloc[0] == pd.Timestamp('2026-09-28 01:24')


def test_streak_counts_snapshots_and_skips_missing_weeks(hist_path):
    # Weeks 08-02, 08-09, (08-16 no run), 08-23. With top_n=2: B drops out
    # in week 2 (C becomes best on every factor), comes back in week 3.
    # (ROE alone is not enough: winsorisation clips a single extreme ROE.)
    history.append_snapshot(universe(), run_ts='2026-08-02 20:00', path=hist_path)
    best_c = {'price_earnings_ttm': 8, 'return_on_equity_fq': 60.0, 'debt_to_equity': 0.1,
              'price_earnings_growth_ttm': 0.4, 'free_cash_flow_ttm': 5e9}
    history.append_snapshot(universe(C=best_c), run_ts='2026-08-09 20:00', path=hist_path)
    history.append_snapshot(universe(), run_ts='2026-08-23 20:00', path=hist_path)
    table = history.persistence(history.load_history(hist_path), top_n=2).set_index('name')
    assert table.loc['A', 'streak'] == 3            # missing 08-16 does not break it
    assert table.loc['A', 'streak_since'] == pd.Timestamp('2026-08-02')
    assert table.loc['B', 'streak'] == 1
    assert table.loc['B', 'weeks_top_n'] == 2
    assert table.loc['C', 'streak'] == 0


def test_decomposition_adds_up(hist_path):
    weeks = ['2026-09-13 20:00', '2026-09-20 20:00', '2026-09-27 20:00', '2026-10-04 20:00']
    pe_path = [12, 13, 14.5, 16]            # A re-rates: price up, EPS flat
    for ts, pe in zip(weeks, pe_path):
        week = universe(A={'price_earnings_ttm': pe, 'close': 100.0 * pe / 12},
                        D={'return_on_equity_fq': 14.0 + 3 * weeks.index(ts)})
        history.append_snapshot(week, run_ts=ts, path=hist_path)
    a = history.persistence(history.load_history(hist_path)).set_index('name').loc['A']

    by_factor = sum(a[f'd_{f}'] for f in screener.FACTOR_COLS)
    assert by_factor == pytest.approx(a['score_delta'])
    assert a['d_own'] + a['d_peers'] == pytest.approx(a['score_delta'])
    assert a['window_weeks'] == 4
    assert a['score_delta'] < 0 and a['score_slope'] < 0
    # Price +33%, implied EPS unchanged: the P/E move is all price
    assert a['price_chg_pct'] == pytest.approx(100 * (16 / 12 - 1))
    assert a['eps_chg_pct'] == pytest.approx(0.0, abs=1e-9)


def test_peer_only_change_has_zero_own_effect(hist_path):
    # A's own values never move; only D improves. Any change in A's score
    # must be attributed to peers.
    history.append_snapshot(universe(), run_ts='2026-09-27 20:00', path=hist_path)
    history.append_snapshot(universe(D={'return_on_equity_fq': 80.0}),
                            run_ts='2026-10-04 20:00', path=hist_path)
    a = history.persistence(history.load_history(hist_path)).set_index('name').loc['A']
    assert a['d_own'] == pytest.approx(0.0, abs=1e-12)
    assert a['score_delta'] < 0
    assert a['d_peers'] == pytest.approx(a['score_delta'])


def test_trend_window_stays_within_current_model(hist_path):
    # Scores from different models are on different scales: the trend window
    # must not reach back across the model change, but the streak does.
    history.append_snapshot(legacy_universe(), run_ts='2026-09-20 20:00', path=hist_path,
                            model_version='pre-0.7')
    history.append_snapshot(legacy_universe(), run_ts='2026-09-27 20:00', path=hist_path,
                            model_version='pre-0.7')
    history.append_snapshot(universe(), run_ts='2026-10-04 20:00', path=hist_path)
    a = history.persistence(history.load_history(hist_path)).set_index('name').loc['A']
    assert a['window_weeks'] == 1 and a['score_delta'] == 0
    assert a['streak'] == 3 and a['streak_mixed_models']
    assert a['model_version'] == screener_version()


def screener_version():
    from src import __version__
    return __version__


def test_legacy_window_uses_legacy_standardisation(hist_path):
    # Old history (raw values, no winsorisation): only D changes. A's own
    # effect must be exactly zero under the legacy standardisation too.
    history.append_snapshot(legacy_universe(), run_ts='2026-09-27 20:00', path=hist_path,
                            model_version='pre-0.7')
    history.append_snapshot(legacy_universe(D={'return_on_equity_fq': 80.0}),
                            run_ts='2026-10-04 20:00', path=hist_path,
                            model_version='pre-0.7')
    a = history.persistence(history.load_history(hist_path)).set_index('name').loc['A']
    assert a['window_weeks'] == 2
    assert a['d_own'] == pytest.approx(0.0, abs=1e-12)
    assert a['d_peers'] == pytest.approx(a['score_delta'])


def test_fading_selects_long_streak_losers():
    table = pd.DataFrame({
        'ticker': ['X:A', 'X:B', 'X:C'], 'name': ['A', 'B', 'C'],
        'rank': [1, 2, 12], 'streak': [4, 2, 0],
        'score_delta': [-0.10, -0.20, -0.30], 'window_weeks': [4, 4, 4],
    })
    assert list(history.fading(table, top_n=10, threshold=-0.05)['name']) == ['A']


def test_telegram_fading_line(hist_path):
    from src import telegram_alerts
    table = pd.DataFrame({
        'ticker': ['X:A'], 'name': ['A'], 'rank': [1], 'streak': [4],
        'score_delta': [-0.14], 'd_own': [0.08], 'd_peers': [-0.22],
        'price_chg_pct': [-4.9], 'eps_chg_pct': [-1e-12], 'window_weeks': [4],
    })
    text = telegram_alerts.format_fading(table)
    assert 'A -0.14 = own +0.08 / peers -0.22 (price -5%, EPS +0%)' in text


def test_empty_history():
    empty = history.load_history('does/not/exist.csv')
    assert empty.empty
    assert history.persistence(empty).empty
