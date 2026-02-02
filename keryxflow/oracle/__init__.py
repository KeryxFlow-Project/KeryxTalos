"""Oracle - Intelligence layer with technical analysis and LLM integration."""

from keryxflow.oracle.brain import (
    ActionRecommendation,
    MarketBias,
    MarketContext,
    OracleBrain,
    get_oracle_brain,
)
from keryxflow.oracle.feeds import (
    NewsAggregator,
    NewsDigest,
    NewsItem,
    NewsSentiment,
    get_news_aggregator,
)
from keryxflow.oracle.signals import (
    SignalGenerator,
    SignalSource,
    SignalType,
    TradingSignal,
    get_signal_generator,
)
from keryxflow.oracle.technical import (
    IndicatorResult,
    SignalStrength,
    TechnicalAnalysis,
    TechnicalAnalyzer,
    TrendDirection,
    get_technical_analyzer,
)

__all__ = [
    # Technical
    "TechnicalAnalyzer",
    "TechnicalAnalysis",
    "IndicatorResult",
    "TrendDirection",
    "SignalStrength",
    "get_technical_analyzer",
    # Feeds
    "NewsAggregator",
    "NewsDigest",
    "NewsItem",
    "NewsSentiment",
    "get_news_aggregator",
    # Brain
    "OracleBrain",
    "MarketContext",
    "MarketBias",
    "ActionRecommendation",
    "get_oracle_brain",
    # Signals
    "SignalGenerator",
    "TradingSignal",
    "SignalType",
    "SignalSource",
    "get_signal_generator",
]
