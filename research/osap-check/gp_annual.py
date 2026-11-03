"""Variant of gp_vw.py with OSAP's construction: quintiles formed at the end of June and held 12 months.
Usage: python gp_annual.py   (after gp_vw.py, which writes gp_vw_monthly.csv)
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gp_vw as g
from src.backtest import analysis, prices, quality
rb = g.rb
data = rb.load_all(False); px, sym2cik = data['prices'], data['sym2cik']
dates = analysis.month_ends(px['close'].index)
adj_m = rb.by_cik(prices.month_end(px['adj_close']), sym2cik).loc[:dates[-1]]
fwd = analysis.forward_returns(adj_m)
pan = pd.read_parquet(rb.CACHE/'panel.parquet'); pan = analysis.attach_returns(pan[pan['date'].isin(dates)], fwd)
hist = quality.quality_history(pan, data['snapshots'])
# annual: quintile from June month-end, kept for 12 months; monthly VW within the held names
h = hist[hist[g.SIG].notna()].copy()
june = h[h.date.dt.month == 6].copy()
june['q'] = june.groupby('date')[g.SIG].transform(lambda s: pd.qcut(s.rank(method='first'), 5, labels=False) + 1)
june['form'] = june.date
h['form'] = h.date.apply(lambda d: pd.Timestamp(d.year if d.month >= 7 else d.year - 1, 6, 30) + pd.offsets.MonthEnd(0))
hh = h.merge(june[['cik', 'form', 'q']], on=['cik', 'form'], how='inner')
res = {}
for lbl, col in [('ew', None), ('vw', 'market_cap_basic')]:
    qs = {}
    for q, gq in hh.groupby('q'):
        w = gq.assign(w=1.0 if col is None else gq[col]).pivot_table(index='date', columns='cik', values='w', aggfunc='first')
        qs[q] = analysis.portfolio_returns(w.div(w.sum(axis=1), axis=0).fillna(0), fwd['1m'])['gross']
    avg = pd.concat(qs.values(), axis=1).mean(axis=1)
    res[f'{lbl}_annual_top_minus_avg'] = qs[5] - avg
    res[f'{lbl}_annual_bottom_minus_avg'] = qs[1] - avg
s = pd.DataFrame(res)
m = pd.read_csv(HERE / 'gp_vw_monthly.csv', index_col=0, parse_dates=True)
s = s.join(m['osap_top_minus_avg'])
for a, b in [('2013-07','2025-12'), ('2013-07','2016-12'), ('2017-01','2021-11'), ('2021-12','2025-12')]:
    x = s.loc[a:b]
    print(a, b, {c: f"{x[c].mean()*12:+.3f} (t {analysis.newey_west_t(x[c].dropna(),3):.2f})" for c in s.columns})
print('corr con OSAP:', s.corr().round(2)['osap_top_minus_avg'].to_dict())
for t in ['NVDA', 'AAPL', 'MSFT']:
    c = [k for k, v in sym2cik.items() if k == t]
    if c:
        cik = sym2cik[c[0]]; x = hh[hh.cik == cik].groupby('form').q.first(); print(t, x.to_dict())
