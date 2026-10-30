import numpy as np, pandas as pd, yfinance as yf
import xs_momentum_us as M

# 1) sector-neutral: demean 12-1 signal within sector each month (sector as of panel row)
sec = M.panel.pivot_table(index="date", columns="symbol", values="sector", aggfunc="last").reindex(columns=M.me.columns).ffill()
raw = M.mom(12)
sn = raw.copy()
for d in sec.index:
    if d in raw.index:
        s = raw.loc[d]; g = sec.loc[d]
        sn.loc[d] = s - s.groupby(g).transform("median")
M.report(M.backtest(sn), "12-1 neutral por sector")
# sector-only: each stock gets its sector's median momentum (pure sector bet)
so = raw.copy()
for d in sec.index:
    if d in raw.index:
        so.loc[d] = raw.loc[d].groupby(sec.loc[d]).transform("median")
M.report(M.backtest(so), "solo sector (mediana del sector)")

# SPY reference over same window
spy = yf.download("SPY", start="2013-01-01", auto_adjust=True, progress=False)["Close"].squeeze().resample("ME").last().pct_change().loc["2013-02":]
print(f"\nSPY CAGR mismo periodo: {(1+spy).prod()**(12/len(spy))-1:.1%}")
