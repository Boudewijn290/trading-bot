"""
Deribit API client — handles authentication and all REST calls.
All strategies and agents import from here.
"""
import requests
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = (
    "https://test.deribit.com/api/v2"
    if os.getenv("DERIBIT_TEST", "true").lower() == "true"
    else "https://www.deribit.com/api/v2"
)


class DeribitClient:
    def __init__(self):
        self.client_id = os.getenv("DERIBIT_CLIENT_ID")
        self.client_secret = os.getenv("DERIBIT_CLIENT_SECRET")
        self.access_token = None

        if not self.client_id or not self.client_secret:
            raise ValueError("Missing DERIBIT_CLIENT_ID or DERIBIT_CLIENT_SECRET in .env")

    def authenticate(self):
        resp = requests.get(BASE_URL + "/public/auth", params={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        data = resp.json()
        if "result" not in data:
            raise Exception(f"Auth failed: {data}")
        self.access_token = data["result"]["access_token"]
        print("[OK] Authenticated with Deribit")

    def public_get(self, endpoint, params=None):
        resp = requests.get(BASE_URL + endpoint, params=params or {})
        return resp.json()["result"]

    def private_post(self, endpoint, params=None):
        if not self.access_token:
            self.authenticate()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        resp = requests.get(BASE_URL + endpoint, params=params or {}, headers=headers)
        data = resp.json()
        if "error" in data:
            raise Exception(f"API error: {data['error']}")
        return data["result"]

    # ── Market data ────────────────────────────────────────────────────────────

    def get_index_price(self, currency="BTC"):
        result = self.public_get("/public/get_index_price", {"index_name": f"{currency.lower()}_usd"})
        return result["index_price"]

    def get_instruments(self, currency="BTC", kind="option"):
        return self.public_get("/public/get_instruments", {
            "currency": currency,
            "kind": kind,
        })

    def get_order_book(self, instrument_name, depth=1):
        return self.public_get("/public/get_order_book", {
            "instrument_name": instrument_name,
            "depth": depth,
        })

    def get_ticker(self, instrument_name):
        return self.public_get("/public/ticker", {"instrument_name": instrument_name})

    # ── Trading ────────────────────────────────────────────────────────────────

    def buy(self, instrument_name, amount, order_type="market", label="bot"):
        return self.private_post("/private/buy", {
            "instrument_name": instrument_name,
            "amount": amount,
            "type": order_type,
            "label": label,
        })

    def sell(self, instrument_name, amount, order_type="market", label="bot-exit"):
        return self.private_post("/private/sell", {
            "instrument_name": instrument_name,
            "amount": amount,
            "type": order_type,
            "label": label,
        })

    # ── Account ────────────────────────────────────────────────────────────────

    def get_positions(self, currency="BTC", kind="option"):
        return self.private_post("/private/get_positions", {
            "currency": currency,
            "kind": kind,
        })

    def get_open_orders(self, currency="BTC", kind="option"):
        return self.private_post("/private/get_open_orders_by_currency", {
            "currency": currency,
            "kind": kind,
        })
