"""Cross-sectional momentum among country ETFs and among US sector ETFs (survivorship-free, 1999-).
Long top-k by 12-1 return, monthly, 10 bp per side; vs equal-weight of the same set."""
import numpy as np, pandas as pd, yfinance as yf, statsmodels.api as sm
SETS = {
  "Países (iShares MSCI + SPY)": "SPY EWA EWC EWD EWG EWH EWI EWJ EWK EWL EWM EWN EWO EWP EWQ EWS EWU EWW EWZ EWT EWY".split(),
  "Sectores EE.UU. (SPDR)": "XLB XLE XLF XLI XLK XLP XLU XLV XLY".split(),
}
def nw(x):
    m = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": 3}); return m.params[0]*12, m.tvalues[0]
cagr = lambda x: (1+x).prod()**(12/len(x))-1
for name, tick in SETS.items():
    px = yf.download(tick, start="1998-01-01", auto_adjust=True, progress=False)["Close"].resample("ME").last()
    ret = px.pct_change(fill_method=None)
    for lb in (12, 6):
        sig = px.shift(1) / px.shift(lb) - 1
        k = 5 if len(tick) > 12 else 3
        rows, prev = [], pd.Series(dtype=float)
        for i in range(lb + 1, len(px) - 1):
            d, nxt = px.index[i], px.index[i+1]
            s = sig.loc[d].dropna(); r = ret.loc[nxt]; s = s[r.reindex(s.index).notna()]
            if len(s) < 8: continue
            top = s.nlargest(k).index; bot = s.nsmallest(k).index
            w = pd.Series(1/k, index=top); tov = w.sub(prev, fill_value=0).abs().sum()
            prev = w * (1+r[top]) / (1+r[top]).mean()
            rows.append({"date": nxt, "top": r[top].mean() - tov*0.001, "bot": r[bot].mean(), "ew": r[s.index].mean(), "tov": tov})
        df = pd.DataFrame(rows).set_index("date"); df["x"] = df.top - df.ew; df["wml"] = df.top - df.bot
        a, t = nw(df.x); a2, t2 = nw(df.wml)
        print(f"\n{name}, {lb}-1, top{k}  ({df.index[0]:%Y-%m}–{df.index[-1]:%Y-%m})")
        print(f"  top CAGR {cagr(df.top):5.1%} vol {df.top.std()*12**.5:5.1%} | EW {cagr(df.ew):5.1%} vol {df.ew.std()*12**.5:5.1%} | turnover/mes {df.tov.mean():.0%}")
        print(f"  top−EW {a:+5.1%}/año t={t:4.2f} | top−bottom {a2:+5.1%}/año t={t2:4.2f}")
        print("  por subperiodo top−EW: " + "  ".join(f"{p}: {df.x.loc[p[:4]:p[5:]].mean()*12:+.1%}" for p in ["1999-2007","2008-2015","2016-2026"]))
