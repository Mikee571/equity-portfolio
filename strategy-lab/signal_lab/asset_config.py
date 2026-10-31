"""
asset_config.py
================
Configuración por activo, validada empíricamente con grid search
(ver tune_horizon_threshold.py y tune_hyperparams.py).

Esto NO es una garantía de que esta configuración seguirá siendo óptima para
siempre -- los mercados cambian de régimen. Se recomienda re-correr el grid
search cada pocos meses (ej. trimestral) y actualizar este archivo si los
resultados cambian de forma significativa.

Última validación: USDJPY=X, HG=F, GDX, NVDA con 2 años de histórico
(jun 2024 - jun 2026), horizon candidatos [3,5,10], threshold [0.01,0.015,0.02].
"""

ASSET_CONFIG = {
    "USDJPY=X": {
        "horizon": 10,
        "threshold": 0.01,
        "xgb_params": {"max_depth": 3, "learning_rate": 0.05, "n_estimators": 200},
        "use_calibration": False,
        "notes": (
            "Activo más débil de los 4 probados (F1 máximo ~0.32 en cualquier "
            "configuración). Señal real pero modesta -- tratar con cautela, "
            "no usar como única fuente de decisión incluso dentro del lab. "
            "IMPORTANTE: calibración EMPEORA este activo (F1 0.32 -> 0.08) "
            "-- con su señal ya débil, la varianza adicional de calibrar con "
            "muestra pequeña daña más de lo que corrige. NO calibrar aquí."
        ),
    },
    "HG=F": {
        "horizon": 10,
        "threshold": 0.01,
        "xgb_params": {"max_depth": 5, "learning_rate": 0.03, "n_estimators": 300},
        "use_calibration": True,
        "notes": (
            "Mejor resultado del universo probado en términos absolutos. "
            "Calibración mejora F1 (0.51->0.54) vía mejor recall, a costa de "
            "algo de precision/accuracy -- trade-off razonable, no mejora pura."
        ),
    },
    "GDX": {
        "horizon": 10,
        "threshold": 0.01,
        "xgb_params": {"max_depth": 3, "learning_rate": 0.05, "n_estimators": 200},
        "use_calibration": True,
        "notes": (
            "Necesita modelo MÁS SIMPLE (max_depth=3, no 4-5) -- con más "
            "profundidad sobreajusta a ruido. Mejora más clara y consistente "
            "de las 4 con calibración: F1 0.47->0.74, accuracy 0.45->0.63."
        ),
    },
    "NVDA": {
        "horizon": 10,
        "threshold": 0.015,
        "xgb_params": {"max_depth": 5, "learning_rate": 0.03, "n_estimators": 300},
        "use_calibration": False,
        "notes": (
            "Segundo mejor resultado sin calibrar (F1~0.49-0.58 según config). "
            "Calibración no aporta aquí (F1 sin cambios significativos) -- se "
            "deja desactivada por simplicidad, ya que no hay beneficio claro. "
            "Único activo con cobertura de sentimiento social potencial."
        ),
    },
}

DEFAULT_CONFIG = {
    "horizon": 10,
    "threshold": 0.01,
    "xgb_params": {"max_depth": 4, "learning_rate": 0.05, "n_estimators": 200},
    "use_calibration": False,
    "notes": "Configuración genérica -- usar solo para activos no validados todavía vía grid search. Calibración desactivada por default hasta validar empíricamente que ayuda (puede perjudicar, ver caso USDJPY=X).",
}


def get_config(ticker: str) -> dict:
    """Devuelve la configuración validada para un ticker, o el default genérico si no existe."""
    return ASSET_CONFIG.get(ticker, DEFAULT_CONFIG)
