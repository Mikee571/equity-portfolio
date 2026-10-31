"""
indicators.py
=============
Indicadores técnicos consistentes con las 9 estrategias ya probadas en el
paper trading lab (6 nativas del MCP tradingview-mcp-server v0.7.0 + 3 custom).

No reimplementamos las estrategias de señal completas aquí (eso ya existe en
custom_strategies.py / el MCP) — extraemos los INDICADORES SUBYACENTES como
features numéricos para el modelo ML. Es una capa distinta: la estrategia 1-9
genera señales discretas (compra/venta), esto genera features continuos.

Fórmulas estándar de industria, mismas que usan TA-Lib / pandas-ta / el MCP.
"""

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI clásico de Wilder."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0):
    """Bandas de Bollinger. Devuelve (mid, upper, lower, %b, bandwidth)."""
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    pct_b = (close - lower) / (upper - lower)
    bandwidth = (upper - lower) / mid
    return mid, upper, lower, pct_b, bandwidth


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD estándar. Devuelve (macd_line, signal_line, histogram)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range — usado por Supertrend y Keltner."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 10, multiplier: float = 3.0):
    """
    Supertrend. Devuelve (supertrend_line, direction) donde direction=1 (alcista)
    o -1 (bajista). Misma lógica que la estrategia nativa del MCP.
    """
    atr_val = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val

    direction = pd.Series(index=close.index, dtype=float)
    st = pd.Series(index=close.index, dtype=float)

    for i in range(len(close)):
        if i == 0 or np.isnan(atr_val.iloc[i]):
            direction.iloc[i] = 1
            st.iloc[i] = lower_band.iloc[i] if not np.isnan(lower_band.iloc[i]) else close.iloc[i]
            continue

        if close.iloc[i] > upper_band.iloc[i - 1] if not np.isnan(upper_band.iloc[i - 1]) else False:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower_band.iloc[i - 1] if not np.isnan(lower_band.iloc[i - 1]) else False:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
            if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i - 1]:
                lower_band.iloc[i] = lower_band.iloc[i - 1]
            if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i - 1]:
                upper_band.iloc[i] = upper_band.iloc[i - 1]

        st.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    return st, direction


def donchian_channel(high: pd.Series, low: pd.Series, period: int = 20):
    """Canal de Donchian. Devuelve (upper, lower, mid)."""
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    mid = (upper + lower) / 2
    return upper, lower, mid


def keltner_channel(high: pd.Series, low: pd.Series, close: pd.Series,
                     ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0):
    """Canal de Keltner — usado por keltner_breakout (estrategia custom #8)."""
    mid = close.ewm(span=ema_period, adjust=False).mean()
    atr_val = atr(high, low, close, atr_period)
    upper = mid + multiplier * atr_val
    lower = mid - multiplier * atr_val
    return mid, upper, lower


def triple_ema_features(close: pd.Series):
    """
    Features para triple_ema (estrategia custom #7):
    EMA20/50 cruce filtrado por SMA200 — evita contra-tendencia.
    """
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    sma200 = close.rolling(200).mean()
    ema_cross_signal = (ema20 - ema50) / close  # normalizado
    trend_filter = (close - sma200) / close  # >0 = por encima de SMA200
    return ema_cross_signal, trend_filter


def rsi_pullback_features(close: pd.Series, rsi_period: int = 14):
    """
    Features para rsi_pullback (estrategia custom #9):
    RSI<40 dentro de tendencia alcista confirmada (SMA50>SMA200).
    """
    rsi_val = rsi(close, rsi_period)
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    uptrend_confirmed = (sma50 > sma200).astype(int)
    pullback_zone = (rsi_val < 40).astype(int)
    return rsi_val, uptrend_confirmed, pullback_zone


def ema_cross_features(close: pd.Series, fast: int = 12, slow: int = 26):
    """Features para ema_cross (estrategia nativa #4 — recordar: 100% win rate
    en solo 3 trades en el backtest real = ruido, no edge confirmado)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    return (ema_fast - ema_slow) / close


def build_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye la matriz completa de features técnicos a partir de un DataFrame
    OHLCV (columnas: Open, High, Low, Close, Volume).

    Cubre las 9 estrategias documentadas en el lab, expresadas como features
    continuos en vez de señales discretas.
    """
    out = pd.DataFrame(index=df.index)
    close, high, low = df["Close"], df["High"], df["Low"]

    # 1. rsi (nativa)
    out["rsi_14"] = rsi(close, 14)

    # 2. bollinger (nativa)
    _, _, _, pct_b, bw = bollinger_bands(close)
    out["bb_pct_b"] = pct_b
    out["bb_bandwidth"] = bw

    # 3. macd (nativa)
    macd_line, signal_line, hist = macd(close)
    out["macd_hist"] = hist / close  # normalizado por precio

    # 4. ema_cross (nativa — edge no confirmado, se incluye como feature de
    #    todas formas; el modelo decide si tiene peso real)
    out["ema_cross_norm"] = ema_cross_features(close)

    # 5. supertrend (nativa)
    _, st_direction = supertrend(high, low, close)
    out["supertrend_direction"] = st_direction

    # 6. donchian (nativa)
    d_upper, d_lower, d_mid = donchian_channel(high, low)
    out["donchian_position"] = (close - d_lower) / (d_upper - d_lower).replace(0, np.nan)

    # 7. triple_ema (custom)
    ema_cross_signal, trend_filter = triple_ema_features(close)
    out["triple_ema_cross"] = ema_cross_signal
    out["triple_ema_trend_filter"] = trend_filter

    # 8. keltner_breakout (custom)
    k_mid, k_upper, k_lower = keltner_channel(high, low, close)
    out["keltner_position"] = (close - k_lower) / (k_upper - k_lower).replace(0, np.nan)

    # 9. rsi_pullback (custom)
    rsi_val, uptrend_confirmed, pullback_zone = rsi_pullback_features(close)
    out["rsi_pullback_uptrend"] = uptrend_confirmed
    out["rsi_pullback_zone"] = pullback_zone

    # Features adicionales de momentum/volatilidad generales
    out["return_1d"] = close.pct_change(1)
    out["return_5d"] = close.pct_change(5)
    out["volatility_10d"] = close.pct_change().rolling(10).std()

    return out
