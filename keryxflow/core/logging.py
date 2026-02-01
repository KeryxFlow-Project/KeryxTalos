"""Structured logging configuration using structlog."""

import logging
import sys
from pathlib import Path
from typing import Literal

import structlog
from structlog.types import Processor


def get_log_level(level: str) -> int:
    """Convert string log level to logging constant."""
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    return levels.get(level.upper(), logging.INFO)


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,  # noqa: ARG001 - Reserved for future file logging
    json_format: bool = False,
) -> None:
    """
    Configure structlog for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
        json_format: Whether to use JSON format (for production)
    """
    log_level = get_log_level(level)

    # Shared processors for all outputs
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        # Production: JSON format
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Development: colored console output
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging for third-party libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("ccxt").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Optional logger name (module name)

    Returns:
        Configured structlog logger
    """
    logger = structlog.get_logger(name)
    return logger


class LogMessages:
    """
    Centralized log messages with beginner-friendly and technical versions.

    Usage:
        msg = LogMessages.signal_generated("BTC/USDT", "long", 0.78)
        logger.info(msg.simple)  # For beginners
        logger.debug(msg.technical)  # For advanced users
    """

    class Message:
        """A log message with simple and technical versions."""

        def __init__(self, simple: str, technical: str):
            self.simple = simple
            self.technical = technical

        def __str__(self) -> str:
            return self.simple

    @staticmethod
    def signal_generated(symbol: str, direction: str, confidence: float) -> "LogMessages.Message":
        """Signal generated message."""
        return LogMessages.Message(
            simple=f"Found a {direction} opportunity for {symbol} (confidence: {confidence:.0%})",
            technical=f"Signal generated: {symbol} {direction.upper()} | confidence={confidence:.2f}",
        )

    @staticmethod
    def order_approved(symbol: str, quantity: float, price: float) -> "LogMessages.Message":
        """Order approved message."""
        return LogMessages.Message(
            simple=f"Trade approved: buying {quantity} {symbol.split('/')[0]} at ${price:,.2f}",
            technical=f"Order approved: {symbol} qty={quantity} entry={price}",
        )

    @staticmethod
    def order_rejected(symbol: str, reason: str, technical_reason: str) -> "LogMessages.Message":
        """Order rejected message."""
        return LogMessages.Message(
            simple=f"Trade not taken: {reason}",
            technical=f"Order rejected: {symbol} | reason={technical_reason}",
        )

    @staticmethod
    def order_filled(
        symbol: str, side: str, quantity: float, price: float
    ) -> "LogMessages.Message":
        """Order filled message."""
        action = "Bought" if side == "buy" else "Sold"
        return LogMessages.Message(
            simple=f"{action} {quantity} {symbol.split('/')[0]} at ${price:,.2f}",
            technical=f"Order filled: {side.upper()} {quantity} {symbol} @ {price}",
        )

    @staticmethod
    def circuit_breaker_triggered(
        drawdown: float, limit: float
    ) -> "LogMessages.Message":
        """Circuit breaker triggered message."""
        return LogMessages.Message(
            simple=f"Trading paused: daily loss limit reached ({drawdown:.1%} of {limit:.1%})",
            technical=f"Circuit breaker triggered: drawdown={drawdown:.2%} limit={limit:.2%}",
        )

    @staticmethod
    def connection_status(exchange: str, status: Literal["connected", "disconnected", "error"]) -> "LogMessages.Message":
        """Connection status message."""
        if status == "connected":
            return LogMessages.Message(
                simple=f"Connected to {exchange}",
                technical=f"Exchange connection established: {exchange}",
            )
        elif status == "disconnected":
            return LogMessages.Message(
                simple=f"Disconnected from {exchange}",
                technical=f"Exchange connection lost: {exchange}",
            )
        else:
            return LogMessages.Message(
                simple=f"Problem connecting to {exchange}",
                technical=f"Exchange connection error: {exchange}",
            )

    @staticmethod
    def price_update(symbol: str, price: float) -> "LogMessages.Message":
        """Price update message."""
        return LogMessages.Message(
            simple=f"{symbol}: ${price:,.2f}",
            technical=f"Price update: {symbol}={price}",
        )

    @staticmethod
    def llm_analysis(symbol: str, sentiment: str, summary: str) -> "LogMessages.Message":
        """LLM analysis message."""
        return LogMessages.Message(
            simple=f"Market analysis: {sentiment} — {summary}",
            technical=f"LLM analysis: {symbol} sentiment={sentiment}",
        )
