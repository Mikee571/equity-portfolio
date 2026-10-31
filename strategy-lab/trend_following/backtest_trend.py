"""
Trend following en materias primas: ¿aporta una regla de tendencia?
=====================================================================
Pregunta: la estrategia teórica "Trend Following commodities" (oro + cobre,
entrada 14-05-2026) no tenía regla de tendencia: era comprar y mantener. ¿Qué
habría aportado una regla real, escrita de antemano?

Diseño fijado ANTES de ver resultados:

- Activos: ETFs, no futuros continuos (los =F de yfinance son el contrato
  más cercano sin ajustar: cada cambio de contrato mete un salto de precio
  que no es retorno). Los ETFs incluyen el coste de roll y son lo invertible.
    A  "tu estrategia": GLD (oro) + CPER (cobre)
    B  cesta diversificada: GLD, SLV, CPER, USO, UNG, DBA, DBB
- Reglas estándar, sin parámetros ajustados a estos datos:
    SMA10   Faber (2007): comprado si el cierre de fin de mes > media de los
            últimos 10 cierres de fin de mes; si no, liquidez
    TSMOM12 Moskowitz, Ooi y Pedersen (2012), versión long/flat: comprado si
            el retorno de 12 meses > 0; si no, liquidez
- Cartera: cada activo con 12 meses de historia recibe 1/N; la parte en
  liquidez rinde la letra del Tesoro a 13 semanas (^IRX). Rebalanceo
  mensual al cierre del mes; coste 0.15% por lado sobre lo negociado.
- Referencia: comprar y mantener la misma cesta a pesos iguales,
  rebalanceada cada mes con el mismo coste.
- Criterio: la regla aporta si su Sharpe (sobre la letra) supera al de
  comprar y mantener con el extremo inferior del IC 90% de la diferencia
  (bootstrap por bloques de 12 meses) > 0. Son 4 pruebas (2 reglas x 2 cestas).

Uso:  python backtest_trend.py
"""
import os
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PRICES_CSV = os.path.join(DATA_DIR, "prices.csv")

BASKETS = {
    "A oro+cobre": ["GLD", "CPER"],
    "B diversificada": ["GLD", "SLV", "CPER", "USO", "UNG", "DBA", "DBB"],
}
CASH = "^IRX"
COST_PER_SIDE = 0.0015
MIN_HISTORY = 12          # meses antes de que un activo entre en la cartera
RULES = ["SMA10", "TSMOM12"]


def load_prices(refresh: bool = False) -> pd.DataFrame:
    if os.path.isfile(PRICES_CSV) and not refresh:
        return pd.read_csv(PRICES_CSV, index_col=0, parse_dates=True)
    tickers = sorted({t for ts in BASKETS.values() for t in ts}) + [CASH]
    px = yf.download(tickers, start="2004-01-01", auto_adjust=True, progress=False)["Close"]
    os.makedirs(DATA_DIR, exist_ok=True)
    px.to_csv(PRICES_CSV)
    return px


def monthly(px: pd.DataFrame) -> pd.DataFrame:
    """Cierre del último día de cada mes completo."""
    last_complete = pd.date_range(end=px.index.max(), periods=1, freq="ME")[0]   # último fin de mes <= último dato
    return px.resample("ME").last().loc[:last_complete]


def signals(prices_m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """1 = comprado, 0 = liquidez, NaN = sin historia suficiente. Solo usa datos hasta cada mes."""
    if rule == "SMA10":
        sig = (prices_m > prices_m.rolling(10).mean()).astype(float)
    elif rule == "TSMOM12":
        sig = (prices_m / prices_m.shift(12) - 1 > 0).astype(float)
    elif rule == "BUY_HOLD":
        sig = pd.DataFrame(1.0, index=prices_m.index, columns=prices_m.columns)
    else:
        raise ValueError(rule)
    enough = prices_m.notna().rolling(MIN_HISTORY + 1).sum() >= MIN_HISTORY + 1
    return sig.where(enough)


def backtest(prices_m: pd.DataFrame, cash_yield_m: pd.Series, rule: str) -> pd.DataFrame:
    """
    Retorno mensual neto. Pesos fijados al cierre del mes t con la señal de t;
    se ganan los retornos del mes t+1. La liquidez rinde la letra de t.
    """
    sig = signals(prices_m, rule)
    n_avail = sig.notna().sum(axis=1)
    w = sig.fillna(0).div(n_avail.replace(0, np.nan), axis=0).fillna(0)
    rets = prices_m.pct_change().shift(-1)                       # retorno de t a t+1
    cash = (cash_yield_m / 100 / 12).fillna(0)                   # ^IRX en % anual
    invested = w.sum(axis=1)
    gross = (w * rets.fillna(0)).sum(axis=1) + (1 - invested) * cash
    drifted = (w * (1 + rets.fillna(0)))
    drifted = drifted.div((drifted.sum(axis=1) + (1 - invested) * (1 + cash)).replace(0, np.nan), axis=0).fillna(0)
    turnover = (w - drifted.shift(1).fillna(0)).abs().sum(axis=1)
    net = gross - turnover * COST_PER_SIDE
    out = pd.DataFrame({"net": net, "cash": cash, "invested": invested, "turnover": turnover})
    out = out[n_avail > 0].iloc[:-1]                             # el último mes no tiene retorno siguiente
    out.index = out.index + pd.offsets.MonthEnd(1)               # el retorno pertenece al mes siguiente
    return out


def sharpe(r: np.ndarray, rf: np.ndarray) -> float:
    ex = r - rf
    return ex.mean() / ex.std() * np.sqrt(12) if ex.std() > 0 else np.nan


def performance(df: pd.DataFrame) -> dict:
    r = df["net"].to_numpy()
    eq = np.cumprod(1 + r)
    return {"cagr": eq[-1] ** (12 / len(r)) - 1, "vol": r.std() * np.sqrt(12),
            "sharpe": sharpe(r, df["cash"].to_numpy()),
            "max_dd": (eq / np.maximum.accumulate(eq) - 1).min(),
            "peor_mes": r.min(), "invertido_medio": df["invested"].mean(),
            "rotacion_anual": df["turnover"].mean() * 12 / 2}


def sharpe_diff_ci(a: pd.DataFrame, b: pd.DataFrame, block: int = 12, n_boot: int = 4000,
                   alpha: float = 0.10, seed: int = 42) -> tuple:
    """IC del Sharpe(a) - Sharpe(b) por moving block bootstrap sobre los mismos meses."""
    idx = a.index.intersection(b.index)
    ra, rb, rf = a.loc[idx, "net"].to_numpy(), b.loc[idx, "net"].to_numpy(), a.loc[idx, "cash"].to_numpy()
    rng = np.random.default_rng(seed)
    n = len(idx)
    n_blocks = int(np.ceil(n / block))
    diffs = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        k = (starts[:, None] + np.arange(block)).ravel()[:n]
        diffs.append(sharpe(ra[k], rf[k]) - sharpe(rb[k], rf[k]))
    point = sharpe(ra, rf) - sharpe(rb, rf)
    lo, hi = np.nanquantile(diffs, [alpha / 2, 1 - alpha / 2])
    return point, lo, hi


def main():
    px = load_prices()
    m = monthly(px)
    print(f"Datos: {m.index.min().date()} -> {m.index.max().date()}")
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    rows, tests = [], []
    for bname, tickers in BASKETS.items():
        pm = m[tickers]
        bh = backtest(pm, m[CASH], "BUY_HOLD")
        results = {"BUY_HOLD": bh}
        for rule in RULES:
            results[rule] = backtest(pm, m[CASH], rule)
        start = max(r.index.min() for r in results.values())
        for name, res in results.items():
            res = res.loc[start:]
            rows.append({"cesta": bname, "regla": name, "desde": res.index.min().date(), **performance(res)})
            if name != "BUY_HOLD":
                point, lo, hi = sharpe_diff_ci(res, bh.loc[start:])
                tests.append({"cesta": bname, "regla": name, "dif_sharpe": point, "ic90_lo": lo, "ic90_hi": hi,
                              "aporta": lo > 0})
        # Subperiodos: diferencia de Sharpe en tercios
        thirds = np.array_split(np.arange(len(bh.loc[start:])), 3)
        for rule in RULES:
            r, b = results[rule].loc[start:], bh.loc[start:]
            parts = []
            for p in thirds:
                ri, bi = r.iloc[p], b.iloc[p]
                parts.append(f"{ri.index[0]:%Y}-{ri.index[-1]:%Y}: "
                             f"{sharpe(ri['net'].to_numpy(), ri['cash'].to_numpy()) - sharpe(bi['net'].to_numpy(), bi['cash'].to_numpy()):+.2f}")
            print(f"  {bname} {rule} dif. Sharpe por tercios: " + " | ".join(parts))
    print("\n=== Resultados netos de costes (mensual) ===")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n=== Criterio: ¿mejora el Sharpe de comprar y mantener? (IC 90% > 0) ===")
    print(pd.DataFrame(tests).to_string(index=False))

    # Qué habría hecho cada regla con tu cesta desde la entrada de la ronda 2
    pm = m[BASKETS["A oro+cobre"]]
    print("\n=== Señales recientes, oro (GLD) y cobre (CPER) — 1 = comprado ===")
    recent = {rule: signals(pm, rule).loc["2026-03-31":] for rule in RULES}
    print(pd.concat(recent, axis=1).to_string())
    return rows, tests


if __name__ == "__main__":
    main()
