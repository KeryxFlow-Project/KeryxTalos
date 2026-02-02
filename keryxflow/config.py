"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RiskSettings(BaseSettings):
    """Risk management configuration."""

    model_config = SettingsConfigDict(env_prefix="KERYXFLOW_RISK_")

    model: Literal["fixed_fractional", "kelly"] = "fixed_fractional"
    risk_per_trade: float = Field(default=0.01, ge=0.001, le=0.1)
    max_daily_drawdown: float = Field(default=0.05, ge=0.01, le=0.5)
    max_open_positions: int = Field(default=3, ge=1, le=20)
    min_risk_reward: float = Field(default=1.5, ge=0.5, le=10.0)
    stop_loss_type: Literal["atr", "fixed", "percentage"] = "atr"
    atr_multiplier: float = Field(default=2.0, ge=0.5, le=5.0)


class MTFSettings(BaseSettings):
    """Multi-Timeframe Analysis configuration."""

    model_config = SettingsConfigDict(env_prefix="KERYXFLOW_MTF_")

    enabled: bool = False
    timeframes: list[str] = ["15m", "1h", "4h"]
    primary_timeframe: str = "1h"
    filter_timeframe: str = "4h"
    min_filter_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class OracleSettings(BaseSettings):
    """Oracle (Intelligence) configuration."""

    model_config = SettingsConfigDict(env_prefix="KERYXFLOW_ORACLE_")

    # Technical Analysis
    indicators: list[str] = ["rsi", "macd", "bbands", "obv", "atr", "ema"]
    rsi_period: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bbands_period: int = 20
    bbands_std: float = 2.0
    ema_periods: list[int] = [9, 21, 50, 200]

    # LLM Integration
    llm_enabled: bool = True
    llm_model: str = "claude-sonnet-4-20250514"
    analysis_interval: int = Field(default=300, ge=60, le=3600)
    max_tokens: int = 1024

    # News Sources
    news_enabled: bool = True
    news_sources: list[str] = ["cryptopanic", "rss"]
    rss_feeds: list[str] = [
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
    ]
    news_lookback_hours: int = Field(default=4, ge=1, le=24)

    # Multi-Timeframe Analysis
    mtf: MTFSettings = Field(default_factory=MTFSettings)


class SystemSettings(BaseSettings):
    """System configuration."""

    model_config = SettingsConfigDict(env_prefix="KERYXFLOW_")

    exchange: str = "binance"
    mode: Literal["paper", "live"] = "paper"
    symbols: list[str] = ["BTC/USDT", "ETH/USDT"]
    base_currency: str = "USDT"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class HermesSettings(BaseSettings):
    """Hermes (TUI) configuration."""

    model_config = SettingsConfigDict(env_prefix="KERYXFLOW_HERMES_")

    refresh_rate: float = Field(default=1.0, ge=0.1, le=10.0)
    chart_width: int = Field(default=60, ge=20, le=200)
    chart_height: int = Field(default=15, ge=5, le=50)
    max_log_lines: int = Field(default=100, ge=10, le=1000)
    theme: Literal["cyberpunk", "minimal"] = "cyberpunk"


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="KERYXFLOW_DB_")

    url: str = "sqlite+aiosqlite:///data/keryxflow.db"


class LiveSettings(BaseSettings):
    """Live trading configuration."""

    model_config = SettingsConfigDict(env_prefix="KERYXFLOW_LIVE_")

    require_confirmation: bool = True
    min_paper_trades: int = Field(default=30, ge=0, le=1000)
    min_balance: float = Field(default=100.0, ge=0.0)
    max_position_value: float = Field(default=1000.0, ge=10.0)
    sync_interval: int = Field(default=60, ge=10, le=300)


class NotificationSettings(BaseSettings):
    """Notification configuration."""

    model_config = SettingsConfigDict(env_prefix="KERYXFLOW_NOTIFY_")

    # Telegram
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""

    # Discord
    discord_enabled: bool = False
    discord_webhook: str = ""

    # Notification preferences
    notify_on_trade: bool = True
    notify_on_circuit_breaker: bool = True
    notify_daily_summary: bool = True
    notify_on_error: bool = True


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys (from .env)
    binance_api_key: SecretStr = Field(default=SecretStr(""))
    binance_api_secret: SecretStr = Field(default=SecretStr(""))
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    cryptopanic_api_key: SecretStr = Field(default=SecretStr(""))

    # Environment
    env: Literal["development", "production"] = "development"

    # Sub-settings
    system: SystemSettings = Field(default_factory=SystemSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    oracle: OracleSettings = Field(default_factory=OracleSettings)
    hermes: HermesSettings = Field(default_factory=HermesSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    live: LiveSettings = Field(default_factory=LiveSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)

    @field_validator("binance_api_key", "binance_api_secret", "anthropic_api_key")
    @classmethod
    def warn_if_empty(cls, v: SecretStr) -> SecretStr:
        """Warn if critical API keys are empty."""
        # Will be validated at runtime when features are used
        return v

    @property
    def is_first_run(self) -> bool:
        """Check if this is the first run (no user profile exists)."""
        db_path = Path(self.database.url.replace("sqlite+aiosqlite:///", ""))
        return not db_path.exists()

    @property
    def is_paper_mode(self) -> bool:
        """Check if running in paper trading mode."""
        return self.system.mode == "paper"

    @property
    def has_binance_credentials(self) -> bool:
        """Check if Binance credentials are configured."""
        return bool(
            self.binance_api_key.get_secret_value() and self.binance_api_secret.get_secret_value()
        )

    @property
    def has_anthropic_credentials(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(self.anthropic_api_key.get_secret_value())


def load_settings() -> Settings:
    """Load settings from environment and config files."""
    return Settings()


# Global settings instance (lazy loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
