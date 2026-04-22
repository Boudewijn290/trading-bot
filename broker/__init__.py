"""
broker/__init__.py — Broker factory.

Usage:
    from broker import get_broker
    broker = get_broker(cfg)

Returns an AlpacaBroker pointed at the paper or live endpoint based on cfg.mode.
The strategy code never imports from this module — only main.py calls get_broker().
"""
from __future__ import annotations

from broker.alpaca import AlpacaBroker
from broker.base import Broker

_PAPER_URL = "https://paper-api.alpaca.markets"
_LIVE_URL = "https://api.alpaca.markets"


def get_broker(cfg) -> Broker:
    """
    Create a broker from config. cfg.mode must be "paper" or "live".
    Raises ValueError if mode is unknown or asset_class is unsupported.
    """
    if cfg.mode == "paper":
        base_url = _PAPER_URL
    elif cfg.mode == "live":
        base_url = _LIVE_URL
    else:
        raise ValueError(f"Unknown mode: {cfg.mode!r}. Must be 'paper' or 'live'.")

    return AlpacaBroker(
        api_key=cfg.alpaca_api_key,
        secret_key=cfg.alpaca_secret_key,
        base_url=base_url,
        asset_class=cfg.asset_class,
    )
