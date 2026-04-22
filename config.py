"""
config.py — System configuration.

Loaded from environment variables (or .env file), with optional config.json
as a base. Environment variables always take precedence over JSON values.

Required:
    ALPACA_API_KEY, ALPACA_SECRET_KEY

Optional (with defaults):
    MODE, SYMBOL, ASSET_CLASS, TIMEFRAME, BAR_LIMIT,
    POLL_INTERVAL_SECONDS, MAX_POSITION_PCT,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT, RUNS_DIR
"""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_VALID_MODES = {"paper", "live"}
_VALID_ASSET_CLASSES = {"us_equity", "crypto"}
_VALID_TIMEFRAMES = {"1Min", "5Min", "15Min", "30Min", "1Hour", "4Hour", "1Day"}


@dataclass
class Config:
    # Broker
    mode: str = "paper"                  # "paper" | "live"
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""

    # Market
    symbol: str = "AAPL"
    asset_class: str = "us_equity"       # "us_equity" | "crypto"
    timeframe: str = "1Hour"             # Alpaca format: 1Min, 5Min, 15Min, 30Min, 1Hour, 4Hour, 1Day
    bar_limit: int = 200
    poll_interval_seconds: int = 60

    # Risk
    max_position_pct: float = 5.0
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

    # Output
    runs_dir: str = "runs"


def load_config(json_path: Optional[str] = "config.json") -> Config:
    """
    Build a Config from environment variables, optionally seeded from a JSON file.
    Environment variables always override JSON values.
    Raises ValueError with a clear message if required fields are missing or invalid.
    """
    from dotenv import load_dotenv
    load_dotenv()

    # Start from JSON defaults if file exists
    data: dict = {}
    if json_path and Path(json_path).exists():
        with open(json_path) as f:
            data = json.load(f)

    # Overlay with environment variables
    _apply_env(data, "MODE", "mode", str)
    _apply_env(data, "ALPACA_API_KEY", "alpaca_api_key", str)
    _apply_env(data, "ALPACA_SECRET_KEY", "alpaca_secret_key", str)
    _apply_env(data, "SYMBOL", "symbol", str)
    _apply_env(data, "ASSET_CLASS", "asset_class", str)
    _apply_env(data, "TIMEFRAME", "timeframe", str)
    _apply_env(data, "BAR_LIMIT", "bar_limit", int)
    _apply_env(data, "POLL_INTERVAL_SECONDS", "poll_interval_seconds", int)
    _apply_env(data, "MAX_POSITION_PCT", "max_position_pct", float)
    _apply_env(data, "STOP_LOSS_PCT", "stop_loss_pct", float, nullable=True)
    _apply_env(data, "TAKE_PROFIT_PCT", "take_profit_pct", float, nullable=True)
    _apply_env(data, "RUNS_DIR", "runs_dir", str)

    # Only pass recognised fields to Config
    valid_fields = {f.name for f in dataclasses.fields(Config)}
    cfg = Config(**{k: v for k, v in data.items() if k in valid_fields})

    # Validate
    if not cfg.alpaca_api_key:
        raise ValueError("ALPACA_API_KEY is required — set it in .env or environment")
    if not cfg.alpaca_secret_key:
        raise ValueError("ALPACA_SECRET_KEY is required — set it in .env or environment")
    if cfg.mode not in _VALID_MODES:
        raise ValueError(f"MODE must be one of {_VALID_MODES}, got: {cfg.mode!r}")
    if cfg.asset_class not in _VALID_ASSET_CLASSES:
        raise ValueError(
            f"ASSET_CLASS must be one of {_VALID_ASSET_CLASSES}, got: {cfg.asset_class!r}"
        )
    if cfg.timeframe not in _VALID_TIMEFRAMES:
        raise ValueError(
            f"TIMEFRAME must be one of {_VALID_TIMEFRAMES}, got: {cfg.timeframe!r}"
        )

    return cfg


def _apply_env(
    data: dict,
    env_key: str,
    field: str,
    cast: type,
    nullable: bool = False,
) -> None:
    val = os.environ.get(env_key)
    if val is None:
        return
    if nullable and val.strip().lower() in ("", "none", "null"):
        data[field] = None
    else:
        data[field] = cast(val)
