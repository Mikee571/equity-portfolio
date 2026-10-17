"""
Point-in-time fundamentals from XBRL facts: one snapshot per fiscal period
end, dated by the day the market could first know it.

Rules
-----
- First reported. Each (concept, start, end) keeps its earliest-filed value,
  and `known` is that filing date. Later restatements are ignored: the
  backtest sees the number the market saw first.
- Share basis. Per-share values and share counts are converted to today's
  share basis with the split dates after their filing date (issuers restate
  per-share data for splits that happen before the statements are issued).
  Prices from yfinance are on today's basis too, so P/E is consistent.
- TTM from year-to-date figures. 10-Qs report income and cash flow
  year-to-date, so for a period ending at E:
      TTM(E) = YTD(E) + FY(previous) - YTD(E one year earlier)
  and TTM(E) = FY(E) at a fiscal year end.
- A snapshot is known on the latest `known` among the inputs it uses.

as_of() then picks, for any date, the latest snapshot already known.
"""

import numpy as np
import pandas as pd

from . import prices

DAY = np.timedelta64(1, 'D')
ANNUAL_DAYS = (340, 390)     # 52/53-week years run 363-370 days
END_TOL_DAYS = 10            # 52/53-week fiscal calendars drift up to 7 days
DUR_TOL_DAYS = 20
STALE_DAYS = 456             # ~15 months: older snapshots are not used

# Quantity -> concepts in priority order (first one available wins).
FLOWS = {
    'ni': ['NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic'],
    'eps': ['EarningsPerShareDiluted', 'EarningsPerShareBasicAndDiluted', 'EarningsPerShareBasic'],
    'cfo': ['NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'],
    'capex': ['PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsToAcquireProductiveAssets',
              'PaymentsForCapitalImprovements', 'PaymentsToAcquireOtherPropertyPlantAndEquipment'],
    'diluted_shares': ['WeightedAverageNumberOfDilutedSharesOutstanding'],
}
INSTANTS = {
    'equity': ['StockholdersEquity',
               'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
    'equity_total': ['StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
                     'StockholdersEquity'],
}
# Inputs of the gross-profitability quality factor (src/backtest/quality.py).
# They get their own `known_quality` date so that adding them leaves the
# screener backtest's `known` untouched.
QUALITY_FLOWS = {
    'gross_profit': ['GrossProfit'],
    'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
                'RevenueFromContractWithCustomerIncludingAssessedTax', 'SalesRevenueNet'],
    'cogs': ['CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfGoodsSold'],
}
QUALITY_INSTANTS = {'assets': ['Assets']}
# Debt is tagged in many ways (see debt_by_date()); operating leases are
# kept apart because only some definitions of debt include them.
DEBT_CONCEPTS = [
    'LongTermDebt', 'LongTermDebtNoncurrent', 'LongTermDebtCurrent', 'DebtCurrent',
    'ShortTermBorrowings', 'CommercialPaper',
    'LongTermDebtAndCapitalLeaseObligations', 'LongTermDebtAndCapitalLeaseObligationsCurrent',
    'LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities',
    'DebtAndCapitalLeaseObligations', 'DebtLongtermAndShorttermCombinedAmount',
    'LongTermNotesPayable',
    'FinanceLeaseLiability', 'FinanceLeaseLiabilityNoncurrent', 'FinanceLeaseLiabilityCurrent',
    'OperatingLeaseLiability', 'OperatingLeaseLiabilityNoncurrent', 'OperatingLeaseLiabilityCurrent',
]
# A balance sheet without debt tags (e.g. a 10-Q that uses company-specific
# tags where the 10-K used standard ones) falls back to the latest complete
# one this recent.
DEBT_CARRY_DAYS = 400
PER_SHARE = {'EarningsPerShareDiluted', 'EarningsPerShareBasicAndDiluted', 'EarningsPerShareBasic'}
SHARE_COUNTS = {'WeightedAverageNumberOfDilutedSharesOutstanding', 'EntityCommonStockSharesOutstanding'}
COVER_SHARES = 'EntityCommonStockSharesOutstanding'


def first_reported(facts: pd.DataFrame) -> pd.DataFrame:
    """Earliest-filed row per (concept, start, end)."""
    return (facts.sort_values('filed', kind='stable')
            .drop_duplicates(['concept', 'start', 'end'], keep='first'))


def to_current_basis(facts: pd.DataFrame, split_events: pd.Series) -> pd.DataFrame:
    """Per-share values and share counts restated to today's share basis."""
    if split_events is None or split_events.empty:
        return facts
    facts = facts.copy()
    factor = prices.split_factor_after(split_events, facts['filed'])
    concept = facts['concept'].astype(str)
    per_share = concept.isin(PER_SHARE).to_numpy()
    counts = concept.isin(SHARE_COUNTS).to_numpy()
    val = facts['val'].to_numpy(dtype=float).copy()
    val[per_share] /= factor[per_share]
    val[counts] *= factor[counts]
    facts['val'] = val
    return facts


def ttm_series(rows: pd.DataFrame) -> pd.DataFrame:
    """
    TTM value of one duration concept at every period end it allows.
    `rows`: first-reported facts of that concept (start, end, val, filed).
    Returns DataFrame indexed by period end with columns val, known.
    """
    rows = rows.dropna(subset=['start'])
    if rows.empty:
        return pd.DataFrame(columns=['val', 'known'])
    start = rows['start'].to_numpy('datetime64[D]')
    end = rows['end'].to_numpy('datetime64[D]')
    val = rows['val'].to_numpy(dtype=float)
    known = rows['filed'].to_numpy('datetime64[D]')
    dur = (end - start) / DAY
    annual = (dur >= ANNUAL_DAYS[0]) & (dur <= ANNUAL_DAYS[1])

    out_end, out_val, out_known = [], [], []
    for e in np.unique(end):
        at_e = np.flatnonzero(end == e)
        ann = at_e[annual[at_e]]
        if len(ann):
            i = ann[0]
            out_end.append(e); out_val.append(val[i]); out_known.append(known[i])
            continue
        at_e = at_e[dur[at_e] < ANNUAL_DAYS[0]]
        if not len(at_e):
            continue
        i = at_e[np.argmax(dur[at_e])]                     # year-to-date figure
        prev_fy_end = start[i] - DAY
        fy = np.flatnonzero(annual & (np.abs((end - prev_fy_end) / DAY) <= END_TOL_DAYS))
        prev_e = e - np.timedelta64(365, 'D')
        ytd = np.flatnonzero(~annual & (np.abs((end - prev_e) / DAY) <= END_TOL_DAYS)
                             & (np.abs(dur - dur[i]) <= DUR_TOL_DAYS))
        if not len(fy) or not len(ytd):
            continue
        j = fy[np.argmin(np.abs((end[fy] - prev_fy_end) / DAY))]
        k = ytd[np.argmin(np.abs((end[ytd] - prev_e) / DAY))]
        out_end.append(e)
        out_val.append(val[i] + val[j] - val[k])
        out_known.append(max(known[i], known[j], known[k]))
    return pd.DataFrame({'val': out_val, 'known': pd.to_datetime(out_known)},
                        index=pd.to_datetime(out_end))


def instant_series(rows: pd.DataFrame) -> pd.DataFrame:
    """Balance-sheet value at every date it was reported: columns val, known."""
    rows = rows[rows['start'].isna()]
    out = rows.drop_duplicates('end').set_index('end')[['val', 'filed']]
    return out.rename(columns={'filed': 'known'}).sort_index()


def by_priority(series_by_concept: dict, concepts: list) -> pd.DataFrame:
    """Combine per-concept series: at each date, the first concept with a value."""
    out = pd.DataFrame({'val': pd.Series(dtype=float), 'known': pd.Series(dtype='datetime64[ns]')})
    for c in concepts:
        s = series_by_concept.get(c)
        if s is not None and not s.empty:
            out = s.copy() if out.empty else out.combine_first(s)
    out['val'] = out['val'].astype(float)
    out['known'] = pd.to_datetime(out['known'])
    return out.sort_index()


def debt_by_date(groups: dict) -> pd.DataFrame:
    """
    Debt per balance-sheet date, from whichever tags the company used there.
    Columns:
        full     total debt incl. current portion and finance leases: the
                 largest of the candidate combinations below that is complete
                 at that date (taking the largest guards against a candidate
                 that misses a component)
        partial  short-term debt alone, for dates with no long-term tag
        oplease  operating lease liabilities (on balance sheet since 2019)
        known    latest filing date among the tags used
    """
    present = [c for c in DEBT_CONCEPTS if c in groups]
    if not present:
        return pd.DataFrame(columns=['full', 'partial', 'oplease', 'known'])
    inst = {c: instant_series(groups[c]) for c in present}
    wide = pd.DataFrame({c: s['val'] for c, s in inst.items()})
    known = pd.DataFrame({c: s['known'] for c, s in inst.items()}).max(axis=1)

    def g(name):
        return wide[name] if name in wide else pd.Series(np.nan, index=wide.index)

    def pair(total, noncurrent, current):
        return g(total).fillna(g(noncurrent) + g(current).fillna(0))

    st = g('ShortTermBorrowings').fillna(0) + g('CommercialPaper').fillna(0)
    fin = pair('FinanceLeaseLiability', 'FinanceLeaseLiabilityNoncurrent',
               'FinanceLeaseLiabilityCurrent').fillna(0)
    candidates = pd.concat([
        g('DebtAndCapitalLeaseObligations'),
        g('DebtLongtermAndShorttermCombinedAmount'),
        g('LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities') + st,
        g('LongTermDebt') + st + fin,
        g('LongTermDebtNoncurrent') + g('DebtCurrent') + fin,        # DebtCurrent: current LTD + short-term
        g('LongTermDebtNoncurrent') + g('LongTermDebtCurrent').fillna(0) + st + fin,
        g('LongTermDebtAndCapitalLeaseObligations')
        + g('LongTermDebtAndCapitalLeaseObligationsCurrent').fillna(0) + st,
        g('LongTermNotesPayable') + st,
    ], axis=1)
    partial = pd.concat([g('DebtCurrent'), st.where(st > 0)], axis=1).max(axis=1)
    oplease = pair('OperatingLeaseLiability', 'OperatingLeaseLiabilityNoncurrent',
                   'OperatingLeaseLiabilityCurrent')
    return pd.DataFrame({'full': candidates.max(axis=1), 'partial': partial,
                         'oplease': oplease, 'known': known}).sort_index()


def latest_before(values: pd.Series, known: pd.Series, dates, max_days: int) -> pd.DataFrame:
    """Latest non-NaN value dated on or before each date, within max_days."""
    v = values.dropna()
    dates = pd.DatetimeIndex(dates)
    if v.empty:
        return pd.DataFrame({'val': np.nan, 'known': pd.NaT}, index=dates)
    pos = np.searchsorted(v.index.values, dates.values, side='right') - 1
    idx = np.maximum(pos, 0)
    ok = (pos >= 0) & ((dates.values - v.index.values[idx]) <= np.timedelta64(max_days, 'D'))
    vals = np.where(ok, v.to_numpy()[idx], np.nan)
    kn = pd.Series(known.reindex(v.index).to_numpy()[idx], index=dates).where(ok)
    return pd.DataFrame({'val': vals, 'known': pd.to_datetime(kn)}, index=dates)


def lookup(series: pd.DataFrame, dates, tol_days: int = 0) -> pd.DataFrame:
    """Value and known date of `series` at each date (nearest within tol_days)."""
    dates = pd.DatetimeIndex(dates)
    if series.empty:
        return pd.DataFrame({'val': np.nan, 'known': pd.NaT}, index=dates)
    s = series.sort_index()
    idx = s.index.get_indexer(dates, method='nearest',
                              tolerance=pd.Timedelta(days=tol_days)) if tol_days else s.index.get_indexer(dates)
    vals = np.where(idx >= 0, s['val'].to_numpy()[idx], np.nan)
    knowns = pd.Series(s['known'].to_numpy()[idx], index=dates).where(idx >= 0)
    return pd.DataFrame({'val': vals, 'known': pd.to_datetime(knowns)}, index=dates)


def company_snapshots(facts: pd.DataFrame, split_events: pd.Series = None) -> pd.DataFrame:
    """
    One row per fiscal period end with a TTM net income. Columns:
        ni, eps, eps_prev (TTM one year earlier), cfo, capex, diluted_shares,
        cover_shares, equity, equity_prev, equity_total, debt (incl. finance
        leases), oplease (operating lease liabilities),
        known (date the snapshot was fully public), capex_reported (False if
        the company never tags capex: capex is then taken as 0).
    """
    facts = to_current_basis(first_reported(facts), split_events)
    groups = {c: g for c, g in facts.groupby(facts['concept'].astype(str), sort=False)}

    flows = {key: by_priority({c: ttm_series(groups[c]) for c in cs if c in groups}, cs)
             for key, cs in FLOWS.items()}
    instants = {key: by_priority({c: instant_series(groups[c]) for c in cs if c in groups}, cs)
                for key, cs in INSTANTS.items()}
    debt = debt_by_date(groups)

    ends = flows['ni'].index
    if not len(ends):
        return pd.DataFrame()
    prev = ends - pd.Timedelta(days=365)
    parts = {
        'ni': lookup(flows['ni'], ends),
        'eps': lookup(flows['eps'], ends),
        'eps_prev': lookup(flows['eps'], prev, END_TOL_DAYS),
        'cfo': lookup(flows['cfo'], ends),
        'capex': lookup(flows['capex'], ends),
        'diluted_shares': lookup(flows['diluted_shares'], ends),
        # for EPS = NI / diluted shares where EPS itself is not tagged
        'ni_prev': lookup(flows['ni'], prev, END_TOL_DAYS),
        'diluted_shares_prev': lookup(flows['diluted_shares'], prev, END_TOL_DAYS),
        'equity': lookup(instants['equity'], ends),
        'equity_prev': lookup(instants['equity'], prev, END_TOL_DAYS),
        'equity_total': lookup(instants['equity_total'], ends),
    }
    # Debt: the latest complete figure, else short-term debt alone, else 0
    # (a company that never tags debt is taken as debt-free).
    full = latest_before(debt['full'], debt['known'], ends, DEBT_CARRY_DAYS)
    partial = latest_before(debt['partial'], debt['known'], ends, DEBT_CARRY_DAYS)
    parts['debt'] = full.fillna({'val': partial['val'], 'known': partial['known']})
    parts['oplease'] = latest_before(debt['oplease'], debt['known'], ends, DEBT_CARRY_DAYS)

    snap = pd.DataFrame({k: p['val'].to_numpy() for k, p in parts.items()}, index=ends)
    snap['debt'] = snap['debt'].fillna(0.0)
    snap['oplease'] = snap['oplease'].fillna(0.0)
    snap['capex_reported'] = 'capex' in flows and not flows['capex'].empty
    if not snap['capex_reported'].iloc[0]:
        snap['capex'] = 0.0
    known = pd.DataFrame({k: p['known'].to_numpy() for k, p in parts.items()}, index=ends)
    snap['known'] = known.max(axis=1).to_numpy()

    # Quality-factor inputs, dated separately (see QUALITY_FLOWS)
    quality = {key: lookup(by_priority({c: ttm_series(groups[c]) for c in cs if c in groups}, cs), ends)
               for key, cs in QUALITY_FLOWS.items()}
    quality.update({key: lookup(by_priority({c: instant_series(groups[c]) for c in cs if c in groups}, cs), ends)
                    for key, cs in QUALITY_INSTANTS.items()})
    for key, p in quality.items():
        snap[key] = p['val'].to_numpy()
    known_q = pd.DataFrame({k: p['known'].to_numpy() for k, p in quality.items()}, index=ends)
    snap['known_quality'] = pd.concat([known.max(axis=1), known_q.max(axis=1)], axis=1).max(axis=1).to_numpy()

    # Cover-page shares outstanding: reported as of a date between the
    # period end and the filing. Take the first one dated after each end,
    # provided it was public by the time the snapshot was (a later filing's
    # cover would be look-ahead).
    snap['cover_shares'] = np.nan
    if COVER_SHARES in groups:
        cover = instant_series(groups[COVER_SHARES])
        pos = np.searchsorted(cover.index.values, ends.values, side='right')
        ok = pos < len(cover)
        at = np.minimum(pos, len(cover) - 1)
        cover_end = np.where(ok, cover.index.values[at], np.datetime64('NaT', 'ns'))
        fresh = (ok & ((cover_end - ends.values) <= np.timedelta64(150, 'D'))
                 & (cover['known'].to_numpy()[at] <= snap['known'].to_numpy()))
        snap.loc[fresh, 'cover_shares'] = cover['val'].to_numpy()[pos[fresh]]
    snap.index.name = 'period_end'
    return snap


def build_snapshots(facts: pd.DataFrame, splits_by_cik: dict) -> pd.DataFrame:
    """company_snapshots for every CIK in `facts`, stacked with a cik column."""
    out = []
    for cik, g in facts.groupby('cik', sort=False):
        snap = company_snapshots(g, splits_by_cik.get(cik))
        if not snap.empty:
            out.append(snap.assign(cik=cik).reset_index())
    snaps = pd.concat(out, ignore_index=True)
    numeric = snaps.columns.difference(['period_end', 'known', 'known_quality', 'cik', 'capex_reported'])
    snaps[numeric] = snaps[numeric].astype(float)
    return snaps


def as_of(snapshots: pd.DataFrame, date, stale_days: int = STALE_DAYS) -> pd.DataFrame:
    """
    Latest snapshot per CIK that was public strictly before `date`, and whose
    period ended within stale_days. One row per CIK.
    """
    date = pd.Timestamp(date)
    s = snapshots[(snapshots['known'] < date)
                  & (snapshots['period_end'] >= date - pd.Timedelta(days=stale_days))]
    return s.sort_values(['cik', 'period_end']).drop_duplicates('cik', keep='last').set_index('cik')
