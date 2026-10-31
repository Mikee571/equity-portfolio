"""
Stat Arb — Análisis de pares cointegrados
==========================================
Calcula el spread, el z-score, y el test de cointegración (Engle-Granger)
para los pares documentados en el paper trading lab.

Pares analizados:
- GDXJ / GDX   (mineras junior vs senior de oro)
- LMT / RHM.DE (defensa US vs defensa Europa)
- XOM / AAL    (energía vs aerolíneas - proxy de costo de combustible)

Uso: python stat_arb_pairs.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import coint, adfuller
from statsmodels.tsa.vector_ar.vecm import coint_johansen
import warnings
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuración de pares
# ---------------------------------------------------------------------------
# HISTORIAL: los 3 pares originales del lab (GDXJ/GDX, LMT/RHM.DE, XOM/AAL)
# NO pasaron la validación de dos etapas (Engle-Granger + Johansen) — ver
# sesión de Semana 1. Tras un scan combinatorio dentro de los mismos sectores
# (Semana 4), se encontraron 2 pares que SÍ están cointegrados y operables:
PAIRS = {
    "GDXJ/KGC":   {"y": "GDXJ", "x": "KGC", "thesis": "Junior miners vs Kinross Gold — cointegrado, half-life 16.2d"},
    "AEM/GLD":    {"y": "AEM",  "x": "GLD", "thesis": "Agnico Eagle vs oro físico — cointegrado, half-life 13.2d"},
}

# Pares originales descartados tras validación (Semana 1) — se mantienen
# comentados como referencia histórica, NO se usan para alertas:
# "GDXJ/GDX": {"y": "GDXJ", "x": "GDX", "thesis": "NO cointegrado (EG p=0.108, Johansen 13.1<15.5)"}
# "LMT/RHM":  {"y": "LMT",  "x": "RHM.DE", "thesis": "NO cointegrado (EG p=0.648)"}
# "XOM/AAL":  {"y": "XOM",  "x": "AAL", "thesis": "NO cointegrado (EG p=0.890) — señal táctica, no Stat Arb"}

PERIOD = "2y"
INTERVAL = "1d"
ZSCORE_ENTRY = 1.5   # umbral de alerta para entrada
ZSCORE_EXIT = 0.5    # umbral de reversión a la media


def fetch_pair_data(ticker_y: str, ticker_x: str, period: str = PERIOD, interval: str = INTERVAL):
    """Descarga precios de cierre ajustados para ambas piernas del par."""
    data = yf.download([ticker_y, ticker_x], period=period, interval=interval,
                        auto_adjust=True, progress=False)
    close = data["Close"][[ticker_y, ticker_x]].dropna()
    close.columns = ["y", "x"]
    return close


def engle_granger_test(y: pd.Series, x: pd.Series, use_log: bool = True):
    """
    Test de cointegración de Engle-Granger.
    H0: no hay cointegración. p-value < 0.05 sugiere cointegración (rechazamos H0).

    use_log=True testea sobre log-precios, no niveles. Esto es importante cuando
    las dos series tienen tasas de crecimiento muy distintas (ej. una se cuadriplica
    y la otra sube 20%) — en niveles, la regresión puede dar betas casi nulos o
    sin sentido económico simplemente por la diferencia de escala/varianza.
    """
    if use_log:
        y, x = np.log(y), np.log(x)
    score, pvalue, _ = coint(y, x)
    return score, pvalue


def hedge_ratio_ols(y: pd.Series, x: pd.Series, use_log: bool = True) -> float:
    """
    Calcula el hedge ratio (beta) vía regresión OLS simple: y = alpha + beta * x
    Este beta es la cantidad de x por cada unidad de y para neutralizar el riesgo direccional.

    use_log=True calcula el beta sobre log-precios — más robusto cuando las series
    tienen volatilidad/escala muy distinta. El spread resultante se interpreta como
    un spread de retornos log, no de precios en dólares.
    """
    if use_log:
        y, x = np.log(y), np.log(x)
    x_with_const = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(x_with_const, y, rcond=None)[0]
    return beta[1]  # beta[0] es el intercepto (alpha)


def half_life_reversion(spread: pd.Series) -> tuple:
    """
    Calcula el half-life de reversión a la media vía regresión AR(1):
        delta_spread(t) = lambda * spread(t-1) + error

    El half-life = -ln(2) / lambda indica cuántos días tarda el spread en
    revertir la mitad de cualquier desviación de su media. Es la métrica
    que determina si un par cointegrado es operable en la práctica:
    - half-life muy corto (<3 días): probablemente ruido, no hay tiempo de capturar
    - half-life razonable (5-30 días): operable
    - half-life muy largo (>60 días): capital atado demasiado tiempo, riesgo de
      ruptura del régimen antes de que revierta

    Solo tiene sentido interpretarlo si el par ya pasó el test de cointegración.
    """
    spread_lag = spread.shift(1).dropna()
    delta_spread = spread.diff().dropna()
    spread_lag = spread_lag.loc[delta_spread.index]

    x_const = np.column_stack([np.ones(len(spread_lag)), spread_lag])
    result = np.linalg.lstsq(x_const, delta_spread, rcond=None)[0]
    lambda_coef = result[1]

    if lambda_coef >= 0:
        return None, None  # no hay reversión (lambda debe ser negativo)

    half_life = -np.log(2) / lambda_coef
    return half_life, lambda_coef


def johansen_test(y: pd.Series, x: pd.Series, use_log: bool = True):
    """
    Test de cointegración de Johansen — segunda etapa de validación.

    A diferencia de Engle-Granger (que regresiona y sobre x, o x sobre y, y el
    resultado puede cambiar según cuál se elija como variable dependiente),
    Johansen trata el sistema de forma simétrica y es más robusto para
    confirmar cointegración en pares donde Engle-Granger da resultado ambiguo.

    Usamos el estadístico de traza (trace statistic) con la hipótesis r=0
    (no hay vectores de cointegración) vs r>=1 (al menos uno).
    Comparamos contra el valor crítico al 95% (columna índice 1 de cvt).

    Retorna: (trace_stat, critical_value_95, is_cointegrated)
    """
    if use_log:
        y, x = np.log(y), np.log(x)

    data = pd.concat([y, x], axis=1).dropna()
    data.columns = ["y", "x"]

    # det_order=0 (constante, no tendencia) y k_ar_diff=1 son los defaults
    # estándar para series de precios financieros diarios
    result = coint_johansen(data, det_order=0, k_ar_diff=1)

    trace_stat_r0 = result.lr1[0]       # estadístico de traza para H0: r=0
    critical_value_95 = result.cvt[0, 1]  # valor crítico al 95% para r=0

    is_cointegrated = trace_stat_r0 > critical_value_95

    return trace_stat_r0, critical_value_95, is_cointegrated


def compute_spread_zscore(y: pd.Series, x: pd.Series, beta: float, window: int = 30):
    """
    Calcula el spread (y - beta*x) y su z-score sobre una ventana móvil.
    Usamos ventana móvil (no histórico completo) porque la relación de
    cointegración puede degradarse con el tiempo — esto es más robusto
    para trading real que un z-score sobre toda la serie.
    """
    spread = y - beta * x
    rolling_mean = spread.rolling(window=window).mean()
    rolling_std = spread.rolling(window=window).std()
    zscore = (spread - rolling_mean) / rolling_std
    return spread, zscore


def adf_test_spread(spread: pd.Series):
    """
    Test de estacionariedad (Augmented Dickey-Fuller) sobre el spread.
    Un spread estacionario es la base de cualquier estrategia de mean-reversion.
    p-value < 0.05 sugiere que el spread es estacionario (válido para Stat Arb).
    """
    result = adfuller(spread.dropna())
    return result[0], result[1]  # adf_stat, pvalue


def analyze_pair(name: str, ticker_y: str, ticker_x: str, thesis: str):
    print(f"\n{'='*60}")
    print(f"PAR: {name}  —  {thesis}")
    print(f"{'='*60}")

    try:
        data = fetch_pair_data(ticker_y, ticker_x)
    except Exception as e:
        print(f"  ERROR descargando datos: {e}")
        return None

    if len(data) < 60:
        print(f"  Datos insuficientes ({len(data)} filas). Se necesitan al menos 60.")
        return None

    y, x = data["y"], data["x"]

    # 1. ENGLE-GRANGER — filtro rápido, primera etapa
    eg_score, eg_pvalue = engle_granger_test(y, x, use_log=True)
    eg_cointegrated = eg_pvalue < 0.05

    # 2. JOHANSEN — validación más rigurosa, segunda etapa.
    #    Lo ejecutamos siempre para tener el dato comparativo, pero su
    #    relevancia decisiva es alta precisamente cuando Engle-Granger
    #    queda en zona ambigua (p-value entre ~0.05 y ~0.15).
    trace_stat, crit_val_95, johansen_cointegrated = johansen_test(y, x, use_log=True)

    # Veredicto final: exigimos que AMBOS tests coincidan en cointegración
    # para clasificar el par como válido para Stat Arb. Si solo uno de los
    # dos lo confirma, el par queda en zona ambigua — se documenta como tal,
    # no se descarta ni se acepta de forma binaria.
    if eg_cointegrated and johansen_cointegrated:
        verdict = "COINTEGRADO"
    elif eg_cointegrated or johansen_cointegrated:
        verdict = "AMBIGUO"
    else:
        verdict = "NO COINTEGRADO"
    is_cointegrated = verdict == "COINTEGRADO"

    # 3. Hedge ratio sobre log-precios
    beta = hedge_ratio_ols(y, x, use_log=True)

    # 4. Spread (en log) y z-score (ventana móvil de 30 días)
    log_y, log_x = np.log(y), np.log(x)
    spread, zscore = compute_spread_zscore(log_y, log_x, beta, window=30)

    # 5. Test de estacionariedad sobre el spread completo
    adf_stat, adf_pvalue = adf_test_spread(spread)

    current_z = zscore.iloc[-1]
    current_spread = spread.iloc[-1]

    print(f"\n  Etapa 1 — Engle-Granger (filtro rápido, log-precios):")
    print(f"    p-value = {eg_pvalue:.4f}  →  {'cointegrado' if eg_cointegrated else 'NO cointegrado'}")
    print(f"\n  Etapa 2 — Johansen (validación rigurosa):")
    print(f"    trace stat = {trace_stat:.3f}  vs  valor crítico 95% = {crit_val_95:.3f}")
    print(f"    →  {'cointegrado' if johansen_cointegrated else 'NO cointegrado'}")
    print(f"\n  VEREDICTO COMBINADO: {verdict}")
    print(f"\n  Estacionariedad del spread (ADF):")
    print(f"    p-value = {adf_pvalue:.4f}  →  {'Estacionario ✓' if adf_pvalue < 0.05 else 'NO estacionario ✗'}")
    print(f"\n  Hedge ratio (beta, en log): {beta:.4f}")
    print(f"\n  Spread actual (log): {current_spread:.4f}")
    print(f"  Z-score actual: {current_z:.2f}")

    # 6. Half-life de reversión — solo se interpreta si el veredicto es COINTEGRADO
    half_life, lambda_coef = half_life_reversion(spread)
    if is_cointegrated and half_life is not None:
        print(f"\n  Half-life de reversión: {half_life:.1f} días")
        if half_life < 3:
            print(f"    ⚠ Muy corto — riesgo de que sea ruido, no señal operable")
        elif half_life > 60:
            print(f"    ⚠ Muy largo — capital atado demasiado tiempo")
        else:
            print(f"    ✓ Rango operable")
    else:
        reason = "el veredicto es AMBIGUO" if verdict == "AMBIGUO" else "el par no está cointegrado"
        print(f"\n  Half-life: NO SE INTERPRETA — {reason}.")
        print(f"    Sin cointegración confirmada por ambos tests, no hay ancla de")
        print(f"    equilibrio que garantice reversión. Cualquier señal de z-score")
        print(f"    aquí es momentum/mean-reversion táctico, NO Stat Arb estricto.")

    # Señal de trading — con advertencia explícita según el veredicto
    if abs(current_z) >= ZSCORE_ENTRY:
        direction = f"CORTO {ticker_y} / LARGO {ticker_x}" if current_z > 0 else f"LARGO {ticker_y} / CORTO {ticker_x}"
        flag = "" if is_cointegrated else f"  [{verdict} — señal táctica, no Stat Arb]"
        print(f"\n  🔔 SEÑAL DE ENTRADA: |z| = {abs(current_z):.2f} >= {ZSCORE_ENTRY}{flag}")
        print(f"     Dirección sugerida: {direction}")
    elif abs(current_z) <= ZSCORE_EXIT:
        print(f"\n  ✓ Z-score cerca de cero ({current_z:.2f}) — zona de salida/sin posición")
    else:
        print(f"\n  — Z-score en zona neutral ({current_z:.2f}) — sin señal clara")

    return {
        "pair": name,
        "verdict": verdict,
        "eg_cointegrated": eg_cointegrated,
        "eg_pvalue": eg_pvalue,
        "johansen_cointegrated": johansen_cointegrated,
        "johansen_trace": trace_stat,
        "johansen_crit_95": crit_val_95,
        "cointegrated": is_cointegrated,
        "stationary": adf_pvalue < 0.05,
        "adf_pvalue": adf_pvalue,
        "beta": beta,
        "current_zscore": current_z,
        "current_spread": current_spread,
        "half_life_days": half_life,
        "spread_series": spread,
        "zscore_series": zscore,
    }


def main():
    print("STAT ARB — Análisis de cointegración y z-score")
    print(f"Periodo: {PERIOD}  |  Intervalo: {INTERVAL}")
    print(f"Umbrales: entrada |z| >= {ZSCORE_ENTRY}  |  salida |z| <= {ZSCORE_EXIT}")

    results = []
    for name, cfg in PAIRS.items():
        r = analyze_pair(name, cfg["y"], cfg["x"], cfg["thesis"])
        if r:
            results.append(r)

    # Resumen final
    print(f"\n\n{'='*60}")
    print("RESUMEN")
    print(f"{'='*60}")
    summary_df = pd.DataFrame([{
        "Par": r["pair"],
        "EG": "Sí" if r["eg_cointegrated"] else "No",
        "Johansen": "Sí" if r["johansen_cointegrated"] else "No",
        "Veredicto": r["verdict"],
        "Z-score actual": f"{r['current_zscore']:.2f}",
        "Half-life (días)": f"{r['half_life_days']:.1f}" if r["half_life_days"] else "N/A",
    } for r in results])
    print(summary_df.to_string(index=False))

    return results


if __name__ == "__main__":
    results = main()
