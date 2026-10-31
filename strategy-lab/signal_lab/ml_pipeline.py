"""
ml_pipeline.py
==============
Random Forest y XGBoost en paralelo, walk-forward validation, evaluación
comparativa y feature importance.

Walk-forward: ventana de entrenamiento EXPANSIVA (no rolling fija) — se
re-entrena cada `retrain_every` días usando TODO el histórico disponible
hasta ese punto. Esto es deliberado: con datos financieros limitados, una
ventana rolling fija desperdiciaría historia útil sin beneficio claro de
adaptabilidad a corto plazo. `max_train_size` permite la ventana rolling
para replicar producción (daily_signal_run.py entrena con los últimos 2 años).

Purga (añadida en la auditoría de 2026-10): el target de la fila t usa el
precio de t + horizon, así que sin hueco entre train y test las últimas
`horizon` etiquetas del train dependen de precios del tramo de test.
`purge_gap` (>= horizon) descarta esas filas. Ver evaluation.py para las
métricas que sustituyen a F1 como referencia.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, brier_score_loss

from evaluation import brier_skill_score, f1_always_up, safe_auc, tranche_strategy_returns

# Hiperparámetros default — usados solo si no se pasa model_params explícito.
# Confirmados como razonables por grid search (ver tune_hyperparams.py):
# GDX se beneficia de árboles más simples (max_depth=3); HG=F y NVDA de
# árboles algo más profundos pero más conservadores en learning_rate.
DEFAULT_XGB_PARAMS = {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05}
DEFAULT_RF_PARAMS = {"n_estimators": 200, "max_depth": 5, "min_samples_leaf": 10}

# Purga por defecto = el mayor horizonte usado en el lab. Purgar de más solo
# cuesta unas filas de train; purgar de menos filtra el test al train.
DEFAULT_PURGE_GAP = 10


def walk_forward_split_indices(n_samples: int, min_train_size: int, retrain_every: int,
                               purge_gap: int = 0):
    """
    Genera los índices (train_end, test_start, test_end) para cada fold.

    train_end = test_start - purge_gap. El primer fold empieza en
    min_train_size + purge_gap para seguir entrenando con min_train_size filas.
    """
    folds = []
    i = min_train_size + purge_gap
    while i < n_samples:
        test_end = min(i + retrain_every, n_samples)
        folds.append((i - purge_gap, i, test_end))  # (train_end_exclusive, test_start, test_end_exclusive)
        i = test_end
    return folds


def run_walk_forward_model(X: pd.DataFrame, y: pd.Series, model_name: str,
                            min_train_size: int = 252, retrain_every: int = 21,
                            random_state: int = 42, model_params: dict = None,
                            calibrate: bool = False, calib_fraction: float = 0.2,
                            decision_threshold: float = 0.5,
                            purge_gap: int = DEFAULT_PURGE_GAP,
                            max_train_size: int = None) -> pd.DataFrame:
    """
    Ejecuta walk-forward validation para 'random_forest' o 'xgboost'.

    Devuelve DataFrame con: fecha, y_true, y_pred, y_proba (prob. de clase 1)
    y base_rate_train (tasa de positivos del train de ese fold: la referencia
    honesta del Brier skill score, porque es lo que se sabía al predecir).

    purge_gap: debe ser >= el horizonte del target (ver docstring del módulo).
    Se aplica también entre el tramo de ajuste y el de calibración.

    max_train_size: None = ventana expansiva; un entero = ventana rolling con
    las últimas max_train_size filas (producción usa ~490, 2 años de datos).

    `retrain_every=21` (~1 mes de trading) es un balance entre fidelidad real
    (re-entrenar más seguido capturaría mejor el régimen actual) y coste
    computacional — re-entrenar diario sobre cientos de folds no aporta
    suficiente valor marginal para este caso de uso semanal/mensual de señal.

    model_params: dict de hiperparámetros específico por activo (ver
    tune_hyperparams.py). Si None, usa los defaults documentados arriba.

    calibrate=True: aplica calibración sigmoid (Platt scaling) usando el
    último `calib_fraction` del tramo de entrenamiento de cada fold como set
    de calibración separado del propio test. Se usa sigmoid (no isotonic)
    porque isotonic colapsa con los tamaños de muestra típicos aquí
    (~100 obs. de calibración) — ver discusión empírica en el notebook.

    decision_threshold: umbral sobre y_proba para decidir y_pred. Default 0.5,
    pero IMPORTANTE: tras calibrar, la distribución de probabilidades puede
    desplazarse (ej. mediana en 0.58 en vez de 0.5), por lo que 0.5 deja de
    ser necesariamente el punto óptimo de F1 — ver find_optimal_threshold()
    para buscar el valor adecuado por activo antes de fijar este parámetro.
    """
    valid_mask = y.notna()
    X_valid = X[valid_mask].reset_index(drop=False)
    y_valid = y[valid_mask].reset_index(drop=True)
    dates = X_valid.iloc[:, 0]
    X_valid = X_valid.iloc[:, 1:]

    n = len(X_valid)
    folds = walk_forward_split_indices(n, min_train_size, retrain_every, purge_gap)

    results = []

    for train_end, test_start, test_end in folds:
        train_start = 0 if max_train_size is None else max(0, train_end - max_train_size)
        X_train_full = X_valid.iloc[train_start:train_end]
        y_train_full = y_valid.iloc[train_start:train_end]
        X_test = X_valid.iloc[test_start:test_end]
        y_test = y_valid.iloc[test_start:test_end]
        dates_test = dates.iloc[test_start:test_end]

        if calibrate:
            # Separar un sub-tramo final del training (no del test) para calibrar,
            # respetando orden temporal -- la calibración nunca ve datos del futuro.
            # La misma purga separa el tramo de ajuste del de calibración.
            calib_split = int(len(X_train_full) * (1 - calib_fraction))
            X_train, y_train = X_train_full.iloc[:calib_split - purge_gap], y_train_full.iloc[:calib_split - purge_gap]
            X_calib, y_calib = X_train_full.iloc[calib_split:], y_train_full.iloc[calib_split:]
        else:
            X_train, y_train = X_train_full, y_train_full
            X_calib, y_calib = None, None

        # Imputación simple: NaN -> 0 tras documentar el porqué (warm-up de
        # medias móviles largas tipo SMA200).
        X_train_clean = X_train.fillna(0).astype(float)
        X_test_clean = X_test.fillna(0).astype(float)

        if y_train.nunique() < 2 or len(y_train_full) < min_train_size:
            continue  # no se puede entrenar un clasificador con una sola clase o muestra insuficiente

        if model_name == "random_forest":
            params = {**DEFAULT_RF_PARAMS, **(model_params or {})}
            model = RandomForestClassifier(
                **params, class_weight="balanced", random_state=random_state, n_jobs=-1,
            )
        elif model_name == "xgboost":
            # scale_pos_weight compensa el desbalance de clases documentado
            # (target binario con threshold=1% suele rondar 20-50% positivos según el activo)
            n_pos = max(y_train.sum(), 1)
            n_neg = max(len(y_train) - n_pos, 1)
            params = {**DEFAULT_XGB_PARAMS, **(model_params or {})}
            model = XGBClassifier(
                **params, scale_pos_weight=n_neg / n_pos, eval_metric="logloss",
                random_state=random_state, n_jobs=-1,
            )
        else:
            raise ValueError(f"modelo desconocido: {model_name}")

        model.fit(X_train_clean, y_train)

        if calibrate and X_calib is not None and y_calib.nunique() == 2 and len(y_calib) >= 20:
            X_calib_clean = X_calib.fillna(0).astype(float)
            try:
                calibrated_model = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
                calibrated_model.fit(X_calib_clean, y_calib)
                y_proba = calibrated_model.predict_proba(X_test_clean)[:, 1]
            except Exception:
                # Si la calibración falla (ej. muy pocas muestras de una clase),
                # se usa el modelo sin calibrar en vez de romper el pipeline.
                y_proba = model.predict_proba(X_test_clean)[:, 1]
        else:
            y_proba = model.predict_proba(X_test_clean)[:, 1]

        y_pred = (y_proba >= decision_threshold).astype(int)
        base_rate_train = float(y_train_full.mean())

        for d, yt, yp, ypr in zip(dates_test, y_test, y_pred, y_proba):
            results.append({"date": d, "y_true": yt, "y_pred": yp, "y_proba": ypr,
                            "base_rate_train": base_rate_train})

    return pd.DataFrame(results)


def find_optimal_threshold(X: pd.DataFrame, y: pd.Series, model_name: str,
                            model_params: dict, calibrate: bool,
                            validation_fraction: float = 0.25,
                            random_state: int = 42) -> float:
    """
    Busca el umbral de decisión que maximiza F1 sobre un tramo de VALIDACIÓN
    separado (el 'validation_fraction' final del histórico disponible HASTA
    ese punto, nunca el set de test real usado en evaluate_predictions).

    ADVERTENCIA EMPÍRICA (documentada tras probarlo): optimizar el umbral en
    un único split de validación es FRÁGIL -- en USD/JPY este método encontró
    un umbral que colapsaba a 0% de predicciones positivas en el periodo de
    test real, peor que simplemente usar 0.5. La causa es que la tasa base
    de positivos no es estable en el tiempo (régimen de mercado cambia), así
    que un umbral fijo "óptimo" en un periodo no necesariamente generaliza.

    RECOMENDACIÓN: usar esta función como diagnóstico exploratorio, no para
    fijar el `decision_threshold` de producción a ciegas. El default robusto
    documentado y recomendado en el notebook es decision_threshold=0.5 CON
    calibrate=True -- el beneficio principal de calibrar es la calidad de la
    probabilidad (Brier score), no necesariamente mover el punto de decisión.
    """
    valid_mask = y.notna()
    X_clean = X[valid_mask].fillna(0).astype(float)
    y_clean = y[valid_mask]

    split = int(len(X_clean) * (1 - validation_fraction))
    X_train, X_val = X_clean.iloc[:split], X_clean.iloc[split:]
    y_train, y_val = y_clean.iloc[:split], y_clean.iloc[split:]

    if y_train.nunique() < 2 or len(X_val) < 20:
        return 0.5  # fallback seguro si no hay suficientes datos para optimizar

    if model_name == "xgboost":
        n_pos, n_neg = max(y_train.sum(), 1), max(len(y_train) - y_train.sum(), 1)
        params = {**DEFAULT_XGB_PARAMS, **(model_params or {})}
        model = XGBClassifier(**params, scale_pos_weight=n_neg / n_pos,
                               eval_metric="logloss", random_state=random_state, n_jobs=-1)
    else:
        params = {**DEFAULT_RF_PARAMS, **(model_params or {})}
        model = RandomForestClassifier(**params, class_weight="balanced",
                                        random_state=random_state, n_jobs=-1)

    model.fit(X_train, y_train)

    if calibrate:
        calib_split = int(len(X_train) * 0.8)
        X_calib, y_calib = X_train.iloc[calib_split:], y_train.iloc[calib_split:]
        if y_calib.nunique() == 2 and len(y_calib) >= 20:
            model = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
            model.fit(X_calib, y_calib)

    proba_val = model.predict_proba(X_val)[:, 1]

    # Salvaguarda: igual que vimos con ARIMA prediciendo siempre "no sube",
    # optimizar F1 sin restricción puede converger a un umbral degenerado que
    # hace que el modelo prediga casi siempre la clase mayoritaria (o
    # minoritaria) sin discriminar de verdad. Se descartan umbrales donde la
    # tasa de predicciones positivas se aleje más de `max_rate_deviation` de
    # la tasa base real observada en el propio tramo de validación.
    base_rate = y_val.mean()
    max_rate_deviation = 0.15  # más estricto que la versión inicial (0.25):
                                # la versión laxa aún dejaba pasar umbrales
                                # que colapsaban en test real (ver advertencia arriba)

    best_threshold, best_f1 = 0.5, -1
    candidates_found = 0
    for th in np.arange(0.35, 0.66, 0.05):
        pred = (proba_val >= th).astype(int)
        pred_rate = pred.mean()
        if abs(pred_rate - base_rate) > max_rate_deviation:
            continue  # umbral degenerado -- predice casi siempre una sola clase
        candidates_found += 1
        f1 = f1_score(y_val, pred, zero_division=0)
        if f1 > best_f1:
            best_f1, best_threshold = f1, th

    if candidates_found == 0:
        return 0.5  # ningún umbral pasó la salvaguarda -- usar el default robusto

    return round(float(best_threshold), 2)


def evaluate_predictions(results: pd.DataFrame, model_label: str) -> dict:
    """
    Calcula métricas estándar de clasificación sobre los resultados walk-forward,
    junto a las referencias triviales con las que hay que compararlas:
    f1_always_up (F1 de decir siempre "sube"), accuracy_majority (acertar
    siempre la clase mayoritaria), roc_auc (0.5 = azar) y brier_skill_score
    (> 0 = probabilidades mejores que la tasa base del train).
    """
    if results.empty:
        return {"model": model_label, "n_predictions": 0}

    y_true, y_pred, y_proba = results["y_true"], results["y_pred"], results["y_proba"]
    base_rate = y_true.mean()
    reference = results["base_rate_train"] if "base_rate_train" in results else base_rate
    return {
        "model": model_label,
        "n_predictions": len(results),
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "brier_score": brier_score_loss(y_true, y_proba),  # 0=perfecto, 0.25=referencia "siempre 50%"
        "base_rate_positive": base_rate,  # referencia: % real de casos positivos
        "f1_always_up": f1_always_up(base_rate),
        "accuracy_majority": max(base_rate, 1 - base_rate),
        "roc_auc": safe_auc(y_true, y_proba),
        "brier_skill_score": brier_skill_score(y_true, y_proba, reference),
    }


def get_feature_importance(X: pd.DataFrame, y: pd.Series, model_name: str,
                            random_state: int = 42) -> pd.Series:
    """
    Entrena el modelo UNA VEZ sobre todo el histórico disponible (no walk-forward)
    solo para extraer feature importance interpretable — esto es exploratorio/
    explicativo, no se usa para generar señales de trading.
    """
    valid_mask = y.notna()
    X_clean = X[valid_mask].fillna(0).astype(float)
    y_clean = y[valid_mask]

    if model_name == "random_forest":
        model = RandomForestClassifier(
            n_estimators=200, max_depth=5, min_samples_leaf=10,
            class_weight="balanced", random_state=random_state, n_jobs=-1,
        )
    elif model_name == "xgboost":
        n_pos = max(y_clean.sum(), 1)
        n_neg = max(len(y_clean) - n_pos, 1)
        model = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            scale_pos_weight=n_neg / n_pos, eval_metric="logloss",
            random_state=random_state, n_jobs=-1,
        )
    else:
        raise ValueError(f"modelo desconocido: {model_name}")

    model.fit(X_clean, y_clean)
    return pd.Series(model.feature_importances_, index=X_clean.columns).sort_values(ascending=False)


def simulate_equity_curve(results: pd.DataFrame, close: pd.Series, horizon: int = 5,
                           cost_pct: float = 0.003) -> pd.Series:
    """
    Simula curva de equity de operar la señal: long cuando y_pred=1, flat si no,
    manteniendo cada entrada `horizon` días (ver tranche_strategy_returns).

    cost_pct=0.003 (0.3%) replica EXACTAMENTE el coste validado en el lab:
    total_cost_pct = (commission_pct + slippage_pct) * 2, confirmado en el
    código fuente del MCP con los valores default (0.1%+0.05%)*2.

    Corregido en 2026-10: la versión anterior encadenaba cada día con señal el
    retorno completo a `horizon` días, así que con señales diarias contaba cada
    movimiento del precio ~horizon veces. Las curvas del notebook v1 están
    infladas por eso.
    """
    if results.empty:
        return pd.Series(dtype=float)

    signals = results.set_index("date")["y_pred"]
    daily = tranche_strategy_returns(signals, close, horizon, cost_pct)
    return (1 + daily["strategy"]).cumprod()
