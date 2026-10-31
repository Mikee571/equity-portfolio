"""Realised vol project, step 1: HAR-RV forecast vs naive/EWMA, then vol targeting on SPY (no leverage)."""
import numpy as np, pandas as pd, yfinance as yf, statsmodels.api as sm

df = yf.download("SPY", start="1993-02-01", auto_adjust=True, progress=False)
df.columns = df.columns.get_level_values(0)
r = np.log(df.Close).diff()
park = np.log(df.High / df.Low) ** 2 / (4 * np.log(2))   # Parkinson daily variance
rv = park.rolling(1).mean()
H = 21
# targets/features on log annualised vol
lv = lambda x: 0.5 * np.log(x.clip(lower=1e-10) * 252)
d, w, m = rv, rv.rolling(5).mean(), rv.rolling(22).mean()
X = pd.concat([lv(d), lv(w), lv(m)], axis=1); X.columns = ["d", "w", "m"]
y = lv(rv.rolling(H).mean().shift(-H))           # future 21d vol
D = pd.concat([X, y.rename("y")], axis=1).dropna()
D_all = X.dropna()

# expanding walk-forward, refit yearly, with H-day embargo
fc = pd.Series(index=D_all.index, dtype=float)
years = sorted(set(D_all.index.year))
for yr in years:
    if yr < 2003: continue
    tr = D[D.index < pd.Timestamp(f"{yr}-01-01") - pd.Timedelta(days=H * 2)]
    mdl = sm.OLS(tr.y, sm.add_constant(tr[["d", "w", "m"]])).fit()
    idx = D_all.index[D_all.index.year == yr]
    fc[idx] = mdl.predict(sm.add_constant(D_all.loc[idx], has_constant="add"))
har = np.exp(fc)                                    # annualised vol forecast
naive = np.exp(lv(m.rolling(1).mean()))             # trailing 22d
ew = np.sqrt((r ** 2).ewm(alpha=0.06).mean() * 252)
real = np.exp(y)
E = pd.concat([har, naive, ew, real], axis=1, keys=["har", "naive", "ewma", "real"]).dropna()
def ql(f, a): return (a**2 / f**2 - np.log(a**2 / f**2) - 1).mean()
print("Forecast eval 2003-, 21d ahead (n=%d)" % len(E))
for c in ["har", "naive", "ewma"]:
    print(f"{c:6s} RMSE={np.sqrt(((E[c]-E.real)**2).mean()):.4f}  QLIKE={ql(E[c],E.real):.4f}  corr={E[c].corr(E.real):.3f}")

# vol targeting
def stats(x, name):
    ann = x.mean() * 252; vol = x.std() * np.sqrt(252)
    eq = (1 + x).cumprod(); dd = (eq / eq.cummax() - 1).min()
    print(f"{name:22s} ret={ann:6.2%} vol={vol:6.2%} sharpe={ann/vol:5.2f} maxDD={dd:6.1%}")
    return eq
ret = df.Close.pct_change()
res = {}
for lab, f in [("HAR", har), ("naive", naive), ("EWMA", ew)]:
    for tgt in (0.10, 0.12):
        lev = (tgt / f).clip(upper=1.0).shift(1)    # signal known at t-1 close
        cost = lev.diff().abs() * 0.0005            # 5bp per unit turnover
        pr = (lev * ret - cost).dropna()
        res[(lab, tgt)] = pr
bh = ret.loc["2003-01-01":].dropna()
print("\nVol targeting on SPY, 2003-, no leverage, cash=0%")
stats(bh, "Buy&hold")
for (lab, tgt), pr in res.items():
    p = pr.loc[bh.index[0]:]
    stats(p, f"{lab} tgt{int(tgt*100)}%")
# subperiods + paired test HAR10 vs B&H on Sharpe diff via bootstrap
p = res[("HAR", 0.10)].loc[bh.index[0]:]
print("\nSubperiods Sharpe (BH vs HAR10):")
for a, b in [("2003","2009"),("2010","2019"),("2020","2026")]:
    x, z = bh[a:b], p[a:b]
    print(a, b, f"BH {x.mean()/x.std()*np.sqrt(252):.2f}  HAR {z.mean()/z.std()*np.sqrt(252):.2f}  ret BH {x.mean()*252:.1%} HAR {z.mean()*252:.1%}")
rng = np.random.default_rng(0); n = len(p); bs = []
dfp = pd.concat([bh, p], axis=1).dropna().values
for _ in range(2000):
    i = (rng.integers(0, n - 20, n // 20)[:, None] + np.arange(20)).ravel()[:n]
    s = dfp[i]; bs.append((s[:,1].mean()/s[:,1].std()) - (s[:,0].mean()/s[:,0].std()))
bs = np.array(bs) * np.sqrt(252)
print(f"Sharpe diff HAR10-BH: {bs.mean():.2f}, 95% CI [{np.percentile(bs,2.5):.2f},{np.percentile(bs,97.5):.2f}]")

# --- Control: is it timing or just lower exposure? static mix with same avg exposure, plus T-bill cash yield
irx = yf.download("^IRX", start="2002-01-01", auto_adjust=True, progress=False)["Close"].squeeze()
rf = (irx / 100 / 252).reindex(ret.index).ffill().fillna(0)
print("\nWith T-bill on cash, 2003-:")
for (lab, tgt) in [("HAR", 0.10), ("naive", 0.10), ("EWMA", 0.10)]:
    f = {"HAR": har, "naive": naive, "EWMA": ew}[lab]
    lev = (tgt / f).clip(upper=1.0).shift(1).loc[bh.index[0]:]
    pr = (lev * ret + (1 - lev) * rf - lev.diff().abs() * 0.0005).dropna()
    avg = lev.mean()
    st = (avg * ret + (1 - avg) * rf).loc[pr.index]
    print(f"{lab} tgt10: avg exposure {avg:.0%}, turnover/yr {lev.diff().abs().sum()/len(lev)*252:.1f}x")
    stats(pr, f"  {lab} timed")
    stats(st, f"  static {avg:.0%} SPY")
stats(ret.loc[bh.index[0]:] , "  B&H (ref)")
