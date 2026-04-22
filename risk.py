"""
risk.py — Minimal execution protection.

Three controls only:
  1. Max position size (% of account balance → number of units to buy)
  2. Optional stop-loss  (% adverse move triggers a market exit)
  3. Optional take-profit (% favorable move triggers a market exit)

No pipelines. No rate limiting. No exposure tracking. No circuit breakers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from broker.base import Position


@dataclass
class RiskManager:
    max_position_pct: float          # e.g. 5.0 → max 5% of balance per trade
    stop_loss_pct: Optional[float]   # e.g. 2.0 → exit at 2% adverse move; None = disabled
    take_profit_pct: Optional[float] # e.g. 4.0 → exit at 4% favorable move; None = disabled

    def position_qty(self, balance: float, price: float) -> float:
        """Return how many units to buy, based on max position size."""
        if price <= 0:
            return 0.0
        max_notional = balance * (self.max_position_pct / 100.0)
        return round(max_notional / price, 6)

    def stop_loss_price(self, entry_price: float, side: str) -> Optional[float]:
        """Return the stop-loss trigger price, or None if stop-loss is disabled."""
        if self.stop_loss_pct is None:
            return None
        pct = self.stop_loss_pct / 100.0
        return entry_price * (1.0 - pct) if side == "buy" else entry_price * (1.0 + pct)

    def take_profit_price(self, entry_price: float, side: str) -> Optional[float]:
        """Return the take-profit trigger price, or None if take-profit is disabled."""
        if self.take_profit_pct is None:
            return None
        pct = self.take_profit_pct / 100.0
        return entry_price * (1.0 + pct) if side == "buy" else entry_price * (1.0 - pct)

    def should_stop_loss(self, position: Position, current_price: float) -> bool:
        """True if current price has breached the stop-loss threshold."""
        if position.stop_loss is None:
            return False
        if position.side == "buy":
            return current_price <= position.stop_loss
        return current_price >= position.stop_loss

    def should_take_profit(self, position: Position, current_price: float) -> bool:
        """True if current price has reached the take-profit threshold."""
        if position.take_profit is None:
            return False
        if position.side == "buy":
            return current_price >= position.take_profit
        return current_price <= position.take_profit
