"""
Example strategy: SMA crossover.

Entry:  fast SMA crosses above slow SMA  →  "buy"
Exit:   fast SMA crosses below slow SMA  →  "sell"
Hold:   no crossover                     →  None

Tune FAST_PERIOD and SLOW_PERIOD to change sensitivity.
Requires at least SLOW_PERIOD + 1 bars to produce a signal.

To test this file directly (no broker needed):
    python strategies/example_strategy.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

# Allow importing indicators when running this file directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators import sma

FAST_PERIOD = 10
SLOW_PERIOD = 30


def generate_signal(bars: pd.DataFrame) -> str | None:
    """
    Parameters
    ----------
    bars : pd.DataFrame
        OHLCV DataFrame with columns: open, high, low, close, volume
        Index: DatetimeTzIndex (UTC), oldest row first, all bars fully closed.

    Returns
    -------
    "buy"  — open a long position
    "sell" — close the current long position
    None   — do nothing
    """
    if len(bars) < SLOW_PERIOD + 1:
        return None  # not enough bars to warm up both SMAs

    closes = bars["close"].tolist()

    fast_now  = sma(closes,       FAST_PERIOD)
    fast_prev = sma(closes[:-1],  FAST_PERIOD)
    slow_now  = sma(closes,       SLOW_PERIOD)
    slow_prev = sma(closes[:-1],  SLOW_PERIOD)

    if fast_prev <= slow_prev and fast_now > slow_now:
        return "buy"   # golden cross: fast crosses above slow

    if fast_prev >= slow_prev and fast_now < slow_now:
        return "sell"  # death cross: fast crosses below slow

    return None


# ── Quick self-test (run: python strategies/example_strategy.py) ──────────────
if __name__ == "__main__":
    # High plateau (20) → dip (10) → sharp rally (5)
    # At bar 34: fast SMA (avg of 5×90 + 5×130 = 110) crosses above
    # slow SMA (avg of 15×110 + 10×90 + 5×130 ≈ 106.7) → golden cross → "buy"
    closes = [110.0] * 20 + [90.0] * 10 + [130.0] * 5  # 35 bars
    index = pd.date_range("2026-01-01", periods=len(closes), freq="D", tz="UTC")
    bars = pd.DataFrame(
        {"open": closes, "high": [c + 1 for c in closes],
         "low": [c - 1 for c in closes], "close": closes,
         "volume": [1000] * len(closes)},
        index=index,
    )
    result = generate_signal(bars)
    print(f"Signal on flat-then-rally data: {result!r}  (expected: 'buy')")
    assert result == "buy", f"Expected 'buy', got {result!r}"
    print("Self-test passed.")
