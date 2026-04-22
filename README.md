# trading-bot

Modular crypto options trading bot running on [Deribit](https://test.deribit.com).  
Currently implements a **long straddle strategy** with sentiment analysis from the Crypto Fear & Greed Index.

---

## How it works

Before entering a trade, the **sentiment agent** checks the Crypto Fear & Greed Index.  
If the market is in fear/uncertainty (score < 40), conditions are good for a straddle — big moves are likely.  
The **straddle strategy** then buys an ATM call + put, monitors the position every 30 seconds, and exits automatically.

```
sentiment_agent  →  signals/sentiment.json  →  straddle strategy
                                                      ↓
                                              enter: buy call + put
                                                      ↓
                                              monitor: check P&L every 30s
                                                      ↓
                                              exit: take profit / stop loss / expiry guard
```

---

## Project structure

```
trading-bot/
│
├── core/
│   ├── client.py        # Deribit API client (auth, orders, market data)
│   └── position.py      # Saves/loads active trade to disk (crash recovery)
│
├── strategies/
│   ├── base.py          # BaseStrategy class — all strategies inherit from this
│   └── straddle.py      # Long straddle strategy
│
├── agents/
│   └── sentiment_agent.py   # Fetches Fear & Greed Index, writes signal
│
├── signals/
│   └── sentiment.json       # Live signal output (git-ignored)
│
├── config.py            # All strategy settings in one place
├── run.py               # Main entry point
├── requirements.txt
└── .env.example         # Credentials template
```

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/Boudewijn290/trading-bot.git
cd trading-bot
```

**2. Create a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Add your credentials**
```bash
cp .env.example .env
```
Edit `.env` and fill in your Deribit API key and secret.  
Get test credentials at [test.deribit.com](https://test.deribit.com) → Account → API.

```
DERIBIT_CLIENT_ID=your_client_id
DERIBIT_CLIENT_SECRET=your_client_secret
DERIBIT_TEST=true
```

---

## Running the bot

```bash
source venv/bin/activate
python run.py
```

The bot will:
1. Check the Fear & Greed sentiment signal
2. Connect to Deribit and authenticate
3. Find the nearest weekly expiry and ATM strike
4. Show you the trade details and ask for confirmation
5. Place both legs and start monitoring

---

## Configuration

All settings are in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CURRENCY` | `BTC` | BTC or ETH |
| `AMOUNT` | `0.1` | Size per leg in BTC |
| `PREFER_DAYS` | `7` | Target days to expiry |
| `MAX_SPREAD_PCT` | `15` | Max bid/ask spread % (liquidity filter) |
| `TAKE_PROFIT_PCT` | `80` | Exit when up this % |
| `STOP_LOSS_PCT` | `40` | Exit when down this % |
| `EXPIRY_GUARD_HRS` | `24` | Auto-exit if less than this many hours to expiry |
| `MONITOR_INTERVAL` | `30` | Seconds between price checks |

---

## Exit conditions

The bot exits automatically when any of these are hit:

- **Take profit** — position value up 80% vs entry cost
- **Stop loss** — position value down 40% vs entry cost
- **Expiry guard** — less than 24h to expiry (avoids expiring worthless)

---

## Adding a new strategy

1. Create `strategies/your_strategy.py`
2. Subclass `BaseStrategy` from `strategies/base.py`
3. Implement `enter()`, `monitor()`, and `exit()`
4. Register it in `run.py` under the `STRATEGIES` dict

```python
from strategies.your_strategy import YourStrategy

STRATEGIES = {
    "straddle": StraddleStrategy,
    "your_strategy": YourStrategy,   # ← add here
}
```

Run it with:
```bash
python run.py --strategy your_strategy
```

---

## Disclaimer

This bot is for educational purposes. Use on testnet before risking real funds.  
Crypto options trading carries significant risk of loss.
