"""KeryxFlow - A hybrid AI & quantitative trading engine."""

import atexit
import sys
import warnings

__version__ = "0.17.0"


# Suppress aiohttp/ccxt unclosed session warnings
# These occur because we use multiple asyncio.run() calls with Textual TUI
# The resources are still cleaned up by garbage collection
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Unclosed connector")
warnings.filterwarnings("ignore", message="binance requires")


class _StderrFilter:
    """Filter to suppress ccxt/aiohttp cleanup messages on stderr."""

    _suppress_patterns = [
        "binance requires to release",
        "Unclosed client session",
        "Unclosed connector",
        "client_session:",
        "connections:",
        "connector:",
    ]

    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        if not any(p in text for p in self._suppress_patterns):
            self._stream.write(text)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _apply_stderr_filter():
    """Apply or reapply stderr filter."""
    if not isinstance(sys.stderr, _StderrFilter):
        sys.stderr = _StderrFilter(sys.__stderr__)


# Apply filter immediately and register to reapply at exit
_apply_stderr_filter()
atexit.register(_apply_stderr_filter)
