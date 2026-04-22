"""
broker/paper.py — Paper trading broker.

A thin subclass of AlpacaBroker that targets the Alpaca paper trading endpoint.
Uses real market data and realistic order execution semantics.
All logic is inherited — only the base URL differs from live mode.
"""
from __future__ import annotations

from broker.alpaca import AlpacaBroker

_PAPER_URL = "https://paper-api.alpaca.markets"


class PaperBroker(AlpacaBroker):
    def __init__(self, api_key: str, secret_key: str, asset_class: str) -> None:
        super().__init__(
            api_key=api_key,
            secret_key=secret_key,
            base_url=_PAPER_URL,
            asset_class=asset_class,
        )
