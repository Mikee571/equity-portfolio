import numpy as np, pandas as pd, yfinance as yf
import short_term_mr as S
rows = []
for t in ["SPY", "QQQ", "IWM", "DIA", "EFA", "EEM"]:
    df = yf.download(t, start="1993-01-01", auto_adjust=True, progress=False); df.columns = df.columns.get_level_values(0); df = df.dropna()
    c = df.Close
    en = (S.rsi(c) < 10) & (c > c.rolling(200).mean()); ex = c > c.rolling(5).mean()
    for a, b in [("1993", "2000"), ("2001", "2008"), ("2009", "2017"), ("2018", "2026")]:
        sub = df.loc[a:b]
        if len(sub) < 300: continue
        tr = S.simulate(sub, en.loc[a:b], ex.loc[a:b], "open")
        bench = S.random_bench(sub, tr, 300)
        rows.append(dict(t=t, per=f"{a}-{b}", n=len(tr), ex=tr.ret.mean() - bench.mean(), sd=tr.ret.std()))
R = pd.DataFrame(rows)
P = R.groupby("per").apply(lambda g: pd.Series({"ETFs": len(g), "n": g.n.sum(), "exceso medio/op": (g.ex * g.n).sum() / g.n.sum(),
                                                "t aprox": (g.ex * g.n).sum() / g.n.sum() / (np.sqrt((g.sd**2 * g.n).sum() / g.n.sum()) / np.sqrt(g.n.sum()))}))
print(P.to_string(formatters={"exceso medio/op": "{:+.2%}".format, "t aprox": "{:.2f}".format, "n": "{:.0f}".format, "ETFs": "{:.0f}".format}))
