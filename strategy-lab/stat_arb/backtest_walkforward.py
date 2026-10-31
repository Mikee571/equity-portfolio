"""
Backtest walk-forward del stat arb: ¿aportan Kalman u OU?
==========================================================
Pregunta: ¿mejora el hedge ratio dinámico (Kalman, notebook 5.1 de cantaro86)
o las bandas de equilibrio OU (notebook 6.1) al método actual del lab? Y,
antes de eso, ¿gana dinero el método actual fuera de muestra y con costes?

Diseño fijado ANTES de ver resultados (lección de la auditoría de la
Estrategia #10: elegir mirando el resultado es otra forma de sobreajuste):

- Universo: los 37 pares de pair_scanner.UNIVERSES (4 sectores del lab).
- Cada trimestre (63 sesiones) se seleccionan pares con la regla actual del
  lab sobre los 2 años previos (504 sesiones): Engle-Granger p < 0.05 Y
  Johansen traza > crítico 95%, half-life MCO entre 3 y 60 días, beta > 0.
  Se operan las 63 sesiones siguientes sin volver a estimar la selección.
- Estrategias:
    STATIC_Z   la actual: beta y alpha MCO de la formación, z-score móvil de
               30 días del spread en log, entrada |z| >= 1.5, salida |z| <= 0.5
    KALMAN_Z   beta_k por Kalman (alpha fija, sigma_eps MCO, sigma_eta MLE en la
               formación), z = innovación / sqrt(S), mismos umbrales, cobertura
               re-ajustada cada día con la beta filtrada
    STATIC_OU  beta MCO; OU ajustado al spread de la formación; entrada a
               theta +- 1 sigma_eq, salida a theta +- 0.1 sigma_eq (notebook 6.1)
  Diagnóstico: STATIC_Z sobre los 37 pares sin selección por cointegración.
- Ejecución al cierre del día de la señal; retorno desde el cierre siguiente.
  Posiciones en dólares: pata y = 1 / (1 + beta), pata x = -beta / (1 + beta)
  por unidad de capital (exposición bruta 1). Al cierre de cada ventana se
  cierra todo.
- Costes: 0.15% por lado y pata (0.1% comisión + 0.05% deslizamiento, el
  coste validado del lab), sobre cada cambio de peso, incluidas las
  re-coberturas de Kalman. Préstamo de la pata corta: 0.5% anual.
- Capital comprometido: cada par seleccionado recibe 1/N del capital de la
  ventana aunque no abra posición (Gatev, Goetzmann y Rouwenhorst, 2006).
- Criterio: KALMAN_Z o STATIC_OU solo sustituyen a STATIC_Z si su retorno
  diario neto supera al de STATIC_Z con t de Newey-West > 2. El stat arb
  merece seguir en vivo si el extremo inferior del IC 90% (bootstrap por
  bloques) del Sharpe neto de la estrategia elegida es > 0.

Uso:  python backtest_walkforward.py   (descarga precios la primera vez)
"""
import os
import sys
import warnings
from itertools import combinations

import numpy as np
import pandas as pd
import yfinance as yf
from statsmodels.tsa.stattools import coint

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kalman_ou import calibrate_joint, calibrate_sigma_eta, fit_ou, kalman_beta, ols_alpha_beta  # noqa: E402
from pair_scanner import MAX_HALF_LIFE, MIN_HALF_LIFE, UNIVERSES  # noqa: E402
from stat_arb_pairs import ZSCORE_ENTRY, ZSCORE_EXIT, half_life_reversion, johansen_test  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PRICES_CSV = os.path.join(DATA_DIR, "walkforward_prices.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "walkforward_results.csv")

START = "2010-01-01"
FORMATION_DAYS = 504
TRADING_DAYS = 63
Z_WINDOW = 30
OU_ENTRY, OU_EXIT = 1.0, 0.1
COST_PER_SIDE = 0.0015
BORROW_ANNUAL = 0.005
# Pre-registradas antes del primer backtest:
STRATEGIES = ["STATIC_Z", "KALMAN_Z", "STATIC_OU"]
# Añadida después, por un diagnóstico de la formación (ver kalman_ou.calibrate_joint):
POST_HOC = ["KALMAN_Z_MLE"]


# ---------------------------------------------------------------- datos

def load_prices(refresh: bool = False) -> pd.DataFrame:
    """Cierres ajustados (dividendos y splits) de todos los tickers del universo."""
    if os.path.isfile(PRICES_CSV) and not refresh:
        return pd.read_csv(PRICES_CSV, index_col=0, parse_dates=True)
    tickers = sorted({t for ts in UNIVERSES.values() for t in ts})
    close = yf.download(tickers, start=START, auto_adjust=True, progress=False)["Close"]
    os.makedirs(DATA_DIR, exist_ok=True)
    close.to_csv(PRICES_CSV)
    return close


def all_pairs() -> list:
    return [(u, y, x) for u, ts in UNIVERSES.items() for y, x in combinations(ts, 2)]


# ---------------------------------------------------------------- selección

def select_pairs(logp: pd.DataFrame, require_cointegration: bool = True) -> list:
    """Regla actual del lab sobre una ventana de formación de log-precios."""
    selected = []
    for universe, y, x in all_pairs():
        if y not in logp or x not in logp:
            continue
        w = logp[[y, x]].dropna()
        if len(w) < FORMATION_DAYS * 0.95:
            continue
        ly, lx = w[y].to_numpy(), w[x].to_numpy()
        alpha, beta, sigma_eps = ols_alpha_beta(ly, lx)
        if beta <= 0:
            continue
        spread = ly - alpha - beta * lx
        half_life, _ = half_life_reversion(pd.Series(spread))
        if require_cointegration:
            if coint(ly, lx)[1] >= 0.05:
                continue
            if not johansen_test(w[y], w[x], use_log=False)[2]:
                continue
            if half_life is None or not MIN_HALF_LIFE <= half_life <= MAX_HALF_LIFE:
                continue
        selected.append({"universe": universe, "y": y, "x": x, "alpha": alpha, "beta": beta,
                         "sigma_eps": sigma_eps, "half_life": half_life, "ou": fit_ou(spread)})
    return selected


# ---------------------------------------------------------------- señales

def signals(strategy: str, pair: dict, ly: np.ndarray, lx: np.ndarray, n_form: int) -> tuple:
    """
    (señal normalizada, beta para cubrir) en cada día de formación + trading.
    Señal > 0 = spread caro (vender spread). Solo usa información hasta cada día.
    """
    a, b = pair["alpha"], pair["beta"]
    if strategy == "KALMAN_Z":
        sigma_eta, _ = calibrate_sigma_eta(ly[:n_form], lx[:n_form], a, b, pair["sigma_eps"])
        k = kalman_beta(ly, lx, a, b, pair["sigma_eps"], sigma_eta)
        pair["sigma_eta"] = sigma_eta
        return k["innov"] / np.sqrt(k["S"]), k["beta_post"]
    if strategy == "KALMAN_Z_MLE":
        sigma_eps, sigma_eta = calibrate_joint(ly[:n_form], lx[:n_form], a, b)
        k = kalman_beta(ly, lx, a, b, sigma_eps, sigma_eta)
        pair["z_std_formation"] = float(np.std(k["innov"][:n_form] / np.sqrt(k["S"][:n_form])))
        return k["innov"] / np.sqrt(k["S"]), k["beta_post"]
    spread = ly - a - b * lx
    hedge = np.full(len(ly), b)
    if strategy == "STATIC_OU":
        ou = pair["ou"]
        if ou is None:
            return np.zeros(len(ly)), hedge
        return (spread - ou["theta"]) / ou["sigma_eq"], hedge
    s = pd.Series(spread)
    z = (s - s.rolling(Z_WINDOW).mean()) / s.rolling(Z_WINDOW).std()
    return z.to_numpy(), hedge


def thresholds(strategy: str) -> tuple:
    return (OU_ENTRY, OU_EXIT) if strategy == "STATIC_OU" else (ZSCORE_ENTRY, ZSCORE_EXIT)


def simulate(sig: np.ndarray, hedge: np.ndarray, ry: np.ndarray, rx: np.ndarray,
             entry: float, exit_: float) -> tuple:
    """
    Una ventana de trading. sig, hedge, ry, rx: arrays de la ventana (ry[t] =
    retorno simple del cierre t-1 al t). Decisión al cierre de t con sig[t];
    el retorno del día t+1 usa los pesos fijados en t. Devuelve (retornos
    diarios netos, lista de trades).
    """
    T = len(sig)
    rets = np.zeros(T)
    w_y = w_x = 0.0
    side, trades, open_trade = 0, [], None
    for t in range(T):
        # P&L del día t con los pesos del cierre t-1
        if side != 0:
            day = w_y * ry[t] + w_x * rx[t] - abs(min(w_y, w_x, 0.0)) * BORROW_ANNUAL / 252
            rets[t] += day
            open_trade["growth"] *= 1 + day
            open_trade["days"] += 1
        # decisión al cierre de t
        z = sig[t]
        new_side = side
        if not np.isfinite(z):
            pass
        elif side == 0:
            new_side = -1 if z >= entry else (1 if z <= -entry else 0)
        elif (side == -1 and z <= exit_) or (side == 1 and z >= -exit_):
            new_side = 0
        if t == T - 1:
            new_side = 0
        b = hedge[t]
        ny, nx = (new_side / (1 + b), -new_side * b / (1 + b)) if new_side != 0 else (0.0, 0.0)
        cost = (abs(ny - w_y) + abs(nx - w_x)) * COST_PER_SIDE
        rets[t] -= cost
        if open_trade is not None:
            open_trade["growth"] *= 1 - cost
        if side == 0 and new_side != 0:
            open_trade = {"side": new_side, "growth": 1 - cost, "days": 0}
        elif side != 0 and new_side == 0:
            trades.append({"side": side, "net_return": open_trade["growth"] - 1, "days": open_trade["days"]})
            open_trade = None
        side, w_y, w_x = new_side, ny, nx
    return rets, trades


# ---------------------------------------------------------------- walk-forward

def walk_forward(prices: pd.DataFrame) -> dict:
    """Retornos diarios por estrategia (capital comprometido), trades y selecciones."""
    logp = np.log(prices)
    simple = prices.pct_change()
    dates = prices.index
    variants = STRATEGIES + POST_HOC + ["STATIC_Z_ALL_PAIRS"]
    daily = {v: pd.Series(0.0, index=dates) for v in variants}
    trades, selections = {v: [] for v in variants}, []
    start = FORMATION_DAYS
    while start + 1 < len(dates):
        form = slice(start - FORMATION_DAYS, start)
        trade = slice(start, min(start + TRADING_DAYS, len(dates)))
        tdates = dates[trade]
        for variant, require in [("selected", True), ("all", False)]:
            chosen = select_pairs(logp.iloc[form], require_cointegration=require)
            strategies = STRATEGIES + POST_HOC if require else ["STATIC_Z"]
            if require:
                selections += [{"start": tdates[0], "pair": f"{p['y']}/{p['x']}", "half_life": p["half_life"]}
                               for p in chosen]
            for p in chosen:
                full = slice(start - FORMATION_DAYS, trade.stop)
                ly = logp[p["y"]].iloc[full].ffill().to_numpy()
                lx = logp[p["x"]].iloc[full].ffill().to_numpy()
                ry = simple[p["y"]].iloc[trade].fillna(0).to_numpy()
                rx = simple[p["x"]].iloc[trade].fillna(0).to_numpy()
                for s in strategies:
                    sig, hedge = signals(s, p, ly, lx, FORMATION_DAYS)
                    entry, exit_ = thresholds(s)
                    r, tr = simulate(sig[FORMATION_DAYS:], hedge[FORMATION_DAYS:], ry, rx, entry, exit_)
                    name = s if require else "STATIC_Z_ALL_PAIRS"
                    daily[name].loc[tdates] += r / len(chosen)
                    trades[name] += [{**t, "pair": f"{p['y']}/{p['x']}", "start": tdates[0],
                                      "sigma_eta": p.get("sigma_eta"),
                                      "z_std_formation": p.get("z_std_formation")} for t in tr]
        start += TRADING_DAYS
    first = dates[FORMATION_DAYS]
    return {"daily": pd.DataFrame(daily).loc[first:], "trades": {k: pd.DataFrame(v) for k, v in trades.items()},
            "selections": pd.DataFrame(selections)}


# ---------------------------------------------------------------- métricas

def newey_west_t(x: np.ndarray, lags: int = 5) -> float:
    x = np.asarray(x, dtype=float)
    n = len(x)
    e = x - x.mean()
    var = e @ e / n
    for k in range(1, lags + 1):
        var += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(var / n) if var > 0 else np.nan


def sharpe(r: np.ndarray) -> float:
    return r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan


def sharpe_ci(r: np.ndarray, block: int = 21, n_boot: int = 2000, alpha: float = 0.10,
              seed: int = 42) -> tuple:
    """IC del Sharpe por moving block bootstrap (bloques de ~1 mes)."""
    rng = np.random.default_rng(seed)
    n = len(r)
    n_blocks = int(np.ceil(n / block))
    stats = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        idx = (starts[:, None] + np.arange(block)).ravel()[:n]
        stats.append(sharpe(r[idx]))
    return tuple(np.nanquantile(stats, [alpha / 2, 1 - alpha / 2]))


def summary(res: dict) -> pd.DataFrame:
    rows = []
    for name, r in res["daily"].items():
        x = r.to_numpy()
        eq = np.cumprod(1 + x)
        lo, hi = sharpe_ci(x)
        tr = res["trades"][name]
        rows.append({
            "estrategia": name,
            "ret_anual": x.mean() * 252,
            "vol_anual": x.std() * np.sqrt(252),
            "sharpe": sharpe(x),
            "sharpe_ic90_lo": lo,
            "sharpe_ic90_hi": hi,
            "t_nw": newey_west_t(x),
            "max_dd": (eq / np.maximum.accumulate(eq) - 1).min(),
            "trades": len(tr),
            "trades_ganadores": (tr["net_return"] > 0).mean() if len(tr) else np.nan,
            "ret_medio_trade": tr["net_return"].mean() if len(tr) else np.nan,
            "dias_medios": tr["days"].mean() if len(tr) else np.nan,
        })
    return pd.DataFrame(rows)


def compare(res: dict, base: str = "STATIC_Z") -> pd.DataFrame:
    """Diferencia de retorno diario neto frente a la estrategia actual."""
    d = res["daily"]
    rows = []
    for name in STRATEGIES + POST_HOC:
        if name == base:
            continue
        diff = (d[name] - d[base]).to_numpy()
        rows.append({"estrategia": name, "vs": base, "dif_ret_anual": diff.mean() * 252,
                     "t_nw": newey_west_t(diff), "sustituye": newey_west_t(diff) > 2})
    return pd.DataFrame(rows)


def main():
    prices = load_prices()
    print(f"Precios: {prices.shape[1]} tickers, {prices.index.min().date()} -> {prices.index.max().date()}")
    res = walk_forward(prices)
    d = res["daily"]
    sel = res["selections"]
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    print(f"\nPeriodo operado: {d.index.min().date()} -> {d.index.max().date()} ({len(d)} sesiones)")
    per_window = sel.groupby("start").size().reindex(d.index[::TRADING_DAYS], fill_value=0)
    print(f"Pares seleccionados por trimestre: media {per_window.mean():.1f}, "
          f"trimestres sin ninguno {(per_window == 0).mean():.0%}")
    print("Pares más seleccionados:", sel["pair"].value_counts().head(8).to_dict())
    s = summary(res)
    print("\n=== Resultados netos de costes (capital comprometido) ===")
    print(s.to_string(index=False))
    print("\n=== ¿Sustituye a STATIC_Z? (criterio: t > 2) ===")
    print(compare(res).to_string(index=False))
    kt = res["trades"]["KALMAN_Z"]
    if len(kt) and "sigma_eta" in kt:
        print(f"\nKalman: sigma_eta MLE mediana {kt['sigma_eta'].median():.2e} "
              f"(límite inferior 1e-8 = beta constante)")
    km = res["trades"]["KALMAN_Z_MLE"]
    if len(km):
        print(f"Kalman MLE conjunta: desv. típica de z en la formación, mediana "
              f"{km['z_std_formation'].median():.2f} (1 = modelo bien especificado)")
    years = {}
    for name in d:
        years[name] = d[name].groupby(d.index.year).apply(lambda r: (1 + r).prod() - 1)
    print("\n=== Retorno por año ===")
    print(pd.DataFrame(years).to_string())
    # Diagnóstico: el mismo walk-forward sin costes ni préstamo, para separar
    # si falta ventaja bruta o si son los costes los que la eliminan.
    global COST_PER_SIDE, BORROW_ANNUAL
    saved = COST_PER_SIDE, BORROW_ANNUAL
    COST_PER_SIDE, BORROW_ANNUAL = 0.0, 0.0
    gross = summary(walk_forward(prices))[["estrategia", "ret_anual", "sharpe", "sharpe_ic90_lo", "sharpe_ic90_hi"]]
    COST_PER_SIDE, BORROW_ANNUAL = saved
    print("\n=== Diagnóstico: BRUTO (sin costes ni préstamo) ===")
    print(gross.to_string(index=False))
    os.makedirs(DATA_DIR, exist_ok=True)
    d.to_csv(OUTPUT_CSV)
    print(f"\nGuardado: {OUTPUT_CSV}")
    return res


if __name__ == "__main__":
    main()
