"""
tune_hyperparams.py
====================
Grid search ligero de hiperparámetros de XGBoost por activo, manteniendo
horizon=10 (ya validado como mejor configuración general en
tune_horizon_threshold.py) y threshold=0.01.

Grid deliberadamente pequeño (no exhaustivo) -- con ~250-500 observaciones
por activo, un grid grande sobreajustaría la elección de hiperparámetros al
propio set de validación walk-forward, que es exactamente el tipo de
overfitting de "segundo orden" que hay que evitar en datasets pequeños.

Actualizado en la auditoría de 2026-10: usa run_walk_forward_model (que ya
acepta model_params) con purga = HORIZON, en vez de una copia propia del
walk-forward sin purga, y elige por AUC en vez de F1 (ver
tune_horizon_threshold.py). Lo elegido aquí debe validarse con
evaluate_strategy10.py en datos no vistos antes de tocar asset_config.py.
"""
import os
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf
from indicators import build_technical_features
from sentiment import build_sentiment_features
from targets_and_benchmark import build_binary_target
from ml_pipeline import run_walk_forward_model, evaluate_predictions

UNIVERSE = ["USDJPY=X", "HG=F", "GDX", "NVDA"]
HORIZON = 10
THRESHOLD = 0.01
MIN_TRAIN_SIZE = 252
RETRAIN_EVERY = 21
OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "hyperparam_grid_results.csv")

# Grid pequeño: profundidad del árbol y tasa de aprendizaje son los dos
# hiperparámetros con más impacto práctico en XGBoost para datasets chicos.
PARAM_GRID = [
    {"max_depth": 3, "learning_rate": 0.05, "n_estimators": 200},
    {"max_depth": 4, "learning_rate": 0.05, "n_estimators": 200},  # actual/default
    {"max_depth": 3, "learning_rate": 0.1, "n_estimators": 100},
    {"max_depth": 5, "learning_rate": 0.03, "n_estimators": 300},
]


def load_asset_data(ticker, period="2y"):
    df = yf.download(ticker, period=period, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


print("Descargando datos y construyendo features (una vez por activo)...")
raw_data = {t: load_asset_data(t) for t in UNIVERSE}
tech_feats = {t: build_technical_features(df) for t, df in raw_data.items()}
sent_feats = {t: build_sentiment_features(t, df.index) for t, df in raw_data.items()}

rows = []
for ticker in UNIVERSE:
    X = tech_feats[ticker].join(sent_feats[ticker])
    y = build_binary_target(raw_data[ticker]["Close"], horizon=HORIZON, threshold=THRESHOLD)

    for params in PARAM_GRID:
        results = run_walk_forward_model(X, y, "xgboost", min_train_size=MIN_TRAIN_SIZE,
                                         retrain_every=RETRAIN_EVERY, model_params=params,
                                         purge_gap=HORIZON)
        ev = evaluate_predictions(results, "xgboost")
        ev.update({"ticker": ticker, **params})
        rows.append(ev)
        print(f"{ticker} | {params}: auc={ev.get('roc_auc', float('nan')):.3f} "
              f"f1={ev.get('f1', float('nan')):.3f} (siempre-sube {ev.get('f1_always_up', float('nan')):.3f})")

grid_df = pd.DataFrame(rows)
grid_df.to_csv(OUTPUT_CSV, index=False)
print(f"\nGuardado: {OUTPUT_CSV}")

print("\n=== Mejor configuración por activo (mayor AUC) ===")
best = grid_df.loc[grid_df.groupby("ticker")["roc_auc"].idxmax()]
print(best[["ticker", "max_depth", "learning_rate", "n_estimators", "roc_auc", "brier_skill_score",
            "f1", "f1_always_up"]].to_string(index=False))
