"""
main.py — Strategy execution runner.

Runs one strategy on one symbol continuously using a simple polling loop:
  1. Fetch latest fully-closed bars from broker
  2. Check stop-loss / take-profit on current position
  3. Evaluate strategy signal on new bar close
  4. Place order if signal requires it
  5. Sleep until next poll

Usage:
    python main.py --strategy strategies/example_strategy.py
    python main.py --strategy strategies/my_strategy.py --config config.json

Key environment variables (or .env file):
    ALPACA_API_KEY          required
    ALPACA_SECRET_KEY       required
    MODE                    paper (default) | live
    SYMBOL                  e.g. AAPL (default)
    ASSET_CLASS             us_equity (default) | crypto
    TIMEFRAME               1Min | 5Min | 15Min | 30Min | 1Hour (default) | 4Hour | 1Day
    POLL_INTERVAL_SECONDS   seconds between bar checks (default: 60)
    BAR_LIMIT               bars fetched per cycle for indicator warmup (default: 200)
    MAX_POSITION_PCT        % of equity per trade (default: 5.0)
    STOP_LOSS_PCT           e.g. 2.0 — stop at 2% adverse move (default: off)
    TAKE_PROFIT_PCT         e.g. 4.0 — exit at 4% favorable move (default: off)
    RUNS_DIR                output directory for CSV log and chart (default: runs)
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from broker import get_broker
from broker.base import Position
from config import load_config
from reporting import Reporter, TradeRecord
from risk import RiskManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def load_strategy(path: str):
    """Load a strategy module from a .py file. Must expose generate_signal()."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Strategy not found: {path!r}")
    spec = importlib.util.spec_from_file_location("strategy", p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "generate_signal"):
        raise AttributeError(
            f"{path!r} must define: generate_signal(bars: pd.DataFrame) -> str | None"
        )
    return module


def run(strategy_path: str, config_path: Optional[str]) -> None:
    cfg = load_config(config_path)
    strategy = load_strategy(strategy_path)
    broker = get_broker(cfg)
    risk = RiskManager(cfg.max_position_pct, cfg.stop_loss_pct, cfg.take_profit_pct)

    initial_balance = broker.get_balance()
    reporter = Reporter(cfg.runs_dir, cfg.symbol, initial_balance)
    _print_header(cfg, Path(strategy_path).name, initial_balance)

    # Graceful shutdown on Ctrl-C or SIGTERM
    _shutdown = {"flag": False}

    def _handle_signal(sig, frame):
        print("\n[Shutting down — finishing current loop iteration...]")
        _shutdown["flag"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Restore position state from broker on startup (e.g. after a restart)
    current_position: Optional[Position] = None
    try:
        existing = broker.get_position(cfg.symbol)
        if existing is not None:
            log.warning(
                f"Existing position detected: {existing.side} {existing.qty} {cfg.symbol} "
                f"@ {existing.entry_price:.4f} — stop-loss and take-profit are NOT active "
                f"(position was opened in a previous session)"
            )
            current_position = existing
    except Exception as exc:
        log.warning(f"Could not check for existing position: {exc}")

    last_bar_ts = None

    while not _shutdown["flag"]:
        try:
            # ── Fetch bars (one call per iteration) ──────────────────────────
            bars = broker.get_bars(cfg.symbol, cfg.timeframe, limit=cfg.bar_limit)
            if bars.empty:
                log.warning("No bars returned — retrying in next cycle...")
                time.sleep(cfg.poll_interval_seconds)
                continue

            close = float(bars["close"].iloc[-1])
            latest_bar_ts = bars.index[-1]
            new_bar = latest_bar_ts != last_bar_ts

            # ── SL/TP check (runs every iteration using last closed bar price) ──
            exit_reason: Optional[str] = None
            if current_position is not None:
                if risk.should_stop_loss(current_position, close):
                    exit_reason = "stop_loss"
                elif risk.should_take_profit(current_position, close):
                    exit_reason = "take_profit"

            if exit_reason is not None:
                order = broker.place_order(cfg.symbol, "sell", current_position.qty)
                filled = order.filled_price or close
                pnl = (filled - current_position.entry_price) * current_position.qty
                reporter.log_trade(
                    TradeRecord(
                        symbol=cfg.symbol,
                        side=current_position.side,
                        qty=current_position.qty,
                        entry_price=current_position.entry_price,
                        exit_price=filled,
                        entry_time=current_position.entry_time,
                        exit_time=datetime.now(timezone.utc),
                        pnl=pnl,
                        exit_reason=exit_reason,
                    ),
                    broker.get_balance(),
                )
                current_position = None
                time.sleep(cfg.poll_interval_seconds)
                continue

            # ── Strategy evaluation (only when a new bar has closed) ──────────
            signal_val: Optional[str] = None
            if new_bar:
                last_bar_ts = latest_bar_ts
                signal_val = strategy.generate_signal(bars)

            reporter.log_bar(latest_bar_ts, close, current_position, signal_val)

            # ── Execute signal ─────────────────────────────────────────────────
            if signal_val == "buy" and current_position is None:
                balance = broker.get_balance()
                qty = risk.position_qty(balance, close)
                if qty > 0:
                    order = broker.place_order(cfg.symbol, "buy", qty)
                    filled = order.filled_price or close
                    sl = risk.stop_loss_price(filled, "buy")
                    tp = risk.take_profit_price(filled, "buy")
                    current_position = Position(
                        symbol=cfg.symbol,
                        side="buy",
                        qty=qty,
                        entry_price=filled,
                        stop_loss=sl,
                        take_profit=tp,
                        entry_time=datetime.now(timezone.utc),
                    )
                    sl_str = f" | sl {sl:.4f}" if sl else ""
                    tp_str = f" | tp {tp:.4f}" if tp else ""
                    print(
                        f"{_now()} | {cfg.symbol} | "
                        f"→ BUY {qty:.4f} @ {filled:.4f}{sl_str}{tp_str}"
                    )
                else:
                    log.warning(
                        "Computed position qty is 0 — check MAX_POSITION_PCT and account balance"
                    )

            elif signal_val == "sell" and current_position is not None:
                order = broker.place_order(cfg.symbol, "sell", current_position.qty)
                filled = order.filled_price or close
                pnl = (filled - current_position.entry_price) * current_position.qty
                reporter.log_trade(
                    TradeRecord(
                        symbol=cfg.symbol,
                        side=current_position.side,
                        qty=current_position.qty,
                        entry_price=current_position.entry_price,
                        exit_price=filled,
                        entry_time=current_position.entry_time,
                        exit_time=datetime.now(timezone.utc),
                        pnl=pnl,
                        exit_reason="signal",
                    ),
                    broker.get_balance(),
                )
                current_position = None

            time.sleep(cfg.poll_interval_seconds)

        except KeyboardInterrupt:
            _shutdown["flag"] = True
        except Exception as exc:
            log.error(f"Loop error: {exc}", exc_info=True)
            time.sleep(cfg.poll_interval_seconds)

    # ── Shutdown ───────────────────────────────────────────────────────────────
    if current_position is not None:
        log.warning(
            f"Shutting down with open position: "
            f"{current_position.side} {current_position.qty} {cfg.symbol} "
            f"@ {current_position.entry_price:.4f}"
        )
        log.warning("Position was NOT auto-closed. Close it manually if needed.")

    reporter.print_final_report(broker.get_balance())


def _print_header(cfg, strategy_name: str, balance: float) -> None:
    sep = "═" * 50
    print(f"\n{sep}")
    print(f"  Strategy:    {strategy_name}")
    print(f"  Symbol:      {cfg.symbol} ({cfg.asset_class})")
    print(f"  Timeframe:   {cfg.timeframe}")
    print(f"  Mode:        {cfg.mode.upper()}")
    print(f"  Balance:     ${balance:,.2f}")
    sl_str = f"{cfg.stop_loss_pct}%" if cfg.stop_loss_pct else "off"
    tp_str = f"{cfg.take_profit_pct}%" if cfg.take_profit_pct else "off"
    print(f"  Stop-loss:   {sl_str}    Take-profit: {tp_str}")
    print(f"  Max pos:     {cfg.max_position_pct}% of equity")
    print(f"  Poll:        every {cfg.poll_interval_seconds}s")
    print(f"{sep}\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy execution runner")
    parser.add_argument(
        "--strategy", required=True, help="Path to strategy .py file"
    )
    parser.add_argument(
        "--config", default=None, help="Path to config.json (optional)"
    )
    args = parser.parse_args()
    run(args.strategy, args.config)


if __name__ == "__main__":
    main()
