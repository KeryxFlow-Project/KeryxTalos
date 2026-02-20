"""Tests for ExchangeAdapter ABC and factory function."""

from unittest.mock import MagicMock, patch

import pytest

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.client import ExchangeClient, get_exchange_adapter
from keryxflow.exchange.kraken import KrakenAdapter
from keryxflow.exchange.okx import OKXAdapter


class TestExchangeAdapterABC:
    """Tests for ExchangeAdapter abstract base class."""

    def test_cannot_instantiate_directly(self):
        """Test that ExchangeAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ExchangeAdapter()

    def test_exchange_client_is_subclass(self):
        """Test that ExchangeClient is a subclass of ExchangeAdapter."""
        assert issubclass(ExchangeClient, ExchangeAdapter)

    def test_kraken_adapter_is_subclass(self):
        """Test that KrakenAdapter is a subclass of ExchangeAdapter."""
        assert issubclass(KrakenAdapter, ExchangeAdapter)

    def test_okx_adapter_is_subclass(self):
        """Test that OKXAdapter is a subclass of ExchangeAdapter."""
        assert issubclass(OKXAdapter, ExchangeAdapter)

    def test_exchange_client_can_be_instantiated(self):
        """Test that ExchangeClient (concrete) can be instantiated."""
        client = ExchangeClient(sandbox=True)
        assert isinstance(client, ExchangeAdapter)

    def test_kraken_adapter_can_be_instantiated(self):
        """Test that KrakenAdapter (concrete) can be instantiated."""
        adapter = KrakenAdapter(sandbox=True)
        assert isinstance(adapter, ExchangeAdapter)

    def test_okx_adapter_can_be_instantiated(self):
        """Test that OKXAdapter (concrete) can be instantiated."""
        adapter = OKXAdapter(sandbox=True)
        assert isinstance(adapter, ExchangeAdapter)


class TestGetExchangeAdapter:
    """Tests for get_exchange_adapter factory function."""

    def _create_mock_settings(self, exchange: str) -> MagicMock:
        """Create a mock settings object with the given exchange."""
        mock_settings = MagicMock()
        mock_settings.system.exchange = exchange
        return mock_settings

    def test_returns_exchange_client_for_binance(self):
        """Test factory returns ExchangeClient for 'binance'."""
        import keryxflow.exchange.client as client_module

        client_module._client = None

        with patch(
            "keryxflow.exchange.client.get_settings",
            return_value=self._create_mock_settings("binance"),
        ):
            adapter = get_exchange_adapter(sandbox=True)
            assert isinstance(adapter, ExchangeClient)

    def test_returns_kraken_adapter_for_kraken(self):
        """Test factory returns KrakenAdapter for 'kraken'."""
        import keryxflow.exchange.client as client_module
        import keryxflow.exchange.kraken as kraken_module

        client_module._client = None
        kraken_module._kraken_client = None

        with patch(
            "keryxflow.exchange.client.get_settings",
            return_value=self._create_mock_settings("kraken"),
        ):
            adapter = get_exchange_adapter(sandbox=True)
            assert isinstance(adapter, KrakenAdapter)

    def test_returns_okx_adapter_for_okx(self):
        """Test factory returns OKXAdapter for 'okx'."""
        import keryxflow.exchange.client as client_module
        import keryxflow.exchange.okx as okx_module

        client_module._client = None
        okx_module._okx_client = None

        with patch(
            "keryxflow.exchange.client.get_settings",
            return_value=self._create_mock_settings("okx"),
        ):
            adapter = get_exchange_adapter(sandbox=True)
            assert isinstance(adapter, OKXAdapter)

    def test_raises_for_unsupported_exchange(self):
        """Test factory raises ValueError for unsupported exchange."""
        with (
            patch(
                "keryxflow.exchange.client.get_settings",
                return_value=self._create_mock_settings("unsupported"),
            ),
            pytest.raises(ValueError, match="Unsupported exchange: unsupported"),
        ):
            get_exchange_adapter(sandbox=True)

    def test_case_insensitive_exchange_name(self):
        """Test that exchange name matching is case-insensitive."""
        import keryxflow.exchange.kraken as kraken_module

        kraken_module._kraken_client = None

        with patch(
            "keryxflow.exchange.client.get_settings",
            return_value=self._create_mock_settings("KRAKEN"),
        ):
            adapter = get_exchange_adapter(sandbox=True)
            assert isinstance(adapter, KrakenAdapter)

    def test_sandbox_parameter_passed_to_adapter(self):
        """Test that sandbox parameter is passed to the adapter."""
        import keryxflow.exchange.client as client_module

        client_module._client = None

        with patch(
            "keryxflow.exchange.client.get_settings",
            return_value=self._create_mock_settings("binance"),
        ):
            adapter = get_exchange_adapter(sandbox=False)
            assert adapter._sandbox is False


class TestExchangeAdapterProtocol:
    """Tests for ExchangeAdapter implementing OrderExecutor protocol."""

    def test_exchange_client_has_execute_market_order(self):
        """Test ExchangeClient has execute_market_order method."""
        client = ExchangeClient(sandbox=True)
        assert hasattr(client, "execute_market_order")
        assert callable(client.execute_market_order)

    def test_exchange_client_has_update_price(self):
        """Test ExchangeClient has update_price method."""
        client = ExchangeClient(sandbox=True)
        assert hasattr(client, "update_price")
        assert callable(client.update_price)

    def test_exchange_client_has_get_price(self):
        """Test ExchangeClient has get_price method."""
        client = ExchangeClient(sandbox=True)
        assert hasattr(client, "get_price")
        assert callable(client.get_price)

    def test_kraken_adapter_has_execute_market_order(self):
        """Test KrakenAdapter has execute_market_order method."""
        adapter = KrakenAdapter(sandbox=True)
        assert hasattr(adapter, "execute_market_order")
        assert callable(adapter.execute_market_order)

    def test_okx_adapter_has_execute_market_order(self):
        """Test OKXAdapter has execute_market_order method."""
        adapter = OKXAdapter(sandbox=True)
        assert hasattr(adapter, "execute_market_order")
        assert callable(adapter.execute_market_order)
