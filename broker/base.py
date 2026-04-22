"""
broker/base.py — Minimal broker interface.

Defines the Broker ABC and simple data containers for Position and Order.
No framework, no event bus, no async. Just the types the runner needs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd


@dataclass
class Position:
    symbol: str
    side: str             # "buy" or "sell"
    qty: float
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    entry_time: datetime


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str             # "buy" or "sell"
    qty: float
    filled_price: Optional[float]
    timestamp: datetime


class Broker(ABC):
    @abstractmethod
    def place_order(self, symbol: str, side: str, qty: float) -> Order:
        """Place a market order. Returns the Order (filled_price may be None if not yet filled)."""

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """Return the current open position for symbol, or None if flat."""

    @abstractmethod
    def get_balance(self) -> float:
        """Return current account equity in USD."""

    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """
        Return a DataFrame of fully-closed OHLCV bars, oldest-first.

        Columns: open, high, low, close, volume
        Index:   DatetimeTzIndex (UTC), name="timestamp"

        The current (incomplete) bar is always dropped before returning.
        """
