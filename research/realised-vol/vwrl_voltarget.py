"""Step 2: vol targeting applied to VWRL (real core holding). Naive 22d Parkinson vol (step 1: HAR adds nothing).
Realistic retail implementation: weekly check, rebalance only if exposure drifts > band; no leverage."""
import numpy as np, pandas as pd, yfinance as yf

def load(t, start):
    d = yf.download(t, start=start, auto_adjust=True, progress=False)
    d.columns = d.columns.get_level_values(0)
    return d.dropna()

def stats(x, name):
    ann = (1 + x).prod() ** (252 / len(x)) - 1; vol = x.std() * np.sqrt(252)
    eq = (1 + x).cumprod(); dd = (eq / eq.cummax() - 1).min()
    worst = x.groupby(x.index.year).apply(lambda s: (1 + s).prod() - 1).min()
    print(f"  {name:30s} CAGR={ann:6.2%} vol={vol:6.2%} ret/vol={ann/vol:5.2f} maxDD={dd:6.1%} peor año={worst:6.1%}")

def run(df, tgt, band, cost, cash, freq):
    ret = df.Close.pct_change()
    park = np.log(df.High / df.Low) ** 2 / (4 * np.log(2))
    # guard: some EU listings have H==L on illiquid days -> fall back to close-close
    cc = np.log(df.Close).diff() ** 2
    v = np.sqrt(park.where(park > 0, cc).rolling(22).mean() * 252)
    want = (tgt / v).clip(upper=1.0)
    lev = pd.Series(np.nan, index=df.index); cur = 1.0; trades = 0; turn = 0.0
    p = df.index.to_series().dt.to_period(freq) if freq != "D" else None
    check = p.ne(p.shift()) if freq != "D" else pd.Series(True, index=df.index)
    for i, t in enumerate(df.index):
        if check.iloc[i] and not np.isnan(want.iloc[i]) and abs(want.iloc[i] - cur) > band:
            turn += abs(want.iloc[i] - cur); cur = want.iloc[i]; trades += 1
        lev.iloc[i] = cur
    L = lev.shift(1)
    tc = L.diff().abs().fillna(0) * cost
    pr = (L * ret + (1 - L) * cash / 252 - tc).dropna()
    yrs = len(pr) / 252
    return pr, L.mean(), trades / yrs, turn / yrs

for tick, start, label in [("VWRL.AS", "2014-01-01", "VWRL.AS (EUR, real; 2013 tiene precios erróneos)"), ("ACWI", "2008-04-01", "ACWI (USD, proxy largo con 2008)")]:
    df = load(tick, start)
    print(f"\n=== {label}: {df.index[0].date()} – {df.index[-1].date()} ===")
    bh = df.Close.pct_change().iloc[23:].dropna()
    stats(bh, "Buy & hold")
    for tgt in (0.10, 0.12):
        for freq, band in [("D", 0.0), ("W", 0.10), ("M", 0.10)]:
            pr, avg, ntr, to = run(df, tgt, band, 0.0010, 0.0, freq)
            pr = pr.loc[bh.index[0]:]
            st = avg * bh
            stats(pr, f"tgt{int(tgt*100)} {freq} banda{int(band*100)}% ({ntr:.0f} op/año)")
        stats(st, f"  control estático {avg:.0%}")
    pr, *_ = run(df, 0.12, 0.10, 0.0010, 0.02, "W")
    stats(pr.loc[bh.index[0]:], "tgt12 W banda10% caja 2%")
