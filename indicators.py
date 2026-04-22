"""
indicators.py — Pure indicator functions.

All functions are stateless. They receive a list of prices (most recent LAST)
and return a single float or tuple of floats.

Convention: values[0] = oldest, values[-1] = most recent (current bar close).
No side effects. No logging. No I/O.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import List, Tuple, Union

Number = Union[float, Decimal]


def _to_float(values: List[Number]) -> List[float]:
    return [float(v) for v in values]


# ── Trend ─────────────────────────────────────────────────────────────────────

def sma(values: List[Number], period: int) -> float:
    """Simple Moving Average over the last `period` values."""
    if len(values) < period:
        return float("nan")
    data = _to_float(values[-period:])
    return sum(data) / period


def ema(values: List[Number], period: int) -> float:
    """
    Exponential Moving Average.
    Uses standard smoothing: k = 2 / (period + 1).
    Seeded from SMA of first `period` values.
    """
    if len(values) < period:
        return float("nan")
    data = _to_float(values)
    k = 2.0 / (period + 1)
    result = sum(data[:period]) / period  # seed from SMA
    for price in data[period:]:
        result = price * k + result * (1 - k)
    return result


def ema_series(values: List[Number], period: int) -> List[float]:
    """Return the full EMA series (same length as values, nan for warm-up)."""
    if len(values) < period:
        return [float("nan")] * len(values)
    data = _to_float(values)
    k = 2.0 / (period + 1)
    result: List[float] = [float("nan")] * (period - 1)
    current = sum(data[:period]) / period
    result.append(current)
    for price in data[period:]:
        current = price * k + current * (1 - k)
        result.append(current)
    return result


# ── Momentum ──────────────────────────────────────────────────────────────────

def rsi(closes: List[Number], period: int = 14) -> float:
    """
    Relative Strength Index (Wilder smoothing).
    Returns value in [0, 100].
    """
    if len(closes) < period + 1:
        return float("nan")
    data = _to_float(closes)
    gains = []
    losses = []
    for i in range(1, len(data)):
        delta = data[i] - data[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    closes: List[Number],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[float, float, float]:
    """
    MACD line, signal line, histogram.
    Returns (macd_line, signal_line, histogram).
    Returns (nan, nan, nan) if insufficient data.
    """
    if len(closes) < slow + signal:
        nan = float("nan")
        return nan, nan, nan
    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    macd_line = [
        f - s if not (math.isnan(f) or math.isnan(s)) else float("nan")
        for f, s in zip(fast_ema, slow_ema)
    ]
    valid_macd = [v for v in macd_line if not math.isnan(v)]
    if len(valid_macd) < signal:
        nan = float("nan")
        return nan, nan, nan
    signal_line = ema(valid_macd, signal)
    last_macd = macd_line[-1]
    if math.isnan(last_macd) or math.isnan(signal_line):
        nan = float("nan")
        return nan, nan, nan
    histogram = last_macd - signal_line
    return last_macd, signal_line, histogram


def stochastic(
    highs: List[Number],
    lows: List[Number],
    closes: List[Number],
    k_period: int = 14,
    d_period: int = 3,
) -> Tuple[float, float]:
    """Stochastic oscillator. Returns (%K, %D)."""
    if len(closes) < k_period:
        return float("nan"), float("nan")
    h = _to_float(highs[-k_period:])
    lo = _to_float(lows[-k_period:])
    c = float(closes[-1])
    highest = max(h)
    lowest = min(lo)
    if highest == lowest:
        k = 100.0
    else:
        k = (c - lowest) / (highest - lowest) * 100.0
    d = k  # simplified; full %D requires K history
    return k, d


# ── Volatility ────────────────────────────────────────────────────────────────

def atr(
    highs: List[Number],
    lows: List[Number],
    closes: List[Number],
    period: int = 14,
) -> float:
    """Average True Range (Wilder smoothing). Requires len >= period + 1."""
    if len(closes) < period + 1:
        return float("nan")
    h = _to_float(highs)
    lo = _to_float(lows)
    c = _to_float(closes)

    trs = []
    for i in range(1, len(c)):
        tr = max(
            h[i] - lo[i],
            abs(h[i] - c[i - 1]),
            abs(lo[i] - c[i - 1]),
        )
        trs.append(tr)

    if len(trs) < period:
        return float("nan")

    result = sum(trs[:period]) / period
    for tr in trs[period:]:
        result = (result * (period - 1) + tr) / period
    return result


def bollinger_bands(
    closes: List[Number],
    period: int = 20,
    std: float = 2.0,
) -> Tuple[float, float, float]:
    """
    Bollinger Bands. Returns (upper, middle, lower).
    middle = SMA, upper/lower = middle ± std * stdev.
    """
    if len(closes) < period:
        nan = float("nan")
        return nan, nan, nan
    data = _to_float(closes[-period:])
    middle = sum(data) / period
    variance = sum((x - middle) ** 2 for x in data) / period
    stddev = math.sqrt(variance)
    upper = middle + std * stddev
    lower = middle - std * stddev
    return upper, middle, lower


def vwap(closes: List[Number], volumes: List[Number]) -> float:
    """Volume-Weighted Average Price. Returns nan if total volume is 0."""
    if not closes or not volumes or len(closes) != len(volumes):
        return float("nan")
    c = _to_float(closes)
    v = _to_float(volumes)
    total_vol = sum(v)
    if total_vol == 0:
        return float("nan")
    return sum(price * vol for price, vol in zip(c, v)) / total_vol


def realized_vol(closes: List[Number], period: int = 20) -> float:
    """
    Annualized realized volatility (log returns, daily bars assumed).
    Returns a decimal (0.15 = 15% annualized vol).
    """
    if len(closes) < period + 1:
        return float("nan")
    data = _to_float(closes[-(period + 1):])
    log_rets = [math.log(data[i] / data[i - 1]) for i in range(1, len(data))]
    mean = sum(log_rets) / len(log_rets)
    variance = sum((r - mean) ** 2 for r in log_rets) / len(log_rets)
    daily_vol = math.sqrt(variance)
    return daily_vol * math.sqrt(252)
