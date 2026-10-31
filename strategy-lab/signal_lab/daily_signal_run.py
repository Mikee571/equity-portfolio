"""
daily_signal_run.py
=====================
Orquestador diario de la Estrategia #10 (señal ML). Pensado para correr una
vez al día vía Task Scheduler de Windows, antes de la apertura europea
(~7-8am hora Madrid).

Qué hace cada ejecución:
  1. Para cada activo en UNIVERSE, descarga precio reciente, construye
     features (técnico + sentimiento), entrena el modelo sobre TODO el
     histórico disponible hasta hoy (re-entrenamiento diario -- ver nota
     de coste computacional abajo), y genera la predicción para el día actual.
  2. Acumula el resultado en un CSV histórico (append, nunca overwrite) --
     esto es lo que construye el track record real out-of-sample necesario
     para evaluar el criterio de promoción definido en el README.
  3. Registra un log detallado (siempre) con timestamp, qué se descargó,
     qué falló, cuánto tardó cada etapa.
  4. Si CUALQUIER activo falla, envía una alerta Telegram de fallo (no
     bloquea el resto -- un activo caído no debe tirar todo el run).

Nota sobre coste computacional: a diferencia del walk-forward usado para
VALIDAR el modelo (que reentrena cada 21 días sobre folds históricos), aquí
se reentrena con TODO el histórico disponible cada vez que corre el script.
Con ~500 observaciones y 4 activos esto toma segundos, no minutos -- ver
benchmarks en el notebook. Si el universo crece mucho (los ~12 activos del
lab), conviene revisar si el reentrenamiento diario sigue siendo barato.

Manejo de errores: cada etapa (descarga, features, modelo) está envuelta en
try/except individual -- un fallo en un activo no debe impedir que los
demás se procesen. Todos los errores se loguean Y se alertan por Telegram
(con resumen agregado, no uno por fallo, para no saturar).
"""

import sys
import os
import time
import logging
import traceback
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

# Asegurar que el directorio del script está en el path, sin importar desde
# dónde lo invoque Task Scheduler (necesario porque las tareas programadas en
# Windows a veces corren con un cwd distinto al del script).
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from indicators import build_technical_features
from sentiment import build_sentiment_features
from targets_and_benchmark import build_binary_target
from ml_pipeline import run_walk_forward_model
from asset_config import get_config, ASSET_CONFIG
from telegram_alerts_signal10 import alert_pipeline_failure, alert_pipeline_summary_if_partial_failure
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator

# --- Configuración del run ---
UNIVERSE = list(ASSET_CONFIG.keys())  # los activos ya validados con grid search
HISTORY_PERIOD = "2y"  # histórico descargado para entrenar cada día
LAB_DIR = os.path.dirname(SCRIPT_DIR)  # strategy-lab/ (logs compartidos con stat_arb)
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "data", "estrategia_10_signal_history.csv")
LOG_FILE = os.path.join(LAB_DIR, "logs", "daily_signal_run.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),  # también visible si se corre manualmente
    ],
)
logger = logging.getLogger("daily_signal_run")


def load_asset_data(ticker: str, period: str = HISTORY_PERIOD) -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        raise ValueError(f"yfinance devolvió un DataFrame vacío para {ticker}")
    return df


def train_and_predict_today(ticker: str, df: pd.DataFrame, cfg: dict) -> dict:
    """
    Entrena el modelo XGBoost sobre TODO el histórico disponible (no
    walk-forward -- eso ya se usó para VALIDAR el modelo, no para producción
    diaria) y predice la dirección para el día actual (última fila disponible).

    Devuelve un dict con la predicción y metadatos -- nunca lanza excepción
    hacia afuera sin loguear primero el contexto específico del fallo.
    """
    X = build_technical_features(df).join(build_sentiment_features(ticker, df.index))
    y = build_binary_target(df["Close"], horizon=cfg["horizon"], threshold=cfg["threshold"])

    valid_mask = y.notna()
    X_train = X[valid_mask].fillna(0).astype(float)
    y_train = y[valid_mask]

    if y_train.nunique() < 2 or len(y_train) < 100:
        raise ValueError(
            f"Histórico insuficiente o sin variabilidad de clase para entrenar "
            f"({len(y_train)} obs. válidas, {y_train.nunique()} clases distintas)"
        )

    n_pos, n_neg = max(y_train.sum(), 1), max(len(y_train) - y_train.sum(), 1)
    model = XGBClassifier(
        **cfg["xgb_params"], scale_pos_weight=n_neg / n_pos,
        eval_metric="logloss", random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train)

    if cfg.get("use_calibration", False):
        calib_split = int(len(X_train) * 0.8)
        X_calib, y_calib = X_train.iloc[calib_split:], y_train.iloc[calib_split:]
        if y_calib.nunique() == 2 and len(y_calib) >= 20:
            model = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
            model.fit(X_calib, y_calib)

    # Fila más reciente disponible = el "hoy" para la predicción.
    # OJO: la última fila puede tener target NaN (por construcción, el target
    # usa precio futuro a `horizon` días) -- eso es esperado y correcto: para
    # PREDECIR hoy no necesitamos el target de hoy, solo las features.
    X_today = X.iloc[[-1]].fillna(0).astype(float)
    proba_today = model.predict_proba(X_today)[0, 1]
    signal_today = int(proba_today >= 0.5)

    return {
        "date": pd.Timestamp(X.index[-1]).strftime("%Y-%m-%d"),
        "ticker": ticker,
        "signal": signal_today,
        "probability": round(float(proba_today), 4),
        "horizon_days": cfg["horizon"],
        "threshold": cfg["threshold"],
        "calibrated": cfg.get("use_calibration", False),
        "n_train_obs": len(y_train),
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def append_to_history_csv(row: dict) -> None:
    """
    Añade una fila al CSV histórico. Si ya existe una fila para la misma
    combinación (date, ticker) -- ej. por una re-ejecución manual el mismo
    día tras un fallo previo -- esa fila se REEMPLAZA en vez de duplicarse.
    Esto protege la integridad del track record: cada (fecha, activo) debe
    aparecer una sola vez, o las métricas de accuracy out-of-sample que se
    calculen sobre este historial quedarían infladas/distorsionadas.
    """
    if os.path.isfile(OUTPUT_CSV):
        history = pd.read_csv(OUTPUT_CSV)
        mask = (history["date"].astype(str) == str(row["date"])) & (history["ticker"] == row["ticker"])
        if mask.any():
            logger.info(f"[{row['ticker']}] Ya existía una fila para {row['date']} -- se reemplaza (no se duplica).")
            history = history[~mask]
        history = pd.concat([history, pd.DataFrame([row])], ignore_index=True)
        history.to_csv(OUTPUT_CSV, index=False)
    else:
        pd.DataFrame([row]).to_csv(OUTPUT_CSV, index=False)


def run_daily_pipeline() -> None:
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"Inicio de run diario — Estrategia #10 — universo: {UNIVERSE}")

    n_success = 0
    failed_tickers = []

    for ticker in UNIVERSE:
        ticker_start = time.time()
        try:
            logger.info(f"[{ticker}] Descargando datos ({HISTORY_PERIOD})...")
            df = load_asset_data(ticker)
            logger.info(f"[{ticker}] {len(df)} filas descargadas, hasta {df.index[-1].date()}")

            cfg = get_config(ticker)
            logger.info(f"[{ticker}] Config: horizon={cfg['horizon']} "
                        f"threshold={cfg['threshold']} calibrated={cfg.get('use_calibration', False)}")

            result = train_and_predict_today(ticker, df, cfg)
            append_to_history_csv(result)

            elapsed = time.time() - ticker_start
            logger.info(
                f"[{ticker}] OK — señal={result['signal']} "
                f"prob={result['probability']:.3f} ({elapsed:.1f}s)"
            )
            n_success += 1

        except Exception as e:
            elapsed = time.time() - ticker_start
            error_detail = f"{type(e).__name__}: {e}"
            logger.error(f"[{ticker}] FALLO tras {elapsed:.1f}s — {error_detail}")
            logger.debug(traceback.format_exc())  # detalle completo solo en log, no en consola
            failed_tickers.append(ticker)
            alert_pipeline_failure(ticker, stage="train_and_predict", error_message=error_detail)

    total_elapsed = time.time() - start_time
    logger.info(
        f"Run completado: {n_success}/{len(UNIVERSE)} activos OK "
        f"en {total_elapsed:.1f}s. Fallaron: {failed_tickers or 'ninguno'}"
    )
    logger.info("=" * 60)

    alert_pipeline_summary_if_partial_failure(n_success, len(UNIVERSE), failed_tickers)

    if n_success == 0:
        # Fallo total -- esto es lo suficientemente grave como para garantizar
        # que el script termine con código de error (visible en Task Scheduler
        # como "última ejecución falló"), no solo en el log.
        sys.exit(1)


if __name__ == "__main__":
    run_daily_pipeline()
