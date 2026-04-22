"""
reporting.py — Trade logging and performance reporting.

Writes a trade log CSV during the session.
Prints live status lines to stdout on every bar evaluation.
Saves a final equity curve chart on shutdown.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from broker.base import Position

log = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    symbol: str
    side: str
    qty: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    exit_reason: str    # "signal" | "stop_loss" | "take_profit"


class Reporter:
    def __init__(self, runs_dir: str, symbol: str, initial_balance: float) -> None:
        self._symbol = symbol
        self._initial_balance = initial_balance
        self._trades: List[TradeRecord] = []
        self._equity_curve: List[Tuple[datetime, float]] = [
            (datetime.now(timezone.utc), initial_balance)
        ]

        out = Path(runs_dir)
        out.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._csv_path = out / f"trades_{ts}.csv"
        self._csv_file = open(self._csv_path, "w", newline="")
        self._csv_writer = csv.DictWriter(
            self._csv_file,
            fieldnames=[
                "symbol", "side", "qty",
                "entry_price", "exit_price",
                "entry_time", "exit_time",
                "pnl", "exit_reason",
            ],
        )
        self._csv_writer.writeheader()
        self._csv_file.flush()
        log.info(f"Trade log: {self._csv_path}")

    def log_trade(self, trade: TradeRecord, current_balance: float) -> None:
        """Record a completed trade, append to CSV, and print a summary line."""
        self._trades.append(trade)
        self._equity_curve.append((trade.exit_time, current_balance))
        self._csv_writer.writerow(
            {
                "symbol": trade.symbol,
                "side": trade.side,
                "qty": trade.qty,
                "entry_price": f"{trade.entry_price:.6f}",
                "exit_price": f"{trade.exit_price:.6f}",
                "entry_time": trade.entry_time.isoformat(),
                "exit_time": trade.exit_time.isoformat(),
                "pnl": f"{trade.pnl:.2f}",
                "exit_reason": trade.exit_reason,
            }
        )
        self._csv_file.flush()
        sign = "+" if trade.pnl >= 0 else ""
        print(
            f"{_now()} | {trade.symbol} | "
            f"CLOSED {trade.side.upper()} {trade.qty:.4f} | "
            f"entry {trade.entry_price:.4f} → exit {trade.exit_price:.4f} | "
            f"PnL {sign}{trade.pnl:.2f} ({trade.exit_reason})"
        )

    def log_bar(
        self,
        bar_ts: datetime,
        close: float,
        position: Optional[Position],
        signal: Optional[str],
    ) -> None:
        """Print one status line for the current bar."""
        if position is not None:
            unreal = (close - position.entry_price) * position.qty
            sign = "+" if unreal >= 0 else ""
            pos_str = (
                f"{position.side.upper()} {position.qty:.4f} @ {position.entry_price:.4f} | "
                f"unreal {sign}{unreal:.2f}"
            )
            if position.stop_loss is not None:
                pos_str += f" | sl {position.stop_loss:.4f}"
            if position.take_profit is not None:
                pos_str += f" | tp {position.take_profit:.4f}"
        else:
            pos_str = "no position"

        sig_str = f"signal: {signal}" if signal else "signal: —"
        bar_str = bar_ts.strftime("%Y-%m-%d %H:%M")
        print(
            f"{_now()} | {self._symbol} | bar {bar_str} | "
            f"close {close:.4f} | {pos_str} | {sig_str}"
        )

    def print_final_report(self, final_balance: float) -> None:
        """Print summary statistics and save an equity curve chart."""
        self._equity_curve.append((datetime.now(timezone.utc), final_balance))
        self._csv_file.close()

        trades = self._trades
        n = len(trades)
        sep = "═" * 48

        print()
        print(sep)
        print(f"  FINAL REPORT — {_now()}")
        print(sep)

        if n == 0:
            print("  No completed trades.")
            print(f"  Trade log: {self._csv_path}")
            print(sep)
            return

        winners = [t for t in trades if t.pnl > 0]
        total_pnl = sum(t.pnl for t in trades)
        win_rate = len(winners) / n * 100
        total_return = (
            (final_balance - self._initial_balance) / self._initial_balance * 100
            if self._initial_balance > 0
            else 0.0
        )

        # Max drawdown from equity curve
        peak = self._initial_balance
        max_dd = 0.0
        for _, eq in self._equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

        print(f"  Trades:       {n}")
        print(f"  Win rate:     {win_rate:.1f}%")
        print(f"  Total PnL:    ${total_pnl:+.2f}")
        print(f"  Return:       {total_return:+.2f}%")
        print(f"  Max DD:       -{max_dd:.2f}%")
        print(f"  Trade log:    {self._csv_path}")

        # Equity curve chart
        try:
            import matplotlib.pyplot as plt

            times = [t for t, _ in self._equity_curve]
            equities = [e for _, e in self._equity_curve]
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(times, equities, linewidth=1.5, color="#2196F3")
            ax.axhline(
                self._initial_balance,
                color="gray",
                linestyle="--",
                linewidth=0.8,
                label="Starting balance",
            )
            ax.set_title(f"{self._symbol} — Equity Curve")
            ax.set_ylabel("Balance ($)")
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            chart_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            chart_path = Path(self._csv_path).parent / f"equity_{chart_ts}.png"
            fig.savefig(chart_path, dpi=120)
            plt.close(fig)
            print(f"  Chart:        {chart_path}")
        except ImportError:
            print("  Chart:        (install matplotlib to enable equity charts)")

        print(sep)
        print()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
