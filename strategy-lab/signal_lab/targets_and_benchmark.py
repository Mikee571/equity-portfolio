"""
targets_and_benchmark.py
=========================
Target binario de dirección + benchmark ARIMA sobre precio puro.

Decisión de diseño (documentada en el notebook): clasificación BINARIA en vez
de 3 clases, por robustez con tamaño de muestra limitado (~12 activos,
frecuencia diaria). Ver discusión completa en sección 4 del notebook.
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
import warnings


def build_binary_target(close: pd.Series, horizon: int = 10, threshold: float = 0.01) -> pd.Series:
    """
    Target binario: 1 si el retorno a `horizon` días supera `threshold`, 0 si no.

    Default horizon=10 (no 5) tras grid search empírico (ver tune_horizon_threshold.py):
    horizon=10 mejoró F1 de forma consistente en los 4 activos probados
    (USDJPY=X, HG=F, GDX, NVDA) frente a horizon=3 o 5 — el ruido de corto
    plazo se diluye más y el modelo capta mejor la tendencia subyacente.

    threshold=0.01 (1%) se mantiene como default tras confirmar que es el
    punto de equilibrio entre balance de clases utilizable y relevancia
    económica de la señal (ver Sección 4 del notebook para el detalle).

    OJO con look-ahead bias: este target usa precio FUTURO (shift negativo).
    Debe excluirse explícitamente de las features de entrada — se construye
    en un paso separado y solo se usa como `y`, nunca como columna de X.
    """
    future_return = close.shift(-horizon) / close - 1
    target = (future_return > threshold).astype(int)
    # Las últimas `horizon` filas no tienen futuro real -> no se pueden usar para entrenar/evaluar
    target.iloc[-horizon:] = np.nan
    return target


def arima_benchmark_predictions(close: pd.Series, train_end_idx: int, horizon: int = 5,
                                 threshold: float = 0.015, order=(1, 1, 1)) -> int:
    """
    Entrena ARIMA(p,d,q) sobre el histórico de precio HASTA train_end_idx (exclusive
    del periodo de test, respetando walk-forward) y predice si el retorno a
    `horizon` días superará `threshold`.

    Devuelve 1 (alcista) o 0 (no), en el mismo formato que el target real,
    para comparación directa de accuracy con RF/XGBoost.

    Esto es deliberadamente un benchmark simple: ARIMA solo ve su propio
    histórico de precio, sin indicadores técnicos, fundamentales ni sentimiento.
    Sirve para responder: "¿el modelo ML con más inputs realmente aporta algo
    sobre un modelo ingenuo de serie temporal univariada?"
    """
    train_prices = close.iloc[:train_end_idx]

    if len(train_prices) < 30:
        return np.nan  # histórico insuficiente para ajustar ARIMA de forma fiable

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ARIMA(train_prices.values, order=order)
            fitted = model.fit()
            forecast = fitted.forecast(steps=horizon)
        last_price = train_prices.iloc[-1]
        predicted_return = forecast[-1] / last_price - 1
        return int(predicted_return > threshold)
    except Exception:
        return np.nan


def run_arima_walk_forward(close: pd.Series, horizon: int = 5, threshold: float = 0.015,
                            min_train_size: int = 252, step: int = 5) -> pd.Series:
    """
    Walk-forward para ARIMA: re-entrena cada `step` días sobre una ventana
    expansiva (todo el histórico disponible hasta ese punto), igual que se
    hace con RF/XGBoost para comparación justa.

    `step=5` (no recalcular cada día) es una decisión deliberada de coste
    computacional — ARIMA es lento de re-ajustar; re-entrenar diario sobre
    cientos de puntos sería excesivo para el valor marginal que aporta.
    """
    predictions = pd.Series(index=close.index, dtype=float)

    for i in range(min_train_size, len(close) - horizon, step):
        pred = arima_benchmark_predictions(close, train_end_idx=i, horizon=horizon, threshold=threshold)
        # La predicción hecha en el punto i aplica a las próximas `step` filas
        # (hasta el siguiente re-entrenamiento), simulando uso real de la señal.
        end_slice = min(i + step, len(close) - horizon)
        predictions.iloc[i:end_slice] = pred

    return predictions
