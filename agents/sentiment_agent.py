"""
Sentiment Agent

Reads the Crypto Fear & Greed Index and writes a signal to signals/sentiment.json.
Strategies can read this signal to decide whether to enter a trade.

Signal output (signals/sentiment.json):
  {
    "score":      42,           # 0 (extreme fear) to 100 (extreme greed)
    "label":      "Fear",       # Extreme Fear / Fear / Neutral / Greed / Extreme Greed
    "signal":     "neutral",    # "volatile" | "neutral" | "trending"
    "updated_at": "2026-04-06T08:00:00+00:00"
  }

Signal interpretation:
  volatile  (score 0-40):  Fear/uncertainty → good for straddles (big moves likely)
  neutral   (score 41-59): Unclear → straddle is okay but not ideal
  trending  (score 60-100): Greed → market trending, straddle less effective
"""
import json
import os
import requests
from datetime import datetime, timezone

SIGNAL_FILE = os.path.join(os.path.dirname(__file__), "..", "signals", "sentiment.json")
API_URL     = "https://api.alternative.me/fng/?limit=1"


def fetch() -> dict:
    resp = requests.get(API_URL, timeout=10)
    data = resp.json()["data"][0]
    score = int(data["value"])
    label = data["value_classification"]

    if score <= 40:
        signal = "volatile"
    elif score <= 59:
        signal = "neutral"
    else:
        signal = "trending"

    return {
        "score":      score,
        "label":      label,
        "signal":     signal,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def write(result: dict):
    os.makedirs(os.path.dirname(SIGNAL_FILE), exist_ok=True)
    with open(SIGNAL_FILE, "w") as f:
        json.dump(result, f, indent=2)


def read():
    if not os.path.exists(SIGNAL_FILE):
        return None
    with open(SIGNAL_FILE) as f:
        return json.load(f)


def run():
    print("[SENTIMENT] Fetching Fear & Greed Index...")
    result = fetch()
    write(result)
    print(f"[SENTIMENT] Score: {result['score']} ({result['label']}) → signal: {result['signal']}")
    return result


if __name__ == "__main__":
    run()
