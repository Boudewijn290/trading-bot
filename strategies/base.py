"""
Base strategy class — all strategies inherit from this.

To add a new strategy:
  1. Create a new file in strategies/ (e.g. strategies/trend.py)
  2. Subclass BaseStrategy
  3. Implement enter(), monitor(), and exit()
  4. Register it in run.py
"""
from abc import ABC, abstractmethod
from core.client import DeribitClient


class BaseStrategy(ABC):
    def __init__(self, client: DeribitClient):
        self.client = client

    @abstractmethod
    def enter(self) -> dict:
        """Open a position. Returns a position dict."""
        pass

    @abstractmethod
    def monitor(self, position: dict):
        """Watch an open position and decide when to exit."""
        pass

    @abstractmethod
    def exit(self, position: dict, reason: str):
        """Close the position."""
        pass
