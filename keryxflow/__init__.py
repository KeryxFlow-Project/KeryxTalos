"""KeryxFlow - A hybrid AI & quantitative trading engine."""

import sys
import warnings

__version__ = "0.17.0"

# =============================================================================
# SILENCE AIOHTTP/CCXT WARNINGS
# These warnings are cosmetic and don't affect functionality.
# They occur because ccxt uses aiohttp internally and the cleanup
# messages are printed during garbage collection.
# =============================================================================

# Suppress Python warnings
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Unclosed connector")
warnings.filterwarnings("ignore", message="binance requires")

# Monkeypatch aiohttp to silence the __del__ warnings
try:
    import aiohttp

    # Silence ClientSession.__del__ warning
    _original_session_del = getattr(aiohttp.ClientSession, "__del__", None)

    def _silent_session_del(self):
        pass  # Do nothing - GC will clean up

    aiohttp.ClientSession.__del__ = _silent_session_del

    # Silence TCPConnector.__del__ warning
    _original_connector_del = getattr(aiohttp.TCPConnector, "__del__", None)

    def _silent_connector_del(self):
        pass  # Do nothing - GC will clean up

    aiohttp.TCPConnector.__del__ = _silent_connector_del

except ImportError:
    pass  # aiohttp not installed

# Monkeypatch ccxt to silence the destructor warning
try:
    import ccxt.async_support as ccxt_async

    _original_exchange_del = getattr(ccxt_async.Exchange, "__del__", None)

    def _silent_exchange_del(self):
        pass  # Do nothing - GC will clean up

    ccxt_async.Exchange.__del__ = _silent_exchange_del

except (ImportError, AttributeError):
    pass  # ccxt not installed or no __del__
