"""
Long Straddle Strategy

Entry:  Buy ATM call + put at the same strike and expiry.
        Liquidity-checked, nearest weekly expiry.

Exit:   - Take profit: position up TAKE_PROFIT_PCT
        - Stop loss:   position down STOP_LOSS_PCT
        - Expiry guard: less than EXPIRY_GUARD_HRS remaining
"""
import sys
import time
from datetime import datetime, timezone

import config
import core.position as position_store
from strategies.base import BaseStrategy


class StraddleStrategy(BaseStrategy):

    # ── Entry ──────────────────────────────────────────────────────────────────

    def enter(self) -> dict:
        spot        = self.client.get_index_price(config.CURRENCY)
        instruments = self.client.get_instruments(config.CURRENCY)
        print(f"[INFO] {config.CURRENCY} spot: ${spot:,.2f}")
        print(f"[INFO] {len(instruments)} option instruments loaded")

        expiry_ts = self._pick_expiry(instruments)
        strike    = self._find_atm_strike(instruments, expiry_ts, spot)

        call_name = put_name = None
        for inst in instruments:
            if inst["expiration_timestamp"] != expiry_ts:
                continue
            if inst["strike"] != strike:
                continue
            if inst["option_type"] == "call":
                call_name = inst["instrument_name"]
            elif inst["option_type"] == "put":
                put_name = inst["instrument_name"]

        if not call_name or not put_name:
            raise Exception(f"Could not find both legs at strike {strike}")

        print("\n[CHECK] Checking liquidity...")
        call_liq = self._check_liquidity(call_name)
        put_liq  = self._check_liquidity(put_name)

        if not call_liq:
            raise Exception(f"Call {call_name} failed liquidity check")
        if not put_liq:
            raise Exception(f"Put {put_name} failed liquidity check")

        _, call_ask, _ = call_liq
        _, put_ask,  _ = put_liq

        entry_cost_btc = (call_ask + put_ask) * config.AMOUNT
        entry_cost_usd = entry_cost_btc * spot
        tp_value       = entry_cost_btc * (1 + config.TAKE_PROFIT_PCT / 100)
        sl_value       = entry_cost_btc * (1 - config.STOP_LOSS_PCT / 100)

        print(f"\n{'─'*50}")
        print(f"  Call:         {call_name}")
        print(f"  Put:          {put_name}")
        print(f"  Call ask:     {call_ask:.4f} BTC")
        print(f"  Put ask:      {put_ask:.4f} BTC")
        print(f"  Entry cost:   {entry_cost_btc:.4f} BTC  (~${entry_cost_usd:,.2f})")
        print(f"  Take profit:  +{config.TAKE_PROFIT_PCT}%  → sell at {tp_value:.4f} BTC")
        print(f"  Stop loss:    -{config.STOP_LOSS_PCT}%   → sell at {sl_value:.4f} BTC")
        print(f"{'─'*50}\n")

        confirm = input("Place orders? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Cancelled.")
            sys.exit(0)

        print("\n[ORDER] Buying call...")
        call_order = self.client.buy(call_name, config.AMOUNT, label="straddle")
        print(f"[ORDER] Call ID: {call_order.get('order', {}).get('order_id', '?')}")

        print("[ORDER] Buying put...")
        put_order = self.client.buy(put_name, config.AMOUNT, label="straddle")
        print(f"[ORDER] Put ID: {put_order.get('order', {}).get('order_id', '?')}")

        print("\n[OK] Straddle entered.")

        pos = {
            "strategy":       "straddle",
            "call_name":      call_name,
            "put_name":       put_name,
            "strike":         strike,
            "expiry_ts":      expiry_ts,
            "entry_cost_btc": entry_cost_btc,
            "entry_cost_usd": entry_cost_usd,
            "amount":         config.AMOUNT,
            "entered_at":     datetime.now(timezone.utc).isoformat(),
        }
        position_store.save(pos)
        return pos

    # ── Monitor ────────────────────────────────────────────────────────────────

    def monitor(self, position: dict):
        entry_cost = position["entry_cost_btc"]
        tp_target  = entry_cost * (1 + config.TAKE_PROFIT_PCT / 100)
        sl_target  = entry_cost * (1 - config.STOP_LOSS_PCT / 100)
        expiry_dt  = datetime.fromtimestamp(position["expiry_ts"] / 1000, tz=timezone.utc)

        print(f"\n[MONITOR] Watching every {config.MONITOR_INTERVAL}s. Press Ctrl+C to stop.\n")

        while True:
            now             = datetime.now(timezone.utc)
            hours_to_expiry = (expiry_dt - now).total_seconds() / 3600
            value, call_bid, put_bid = self._get_value(position)
            pnl_pct         = ((value - entry_cost) / entry_cost) * 100

            print(
                f"[{now.strftime('%H:%M:%S')}]  "
                f"Call bid: {call_bid:.4f}  Put bid: {put_bid:.4f}  |  "
                f"Value: {value:.4f} BTC  |  "
                f"P&L: {pnl_pct:+.1f}%  |  "
                f"Expiry in: {hours_to_expiry:.1f}h"
            )

            if value >= tp_target:
                self.exit(position, f"Take profit hit (+{pnl_pct:.1f}%)")
                break
            if value <= sl_target:
                self.exit(position, f"Stop loss hit ({pnl_pct:.1f}%)")
                break
            if hours_to_expiry <= config.EXPIRY_GUARD_HRS:
                self.exit(position, f"Expiry guard — {hours_to_expiry:.1f}h left")
                break

            time.sleep(config.MONITOR_INTERVAL)

        self._print_summary(position)

    # ── Exit ───────────────────────────────────────────────────────────────────

    def exit(self, position: dict, reason: str):
        print(f"\n[EXIT] {reason}")
        for leg, name in [("call", position["call_name"]), ("put", position["put_name"])]:
            print(f"[ORDER] Selling {leg}...")
            try:
                self.client.sell(name, position["amount"], label="straddle-exit")
                print(f"[ORDER] {leg.capitalize()} sold.")
            except Exception as e:
                print(f"[ERROR] Failed to sell {leg}: {e}")
        position_store.clear()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _pick_expiry(self, instruments):
        now  = datetime.now(timezone.utc)
        seen = {}
        for inst in instruments:
            ts     = inst["expiration_timestamp"]
            exp_dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            days   = (exp_dt - now).days
            if days >= 1:
                seen[ts] = (exp_dt, days)
        if not seen:
            raise Exception("No valid expiries found")
        best_ts    = min(seen, key=lambda ts: abs(seen[ts][1] - config.PREFER_DAYS))
        exp_dt, days = seen[best_ts]
        print(f"[INFO] Expiry: {exp_dt.strftime('%d %b %Y')} ({days} days out)")
        return best_ts

    def _find_atm_strike(self, instruments, expiry_ts, spot):
        strikes = {inst["strike"] for inst in instruments if inst["expiration_timestamp"] == expiry_ts}
        atm     = min(strikes, key=lambda s: abs(s - spot))
        print(f"[INFO] ATM strike: ${atm:,.0f}  (spot: ${spot:,.2f})")
        return atm

    def _check_liquidity(self, instrument_name):
        ticker = self.client.get_ticker(instrument_name)
        bid    = ticker.get("best_bid_price", 0)
        ask    = ticker.get("best_ask_price", 0)
        if not bid or not ask:
            return None
        mid        = (bid + ask) / 2
        spread_pct = ((ask - bid) / mid) * 100
        if spread_pct > config.MAX_SPREAD_PCT:
            print(f"[SKIP] {instrument_name} spread {spread_pct:.1f}% — illiquid")
            return None
        return bid, ask, mid

    def _get_value(self, position):
        call_bid = self.client.get_ticker(position["call_name"]).get("best_bid_price", 0)
        put_bid  = self.client.get_ticker(position["put_name"]).get("best_bid_price", 0)
        return (call_bid + put_bid) * position["amount"], call_bid, put_bid

    def _print_summary(self, position):
        value, _, _  = self._get_value(position)
        entry_cost   = position["entry_cost_btc"]
        pnl_btc      = value - entry_cost
        pnl_usd      = pnl_btc * self.client.get_index_price(config.CURRENCY)
        pnl_pct      = (pnl_btc / entry_cost) * 100
        print(f"\n{'─'*50}")
        print(f"  Entry cost:  {entry_cost:.4f} BTC  (${position['entry_cost_usd']:,.2f})")
        print(f"  Exit value:  {value:.4f} BTC")
        print(f"  P&L:         {pnl_btc:+.4f} BTC  (~${pnl_usd:+,.2f})  ({pnl_pct:+.1f}%)")
        print(f"{'─'*50}\n")
