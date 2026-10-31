"""
Pair Scanner — búsqueda combinatoria de pares cointegrados
=============================================================
Los 3 pares originales del lab (GDXJ/GDX, LMT/RHM.DE, XOM/AAL) no pasaron
la validación de dos etapas (Engle-Granger + Johansen). En vez de abandonar
Stat Arb, ampliamos la búsqueda DENTRO de los mismos sectores de nuestras
estrategias — mineras de oro, defensa, energía, aerolíneas — probando todas
las combinaciones posibles, no solo las parejas "obvias" por tesis.

Uso: python pair_scanner.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
from itertools import combinations
import warnings
warnings.filterwarnings("ignore")

from stat_arb_pairs import (
    engle_granger_test, hedge_ratio_ols, compute_spread_zscore,
    johansen_test, half_life_reversion, adf_test_spread, ZSCORE_ENTRY,
)

# ---------------------------------------------------------------------------
# Universos sectoriales — ligados a los activos de nuestras 6 estrategias
# ---------------------------------------------------------------------------
UNIVERSES = {
    "Mineras de oro (Global Macro)": ["GDX", "GDXJ", "NEM", "AEM", "KGC", "GLD"],
    "Defensa (Global Macro)":        ["LMT", "RTX", "NOC", "GD", "LHX"],
    "Energía integrada (Stat Arb)":  ["XOM", "CVX", "COP", "SLB"],
    "Aerolíneas (Stat Arb)":         ["AAL", "DAL", "UAL", "LUV"],
}

PERIOD = "2y"
INTERVAL = "1d"
MIN_HALF_LIFE = 3     # días — por debajo, riesgo de que sea ruido
MAX_HALF_LIFE = 60    # días — por encima, capital atado demasiado tiempo


def fetch_universe_data(tickers: list, period: str = PERIOD, interval: str = INTERVAL) -> pd.DataFrame:
    """Descarga todos los tickers de un universo en una sola llamada."""
    data = yf.download(tickers, period=period, interval=interval,
                        auto_adjust=True, progress=False)
    close = data["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame()
    return close.dropna(how="all")


def scan_universe(name: str, tickers: list) -> list:
    """
    Prueba todas las combinaciones C(n,2) dentro de un universo y devuelve
    los resultados de validación (EG + Johansen + half-life) para cada par.
    """
    print(f"\n{'='*70}")
    print(f"UNIVERSO: {name}  —  {len(tickers)} activos, {len(list(combinations(tickers, 2)))} combinaciones")
    print(f"{'='*70}")

    try:
        prices = fetch_universe_data(tickers)
    except Exception as e:
        print(f"  Error descargando universo: {e}")
        return []

    available = [t for t in tickers if t in prices.columns and prices[t].notna().sum() > 60]
    missing = set(tickers) - set(available)
    if missing:
        print(f"  Sin datos suficientes, excluidos: {missing}")

    results = []
    for ticker_y, ticker_x in combinations(available, 2):
        pair_data = prices[[ticker_y, ticker_x]].dropna()
        if len(pair_data) < 60:
            continue

        y, x = pair_data[ticker_y], pair_data[ticker_x]

        try:
            eg_score, eg_pvalue = engle_granger_test(y, x, use_log=True)
            eg_cointegrated = eg_pvalue < 0.05

            trace_stat, crit_val_95, johansen_cointegrated = johansen_test(y, x, use_log=True)

            if eg_cointegrated and johansen_cointegrated:
                verdict = "COINTEGRADO"
            elif eg_cointegrated or johansen_cointegrated:
                verdict = "AMBIGUO"
            else:
                verdict = "NO COINTEGRADO"

            beta = hedge_ratio_ols(y, x, use_log=True)
            log_y, log_x = np.log(y), np.log(x)
            spread, zscore = compute_spread_zscore(log_y, log_x, beta, window=30)
            current_z = zscore.iloc[-1]

            half_life = None
            if verdict == "COINTEGRADO":
                half_life, _ = half_life_reversion(spread)

            operable = (
                verdict == "COINTEGRADO"
                and half_life is not None
                and MIN_HALF_LIFE <= half_life <= MAX_HALF_LIFE
            )

            results.append({
                "universe": name,
                "pair": f"{ticker_y}/{ticker_x}",
                "eg_pvalue": eg_pvalue,
                "johansen_trace": trace_stat,
                "johansen_crit95": crit_val_95,
                "verdict": verdict,
                "current_zscore": current_z,
                "half_life": half_life,
                "operable": operable,
            })
        except Exception:
            continue

    # Ordenar: cointegrados primero, luego por p-value de EG ascendente (más fuerte)
    results.sort(key=lambda r: (r["verdict"] != "COINTEGRADO", r["eg_pvalue"]))

    print(f"\n  {'PAR':<14} {'EG p-val':>9}  {'Johansen':>9} vs {'crit95':>7}  {'VEREDICTO':<16} {'half-life':>10}  {'z actual':>9}")
    print("  " + "-" * 85)
    for r in results:
        hl_str = f"{r['half_life']:.1f}d" if r["half_life"] else "—"
        flag = " ✓ OPERABLE" if r["operable"] else ""
        print(f"  {r['pair']:<14} {r['eg_pvalue']:>9.4f}  {r['johansen_trace']:>9.2f} vs {r['johansen_crit95']:>7.2f}  {r['verdict']:<16} {hl_str:>10}  {r['current_zscore']:>9.2f}{flag}")

    return results


def main():
    print("PAIR SCANNER — búsqueda combinatoria dentro de sectores del lab")
    print(f"Periodo: {PERIOD}  |  Half-life operable: {MIN_HALF_LIFE}-{MAX_HALF_LIFE} días")

    all_results = []
    for name, tickers in UNIVERSES.items():
        results = scan_universe(name, tickers)
        all_results.extend(results)

    operable_pairs = [r for r in all_results if r["operable"]]

    print(f"\n\n{'='*70}")
    print("RESUMEN — pares OPERABLES encontrados (cointegrados + half-life razonable)")
    print(f"{'='*70}")
    if operable_pairs:
        for r in operable_pairs:
            print(f"  {r['universe']}: {r['pair']}  (EG p={r['eg_pvalue']:.4f}, "
                  f"half-life={r['half_life']:.1f}d, z={r['current_zscore']:.2f})")
    else:
        print("  Ninguno encontrado en estos universos con estos criterios.")

    return all_results


if __name__ == "__main__":
    all_results = main()
