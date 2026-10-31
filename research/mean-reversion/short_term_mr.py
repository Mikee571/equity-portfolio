"""Short-term mean reversion on liquid index ETFs.
Rules are fixed from published literature (Connors RSI(2), 2008) -> 2009+ is genuine post-publication out-of-sample.
Long-only. Signal at close t; two fills: (a) same close (optimistic, needs MOC), (b) next open (realistic).
Cost 5 bp per side. Benchmark: random entries with the same number/length of trades (exposure-matched)."""
import numpy as np, pandas as pd, yfinance as yf
TICK = ["SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "VWRL.AS"]
COST = 0.0005
rng = np.random.default_rng(0)

def rsi(c, n=2):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1/n).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1/n).mean()
    return 100 - 100 / (1 + up / dn)

def simulate(df, entry, exit_fn, fill):
    """Returns list of trade returns and in-market boolean series."""
    c, o = df.Close.values, df.Open.values
    ent, ex = entry.values, exit_fn.values
    trades, inmkt = [], np.zeros(len(df), bool); i = 0
    while i < len(df) - 2:
        if ent[i]:
            if fill == "close": px_in, j0 = c[i], i + 1
            else: px_in, j0 = o[i + 1], i + 1
            j = j0
            while j < len(df) - 1 and not ex[j]: j += 1
            px_out = c[j] if fill == "close" else o[min(j + 1, len(df) - 1)]
            trades.append((df.index[i], px_out / px_in - 1 - 2 * COST, j - i))
            inmkt[j0:j + 1] = True
            i = j + 1
        else:
            i += 1
    return pd.DataFrame(trades, columns=["date", "ret", "days"])

def random_bench(df, tr, n=500):
    """Same number of trades with same holding lengths, random start dates; close-to-close, same costs."""
    c = df.Close.values; L = len(c); out = []
    for _ in range(n):
        tot = 0.0
        for d in tr.days.values:
            s = rng.integers(200, L - d - 1); tot += c[s + d] / c[s] - 1 - 2 * COST
        out.append(tot / len(tr))
    return np.array(out)

def summary(tr, label, years):
    if len(tr) == 0: print(f"  {label}: sin operaciones"); return
    tot = (1 + tr.ret).prod() - 1
    print(f"  {label:18s} n={len(tr):4d} ({len(tr)/years:4.1f}/año) media={tr.ret.mean():+.2%} acierto={(tr.ret>0).mean():.0%} "
          f"días={tr.days.mean():.1f} CAGR={(1+tot)**(1/years)-1:+.1%} peor={tr.ret.min():+.1%}")

if __name__ == "__main__":
    allrows = []
    for t in TICK:
        df = yf.download(t, start="1993-01-01", auto_adjust=True, progress=False)
        df.columns = df.columns.get_level_values(0); df = df.dropna()
        if t == "VWRL.AS": df = df.loc["2014":]
        df = df[(df.Open > 0) & (df.High >= df.Low)]
        c = df.Close; sma200, sma5 = c.rolling(200).mean(), c.rolling(5).mean()
        z = (c - c.rolling(5).mean()) / c.rolling(20).std()
        R = {"RSI2<10 >SMA200": ((rsi(c) < 10) & (c > sma200), c > sma5),
             "z5<-1.5 >SMA200": ((z < -1.5) & (c > sma200), z > 0),
             "RSI2<10 sin filtro": (rsi(c) < 10, c > sma5)}
        print(f"\n=== {t} ({df.index[0]:%Y}–{df.index[-1]:%Y}) ===")
        for name, (en, exr) in R.items():
            for per, (a, b) in {"pre-2009": ("1993", "2008"), "post-2009": ("2009", "2026")}.items():
                sub = df.loc[a:b]
                if len(sub) < 300: continue
                yrs = len(sub) / 252
                for fill in ("close", "open"):
                    tr = simulate(sub, en.loc[a:b], exr.loc[a:b], fill)
                    if len(tr) < 5: continue
                    if fill == "open":
                        bench = random_bench(sub, tr)
                        p = (bench >= tr.ret.mean()).mean()
                        allrows.append(dict(tick=t, rule=name, period=per, n=len(tr), mean=tr.ret.mean(), bench=bench.mean(), p=p))
                    summary(tr, f"{name[:9]} {per} {fill}", yrs)
    R = pd.DataFrame(allrows)
    print("\n=== Resumen (fill = siguiente apertura) — media por operación vs entradas aleatorias de igual duración ===")
    R["exceso"] = R["mean"] - R.bench
    print(R.to_string(index=False, formatters={"mean": "{:+.2%}".format, "bench": "{:+.2%}".format, "exceso": "{:+.2%}".format, "p": "{:.3f}".format}))
    R.to_csv("summary_open_fill.csv", index=False)
