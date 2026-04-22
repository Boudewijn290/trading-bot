# DOCS.md — Strategy Execution Engine

A simple, synchronous trading engine. One strategy, one symbol, one loop. Runs 24/7 on paper or live.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [How It Works](#how-it-works)
3. [Configuration](#configuration)
4. [Writing a Strategy](#writing-a-strategy)
5. [Available Indicators](#available-indicators)
6. [Risk Controls](#risk-controls)
7. [Broker Setup (Alpaca)](#broker-setup-alpaca)
8. [Switching Paper to Live](#switching-paper-to-live)
9. [Reading the Output](#reading-the-output)
10. [File Reference](#file-reference)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create your .env file
cp .env.example .env
# Fill in ALPACA_API_KEY and ALPACA_SECRET_KEY

# 3. Run in paper mode (default)
python main.py --strategy strategies/example_strategy.py
```

That's it. Press `Ctrl-C` to stop. A final report and equity chart are saved to `runs/`.

---

## How It Works

The runner is a single `while True` loop:

```
loop forever:
    fetch latest closed bars from broker
    check stop-loss / take-profit on open position
    if new bar has closed:
        call strategy.generate_signal(bars)
        if signal == "buy"  and no position → place buy order
        if signal == "sell" and have position → place sell order
    sleep POLL_INTERVAL_SECONDS
```

Key properties:
- **Only closed bars are passed to the strategy.** The current (open) bar is always dropped before calling `generate_signal()`.
- **Signals are evaluated once per bar.** If the poll interval is 60s and the timeframe is 1Hour, the strategy runs once per hour.
- **Stop-loss and take-profit check on every poll.** They use the close price of the last completed bar, not a live tick.
- **No auto-close on shutdown.** If you stop the runner with an open position, it is left open. A warning is printed. Close it manually.

---

## Configuration

All configuration is via environment variables (or a `.env` file in the project root). An optional `config.json` can set defaults; env vars always override it.

| Variable | Default | Description |
|---|---|---|
| `ALPACA_API_KEY` | *required* | Alpaca API key |
| `ALPACA_SECRET_KEY` | *required* | Alpaca secret key |
| `MODE` | `paper` | `paper` or `live` |
| `SYMBOL` | `AAPL` | Ticker symbol (e.g. `AAPL`, `BTCUSD`) |
| `ASSET_CLASS` | `us_equity` | `us_equity` or `crypto` |
| `TIMEFRAME` | `1Hour` | Bar size: `1Min` `5Min` `15Min` `30Min` `1Hour` `4Hour` `1Day` |
| `BAR_LIMIT` | `200` | Bars fetched per cycle (must cover indicator warm-up period) |
| `POLL_INTERVAL_SECONDS` | `60` | How often the loop runs (in seconds) |
| `MAX_POSITION_PCT` | `5.0` | Max % of account equity per trade |
| `STOP_LOSS_PCT` | *(off)* | e.g. `2.0` → stop at 2% adverse move |
| `TAKE_PROFIT_PCT` | *(off)* | e.g. `4.0` → exit at 4% favorable move |
| `RUNS_DIR` | `runs` | Directory for trade log CSV and equity chart |

**Recommended poll intervals by timeframe:**

| Timeframe | Poll interval |
|---|---|
| `1Min` | 15–30s |
| `5Min` | 60s |
| `15Min` | 120s |
| `1Hour` | 60–300s |
| `1Day` | 1800–3600s |

**Using a config.json** (optional):

```json
{
  "symbol": "AAPL",
  "timeframe": "1Hour",
  "max_position_pct": 5.0,
  "stop_loss_pct": 2.0,
  "take_profit_pct": 6.0
}
```

Pass it with `--config config.json`. Credentials should stay in `.env`, not the JSON file.

---

## Writing a Strategy

Create a file in `strategies/`. It must define exactly one function:

```python
def generate_signal(bars: pd.DataFrame) -> str | None:
    ...
```

### The `bars` DataFrame

| Property | Value |
|---|---|
| Columns | `open`, `high`, `low`, `close`, `volume` |
| Index | `DatetimeTzIndex` (UTC), name=`timestamp` |
| Order | Oldest row first (`bars.iloc[0]` = oldest, `bars.iloc[-1]` = most recent) |
| Completeness | All rows are fully closed bars. The current open bar is never included. |

### Return values

| Value | Meaning |
|---|---|
| `"buy"` | Open a long position (ignored if already in a position) |
| `"sell"` | Close the current long position (ignored if flat) |
| `None` | Do nothing |

### Example: RSI strategy

```python
import pandas as pd
from indicators import rsi

RSI_PERIOD = 14
OVERSOLD = 30
OVERBOUGHT = 70


def generate_signal(bars: pd.DataFrame) -> str | None:
    if len(bars) < RSI_PERIOD + 1:
        return None

    closes = bars["close"].tolist()
    current_rsi = rsi(closes, RSI_PERIOD)

    if current_rsi < OVERSOLD:
        return "buy"

    if current_rsi > OVERBOUGHT:
        return "sell"

    return None
```

### Example: EMA crossover

```python
import pandas as pd
from indicators import ema

FAST = 12
SLOW = 26


def generate_signal(bars: pd.DataFrame) -> str | None:
    if len(bars) < SLOW + 1:
        return None

    closes = bars["close"].tolist()

    fast_now  = ema(closes,       FAST)
    fast_prev = ema(closes[:-1],  FAST)
    slow_now  = ema(closes,       SLOW)
    slow_prev = ema(closes[:-1],  SLOW)

    if fast_prev <= slow_prev and fast_now > slow_now:
        return "buy"

    if fast_prev >= slow_prev and fast_now < slow_now:
        return "sell"

    return None
```

### Example: Bollinger Band mean reversion

```python
import pandas as pd
from indicators import bollinger_bands

PERIOD = 20
STD = 2.0


def generate_signal(bars: pd.DataFrame) -> str | None:
    if len(bars) < PERIOD:
        return None

    closes = bars["close"].tolist()
    upper, middle, lower = bollinger_bands(closes, PERIOD, STD)
    close = closes[-1]

    if close < lower:
        return "buy"   # price below lower band

    if close > upper:
        return "sell"  # price above upper band

    return None
```

### Running a strategy

```bash
python main.py --strategy strategies/my_strategy.py
```

With a config file:
```bash
python main.py --strategy strategies/my_strategy.py --config config.json
```

With env var overrides:
```bash
SYMBOL=BTCUSD ASSET_CLASS=crypto TIMEFRAME=1Hour \
  python main.py --strategy strategies/my_strategy.py
```

---

## Available Indicators

All indicators live in [indicators.py](indicators.py). They are pure functions — no state, no side effects.

**Convention:** Input lists are oldest-first. `values[-1]` is the most recent bar.
All functions return `float("nan")` if there is insufficient data for warm-up.

### Trend

```python
sma(values, period) -> float
# Simple Moving Average over the last `period` values.

ema(values, period) -> float
# Exponential Moving Average. Seeded from SMA. k = 2/(period+1).

ema_series(values, period) -> list[float]
# Full EMA series, same length as values. NaN for warm-up bars.
```

### Momentum

```python
rsi(closes, period=14) -> float
# Relative Strength Index (Wilder smoothing). Returns [0, 100].

macd(closes, fast=12, slow=26, signal=9) -> tuple[float, float, float]
# Returns (macd_line, signal_line, histogram). NaN tuple if insufficient data.

stochastic(highs, lows, closes, k_period=14, d_period=3) -> tuple[float, float]
# Returns (%K, %D). Simplified — %D is approximated from current %K.
```

### Volatility

```python
atr(highs, lows, closes, period=14) -> float
# Average True Range (Wilder smoothing). Requires len >= period + 1.

bollinger_bands(closes, period=20, std=2.0) -> tuple[float, float, float]
# Returns (upper, middle, lower). middle = SMA.

realized_vol(closes, period=20) -> float
# Annualized realized volatility assuming daily bars. Returns decimal (0.15 = 15%).
```

### Volume

```python
vwap(closes, volumes) -> float
# Volume-Weighted Average Price over the provided window. NaN if total volume is 0.
```

### Using indicators with the bars DataFrame

```python
closes = bars["close"].tolist()
highs  = bars["high"].tolist()
lows   = bars["low"].tolist()
vols   = bars["volume"].tolist()

current_rsi = rsi(closes, 14)
upper, mid, lower = bollinger_bands(closes, 20, 2.0)
current_atr = atr(highs, lows, closes, 14)
```

---

## Risk Controls

Three controls only. Configure via env vars.

### 1. Max position size

`MAX_POSITION_PCT` (default: `5.0`)

The runner computes position size as:
```
qty = (account_balance * MAX_POSITION_PCT / 100) / current_price
```

Example: balance $50,000, price $200, `MAX_POSITION_PCT=5.0` → qty = 12.5 shares ($2,500 notional).

### 2. Stop-loss

`STOP_LOSS_PCT` (default: off)

If set, the runner checks on every poll whether the price has moved adversely by this percentage from entry. If triggered, it places a market sell immediately.

Example: `STOP_LOSS_PCT=2.0` → if price drops 2% below entry, exit.

Note: stop-loss is polling-based, not a server-side bracket order. It checks the last closed bar's price, so there is a lag of up to `POLL_INTERVAL_SECONDS`.

### 3. Take-profit

`TAKE_PROFIT_PCT` (default: off)

Same mechanism as stop-loss. If price moves favorably by this percentage from entry, exit.

Example: `TAKE_PROFIT_PCT=6.0` → exit when price rises 6% above entry.

---

## Broker Setup (Alpaca)

The system uses Alpaca exclusively. Alpaca supports US equities and crypto with a free paper trading account.

### Getting credentials

1. Sign up at [alpaca.markets](https://alpaca.markets)
2. Go to **Paper Trading** → API Keys → Generate
3. Copy key and secret into your `.env` file:

```
ALPACA_API_KEY=PKxxxxxxxxxxxxxxxx
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Supported assets

| Asset class | `ASSET_CLASS` value | Example symbols |
|---|---|---|
| US stocks / ETFs | `us_equity` | `AAPL`, `TSLA`, `SPY`, `QQQ` |
| Crypto | `crypto` | `BTCUSD`, `ETHUSD`, `SOLUSD` |

For unsupported asset classes (forex, futures, options), the system will raise a `ValueError` at startup.

### How orders are placed

All orders are **market orders**. The runner submits a market order and polls for fill confirmation for up to 15 seconds. If not confirmed within 15 seconds, it logs a warning and continues.

For `us_equity`: `time_in_force = "day"` (order expires end of trading day if unfilled)
For `crypto`: `time_in_force = "gtc"` (good till cancelled — crypto markets are 24/7)

---

## Switching Paper to Live

Change one env var:

```bash
# Paper (default)
MODE=paper python main.py --strategy strategies/my_strategy.py

# Live
MODE=live python main.py --strategy strategies/my_strategy.py
```

The strategy code is **identical** in both modes. The only difference is which Alpaca endpoint is used:
- Paper: `https://paper-api.alpaca.markets`
- Live: `https://api.alpaca.markets`

**Before switching to live:**
- Run the strategy in paper mode long enough to understand its behaviour
- Ensure you understand what positions it will open and how it sizes them
- Set `MAX_POSITION_PCT` conservatively
- Consider setting `STOP_LOSS_PCT` as a safety net

---

## Reading the Output

### While running

Each line printed is one of:

**Status line** (printed every loop iteration):
```
2026-04-21 14:00:05 | AAPL | bar 2026-04-21 13:00 | close 192.34 | no position | signal: —
```

**New bar with signal:**
```
2026-04-21 15:00:08 | AAPL | bar 2026-04-21 14:00 | close 195.10 | no position | signal: buy
2026-04-21 15:00:08 | AAPL | → BUY 5.1235 @ 195.10 | sl 191.20 | tp 207.81
```

**Position open:**
```
2026-04-21 16:00:06 | AAPL | bar 2026-04-21 15:00 | close 197.42 | BUY 5.1235 @ 195.10 | unreal +$11.93 | sl 191.20 | tp 207.81 | signal: —
```

**Trade closed:**
```
2026-04-21 17:00:09 | AAPL | CLOSED BUY 5.1235 | entry 195.10 → exit 201.30 | PnL +$31.77 (signal)
```

### Final report (on Ctrl-C or SIGTERM)

```
══════════════════════════════════════════════════
  FINAL REPORT — 2026-04-21 18:30:00
══════════════════════════════════════════════════
  Trades:       14
  Win rate:     57.1%
  Total PnL:    +$842.10
  Return:       +8.42%
  Max DD:       -4.17%
  Trade log:    runs/trades_20260421_090005.csv
  Chart:        runs/equity_20260421_183000.png
══════════════════════════════════════════════════
```

### Output files

| File | Contents |
|---|---|
| `runs/trades_YYYYMMDD_HHMMSS.csv` | One row per completed trade: symbol, side, qty, entry price, exit price, entry time, exit time, PnL, exit reason |
| `runs/equity_YYYYMMDD_HHMMSS.png` | Equity curve chart (requires matplotlib) |

Exit reason values: `signal`, `stop_loss`, `take_profit`

---

## File Reference

| File | Purpose | Modify for strategies? |
|---|---|---|
| [main.py](main.py) | Runner loop, CLI entry point | No |
| [config.py](config.py) | Config dataclass, env var loading | No |
| [indicators.py](indicators.py) | Pure indicator functions | Add new indicators here |
| [risk.py](risk.py) | Position sizing, SL/TP checks | No |
| [reporting.py](reporting.py) | CSV log, status lines, equity chart | No |
| [broker/base.py](broker/base.py) | Broker interface, Position, Order | No |
| [broker/alpaca.py](broker/alpaca.py) | Alpaca REST implementation | No |
| [broker/paper.py](broker/paper.py) | Paper trading subclass | No |
| [broker/__init__.py](broker/__init__.py) | Broker factory | No |
| [strategies/example_strategy.py](strategies/example_strategy.py) | Template strategy | Copy and modify |
