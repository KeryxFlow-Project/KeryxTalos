```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██╗  ██╗███████╗██████╗ ██╗   ██╗██╗  ██╗                   ║
║   ██║ ██╔╝██╔════╝██╔══██╗╚██╗ ██╔╝╚██╗██╔╝                   ║
║   █████╔╝ █████╗  ██████╔╝ ╚████╔╝  ╚███╔╝                    ║
║   ██╔═██╗ ██╔══╝  ██╔══██╗  ╚██╔╝   ██╔██╗                    ║
║   ██║  ██╗███████╗██║  ██║   ██║   ██╔╝ ██╗                   ║
║   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝  FLOW             ║
║                                                               ║
║   Your keys, your trades, your code.                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

[![CI](https://github.com/KeryxFlow-Project/Kerykeion/actions/workflows/ci.yml/badge.svg)](https://github.com/KeryxFlow-Project/Kerykeion/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/keryxflow?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/keryxflow/)
![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-MVP-orange)

---

An AI-powered cryptocurrency trading engine that helps you accumulate Bitcoin.

- Watches cryptocurrency prices in real-time
- Uses AI (Claude) to analyze market context autonomously
- Finds trading opportunities using technical analysis, not emotions
- Protects your capital with immutable risk guardrails
- Learns from every trade via episodic memory and reflections

**Open source because trust requires transparency.**

---

## Quick Start

> Full walkthrough: [5-Minute Quickstart Guide](docs/quickstart.md)

### Prerequisites

- Python 3.12+
- A Binance account ([create one](https://www.binance.com))
- An Anthropic API key ([get one](https://console.anthropic.com))

### Installation

```bash
git clone https://github.com/KeryxFlow-Project/Kerykeion.git keryxflow
cd keryxflow
poetry install
cp .env.example .env
```

### First Run

```bash
poetry run keryxflow
```

KeryxFlow starts in **paper trading mode** by default — no real money is used until you explicitly enable live trading.

---

## Architecture

KeryxFlow uses a 12-layer event-driven architecture. Modules communicate through an async event bus, not direct calls. The AI agent operates autonomously within immutable safety guardrails.

```
HERMES (TUI) ─── ENGINE (Orchestrator) ─── API (REST/WS)
                      │
         AGENT ── ORACLE ── AEGIS
           │
        MEMORY     EXCHANGE     NOTIFICATIONS
                      │
     BACKTESTER ── OPTIMIZER
                      │
                    CORE (Events, DB, Logging)
```

**Trading flow:** Price Update -> OHLCV Buffer -> Oracle/Agent Signal -> Aegis Approval -> Exchange Execution -> Memory Record

For full details, see [Architecture Reference](docs/architecture.md).

---

## Safety

| Protection | Description |
|------------|-------------|
| **Paper Mode Default** | Starts with simulated money |
| **Immutable Guardrails** | Hardcoded limits: 10% max position, 5% daily loss cap, 20% max drawdown |
| **Circuit Breaker** | Automatic trading halt on drawdown limits |
| **Panic Button** | Press `P` to close everything immediately |
| **AI Guardrail Enforcement** | All agent execution tools pass through `GuardrailEnforcer` |

**Start with paper trading. Never invest more than you can afford to lose.**

---

## Backtesting & Optimization

```bash
# Backtest a strategy
poetry run keryxflow-backtest --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30

# Optimize parameters
poetry run keryxflow-optimize --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30 --grid quick
```

See [Optimization Guide](docs/optimization.md) for details.

---

## Development

```bash
poetry run pytest                    # Run tests
poetry run ruff check .              # Lint
poetry run ruff format .             # Format
```

See [Development Guide](docs/development.md) and [Contributing](CONTRIBUTING.md).

---

## Documentation

| Document | Description |
|----------|-------------|
| [Quickstart](docs/quickstart.md) | 5-minute setup guide |
| [Architecture](docs/architecture.md) | System design and module reference |
| [Trading Guide](docs/trading-guide.md) | How the trading system works |
| [Configuration](docs/configuration.md) | All configuration options |
| [Strategy Guide](docs/strategy-guide.md) | Strategy creation and selection |
| [API Reference](docs/api.md) | REST and WebSocket API |
| [Optimization](docs/optimization.md) | Parameter optimization guide |
| [Development](docs/development.md) | Developer setup and guidelines |

---

## Disclaimer

This software is experimental. Cryptocurrency trading involves significant financial risk. Past performance does not guarantee future results. Never trade with money you cannot afford to lose. **Use at your own risk.**

---

## License

MIT License — See [LICENSE](LICENSE)

---

<p align="center">
  <strong>Stack sats. ₿</strong>
</p>
