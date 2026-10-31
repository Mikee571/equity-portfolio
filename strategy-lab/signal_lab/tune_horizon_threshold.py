"""
tune_horizon_threshold.py
==========================
Grid search de (horizon, threshold) por activo, usando XGBoost con walk-forward,
para verificar empíricamente si la configuración fija (5d, 1%) es subóptima
para algunos activos, y por cuánto.

Actualizado en la auditoría de 2026-10:
- Walk-forward con purga = horizon (antes sin hueco: el train veía precios
  del test a través de sus últimas etiquetas).
- Se elige por AUC, no por F1: F1 de la clase positiva lo maximiza decir
  siempre "sube", y cada horizonte/umbral cambia la tasa de positivos, así
  que comparar F1 entre configuraciones favorecía a las de más positivos.
  Se imprimen f1_always_up y accuracy_majority como referencia.
- Cualquier configuración elegida aquí está contaminada por la elección
  (multiple testing): validarla con evaluate_strategy10.py en datos que este
  grid search no haya visto antes de cambiar asset_config.py.
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
HORIZONS = [3, 5, 10]
THRESHOLDS = [0.01, 0.015, 0.02]
MIN_TRAIN_SIZE = 252
RETRAIN_EVERY = 21
OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "grid_search_results.csv")


def load_asset_data(ticker, period="2y"):
    df = yf.download(ticker, period=period, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


print("Descargando datos y construyendo features técnicos/sentimiento (una sola vez por activo)...")
raw_data = {t: load_asset_data(t) for t in UNIVERSE}
tech_feats = {t: build_technical_features(df) for t, df in raw_data.items()}
sent_feats = {t: build_sentiment_features(t, df.index) for t, df in raw_data.items()}

rows = []
for ticker in UNIVERSE:
    X_base = tech_feats[ticker].join(sent_feats[ticker])
    close = raw_data[ticker]["Close"]

    for horizon in HORIZONS:
        for threshold in THRESHOLDS:
            y = build_binary_target(close, horizon=horizon, threshold=threshold)
            pct_positive = y.dropna().mean()

            # Saltar configuraciones demasiado desbalanceadas (menos de 10%
            # positivos) -- ya sabemos por el caso ARIMA que ahí el accuracy
            # se vuelve ilusorio sin aportar información real.
            if pct_positive < 0.10 or pct_positive > 0.90:
                rows.append({
                    "ticker": ticker, "horizon": horizon, "threshold": threshold,
                    "pct_positive": pct_positive, "skipped_imbalanced": True,
                })
                continue

            results = run_walk_forward_model(
                X_base, y, "xgboost",
                min_train_size=MIN_TRAIN_SIZE, retrain_every=RETRAIN_EVERY,
                purge_gap=horizon,
            )
            ev = evaluate_predictions(results, "xgboost")
            ev.update({"ticker": ticker, "horizon": horizon, "threshold": threshold,
                       "pct_positive": pct_positive, "skipped_imbalanced": False})
            rows.append(ev)
            print(f"{ticker} | horizon={horizon} threshold={threshold}: "
                  f"auc={ev.get('roc_auc', float('nan')):.3f} "
                  f"f1={ev.get('f1', float('nan')):.3f} (siempre-sube {ev.get('f1_always_up', float('nan')):.3f}) "
                  f"pct_pos={pct_positive:.2f}")

grid_df = pd.DataFrame(rows)
grid_df.to_csv(OUTPUT_CSV, index=False)
print(f"\nGuardado: {OUTPUT_CSV}")

print("\n=== Mejor configuración por activo (mayor AUC, excluyendo desbalanceados) ===")
valid = grid_df[~grid_df["skipped_imbalanced"]]
best = valid.loc[valid.groupby("ticker")["roc_auc"].idxmax()]
print(best[["ticker", "horizon", "threshold", "roc_auc", "brier_skill_score", "f1", "f1_always_up",
            "accuracy", "accuracy_majority", "pct_positive"]].to_string(index=False))
