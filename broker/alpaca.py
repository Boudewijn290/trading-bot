"""
broker/alpaca.py — Alpaca REST broker adapter.

Works for both paper and live trading. The only difference is the base_url:
  paper: "https://paper-api.alpaca.markets"
  live:  "https://api.alpaca.markets"

Market data always comes from https://data.alpaca.markets (same for both modes).

Supported asset classes:
  "us_equity" → GET /v2/stocks/{symbol}/bars
  "crypto"    → GET /v1beta3/crypto/us/bars?symbols={symbol}

If the asset class is not supported, raises ValueError at init.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pandas as pd
import requests

from broker.base import Broker, Order, Position

log = logging.getLogger(__name__)

_DATA_URL = "https://data.alpaca.markets"

# Duration in seconds per timeframe — used to detect an incomplete (open) bar
_TIMEFRAME_SECONDS: dict = {
    "1Min": 60,
    "5Min": 300,
    "15Min": 900,
    "30Min": 1800,
    "1Hour": 3600,
    "4Hour": 14400,
    "1Day": 86400,
}

_SUPPORTED_ASSET_CLASSES = {"us_equity", "crypto"}


class AlpacaBroker(Broker):
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str,
        asset_class: str,
    ) -> None:
        if asset_class not in _SUPPORTED_ASSET_CLASSES:
            raise ValueError(
                f"asset_class {asset_class!r} is not supported by Alpaca. "
                f"Supported: {_SUPPORTED_ASSET_CLASSES}"
            )
        self._trading_url = base_url.rstrip("/")
        self._asset_class = asset_class
        self._session = requests.Session()
        self._session.headers.update(
            {
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key,
            }
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def get_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """
        Fetch up to `limit` fully-closed bars.
        Drops the current (incomplete) bar if its period has not yet elapsed.
        Returns an empty DataFrame if the API returns no data.
        """
        if timeframe not in _TIMEFRAME_SECONDS:
            raise ValueError(
                f"Unsupported timeframe: {timeframe!r}. "
                f"Valid values: {sorted(_TIMEFRAME_SECONDS)}"
            )

        if self._asset_class == "us_equity":
            bars = self._fetch_stock_bars(symbol, timeframe, limit)
        else:
            bars = self._fetch_crypto_bars(symbol, timeframe, limit)

        if bars.empty:
            return bars

        # Drop the last bar if it is still open
        dur = timedelta(seconds=_TIMEFRAME_SECONDS[timeframe])
        now = datetime.now(timezone.utc)
        if not bars.empty and bars.index[-1] + dur > now:
            bars = bars.iloc[:-1]

        return bars

    def place_order(self, symbol: str, side: str, qty: float) -> Order:
        """Submit a market order and wait up to 15 seconds for a fill."""
        tif = "gtc" if self._asset_class == "crypto" else "day"
        resp = self._session.post(
            f"{self._trading_url}/v2/orders",
            json={
                "symbol": symbol,
                "qty": str(round(qty, 6)),
                "side": side,
                "type": "market",
                "time_in_force": tif,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        order_id = data["id"]
        log.info(f"Order submitted: {side} {qty} {symbol} (id={order_id})")

        filled_price = self._wait_for_fill(order_id)
        return Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            filled_price=filled_price,
            timestamp=datetime.now(timezone.utc),
        )

    def get_position(self, symbol: str) -> Optional[Position]:
        """Return the open position for symbol, or None if flat."""
        resp = self._session.get(
            f"{self._trading_url}/v2/positions/{symbol}",
            timeout=30,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return Position(
            symbol=symbol,
            side="buy" if data["side"] == "long" else "sell",
            qty=float(data["qty"]),
            entry_price=float(data["avg_entry_price"]),
            stop_loss=None,    # SL/TP are managed locally in the runner
            take_profit=None,
            entry_time=datetime.now(timezone.utc),
        )

    def get_balance(self) -> float:
        """Return current account equity in USD."""
        resp = self._session.get(f"{self._trading_url}/v2/account", timeout=30)
        resp.raise_for_status()
        return float(resp.json()["equity"])

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch_stock_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pd.DataFrame:
        resp = self._session.get(
            f"{_DATA_URL}/v2/stocks/{symbol}/bars",
            params={
                "timeframe": timeframe,
                "limit": limit,
                "adjustment": "raw",
                "feed": "iex",
                "sort": "asc",
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("bars", [])
        return _parse_bars(raw)

    def _fetch_crypto_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pd.DataFrame:
        resp = self._session.get(
            f"{_DATA_URL}/v1beta3/crypto/us/bars",
            params={
                "symbols": symbol,
                "timeframe": timeframe,
                "limit": limit,
                "sort": "asc",
            },
            timeout=30,
        )
        resp.raise_for_status()
        bars_by_symbol = resp.json().get("bars", {})
        raw = bars_by_symbol.get(symbol, [])
        return _parse_bars(raw)

    def _wait_for_fill(self, order_id: str, timeout: int = 15) -> Optional[float]:
        """Poll the order endpoint until filled or timeout (seconds)."""
        for _ in range(timeout):
            time.sleep(1)
            resp = self._session.get(
                f"{self._trading_url}/v2/orders/{order_id}",
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "filled":
                return float(data["filled_avg_price"])
            if status in ("canceled", "expired", "rejected"):
                log.warning(f"Order {order_id} ended with status: {status!r}")
                return None
        log.warning(f"Order {order_id} not filled within {timeout}s")
        return None


def _parse_bars(raw: List[dict]) -> pd.DataFrame:
    """Convert raw Alpaca bar dicts into an OHLCV DataFrame with UTC DatetimeIndex."""
    if not raw:
        return pd.DataFrame()
    records = [
        {
            "timestamp": pd.Timestamp(b["t"]).tz_convert("UTC"),
            "open": float(b["o"]),
            "high": float(b["h"]),
            "low": float(b["l"]),
            "close": float(b["c"]),
            "volume": float(b["v"]),
        }
        for b in raw
    ]
    df = pd.DataFrame(records).set_index("timestamp")
    df.index.name = "timestamp"
    return df
