"""
¿Mejora la cartera real 70/20/10 una capa de quality o de tendencia?
=====================================================================
Las pruebas de la ronda 2 (quality, trend following) no encontraron
rentabilidad extra, pero sí control de riesgo. Aquí se mide si ese control
de riesgo mejora la cartera completa del usuario.

Diseño fijado ANTES de ver resultados:

- Cartera base (70/20/10, la real):
    70% núcleo    VWRL.AS (el ETF real, en euros)
    20% valor     top 10 del screener (backtest point-in-time, neto)
    10% táctico   discrecional, no reconstruible: se representa con el
                  universo a pesos iguales (escoger valores sin ventaja)
- Variantes: se añade una capa del 10% o del 20%, financiada con el núcleo:
    QUALITY_10/20  quintil superior del quality estilo MSCI (neto)
    TREND_10/20    cesta diversificada de materias primas con TSMOM12, la
                   regla canónica (Moskowitz, Ooi y Pedersen); en liquidez
                   cuando no hay tendencia
- Todo en euros: las capas en USD se convierten con EUR/USD. Rebalanceo
  mensual a los pesos objetivo, sin coste adicional (los costes de cada capa
  ya están dentro de sus retornos).
- Criterio: una variante mejora la cartera si su Sharpe supera al de la base
  con el extremo inferior del IC 90% (bootstrap por bloques de 12 meses) > 0.
  Son 4 pruebas. Sharpe con tipo libre 0 (los tipos en euros estuvieron
  cerca de 0 o negativos gran parte del periodo; afecta igual a todas).

Entradas: equity-screener/data/backtest/sleeves.csv (python -m
src.backtest.export_sleeves en equity-screener) y
trend_following/backtest_trend.py.

Uso:  python portfolio_mix.py
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "trend_following"))

import backtest_trend as bt  # noqa: E402

SLEEVES_CSV = os.path.join(HERE, "..", "..", "equity-screener", "data", "backtest", "sleeves.csv")

MIXES = {
    "BASE_70_20_10": {"core": 0.70, "value": 0.20, "tactical": 0.10},
    "QUALITY_10": {"core": 0.60, "value": 0.20, "tactical": 0.10, "quality": 0.10},
    "QUALITY_20": {"core": 0.50, "value": 0.20, "tactical": 0.10, "quality": 0.20},
    "TREND_10": {"core": 0.60, "value": 0.20, "tactical": 0.10, "trend": 0.10},
    "TREND_20": {"core": 0.50, "value": 0.20, "tactical": 0.10, "trend": 0.20},
}


def to_eur(r_usd: pd.Series, eurusd: pd.Series) -> pd.Series:
    """Retorno mensual en USD -> EUR. eurusd = dólares por euro a fin de mes."""
    fx = eurusd.reindex(r_usd.index.union(eurusd.index)).ffill()
    fx_ratio = fx.shift(1) / fx
    return ((1 + r_usd) * fx_ratio.reindex(r_usd.index) - 1)


def load_sleeves() -> pd.DataFrame:
    s = pd.read_csv(SLEEVES_CSV, index_col=0, parse_dates=True)
    px = yf.download(["VWRL.AS", "EURUSD=X"], start="2012-01-01", auto_adjust=True, progress=False)["Close"]
    m = px.resample("ME").last()
    eurusd = m["EURUSD=X"]
    core = m["VWRL.AS"].pct_change()                       # ya en euros
    tm = bt.monthly(bt.load_prices())
    trend_usd = bt.backtest(tm[bt.BASKETS["B diversificada"]], tm[bt.CASH], "TSMOM12")["net"]
    out = pd.DataFrame({
        "core": core,
        "value": to_eur(s["screener_top10"], eurusd),
        "tactical": to_eur(s["universe_ew"], eurusd),
        "quality": to_eur(s["quality_msci"], eurusd),
        "trend": to_eur(trend_usd, eurusd),
    })
    return out.dropna()


def mix_returns(sleeves: pd.DataFrame, weights: dict) -> pd.Series:
    return sum(sleeves[k] * w for k, w in weights.items())


def sharpe(r: np.ndarray) -> float:
    return r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else np.nan


def performance(r: pd.Series) -> dict:
    eq = (1 + r).cumprod()
    roll12 = (1 + r).rolling(12).apply(np.prod, raw=True) - 1
    return {"cagr": eq.iloc[-1] ** (12 / len(r)) - 1, "vol": r.std() * np.sqrt(12),
            "sharpe": sharpe(r.to_numpy()), "max_dd": (eq / eq.cummax() - 1).min(),
            "peor_12m": roll12.min()}


def sharpe_diff_ci(a: pd.Series, b: pd.Series, block: int = 12, n_boot: int = 4000,
                   alpha: float = 0.10, seed: int = 42) -> tuple:
    ra, rb = a.to_numpy(), b.to_numpy()
    rng = np.random.default_rng(seed)
    n = len(ra)
    n_blocks = int(np.ceil(n / block))
    diffs = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        k = (starts[:, None] + np.arange(block)).ravel()[:n]
        diffs.append(sharpe(ra[k]) - sharpe(rb[k]))
    lo, hi = np.quantile(diffs, [alpha / 2, 1 - alpha / 2])
    return sharpe(ra) - sharpe(rb), lo, hi


def main():
    sleeves = load_sleeves()
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    print(f"Periodo (EUR): {sleeves.index.min():%Y-%m} -> {sleeves.index.max():%Y-%m} ({len(sleeves)} meses)")
    print("\n=== Cada capa por separado (EUR) ===")
    print(pd.DataFrame({k: performance(sleeves[k]) for k in sleeves}).T.to_string())
    print("\n=== Correlaciones mensuales entre capas ===")
    print(sleeves.corr().round(2).to_string())

    base = mix_returns(sleeves, MIXES["BASE_70_20_10"])
    rows, tests = [], []
    for name, w in MIXES.items():
        r = mix_returns(sleeves, w)
        rows.append({"cartera": name, **performance(r)})
        if name != "BASE_70_20_10":
            d, lo, hi = sharpe_diff_ci(r, base)
            tests.append({"cartera": name, "dif_sharpe": d, "ic90_lo": lo, "ic90_hi": hi, "mejora": lo > 0,
                          "dif_cagr": performance(r)["cagr"] - performance(base)["cagr"],
                          "dif_max_dd": performance(r)["max_dd"] - performance(base)["max_dd"]})
    print("\n=== Carteras (EUR, rebalanceo mensual) ===")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n=== Criterio: ¿mejora el Sharpe de la base? (IC 90% > 0) ===")
    print(pd.DataFrame(tests).to_string(index=False))

    # Las peores caídas de la base: ¿qué hizo cada variante en esos meses?
    eq = (1 + base).cumprod()
    dd = eq / eq.cummax() - 1
    trough = dd.idxmin()
    peak = eq.loc[:trough].idxmax()
    print(f"\nPeor caída de la base: {peak:%Y-%m} -> {trough:%Y-%m} ({dd.min():.1%})")
    for name, w in MIXES.items():
        r = mix_returns(sleeves, w).loc[peak:trough].iloc[1:]
        print(f"  {name:14s} en ese tramo: {(1 + r).prod() - 1:+.1%}")
    return sleeves


if __name__ == "__main__":
    main()
