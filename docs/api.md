# KeryxFlow API Reference

Internal API documentation for developers extending KeryxFlow.

## Core Module

### Event Bus (`keryxflow/core/events.py`)

Async pub/sub system for inter-module communication.

#### EventType

```python
class EventType(str, Enum):
    # Price events
    PRICE_UPDATE = "price_update"
    OHLCV_UPDATE = "ohlcv_update"

    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_VALIDATED = "signal_validated"
    SIGNAL_REJECTED = "signal_rejected"

    # Order events
    ORDER_REQUESTED = "order_requested"
    ORDER_APPROVED = "order_approved"
    ORDER_REJECTED = "order_rejected"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"

    # Position events
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"

    # Risk events
    RISK_ALERT = "risk_alert"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    DRAWDOWN_WARNING = "drawdown_warning"

    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    SYSTEM_PAUSED = "system_paused"
    SYSTEM_RESUMED = "system_resumed"
    PANIC_TRIGGERED = "panic_triggered"
```

#### Event

```python
@dataclass
class Event:
    type: EventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict[str, Any] = field(default_factory=dict)
```

#### EventBus

```python
class EventBus:
    def __init__(self, max_queue_size: int = 1000): ...

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to an event type."""

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from an event type."""

    async def publish(self, event: Event) -> None:
        """Publish event to queue (async dispatch)."""

    async def publish_sync(self, event: Event) -> None:
        """Publish and wait for all handlers to complete."""

    async def start(self) -> None:
        """Start the event processor."""

    async def stop(self) -> None:
        """Stop the event processor."""

    @property
    def is_running(self) -> bool: ...

    @property
    def queue_size(self) -> int: ...

# Global instance
def get_event_bus() -> EventBus: ...
```

**Usage:**

```python
from keryxflow.core.events import Event, EventType, get_event_bus

bus = get_event_bus()

# Subscribe
async def on_price(event: Event):
    print(f"Price: {event.data['price']}")

bus.subscribe(EventType.PRICE_UPDATE, on_price)

# Publish
await bus.publish(Event(
    type=EventType.PRICE_UPDATE,
    data={"symbol": "BTC/USDT", "price": 67000.0}
))
```

---

### Trading Engine (`keryxflow/core/engine.py`)

#### OHLCVBuffer

```python
class OHLCVBuffer:
    def __init__(self, max_candles: int = 100): ...

    def update(self, symbol: str, price: float, volume: float = 0) -> bool:
        """Update buffer with new price. Returns True if new candle created."""

    def add_candle(
        self, symbol: str, timestamp: datetime,
        open_: float, high: float, low: float, close: float, volume: float
    ) -> None:
        """Add historical candle to buffer."""

    def get_ohlcv(self, symbol: str) -> pd.DataFrame | None:
        """Get OHLCV DataFrame for symbol."""

    def get_current_price(self, symbol: str) -> float | None:
        """Get latest price for symbol."""
```

#### TradingEngine

```python
class TradingEngine:
    def __init__(
        self,
        exchange_client: ExchangeClient,
        paper_engine: PaperTradingEngine,
        event_bus: EventBus | None = None,
    ): ...

    async def start(self) -> None:
        """Start the trading engine."""

    async def stop(self) -> None:
        """Stop the trading engine."""

    def get_status(self) -> dict[str, Any]:
        """Get current engine status."""

    @property
    def is_running(self) -> bool: ...

    @property
    def is_paused(self) -> bool: ...

    # Components
    @property
    def signals(self) -> SignalGenerator: ...

    @property
    def risk(self) -> RiskManager: ...
```

---

### Configuration (`keryxflow/config.py`)

#### Settings Classes

```python
class RiskSettings(BaseSettings):
    model: Literal["fixed_fractional", "kelly"] = "fixed_fractional"
    risk_per_trade: float = 0.01
    max_daily_drawdown: float = 0.05
    max_open_positions: int = 3
    min_risk_reward: float = 1.5
    stop_loss_type: Literal["atr", "fixed", "percentage"] = "atr"
    atr_multiplier: float = 2.0

class OracleSettings(BaseSettings):
    indicators: list[str] = ["rsi", "macd", "bbands", "obv", "atr", "ema"]
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    llm_enabled: bool = True
    llm_model: str = "claude-sonnet-4-20250514"
    analysis_interval: int = 300
    news_enabled: bool = True

class SystemSettings(BaseSettings):
    exchange: str = "binance"
    mode: Literal["paper", "live"] = "paper"
    symbols: list[str] = ["BTC/USDT", "ETH/USDT"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

class Settings(BaseSettings):
    binance_api_key: SecretStr
    binance_api_secret: SecretStr
    anthropic_api_key: SecretStr

    system: SystemSettings
    risk: RiskSettings
    oracle: OracleSettings
    hermes: HermesSettings
    database: DatabaseSettings
    live: LiveSettings
    notifications: NotificationSettings

    @property
    def is_paper_mode(self) -> bool: ...

    @property
    def has_binance_credentials(self) -> bool: ...

def get_settings() -> Settings: ...
```

---

## Oracle Module

### Signal Generator (`keryxflow/oracle/signals.py`)

#### SignalType

```python
class SignalType(str, Enum):
    LONG = "long"
    SHORT = "short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    NO_ACTION = "no_action"
```

#### TradingSignal

```python
@dataclass
class TradingSignal:
    symbol: str
    signal_type: SignalType
    strength: SignalStrength
    confidence: float  # 0.0 to 1.0
    source: SignalSource
    timestamp: datetime

    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = None

    simple_reason: str = ""
    technical_reason: str = ""

    def to_dict(self) -> dict[str, Any]: ...

    @property
    def is_actionable(self) -> bool: ...

    @property
    def is_entry(self) -> bool: ...
```

#### SignalGenerator

```python
class SignalGenerator:
    def __init__(
        self,
        technical_analyzer: TechnicalAnalyzer | None = None,
        news_aggregator: NewsAggregator | None = None,
        brain: OracleBrain | None = None,
        event_bus: EventBus | None = None,
        publish_events: bool = True,
    ): ...

    async def generate_signal(
        self,
        symbol: str,
        ohlcv: pd.DataFrame,
        current_price: float | None = None,
        include_news: bool = True,
        include_llm: bool = True,
    ) -> TradingSignal:
        """Generate a trading signal for a symbol."""

    def format_signal(self, signal: TradingSignal, simple: bool = True) -> str:
        """Format a signal for display."""

def get_signal_generator() -> SignalGenerator: ...
```

### Technical Analyzer (`keryxflow/oracle/technical.py`)

```python
class TechnicalAnalyzer:
    def analyze(self, ohlcv: pd.DataFrame, symbol: str) -> TechnicalAnalysis:
        """Run all indicators and return analysis."""

@dataclass
class TechnicalAnalysis:
    symbol: str
    timestamp: datetime
    indicators: dict[str, IndicatorResult]
    overall_trend: TrendDirection
    overall_strength: SignalStrength
    confidence: float
    simple_summary: str
    technical_summary: str

    def to_dict(self) -> dict[str, Any]: ...

def get_technical_analyzer() -> TechnicalAnalyzer: ...
```

---

## Aegis Module

### Risk Manager (`keryxflow/aegis/risk.py`)

```python
class RiskManager:
    def __init__(self, settings: RiskSettings | None = None): ...

    async def approve_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        current_balance: float = 0,
        open_positions: int = 0,
        daily_pnl: float = 0,
    ) -> tuple[bool, str]:
        """Approve or reject an order. Returns (approved, reason)."""

    def calculate_position_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """Calculate position size based on risk parameters."""

    def get_status(self) -> dict[str, Any]:
        """Get current risk status."""
```

### Circuit Breaker (`keryxflow/aegis/circuit.py`)

```python
class CircuitBreaker:
    def __init__(
        self,
        max_daily_drawdown: float = 0.05,
        max_total_drawdown: float = 0.10,
        max_consecutive_losses: int = 5,
        rapid_loss_window: int = 3600,
        rapid_loss_count: int = 3,
        cooldown_minutes: int = 60,
    ): ...

    def check(
        self,
        daily_pnl_pct: float,
        total_pnl_pct: float,
        consecutive_losses: int,
    ) -> bool:
        """Check if circuit breaker should trigger. Returns True if tripped."""

    def trip(self, reason: str) -> None:
        """Manually trip the circuit breaker."""

    def reset(self) -> bool:
        """Reset the circuit breaker. Returns False if in cooldown."""

    @property
    def is_tripped(self) -> bool: ...

    @property
    def trip_reason(self) -> str | None: ...

    def get_status(self) -> dict[str, Any]: ...
```

### Quant Engine (`keryxflow/aegis/quant.py`)

```python
class QuantEngine:
    @staticmethod
    def position_size(
        balance: float,
        risk_pct: float,
        entry: float,
        stop_loss: float,
    ) -> float:
        """Calculate position size from risk percentage."""

    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate optimal bet size using Kelly Criterion."""

    @staticmethod
    def atr_stop_loss(
        entry: float,
        atr: float,
        multiplier: float = 2.0,
        is_long: bool = True,
    ) -> float:
        """Calculate ATR-based stop loss."""

    @staticmethod
    def risk_reward_ratio(
        entry: float,
        stop_loss: float,
        take_profit: float,
    ) -> float:
        """Calculate risk/reward ratio."""

    @staticmethod
    def drawdown(equity_curve: list[float]) -> tuple[float, float]:
        """Calculate current and max drawdown. Returns (current_dd, max_dd)."""

    @staticmethod
    def sharpe_ratio(
        returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> float:
        """Calculate Sharpe ratio."""
```

---

## Exchange Module

### Exchange Client (`keryxflow/exchange/client.py`)

```python
class ExchangeClient:
    def __init__(self, sandbox: bool = True): ...

    async def connect(self) -> bool:
        """Connect to exchange. Returns success status."""

    async def disconnect(self) -> None:
        """Disconnect from exchange."""

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """Fetch current ticker for symbol."""

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100,
    ) -> list[list]:
        """Fetch OHLCV candles."""

    async def fetch_balance(self) -> dict[str, Any]:
        """Fetch account balance."""

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> dict[str, Any]:
        """Create a market order."""

    @property
    def is_connected(self) -> bool: ...
```

### Paper Trading Engine (`keryxflow/exchange/paper.py`)

```python
class PaperTradingEngine:
    def __init__(
        self,
        initial_balance: float = 10000.0,
        slippage_pct: float = 0.001,
    ): ...

    async def initialize(self) -> None:
        """Initialize from database."""

    def update_price(self, symbol: str, price: float) -> None:
        """Update current price for PnL calculation."""

    async def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> dict[str, Any]:
        """Execute a paper order."""

    async def close_position(self, symbol: str) -> dict[str, Any] | None:
        """Close an open position."""

    async def close_all_positions(self) -> list[dict[str, Any]]:
        """Close all open positions (panic mode)."""

    async def get_balance(self) -> dict[str, Any]:
        """Get current balance."""

    async def get_positions(self) -> list[dict[str, Any]]:
        """Get all open positions."""
```

---

## Backtester Module

### Data Loader (`keryxflow/backtester/data.py`)

```python
class DataLoader:
    @staticmethod
    async def from_binance(
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1h",
    ) -> pd.DataFrame:
        """Load OHLCV data from Binance."""

    @staticmethod
    def from_csv(path: str) -> pd.DataFrame:
        """Load OHLCV data from CSV file."""

    @staticmethod
    def validate(df: pd.DataFrame) -> bool:
        """Validate OHLCV DataFrame."""

    @staticmethod
    def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample to different timeframe."""
```

### Backtest Engine (`keryxflow/backtester/engine.py`)

```python
class BacktestEngine:
    def __init__(
        self,
        initial_balance: float = 10000.0,
        commission_pct: float = 0.001,
        slippage_pct: float = 0.001,
    ): ...

    async def run(
        self,
        data: dict[str, pd.DataFrame],
        oracle_settings: OracleSettings | None = None,
        risk_settings: RiskSettings | None = None,
    ) -> BacktestResult:
        """Run backtest on historical data."""

@dataclass
class BacktestResult:
    initial_balance: float
    final_balance: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    sharpe_ratio: float
    trades: list[Trade]
    equity_curve: list[float]
```

---

## Optimizer Module

### Parameter Grid (`keryxflow/optimizer/grid.py`)

```python
@dataclass
class ParameterRange:
    name: str
    values: list[Any]
    category: Literal["oracle", "risk"] = "oracle"

class ParameterGrid:
    def __init__(self, ranges: list[ParameterRange] | None = None): ...

    def add_range(self, range_: ParameterRange) -> None:
        """Add a parameter range."""

    def combinations(self) -> Iterator[dict[str, Any]]:
        """Generate all parameter combinations."""

    def combinations_flat(self) -> Iterator[dict[str, Any]]:
        """Generate flat (uncategorized) combinations."""

    @classmethod
    def preset(cls, name: str) -> "ParameterGrid":
        """Get a preset grid: 'quick', 'oracle', 'risk', 'full'."""

    def __len__(self) -> int: ...
```

### Optimization Engine (`keryxflow/optimizer/engine.py`)

```python
@dataclass
class OptimizationResult:
    parameters: dict[str, Any]
    metrics: BacktestResult
    run_time: float

class OptimizationEngine:
    def __init__(
        self,
        backtest_engine: BacktestEngine | None = None,
    ): ...

    async def optimize(
        self,
        data: dict[str, pd.DataFrame],
        grid: ParameterGrid,
        metric: str = "sharpe_ratio",
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[OptimizationResult]:
        """Run optimization across parameter grid."""
```

---

## Notifications Module

### Notification Manager (`keryxflow/notifications/manager.py`)

```python
class NotificationManager:
    def __init__(self, settings: NotificationSettings | None = None): ...

    async def start(self) -> None:
        """Start and subscribe to events."""

    async def stop(self) -> None:
        """Stop and unsubscribe."""

    async def notify(self, message: str, level: str = "info") -> None:
        """Send notification to all enabled channels."""

    async def notify_order_filled(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> None:
        """Notify about filled order."""

    async def notify_circuit_breaker(self, reason: str) -> None:
        """Notify about circuit breaker trigger."""

    async def notify_daily_summary(
        self,
        pnl: float,
        trades: int,
        win_rate: float,
    ) -> None:
        """Send daily summary."""
```

---

## Utility Functions

### Logging (`keryxflow/core/logging.py`)

```python
def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger."""

def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    json_format: bool = False,
) -> None:
    """Configure logging for the application."""
```

### Database (`keryxflow/core/database.py`)

```python
async def init_db() -> None:
    """Initialize database tables."""

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager."""

async def get_or_create_user_profile(session: AsyncSession) -> UserProfile:
    """Get or create the user profile."""
```

---

## Type Aliases

```python
# Event handler signature
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]

# Common data types
Symbol = str  # e.g., "BTC/USDT"
Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
```
