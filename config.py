# ── Global bot configuration ───────────────────────────────────────────────────
# Edit these values to change strategy behaviour.
# Credentials are loaded from .env — never put them here.

# Exchange
CURRENCY         = "BTC"    # BTC or ETH
AMOUNT           = 0.1      # Size per leg (Deribit minimum is 0.1 BTC)

# Entry
PREFER_DAYS      = 7        # Target expiry: nearest expiry to this many days out
MAX_SPREAD_PCT   = 15       # Skip options where bid/ask spread > this % of mid

# Exit
TAKE_PROFIT_PCT  = 80       # Sell when position is up this % vs entry cost
STOP_LOSS_PCT    = 40       # Sell when position is down this % vs entry cost
EXPIRY_GUARD_HRS = 24       # Auto-exit if less than this many hours to expiry

# Monitoring
MONITOR_INTERVAL = 30       # Seconds between price checks
