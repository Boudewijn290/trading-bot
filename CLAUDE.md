# Trading Bot — Project Context

## Goal
Build a modular trading bot framework supporting multiple strategies running in parallel.
The system should cover strategy research, backtesting, visualization, and eventually paper and live execution.

## Team
Two developers. Still exploring which strategies to prioritize — the system must be strategy-agnostic and easy to extend.

## Markets
Exact markets still being defined. Architecture must support multiple market types and timeframes.

## Strategies
Multiple strategies with different time horizons. Candidates: trend-following, mean reversion, breakout/momentum, multi-timeframe confluence.
New strategies must be addable without rewriting the system.

## Exchanges
Exchange-specific logic must be isolated from strategy logic. Different exchanges/brokers per market.

## Risk
- Max 10% of total balance at risk per trade (to be refined into proper portfolio and strategy-level rules).
- Risk tolerance depends on strategy and backtested success rate.

---

## What we need help with
1. Modular trading framework design
2. Backtesting architecture
3. Visualization and analytics
4. Strategy abstraction and clean interfaces
5. Risk management and portfolio allocation
6. Preparing for paper trading and live trading

## Important requirements
- Separate strategy logic from execution logic
- Reproducible and testable
- Backtests must include fees, slippage, and realistic execution assumptions
- Performance analytics: equity curve, drawdown, win rate, expectancy, trade logs
- Strategy comparison across markets and timeframes

---

## Proposed architecture

### Module structure
```
trading-bot/
├── data/               # Market data ingestion and storage
│   ├── feeds/          # Exchange/broker-specific data adapters
│   └── store/          # Local data caching (Parquet/SQLite)
│
├── strategies/         # Strategy logic only — no execution, no I/O
│   ├── base.py         # BaseStrategy ABC: generate_signals(data) → signals
│   ├── straddle.py     # (existing)
│   └── ...
│
├── backtester/         # Simulation engine
│   ├── engine.py       # Event loop, order matching, fills
│   ├── account.py      # Virtual portfolio: cash, positions, equity
│   └── report.py       # Analytics output
│
├── risk/               # Position sizing and portfolio-level guards
│   ├── sizer.py        # Size each trade given account and rules
│   └── portfolio.py    # Cross-strategy allocation and exposure limits
│
├── execution/          # Live and paper order routing
│   ├── paper.py        # Paper trading (same interface as live)
│   └── live.py         # Routes to exchange clients
│
├── core/               # Shared exchange clients
│   ├── client.py       # (existing Deribit client)
│   └── position.py     # (existing crash recovery)
│
├── agents/             # Signal producers (sentiment, macro, etc.)
│   └── sentiment_agent.py
│
├── analytics/          # Visualization and reporting
│   ├── charts.py       # Equity curve, drawdown, trade overlay
│   └── compare.py      # Side-by-side strategy comparison
│
├── config.py           # Global defaults
├── run.py              # Entry point
└── CLAUDE.md
```

### Data flow
```
Data feeds → strategies (signals) → risk sizer → execution → position store
                                                       ↓
                                              analytics / reporting
```

In backtesting, the execution layer is replaced by the backtester engine. Strategy code does not change.

### Key interfaces

**BaseStrategy**
```python
def generate_signals(self, data: pd.DataFrame) -> list[Signal]:
    # Returns buy/sell/hold signals with metadata
```

**Signal**
```python
@dataclass
class Signal:
    timestamp: datetime
    instrument: str
    direction: Literal["long", "short", "exit"]
    confidence: float       # 0–1, used by risk sizer
    timeframe: str
    strategy_id: str
```

**BaseExecution**
```python
def submit(self, order: Order) -> Fill: ...
def get_positions(self) -> list[Position]: ...
```

Paper and live execution both implement `BaseExecution` — strategies never know which is running.

---

## Backtesting design
- Event-driven engine iterating over OHLCV bars
- Account tracks cash + open positions + running equity
- Order matching: market orders fill on next bar open; limit orders fill when price crosses
- Fees and slippage configurable per instrument/exchange
- Output: trade log (CSV), equity curve, drawdown series, summary stats

## Risk management design
- Per-trade max risk: 10% of total balance (configurable per strategy)
- Position size = (account * risk_pct) / (entry - stop_loss)
- Portfolio-level: max total exposure, max correlated exposure, max open positions
- Strategy-level: independent risk budgets, drawdown circuit breakers

## Analytics outputs
- Equity curve vs benchmark
- Drawdown chart (absolute and %)
- Trade log with entry/exit/PnL per trade
- Win rate, expectancy, Sharpe, Sortino, max drawdown
- Strategy comparison table across markets and timeframes

---

## Development roadmap
1. Data layer — ingest and cache OHLCV data for target markets
2. Backtester engine — simulate fills, track account, output trade log
3. Strategy interface — refactor existing strategies to `generate_signals()`
4. Risk module — per-trade sizer, portfolio exposure limits
5. Analytics — equity curve, drawdown, comparison reports
6. Paper trading — plug live data + paper execution into same pipeline
7. Live trading — swap paper execution for real exchange clients

## Common pitfalls to avoid
- Look-ahead bias: never use future data in signal generation; align bar timestamps carefully
- Overfitting: walk-forward validation, out-of-sample testing, avoid over-parameterised strategies
- Ignoring costs: always include fees and realistic slippage in backtests
- Tight coupling: keep strategy logic completely free of exchange or I/O dependencies
- Missing crash recovery: persist position state before submitting orders (already in place)
- Assuming fills: backtests should model partial fills and liquidity limits for realistic results
