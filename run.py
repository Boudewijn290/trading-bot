"""
run.py — main entry point

Usage:
  python run.py                    # runs straddle strategy (default)
  python run.py --strategy straddle

To add a new strategy:
  1. Create strategies/your_strategy.py with a class inheriting BaseStrategy
  2. Import and register it in the STRATEGIES dict below
"""
import argparse
import sys

import core.position as position_store
from core.client import DeribitClient
from agents.sentiment_agent import run as run_sentiment
from strategies.straddle import StraddleStrategy

STRATEGIES = {
    "straddle": StraddleStrategy,
    # "trend":    TrendStrategy,   ← add new strategies here
}


def main():
    parser = argparse.ArgumentParser(description="Crypto options bot")
    parser.add_argument("--strategy", default="straddle", choices=STRATEGIES.keys())
    parser.add_argument("--skip-sentiment", action="store_true", help="Skip sentiment check")
    args = parser.parse_args()

    # ── Sentiment check ────────────────────────────────────────────────────────
    if not args.skip_sentiment:
        sentiment = run_sentiment()
        print()
        if sentiment["signal"] == "trending":
            print(f"[WARN] Market is {sentiment['label']} (score {sentiment['score']}) — "
                  f"straddle is less effective in trending markets.")
            answer = input("Continue anyway? (yes/no): ").strip().lower()
            if answer != "yes":
                sys.exit(0)

    # ── Exchange connection ────────────────────────────────────────────────────
    client = DeribitClient()
    client.authenticate()

    # ── Resume or enter ────────────────────────────────────────────────────────
    strategy = STRATEGIES[args.strategy](client)
    saved    = position_store.load()

    if saved and saved.get("strategy") == args.strategy:
        print(f"\n[RESUME] Found existing {args.strategy} position:")
        print(f"  Call:       {saved.get('call_name', '—')}")
        print(f"  Put:        {saved.get('put_name', '—')}")
        print(f"  Entry cost: {saved['entry_cost_btc']:.4f} BTC  (~${saved['entry_cost_usd']:,.2f})")
        print(f"  Entered at: {saved['entered_at']}")
        answer = input("\nResume monitoring this position? (yes/no): ").strip().lower()
        if answer == "yes":
            position = saved
        else:
            position_store.clear()
            position = strategy.enter()
    else:
        position = strategy.enter()

    strategy.monitor(position)


if __name__ == "__main__":
    main()
