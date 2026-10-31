"""
Evaluación de las estrategias teóricas de la ronda 2 (entrada 14 de mayo de 2026)
================================================================================
Definiciones tal como se fijaron (pegadas por el usuario el 2026-10-07). Los pesos
marcados como asumidos NO se especificaron en mayo: se asumieron después.

| Estrategia | Universo | Pesos |
|---|---|---|
| Relative Value LO | AMD | 100% |
| Trend Following commodities | Cobre (HG=F) + Oro (GC=F) | 50/50 asumido |
| Quality Factor | JPM, MSFT, GOOGL, UNH, V | 20% c/u asumido |
| TAA sectorial | XLF, XLE, XLK, XLB (Materials) | rotación trimestral "según régimen Fed",
                                                   sin regla escrita: se evalúa compra-y-
                                                   mantener equiponderado como referencia |

Compra-y-mantener desde el cierre del 14-05-2026 (sin rebalanceo), precios
ajustados por dividendos. Referencias: SPY (USD) y VWRL.AS (EUR). Las carteras están en USD; para un inversor en euros, el cambio
EUR/USD del periodo se informa aparte.

Uso:  python evaluate_round2.py
"""
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

ENTRY = "2026-05-14"
STRATEGIES = {
    "Relative Value LO": {"AMD": 1.0},
    "Trend Following commodities": {"HG=F": 0.5, "GC=F": 0.5},
    "Quality Factor": {t: 0.2 for t in ["JPM", "MSFT", "GOOGL", "UNH", "V"]},
    "TAA sectorial (compra-y-mantener)": {t: 0.25 for t in ["XLF", "XLE", "XLK", "XLB"]},
}
BENCHMARKS = {"SPY": {"SPY": 1.0}, "VWRL (EUR)": {"VWRL.AS": 1.0}, "Semis (SMH)": {"SMH": 1.0}}
EXTRA = ["EURUSD=X"]


def load(tickers):
    px = yf.download(sorted(set(tickers)), start="2026-04-01", auto_adjust=True, progress=False)["Close"]
    return px.ffill()


def basket(px, weights):
    """Valor de 1 invertido a la entrada, compra-y-mantener."""
    rel = px[list(weights)].loc[ENTRY:] / px[list(weights)].loc[:ENTRY].iloc[-1]
    return (rel * pd.Series(weights)).sum(axis=1)


def stats(v, spy):
    r = v.pct_change().dropna()
    rs = spy.pct_change().reindex(r.index)
    beta = r.cov(rs) / rs.var()
    return {"retorno": v.iloc[-1] - 1, "vol_anual": r.std() * np.sqrt(252),
            "max_dd": (v / v.cummax() - 1).min(), "beta_spy": beta,
            "exceso_vs_spy": v.iloc[-1] - spy.iloc[-1] / spy.iloc[0]}


def main():
    tickers = [t for w in {**STRATEGIES, **BENCHMARKS}.values() for t in w] + EXTRA
    px = load(tickers)
    entry_day = px.loc[:ENTRY].index[-1]
    last_day = px.index[-1]
    print(f"Entrada: cierre {entry_day.date()} | último dato: {last_day.date()} "
          f"({len(px.loc[ENTRY:]) - 1} sesiones)\n")
    spy = basket(px, {"SPY": 1.0})
    rows = []
    for name, w in {**STRATEGIES, **BENCHMARKS}.items():
        rows.append({"cartera": name, **stats(basket(px, w), spy)})
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    print(pd.DataFrame(rows).to_string(index=False))

    eur = px["EURUSD=X"]
    fx = eur.iloc[-1] / eur.loc[:ENTRY].iloc[-1] - 1
    print(f"\nEUR/USD en el periodo: {fx:+.1%} (para un inversor en euros, un activo en USD "
          f"rinde aprox. {-fx:+.1%} menos/más por el cambio)")

    print("\nContribución por posición (peso inicial x retorno):")
    for name, w in STRATEGIES.items():
        rel = px[list(w)].iloc[-1] / px[list(w)].loc[:ENTRY].iloc[-1] - 1
        contrib = (rel * pd.Series(w)).sort_values(ascending=False)
        total = contrib.sum()
        parts = ", ".join(f"{t} {c:+.1%} (activo {rel[t]:+.1%})" for t, c in contrib.items())
        top = contrib.iloc[0] / total if total else np.nan
        print(f"  {name}: total {total:+.1%} | {parts} | la mejor posición explica {top:.0%}")


if __name__ == "__main__":
    main()
