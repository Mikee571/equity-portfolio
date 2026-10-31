"""
evaluate_strategy10.py
======================
Auditoría de la Estrategia #10: ¿tiene la señal habilidad real?

1. Backtest walk-forward fiel a producción: ventana rolling de TRAIN_SIZE
   filas (las que ve daily_signal_run.py con 2 años de datos), re-entreno
   cada 21 días, purga = horizonte, configuración de asset_config.py, 10 años.
2. Resultados separados respecto al grid search que fijó esa configuración
   (evaluation.SELECTION_WINDOW): pre_seleccion son datos que el grid search
   no vio, seleccion está contaminado por la propia elección de parámetros
   (~15 configuraciones probadas por activo), post_seleccion es posterior.
   Si la señal solo funciona dentro de la ventana de selección, lo que se
   midió fue la elección, no la señal.
3. El mismo backtest sin purga, para medir cuánto inflaba la fuga.
4. Las señales en vivo (data/estrategia_10_signal_history.csv) con su
   resultado realizado, contra el criterio de promoción del README.

Solo features técnicas: el sentimiento RSS cubre ~5 días, cuyas filas aún no
tienen etiqueta, así que el modelo nunca entrena con un sentimiento distinto
de 0 y la feature no influye en la predicción (ver README).

Uso:  python evaluate_strategy10.py      (unos minutos; escribe data/strategy10_evaluation.csv)
"""
import os
import warnings

warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf

from asset_config import ASSET_CONFIG
from evaluation import (check_promotion, resolve_live_signals, safe_auc,
                        score_signal, selection_period)
from indicators import build_technical_features
from ml_pipeline import run_walk_forward_model
from targets_and_benchmark import build_binary_target

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_CSV = os.path.join(SCRIPT_DIR, "data", "estrategia_10_signal_history.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "data", "strategy10_evaluation.csv")

BACKTEST_PERIOD = "10y"
TRAIN_SIZE = 490      # n_train_obs de las señales en vivo: 2 años menos las filas sin etiqueta
RETRAIN_EVERY = 21
PERIODS = ["pre_seleccion", "seleccion", "post_seleccion", "total"]


def load_asset_data(ticker: str) -> pd.DataFrame:
    """Misma descarga que daily_signal_run.py, con más historia."""
    df = yf.download(ticker, period=BACKTEST_PERIOD, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        raise ValueError(f"yfinance devolvió un DataFrame vacío para {ticker}")
    return df


def backtest_asset(ticker: str, cfg: dict, df: pd.DataFrame) -> list:
    close = df["Close"]
    X = build_technical_features(df)
    y = build_binary_target(close, horizon=cfg["horizon"], threshold=cfg["threshold"])
    common = dict(min_train_size=TRAIN_SIZE, max_train_size=TRAIN_SIZE,
                  retrain_every=RETRAIN_EVERY, model_params=cfg["xgb_params"],
                  calibrate=cfg["use_calibration"])
    purged = run_walk_forward_model(X, y, "xgboost", purge_gap=cfg["horizon"], **common)
    leaky = run_walk_forward_model(X, y, "xgboost", purge_gap=0, **common)
    leaky = leaky[leaky["date"] >= purged["date"].min()]  # mismas fechas de test
    purged["periodo"] = selection_period(purged["date"]).to_numpy()
    leaky["periodo"] = selection_period(leaky["date"]).to_numpy()

    rows = []
    for period in PERIODS:
        sub = purged if period == "total" else purged[purged["periodo"] == period]
        sub_leaky = leaky if period == "total" else leaky[leaky["periodo"] == period]
        if sub.empty:
            continue
        metrics = score_signal(sub, close, cfg["horizon"])
        rows.append({
            "fuente": "backtest", "ticker": ticker, "periodo": period,
            "desde": sub["date"].min().date(), "hasta": sub["date"].max().date(),
            "calibrado": cfg["use_calibration"], **metrics,
            "auc_sin_purga": safe_auc(sub_leaky["y_true"], sub_leaky["y_proba"]),
        })
    return rows


def evaluate_live(closes: dict) -> list:
    history = pd.read_csv(HISTORY_CSV)
    live = resolve_live_signals(history, closes)
    rows = []
    for ticker, cfg in ASSET_CONFIG.items():
        sub = live[live["ticker"] == ticker].sort_values("date")
        resolved = sub[sub["y_true"].notna()]
        if resolved.empty:
            continue
        results = pd.DataFrame({
            "date": pd.to_datetime(resolved["date"]),
            "y_true": resolved["y_true"].astype(int),
            "y_pred": resolved["signal"],
            "y_proba": resolved["probability"],
        })
        metrics = score_signal(results, closes[ticker], cfg["horizon"])
        rows.append({
            "fuente": "en_vivo", "ticker": ticker, "periodo": "en_vivo",
            "desde": results["date"].min().date(), "hasta": results["date"].max().date(),
            "calibrado": cfg["use_calibration"], "n_sin_resolver": len(sub) - len(resolved),
            **metrics,
        })
    return rows


def print_table(df: pd.DataFrame) -> None:
    show = pd.DataFrame({
        "ticker": df["ticker"],
        "periodo": df["periodo"],
        "fechas": df["desde"].astype(str) + " → " + df["hasta"].astype(str),
        "n": df["n"],
        "%sube": (df["base_rate"] * 100).round(0).astype(int),
        "AUC [IC 90%]": df.apply(lambda r: f"{r.auc:.2f} [{r.auc_ci_low:.2f}, {r.auc_ci_high:.2f}]", axis=1),
        "BSS": df["bss"].round(2),
        "F1 / siempre-sube": df.apply(lambda r: f"{r.f1:.2f} / {r.f1_always_up:.2f}", axis=1),
        "Sharpe señal / B&H": df.apply(
            lambda r: f"{'sin exposición' if r.exposure == 0 else f'{r.sharpe_signal:.2f}'} / {r.sharpe_buy_hold:.2f}",
            axis=1),
    })
    if "auc_sin_purga" in df and df["auc_sin_purga"].notna().any():
        show["AUC sin purga"] = df["auc_sin_purga"].round(2)
    print(show.to_string(index=False))


def main():
    rows, closes = [], {}
    for ticker, cfg in ASSET_CONFIG.items():
        print(f"Backtest {ticker}...", flush=True)
        df = load_asset_data(ticker)
        closes[ticker] = df["Close"]
        rows += backtest_asset(ticker, cfg, df)
    rows += evaluate_live(closes)

    report = pd.DataFrame(rows)
    report.to_csv(OUTPUT_CSV, index=False)

    pd.set_option("display.width", 250)
    backtest = report[report["fuente"] == "backtest"]
    live = report[report["fuente"] == "en_vivo"]

    print("\n=== Backtest walk-forward con purga (ventana rolling de producción, 10 años) ===")
    print("AUC 0.5 = azar. BSS > 0 = probabilidades mejores que la tasa base del train.")
    print_table(backtest)

    print("\n=== Señales en vivo resueltas (horizonte ya vencido) ===")
    print_table(live)

    print("\n=== Criterio de promoción ===")
    for source, frame in [("backtest pre_seleccion (requisito previo)", backtest[backtest["periodo"] == "pre_seleccion"]),
                          ("en vivo", live)]:
        print(f"\n{source}:")
        for _, r in frame.iterrows():
            checks = check_promotion(r.to_dict(), calibrated=bool(r["calibrado"]))
            detail = ", ".join(f"{k}={'sí' if v else 'no'}" for k, v in checks.items() if k != "promociona")
            print(f"  {r['ticker']:<9} {'PROMOCIONA' if checks['promociona'] else 'no promociona'}  ({detail})")

    print(f"\nGuardado: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
