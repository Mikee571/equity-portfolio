"""
Estrategias custom — no disponibles en tradingview-mcp-server (v0.7.0)
========================================================================
Confirmado por inspección directa del código fuente: el MCP solo implementa
6 estrategias (rsi, bollinger, macd, ema_cross, supertrend, donchian).
Estas 3 estrategias del mapeo original del lab no existen ahí — se
implementan aquí desde cero, con la misma rigurosidad aplicada a Stat Arb:
costes realistas por clase de activo y Sharpe corregido (anualizado por
trades/año real, no por velas/año — ver corrected_sharpe.py).

Estrategias:
  - triple_ema:       EMA20/50 cross filtrado por SMA200 (evita contra-tendencia)
  - keltner_breakout:  Breakout de banda ATR-normalizada (alternativa a Donchian)
  - rsi_pullback:      Dip-buy en uptrend confirmado (SMA50>SMA200 + RSI<40)
"""

import numpy as np
import pandas as pd
import statistics
import math


# ─── Indicadores ────────────────────────────────────────────────────────────

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder estándar."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def calc_keltner(high: pd.Series, low: pd.Series, close: pd.Series,
                  ema_period: int = 20, atr_period: int = 10, mult: float = 2.0) -> dict:
    """Keltner Channels: EMA central +/- multiplo * ATR."""
    mid = close.ewm(span=ema_period, adjust=False).mean()
    atr = calc_atr(high, low, close, atr_period)
    return {"mid": mid, "upper": mid + mult * atr, "lower": mid - mult * atr}


# ─── Estrategia 1: triple_ema ───────────────────────────────────────────────

def triple_ema_position(close: pd.Series, fast: int = 20, slow: int = 50, trend: int = 200) -> pd.Series:
    """
    EMA20/50 cross filtrado por SMA200 — lógica de máquina de estados.

    IMPORTANTE: el filtro de tendencia se evalúa SOLO en el momento del
    cruce de EMA (la entrada), no bar-a-bar. Una primera versión evaluaba
    la condición AND en cada vela, lo cual causaba whipsaws artificiales
    cuando el precio tocaba el SMA200 por ruido de una sola vela sin que
    la tendencia de EMA20/50 hubiera cambiado realmente (verificado: 337
    trades vs 111 del EMA cross simple — 3x más, señal de bug, no de edge).

    Con esta versión: una vez dentro de una posición, se mantiene hasta que
    el cruce de EMA se invierte — el SMA200 solo decide si esa nueva señal
    de cruce se toma o se ignora (se queda plano) en el momento en que ocurre.
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    sma_trend = close.rolling(window=trend).mean()

    ema_bullish = (ema_fast > ema_slow)
    cross_signal = ema_bullish.astype(int).diff().fillna(0)  # +1 = golden cross, -1 = death cross

    closes = close.values
    sma_vals = sma_trend.values
    cross_vals = cross_signal.values

    position = np.zeros(len(close))
    current_pos = 0
    for i in range(len(close)):
        if cross_vals[i] == 1:  # golden cross ocurre ahora
            current_pos = 1 if (not np.isnan(sma_vals[i]) and closes[i] > sma_vals[i]) else 0
        elif cross_vals[i] == -1:  # death cross ocurre ahora
            current_pos = -1 if (not np.isnan(sma_vals[i]) and closes[i] < sma_vals[i]) else 0
        position[i] = current_pos

    position = pd.Series(position, index=close.index)
    return position.shift(1).fillna(0)  # shift evita lookahead


# ─── Estrategia 2: keltner_breakout ─────────────────────────────────────────

def keltner_breakout_position(high: pd.Series, low: pd.Series, close: pd.Series,
                                ema_period: int = 20, atr_period: int = 10, mult: float = 2.0) -> pd.Series:
    """
    Breakout de banda Keltner. Long cuando el precio rompe la banda superior,
    short cuando rompe la inferior, mantiene posición hasta el breakout opuesto
    (igual lógica que Donchian, pero con banda normalizada por volatilidad).
    """
    kc = calc_keltner(high, low, close, ema_period, atr_period, mult)

    raw_signal = pd.Series(np.nan, index=close.index)
    raw_signal[close > kc["upper"]] = 1
    raw_signal[close < kc["lower"]] = -1
    position = raw_signal.ffill().fillna(0)
    return position.shift(1).fillna(0)


# ─── Estrategia 3: rsi_pullback ─────────────────────────────────────────────

def rsi_pullback_position(close: pd.Series, rsi_period: int = 14,
                            entry_rsi: float = 40, exit_rsi: float = 60,
                            trend_fast: int = 50, trend_slow: int = 200) -> pd.Series:
    """
    Dip-buy en uptrend confirmado. Solo LONG (no shortea), pensada para
    timing de entrada en activos con tesis fundamental ya definida (ej. GDX).

    Entra cuando: SMA50>SMA200 (uptrend) Y RSI<entry_rsi (pullback)
    Sale cuando: RSI>exit_rsi (recuperación) O SMA50<SMA200 (se rompe la tendencia)
    Es de tipo "mantener hasta condición de salida", no instantáneo bar-a-bar.
    """
    rsi = calc_rsi(close, rsi_period)
    sma_fast = close.rolling(window=trend_fast).mean()
    sma_slow = close.rolling(window=trend_slow).mean()
    uptrend = sma_fast > sma_slow

    position = pd.Series(0, index=close.index)
    in_position = False
    pos_values = np.zeros(len(close))
    rsi_vals = rsi.values
    uptrend_vals = uptrend.values

    for i in range(len(close)):
        if not in_position:
            if uptrend_vals[i] and rsi_vals[i] < entry_rsi:
                in_position = True
        else:
            if rsi_vals[i] > exit_rsi or not uptrend_vals[i]:
                in_position = False
        pos_values[i] = 1 if in_position else 0

    position = pd.Series(pos_values, index=close.index)
    return position.shift(1).fillna(0)


# ─── Motor de backtest con Sharpe corregido ────────────────────────────────

def backtest_position_series(close: pd.Series, position: pd.Series,
                               commission_pct: float, slippage_pct: float,
                               period_years: float, risk_free_rate: float = 0.04) -> dict:
    """
    Backtest genérico a partir de una serie de posición (-1, 0, 1).
    Calcula trades discretos (no retornos bar-a-bar) y aplica el Sharpe
    CORREGIDO: anualizado por trades/año reales, no por velas/año.

    Coste aplicado: (commission_pct + slippage_pct) * 2, igual convención
    que confirmamos en el código fuente del MCP — aplicado una vez por
    entrada+salida (round trip), no por vela.
    """
    pos_change = position.diff().fillna(position.iloc[0] if len(position) > 0 else 0)
    closes = close.values
    pos_vals = position.values

    trades = []
    entry_idx = None
    entry_side = 0

    for i in range(1, len(pos_vals)):
        if pos_vals[i] != pos_vals[i-1]:
            if entry_idx is not None and entry_side != 0:
                gross = (closes[i] - closes[entry_idx]) / closes[entry_idx] * entry_side * 100
                trades.append({"entry_idx": entry_idx, "exit_idx": i, "gross_return_pct": gross})
            if pos_vals[i] != 0:
                entry_idx = i
                entry_side = pos_vals[i]
            else:
                entry_idx = None
                entry_side = 0

    if entry_idx is not None and entry_side != 0:
        gross = (closes[-1] - closes[entry_idx]) / closes[entry_idx] * entry_side * 100
        trades.append({"entry_idx": entry_idx, "exit_idx": len(closes)-1, "gross_return_pct": gross})

    if not trades:
        return {"n_trades": 0, "total_return_pct": 0, "sharpe_corrected": 0, "win_rate_pct": 0}

    total_cost_pct = (commission_pct + slippage_pct) * 2
    for t in trades:
        t["net_return_pct"] = t["gross_return_pct"] - total_cost_pct

    net_returns = [t["net_return_pct"] for t in trades]
    capital = 1.0
    for r in net_returns:
        capital *= (1 + r/100)
    total_return_pct = (capital - 1) * 100

    n_trades = len(trades)
    wins = sum(1 for r in net_returns if r > 0)
    win_rate_pct = wins / n_trades * 100

    sharpe_corrected = 0.0
    if n_trades > 1:
        returns_frac = [r/100 for r in net_returns]
        mean_r = statistics.mean(returns_frac)
        std_r = statistics.stdev(returns_frac)
        if std_r > 0:
            trades_per_year = n_trades / period_years
            rf_per_trade = risk_free_rate / trades_per_year
            sharpe_corrected = round((mean_r - rf_per_trade) / std_r * math.sqrt(trades_per_year), 2)

    return {
        "n_trades": n_trades,
        "total_return_pct": round(total_return_pct, 2),
        "sharpe_corrected": sharpe_corrected,
        "win_rate_pct": round(win_rate_pct, 1),
        "trades_per_year": round(n_trades / period_years, 1),
    }
