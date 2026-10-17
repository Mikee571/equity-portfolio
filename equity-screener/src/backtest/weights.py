"""
Are the score weights worth changing? Evidence from the point-in-time backtest.

The survivors and their z-scores do not depend on the weights (thresholds and
standardisation come first), so any weighting can be evaluated by re-ranking
the same survivors every month. Four questions:

1. Sensitivity: how much do plausible alternatives change the ranking and
   the top N? (no returns involved)
2. Power: the smallest annual return difference between two weightings the
   backtest could detect (t = 2), given their tracking error.
3. Where do the current weights sit among random weightings?
4. Persistence: do the weights that worked best in one half of the sample
   still work in the other? If not, choosing weights on past returns does
   not help.

The alternatives in ALTERNATIVES were fixed before looking at their returns.

Usage:  python -m src.backtest.weights   (needs the run_backtest.py caches)
"""

import numpy as np
import pandas as pd

from .. import config
from . import analysis

FACTORS = list(config.SCORE_WEIGHTS)
ZCOLS = [f'z_{f}' for f in FACTORS]
CURRENT = np.array([config.SCORE_WEIGHTS[f] for f in FACTORS])
ALTERNATIVES = {
    'current': CURRENT,
    'equal': np.full(len(FACTORS), 1 / len(FACTORS)),
    # ROE's weight shared pro rata: ROE > 12% is already a threshold
    'no_roe': np.where(np.array(FACTORS) == 'roe', 0, CURRENT) / (1 - config.SCORE_WEIGHTS['roe']),
}
SPLIT = pd.Timestamp('2018-12-31')
N_RANDOM = 2000


def monthly_groups(ranked: pd.DataFrame) -> list:
    """[(date, z matrix, next-month returns, ciks)] for months with a forward return."""
    ranked = ranked[ranked['fwd_1m'].notna().groupby(ranked['date']).transform('any')]
    return [(d, g[ZCOLS].to_numpy(), g['fwd_1m'].fillna(0).to_numpy(), g['cik'].to_numpy())
            for d, g in ranked.groupby('date', sort=True)]


def top_n(groups: list, w: np.ndarray, n: int = config.TOP_N) -> tuple:
    """(equal-weighted next-month return of the top n by w . z, the ciks picked), per month."""
    rets, picks = [], []
    for _, z, r, ciks in groups:
        idx = np.argsort(-(z @ w), kind='stable')[:n]
        rets.append(r[idx].mean())
        picks.append(set(ciks[idx]))
    return pd.Series(rets, index=pd.DatetimeIndex([g[0] for g in groups])), picks


def excess(r: pd.Series, bench: pd.Series) -> dict:
    ex = (r - bench).dropna()
    te = ex.std() * np.sqrt(12)
    return {'excess_ann': ex.mean() * 12, 't_stat': analysis.newey_west_t(ex, 3), 'tracking_error': te,
            'min_detectable': 2 * te / np.sqrt(len(ex) / 12) if te > 0 else np.nan}


def study(ranked: pd.DataFrame, universe_ret: pd.Series, seed: int = 7) -> dict:
    groups = monthly_groups(ranked)
    cur_ret, cur_picks = top_n(groups, CURRENT)

    sens, perf = [], []
    for name, w in ALTERNATIVES.items():
        ret, picks = top_n(groups, w)
        rc = np.mean([pd.Series(z @ w).rank().corr(pd.Series(z @ CURRENT).rank()) for _, z, _, _ in groups])
        sens.append({'weights': name, 'score_rank_corr': rc,
                     'top_n_in_common': np.mean([len(a & b) for a, b in zip(picks, cur_picks)])})
        vs_cur = excess(ret, cur_ret) if name != 'current' else {}
        perf.append({'weights': name, **{f'{k}_vs_universe': v for k, v in excess(ret, universe_ret).items()
                                         if k in ('excess_ann', 't_stat')},
                     **{f'{k}_vs_current': v for k, v in vs_cur.items()}})

    rng = np.random.default_rng(seed)
    w_rand = rng.dirichlet(np.ones(len(FACTORS)), N_RANDOM)
    full, first, second = [], [], []
    for w in w_rand:
        ex = top_n(groups, w)[0] - universe_ret
        full.append(ex.mean() * 12)
        first.append(ex[ex.index <= SPLIT].mean() * 12)
        second.append(ex[ex.index > SPLIT].mean() * 12)
    full, first, second = map(np.array, (full, first, second))
    cur_ex = cur_ret - universe_ret
    best = np.argsort(-first)[:20]
    random = {
        'current_excess': cur_ex.mean() * 12,
        'current_percentile': (full < cur_ex.mean() * 12).mean(),
        'random_median': np.median(full),
        'random_p5': np.quantile(full, 0.05),
        'random_p95': np.quantile(full, 0.95),
        'persistence_rank_corr': pd.Series(first).rank().corr(pd.Series(second).rank()),
        'best20_first_half': first[best].mean(),
        'best20_second_half': second[best].mean(),
        'all_second_half_median': np.median(second),
        'current_first_half': cur_ex[cur_ex.index <= SPLIT].mean() * 12,
        'current_second_half': cur_ex[cur_ex.index > SPLIT].mean() * 12,
    }
    return {'sensitivity': pd.DataFrame(sens), 'performance': pd.DataFrame(perf),
            'random_weights': pd.Series(random)}


def main():
    import run_backtest as rb
    from . import prices

    data = rb.load_all(False)
    px, sym2cik = data['prices'], data['sym2cik']
    dates = analysis.month_ends(px['close'].index)
    adj_m = rb.by_cik(prices.month_end(px['adj_close']), sym2cik).loc[:dates[-1]]
    pan = pd.read_parquet(rb.CACHE / 'panel.parquet')
    pan = analysis.attach_returns(pan[pan['date'].isin(dates)], analysis.forward_returns(adj_m))
    uni, ranked, _ = analysis.screen_history(pan)
    universe_ret = uni.groupby('date')['fwd_1m'].apply(lambda r: r.fillna(0).mean())
    out = study(ranked, universe_ret)
    pd.set_option('display.width', 200)
    pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
    for key, frame in out.items():
        print(f"\n=== {key} ===")
        print(frame.to_string() if isinstance(frame, pd.Series) else frame.to_string(index=False))


if __name__ == '__main__':
    main()
