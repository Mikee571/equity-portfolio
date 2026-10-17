"""
Explain where a ticker drops out of the screener, or where it ranks.

    python -m src.diagnose MU VRT PLTR CAT

Runs the live pipeline once and reports, for every listing of each name:

    not fetched   market cap below the floor, or not on a domestic exchange
                  of the screened markets
    cleaning      the cleaning rule that removed it (universe.CLEANING_REASONS)
    missing data  loss-making, EPS falling, or a data gap
                  (screener.missing_data_reason)
    threshold     every five-factor threshold it fails, with its value
    quarantine    the data errors that held it back (src/validation.py)
    ranked        its rank and score, plus any data warnings

Names are TradingView symbols (MU, SHEL, GTT), not exchange-prefixed.
"""

import sys

import pandas as pd
from tradingview_screener import Query, col

from . import config, screener, universe, validation


def lookup(names: list) -> pd.DataFrame:
    """Every listing of these symbols in the screened markets, no filters."""
    _, df = (Query().set_markets(*config.MARKETS)
             .select('name', 'exchange', 'country', 'market_cap_basic')
             .where(col('name').isin(list(names)))
             .limit(500).get_scanner_data())
    return df


def _not_fetched_reason(rows: pd.DataFrame) -> str:
    if rows.empty:
        return 'not found in the screened markets'
    domestic = [config.EXCHANGE_COUNTRY.get(ex) is not None and c in config.EXCHANGE_COUNTRY[ex]
                for ex, c in zip(rows['exchange'], rows['country'])]
    home = rows[domestic]
    if home.empty:
        venues = ', '.join(sorted(set(rows['exchange'])))
        return f'no domestic listing in the screened markets (found on {venues})'
    mcap = home['market_cap_basic'].max()
    if pd.isna(mcap) or mcap <= config.MARKET_CAP_MIN:
        return f'market cap {mcap / 1e9:.2f}B below the {config.MARKET_CAP_MIN / 1e9:.0f}B floor'
    return 'listed and above the floor, but not returned by the query (incomplete fetch?)'


def explain(names: list, raw: pd.DataFrame, listings: pd.DataFrame = None) -> pd.DataFrame:
    """
    One row per listing found: name, ticker, stage, detail. `raw` is the
    fetched universe (universe.fetch_universe); `listings` is lookup(names)
    for names not in raw, and may be None if every name was fetched.
    """
    clean, dropped = universe.clean_universe(raw, return_dropped=True)
    prepared = screener.prepare(clean)
    reasons = screener.missing_data_reason(prepared)
    complete = validation.validate(prepared[reasons == ''])
    checks = screener.threshold_checks(complete)
    ranked, quarantine = screener.run_screener(clean)
    rank_of = {t: i + 1 for i, t in enumerate(ranked['ticker'])}
    score_of = dict(zip(ranked['ticker'], ranked['score']))

    out = []
    for name in names:
        rows = []
        for _, r in dropped[dropped['name'] == name].iterrows():
            detail = universe.CLEANING_REASONS[r['drop_reason']]
            if isinstance(r.get('kept_instead'), str):
                detail += f" ({r['kept_instead']})"
            rows.append((r['ticker'], 'cleaning', detail))

        for idx in clean.index[clean['name'] == name]:
            t = clean.at[idx, 'ticker']
            if reasons[idx]:
                missing = [f for f, c in screener.FACTOR_COLS.items() if pd.isna(prepared.at[idx, c])]
                rows.append((t, 'missing data', f"{reasons[idx]}: no {', '.join(missing)}"))
            elif t in rank_of:
                warn = complete.at[idx, 'data_warnings']
                rows.append((t, 'ranked', f"#{rank_of[t]} of {len(ranked)}, score {score_of[t]:+.2f}"
                                          + (f" (warning: {warn})" if warn else '')))
            elif t in set(quarantine['ticker']):
                rows.append((t, 'quarantine', complete.at[idx, 'data_errors']))
            else:
                failed = [c for c in checks.columns if not checks.at[idx, c]]
                values = {'P/E': 'price_earnings_ttm', 'ROE': 'return_on_equity_fq',
                          'D/E': 'debt_to_equity', '0 < PEG': 'price_earnings_growth_ttm',
                          'FCF': 'free_cash_flow_ttm'}
                parts = []
                for c in failed:
                    field = next(v for k, v in values.items() if c.startswith(k))
                    parts.append(f"{c} (is {complete.at[idx, field]:.4g})")
                rows.append((t, 'threshold', '; '.join(parts)))

        if not rows:
            found = (listings[listings['name'] == name] if listings is not None
                     else pd.DataFrame(columns=['exchange', 'country', 'market_cap_basic']))
            rows.append(('-', 'not fetched', _not_fetched_reason(found)))

        out += [{'name': name, 'ticker': t, 'stage': s, 'detail': d} for t, s, d in rows]
    return pd.DataFrame(out, columns=['name', 'ticker', 'stage', 'detail'])


def main(argv=None) -> None:
    names = [n.upper() for n in (argv if argv is not None else sys.argv[1:])]
    if not names:
        print(__doc__)
        return
    print('Fetching universe...')
    raw = universe.fetch_universe()
    missing = [n for n in names if n not in set(raw['name'])]
    listings = lookup(missing) if missing else None
    table = explain(names, raw, listings)
    with pd.option_context('display.width', 200, 'display.max_colwidth', 120):
        print('\n' + table.to_string(index=False))


if __name__ == '__main__':
    main()
