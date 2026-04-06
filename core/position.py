"""
Position persistence — saves and loads active trade state to disk.
This allows the bot to resume after a crash or restart.
"""
import json
import os

POSITION_FILE = os.path.join(os.path.dirname(__file__), "..", "position.json")


def save(position: dict):
    with open(POSITION_FILE, "w") as f:
        json.dump(position, f, indent=2)


def load():
    if not os.path.exists(POSITION_FILE):
        return None
    with open(POSITION_FILE) as f:
        return json.load(f)


def clear():
    if os.path.exists(POSITION_FILE):
        os.remove(POSITION_FILE)
