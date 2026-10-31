"""
evaluation.py
=============
Evaluación de la Estrategia #10 contra referencias que no saben nada.

Por qué existe (auditoría 2026-10-07): F1 de la clase positiva, la métrica de
referencia hasta ahora, lo maximiza un clasificador que dice siempre "sube"
(recall = 1, F1 = 2p / (1 + p), con p = tasa de positivos). En la réplica de
esa fecha, ese clasificador trivial superó el F1 del modelo en los 8 casos
probados (4 activos x 2 y 5 años). El único benchmark usado hasta entonces
era ARIMA, que hacía lo contrario (decir siempre "no sube", F1 = 0), así que
cualquier modelo con algo de recall parecía bueno a su lado.

Lo que se mide aquí:

- roc_auc: ¿ordena el modelo los días mejor que el azar? 0.5 = azar. No
  depende del umbral de decisión ni de la calibración.
- brier_skill_score: ¿son sus probabilidades mejores que repetir la tasa base
  conocida en el train? > 0 = mejor. Solo es exigible en activos calibrados:
  sin calibrar, scale_pos_weight desplaza las probabilidades a propósito.
- block_bootstrap_ci: intervalo de confianza que respeta el solape de las
  etiquetas. Con horizonte 10, dos días seguidos comparten 9 de sus 10 días
  de retorno; tratar cada día como independiente da intervalos ~3x estrechos.
- tranche_strategy_returns: retorno de operar la señal, neto de costes, junto
  al buy-and-hold del mismo periodo.
- check_promotion: el criterio de promoción del README, en código.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

# Datos que vio el grid search que fijó asset_config.py (2 años hasta jun 2026)
# y fecha de la primera señal en vivo con esa configuración. Las predicciones
# dentro de la ventana de selección están contaminadas por la propia elección
# de configuración; las de antes y después no.
SELECTION_WINDOW = (pd.Timestamp("2024-06-21"), pd.Timestamp("2026-06-19"))

# Criterio de promoción (README, sección "Criterio de promoción"). Se aplica a
# las señales en vivo y, como requisito previo, al backtest pre-selección.
PROMOTION_CRITERIA = {
    "min_resolved_days": 126,       # ~6 meses de señales con horizonte ya vencido
    "auc_ci_low_min": 0.50,         # el IC 90% del AUC debe quedar por encima del azar
    "sharpe_excess_min": 0.0,       # Sharpe neto de la señal >= Sharpe de buy-and-hold
    "bss_min_if_calibrated": 0.0,   # activos calibrados: probabilidades mejores que la tasa base
}


def f1_always_up(base_rate: float) -> float:
    """F1 de la clase positiva de un clasificador que siempre predice 1."""
    return 2 * base_rate / (1 + base_rate) if base_rate > 0 else 0.0


def safe_auc(y_true, y_score) -> float:
    """ROC AUC, o NaN si solo hay una clase."""
    y_true = np.asarray(y_true)
    if len(np.unique(y_true)) < 2:
        return np.nan
    return roc_auc_score(y_true, y_score)


def brier_skill_score(y_true, y_proba, reference) -> float:
    """
    1 - Brier(modelo) / Brier(referencia). `reference` es una probabilidad
    constante o un array (p. ej. la tasa base del train de cada fold, la
    información que habría tenido un predictor sin modelo en ese momento).
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_proba, dtype=float)
    ref = np.broadcast_to(np.asarray(reference, dtype=float), y.shape)
    brier_ref = np.mean((ref - y) ** 2)
    if brier_ref == 0:
        return np.nan
    return 1 - np.mean((p - y) ** 2) / brier_ref


def block_bootstrap_ci(y_true, y_score, metric=safe_auc, block: int = 21,
                       n_boot: int = 1000, alpha: float = 0.10, seed: int = 42):
    """
    Intervalo de confianza (1 - alpha) de `metric` por moving block bootstrap:
    se remuestrean bloques contiguos de `block` días, que conservan la
    dependencia entre etiquetas solapadas. block=21 > horizon=10.

    Devuelve (low, high), o (NaN, NaN) si la muestra es demasiado corta.
    """
    y, s = np.asarray(y_true), np.asarray(y_score)
    n = len(y)
    if n < 2 * block:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    offsets = np.arange(block)
    stats = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        idx = (starts[:, None] + offsets).ravel()[:n]
        value = metric(y[idx], s[idx])
        if not np.isnan(value):
            stats.append(value)
    if len(stats) < n_boot / 2:
        return (np.nan, np.nan)
    low, high = np.quantile(stats, [alpha / 2, 1 - alpha / 2])
    return (float(low), float(high))


def tranche_strategy_returns(signals: pd.Series, close: pd.Series, horizon: int,
                             cost_pct: float = 0.003) -> pd.DataFrame:
    """
    Opera la señal como `horizon` carteras solapadas: cada día con señal 1 se
    abre un tramo de 1/horizon del capital y se mantiene `horizon` días. La
    exposición del día t es la suma de los tramos abiertos y se gana el
    retorno de t a t+1, así que cada día de mercado cuenta una sola vez.
    (La versión anterior de simulate_equity_curve encadenaba cada día el
    retorno completo a `horizon` días: contaba cada movimiento ~horizon veces.)

    Días sin señal dentro del periodo (fallos del run diario) no abren tramo.
    cost_pct es de ida y vuelta (0.3%, el coste validado del lab): cada unidad
    de exposición que cambia paga la mitad.

    Devuelve un DataFrame indexado por fecha con exposure, strategy (retorno
    diario neto) y buy_hold (retorno diario del activo).
    """
    signals = signals.sort_index()
    close = close.sort_index()
    window = close.loc[signals.index[0]:signals.index[-1]].index
    sig = signals.reindex(window).fillna(0).astype(float)
    exposure = sig.rolling(horizon, min_periods=1).sum() / horizon
    fwd_return = (close.shift(-1) / close - 1).reindex(window)
    turnover = exposure.diff().abs().fillna(exposure.iloc[0])
    out = pd.DataFrame({
        "exposure": exposure,
        "strategy": exposure * fwd_return - turnover * cost_pct / 2,
        "buy_hold": fwd_return,
    })
    return out.dropna()


def performance_summary(daily_returns: pd.Series, periods_per_year: int = 252) -> dict:
    """Retorno anualizado, volatilidad, Sharpe (sin tipo libre) y máximo drawdown."""
    r = daily_returns.dropna()
    if len(r) < 2 or r.std() == 0:
        return {"ann_return": np.nan, "ann_vol": np.nan, "sharpe": np.nan, "max_drawdown": np.nan}
    equity = (1 + r).cumprod()
    return {
        "ann_return": equity.iloc[-1] ** (periods_per_year / len(r)) - 1,
        "ann_vol": r.std() * np.sqrt(periods_per_year),
        "sharpe": r.mean() / r.std() * np.sqrt(periods_per_year),
        "max_drawdown": (equity / equity.cummax() - 1).min(),
    }


def selection_period(dates) -> pd.Series:
    """Etiqueta cada fecha como pre_seleccion, seleccion o post_seleccion."""
    dates = pd.to_datetime(pd.Series(dates))
    start, end = SELECTION_WINDOW
    label = np.where(dates < start, "pre_seleccion",
                     np.where(dates <= end, "seleccion", "post_seleccion"))
    return pd.Series(label, index=dates.index)


def score_signal(results: pd.DataFrame, close: pd.Series, horizon: int,
                 cost_pct: float = 0.003) -> dict:
    """
    Métricas de una señal frente a sus referencias triviales. `results` necesita
    date, y_true, y_pred y y_proba; base_rate_train (opcional) es la referencia
    del Brier skill score. Sin ella se usa la tasa base del propio periodo, que
    es una referencia más difícil de batir (se conoce a posteriori).
    """
    if results.empty:
        return {"n": 0}
    y_true = results["y_true"].astype(int).to_numpy()
    y_pred = results["y_pred"].astype(int).to_numpy()
    y_proba = results["y_proba"].to_numpy()
    base_rate = y_true.mean()
    reference = results["base_rate_train"] if "base_rate_train" in results else base_rate
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    n_pred_pos, n_pos = int(y_pred.sum()), int(y_true.sum())
    f1 = 2 * tp / (n_pred_pos + n_pos) if (n_pred_pos + n_pos) else 0.0
    auc_low, auc_high = block_bootstrap_ci(y_true, y_proba)

    signals = pd.Series(y_pred, index=pd.to_datetime(results["date"]))
    daily = tranche_strategy_returns(signals, close, horizon, cost_pct)
    strat = performance_summary(daily["strategy"])
    bh = performance_summary(daily["buy_hold"])

    return {
        "n": len(y_true),
        "base_rate": base_rate,
        "pct_pred_up": y_pred.mean(),
        "f1": f1,
        "f1_always_up": f1_always_up(base_rate),
        "accuracy": (y_true == y_pred).mean(),
        "accuracy_majority": max(base_rate, 1 - base_rate),
        "auc": safe_auc(y_true, y_proba),
        "auc_ci_low": auc_low,
        "auc_ci_high": auc_high,
        "bss": brier_skill_score(y_true, y_proba, reference),
        "exposure": daily["exposure"].mean() if len(daily) else np.nan,
        "sharpe_signal": strat["sharpe"],
        "sharpe_buy_hold": bh["sharpe"],
        "ann_return_signal": strat["ann_return"],
        "ann_return_buy_hold": bh["ann_return"],
        "max_dd_signal": strat["max_drawdown"],
        "max_dd_buy_hold": bh["max_drawdown"],
    }


def check_promotion(metrics: dict, calibrated: bool, criteria: dict = PROMOTION_CRITERIA) -> dict:
    """Aplica el criterio de promoción. Devuelve cada condición y el veredicto."""
    checks = {
        "muestra_suficiente": metrics.get("n", 0) >= criteria["min_resolved_days"],
        "auc_sobre_azar": bool(metrics.get("auc_ci_low", np.nan) > criteria["auc_ci_low_min"]),
        "bate_buy_hold": bool(metrics.get("sharpe_signal", np.nan) - metrics.get("sharpe_buy_hold", np.nan)
                              >= criteria["sharpe_excess_min"]),
    }
    if calibrated:
        checks["probabilidades_utiles"] = bool(metrics.get("bss", np.nan) > criteria["bss_min_if_calibrated"])
    checks["promociona"] = all(checks.values())
    return checks


def resolve_live_signals(history: pd.DataFrame, closes: dict) -> pd.DataFrame:
    """
    Añade el resultado realizado a cada señal del histórico en vivo
    (estrategia_10_signal_history.csv): y_true = 1 si el cierre `horizon_days`
    sesiones después supera al de la fecha de la señal en más de `threshold`.
    Las filas cuyo horizonte aún no ha vencido quedan con y_true = NaN.
    `closes` mapea ticker -> serie de cierres.
    """
    rows = []
    for row in history.itertuples(index=False):
        close = closes[row.ticker].dropna()
        date = pd.Timestamp(row.date)
        pos = close.index.get_indexer([date])[0]
        y_true = np.nan
        if pos >= 0 and pos + row.horizon_days < len(close):
            fwd = close.iloc[pos + row.horizon_days] / close.iloc[pos] - 1
            y_true = float(fwd > row.threshold)
        rows.append({**row._asdict(), "y_true": y_true})
    return pd.DataFrame(rows)
