"""
TAA sectorial: ¿aporta rotar entre XLF, XLE, XLK y XLB?
========================================================
La estrategia teórica de la ronda 2 (entrada 14-05-2026) se definió como
"rotación trimestral según régimen Fed" sobre estos 4 ETFs, sin regla
escrita. Aquí se escribe una, ANTES de ver resultados, y se prueba desde 1999.

Reglas (fijadas de antemano):

- FED_REGIME. Cada fin de trimestre se mira la letra del Tesoro a 3 meses
  (^IRX), que sigue a los tipos de la Fed y se conoce en tiempo real:
      sube > 0.25 pp en 6 meses   -> endurecimiento: 50% XLF + 50% XLE
      baja > 0.25 pp en 6 meses   -> relajación:     50% XLK + 50% XLB
      si no                       -> neutral:        25% cada uno
  Asignación según la lectura habitual de la literatura (Conover, Jensen,
  Johnson y Mercer, 2008, "Sector rotation and monetary conditions"):
  financieras y energía en endurecimiento (margen de intereses, cobertura
  de inflación); tecnología y materiales en relajación (duración larga,
  inicio de ciclo). Es una interpretación: la definición original no
  especificaba el reparto.
- MOMENTUM_TOP2. Cada fin de trimestre, 50/50 en los 2 ETFs con mayor
  retorno a 12 meses (rotación sectorial por momentum, sin macro).

Referencia: los 4 ETFs a pesos iguales, rebalanceados cada trimestre. SPY
solo como contexto. Coste 0.15% por lado sobre lo negociado en cada
rebalanceo; entre rebalanceos los pesos derivan con los precios.

Criterio: la rotación aporta si su retorno mensual neto supera al de la
referencia con t de Newey-West (3 retardos) > 2. Son 2 pruebas.

Uso:  python backtest_taa.py
"""
import os
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PRICES_CSV = os.path.join(DATA_DIR, "prices.csv")

SECTORS = ["XLF", "XLE", "XLK", "XLB"]
RATE = "^IRX"
REFERENCE = "SPY"
TIGHTENING = {"XLF": 0.5, "XLE": 0.5}
EASING = {"XLK": 0.5, "XLB": 0.5}
LOOKBACK_MONTHS = 6
BAND_PP = 0.25
MOMENTUM_MONTHS = 12
COST_PER_SIDE = 0.0015
RULES = ["FED_REGIME", "MOMENTUM_TOP2"]


def load_prices(refresh: bool = False) -> pd.DataFrame:
    if os.path.isfile(PRICES_CSV) and not refresh:
        return pd.read_csv(PRICES_CSV, index_col=0, parse_dates=True)
    px = yf.download(SECTORS + [RATE, REFERENCE], start="1998-12-01", auto_adjust=True,
                     progress=False)["Close"]
    os.makedirs(DATA_DIR, exist_ok=True)
    px.to_csv(PRICES_CSV)
    return px


def monthly(px: pd.DataFrame) -> pd.DataFrame:
    last_complete = pd.date_range(end=px.index.max(), periods=1, freq="ME")[0]
    return px.resample("ME").last().loc[:last_complete]


def regime(rate_m: pd.Series) -> pd.Series:
    """'tightening', 'easing' o 'neutral' en cada fin de mes, con datos hasta ese mes."""
    change = rate_m - rate_m.shift(LOOKBACK_MONTHS)
    out = pd.Series("neutral", index=rate_m.index)
    out[change > BAND_PP] = "tightening"
    out[change < -BAND_PP] = "easing"
    return out.where(change.notna())


def target_weights(m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Pesos objetivo en cada fin de trimestre (filas = fechas de rebalanceo)."""
    quarter_ends = m.index[m.index.month.isin([3, 6, 9, 12])]
    rows = {}
    if rule == "EQUAL":
        for d in quarter_ends:
            rows[d] = {s: 0.25 for s in SECTORS}
    elif rule == "FED_REGIME":
        reg = regime(m[RATE])
        for d in quarter_ends:
            r = reg.get(d)
            if pd.isna(r):
                continue
            rows[d] = TIGHTENING if r == "tightening" else EASING if r == "easing" else {s: 0.25 for s in SECTORS}
    elif rule == "MOMENTUM_TOP2":
        mom = m[SECTORS] / m[SECTORS].shift(MOMENTUM_MONTHS) - 1
        for d in quarter_ends:
            row = mom.loc[d].dropna()
            if len(row) < len(SECTORS):
                continue
            rows[d] = {s: 0.5 for s in row.nlargest(2).index}
    else:
        raise ValueError(rule)
    return pd.DataFrame.from_dict(rows, orient="index").reindex(columns=SECTORS).fillna(0.0)


def backtest(m: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """
    Retorno mensual neto. En cada fecha de `targets` se rebalancea al cierre;
    entre rebalanceos los pesos derivan. El retorno del mes t+1 se apunta en t+1.
    """
    rets = m[SECTORS].pct_change()
    dates = m.index[m.index >= targets.index.min()]
    w = pd.Series(0.0, index=SECTORS)
    out = []
    for i, d in enumerate(dates[:-1]):
        turnover = 0.0
        if d in targets.index:
            new = targets.loc[d]
            turnover = (new - w).abs().sum()
            w = new.copy()
        nxt = dates[i + 1]
        r = rets.loc[nxt].fillna(0)
        gross = float((w * r).sum())
        net = gross - turnover * COST_PER_SIDE
        out.append({"date": nxt, "net": net, "turnover": turnover})
        grown = w * (1 + r)
        w = grown / grown.sum() if grown.sum() > 0 else grown
    return pd.DataFrame(out).set_index("date")


def newey_west_t(x: np.ndarray, lags: int = 3) -> float:
    x = np.asarray(x, dtype=float)
    n = len(x)
    e = x - x.mean()
    var = e @ e / n
    for k in range(1, lags + 1):
        var += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(var / n) if var > 0 else np.nan


def performance(r: pd.Series, cash: pd.Series) -> dict:
    eq = (1 + r).cumprod()
    ex = r - cash.reindex(r.index).fillna(0)
    return {"cagr": eq.iloc[-1] ** (12 / len(r)) - 1, "vol": r.std() * np.sqrt(12),
            "sharpe": ex.mean() / ex.std() * np.sqrt(12), "max_dd": (eq / eq.cummax() - 1).min()}


def main():
    px = load_prices()
    m = monthly(px)
    cash = (m[RATE] / 100 / 12).shift(1)                   # letra conocida al inicio del mes
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")

    results = {rule: backtest(m, target_weights(m, rule)) for rule in ["EQUAL"] + RULES}
    start = max(r.index.min() for r in results.values())
    results = {k: v.loc[start:] for k, v in results.items()}
    spy = m[REFERENCE].pct_change().loc[start:results["EQUAL"].index.max()]
    bench = results["EQUAL"]["net"]
    print(f"Periodo: {start.date()} -> {bench.index.max().date()} ({len(bench)} meses)")

    rows, tests = [], []
    for name, res in {**results, "SPY": pd.DataFrame({"net": spy})}.items():
        rows.append({"estrategia": name, **performance(res["net"], cash),
                     "rotacion_anual": res["turnover"].sum() / (len(res) / 12) / 2 if "turnover" in res else np.nan})
    for rule in RULES:
        ex = (results[rule]["net"] - bench).dropna()
        tests.append({"regla": rule, "exceso_anual": ex.mean() * 12, "te": ex.std() * np.sqrt(12),
                      "t_nw": newey_west_t(ex.to_numpy()), "aporta": newey_west_t(ex.to_numpy()) > 2,
                      **{f"tercio_{i + 1}": part.mean() * 12
                         for i, part in enumerate(np.array_split(ex, 3))}})
    print("\n=== Resultados netos (mensual, rebalanceo trimestral) ===")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n=== Criterio: exceso frente a los 4 ETFs a pesos iguales (t > 2) ===")
    print(pd.DataFrame(tests).to_string(index=False))

    # Diagnóstico de la regla Fed: ¿gana la cesta "correcta" en cada régimen?
    reg = regime(m[RATE])
    rets = m[SECTORS].pct_change().shift(-1)               # mes siguiente al régimen observado
    tight = rets[list(TIGHTENING)].mean(axis=1)
    ease = rets[list(EASING)].mean(axis=1)
    diag = pd.DataFrame({"regimen": reg, "tight_menos_ease": tight - ease}).dropna().loc[start:]
    print("\n=== Régimen Fed: retorno mensual de XLF+XLE menos XLK+XLB al mes siguiente ===")
    print(diag.groupby("regimen")["tight_menos_ease"].agg(["count", "mean"]).assign(
        anualizado=lambda d: d["mean"] * 12).to_string())

    print("\n=== Ronda 2: régimen y posiciones recientes ===")
    for rule in RULES:
        tw = target_weights(m, rule)
        print(f"  {rule}:")
        print(tw.loc["2025-12-31":].to_string())
    print("  régimen:", reg.loc["2025-12-31":].to_dict())
    return results


if __name__ == "__main__":
    main()
