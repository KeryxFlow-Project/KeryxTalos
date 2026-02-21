"""Tests for live trading safeguards."""

import pytest
from pydantic import SecretStr

from keryxflow.config import Settings
from keryxflow.core.safeguards import LiveTradingSafeguards, SafeguardCheck, SafeguardResult


class TestSafeguardCheck:
    """Tests for SafeguardCheck dataclass."""

    def test_create_passed_check(self):
        """Test creating a passed check."""
        check = SafeguardCheck(
            name="Test Check",
            passed=True,
            message="All good",
        )

        assert check.passed is True
        assert check.severity == "error"  # default

    def test_create_failed_check(self):
        """Test creating a failed check."""
        check = SafeguardCheck(
            name="Test Check",
            passed=False,
            message="Something wrong",
            severity="warning",
        )

        assert check.passed is False
        assert check.severity == "warning"


class TestSafeguardResult:
    """Tests for SafeguardResult dataclass."""

    def test_empty_result(self):
        """Test empty result."""
        result = SafeguardResult(passed=True, checks=[])

        assert result.passed is True
        assert len(result.checks) == 0

    def test_failed_checks_property(self):
        """Test failed_checks property."""
        checks = [
            SafeguardCheck(name="A", passed=True, message="ok"),
            SafeguardCheck(name="B", passed=False, message="fail"),
            SafeguardCheck(name="C", passed=True, message="ok"),
        ]
        result = SafeguardResult(passed=False, checks=checks)

        assert len(result.failed_checks) == 1
        assert result.failed_checks[0].name == "B"

    def test_warnings_and_errors(self):
        """Test warnings and errors properties."""
        checks = [
            SafeguardCheck(name="Error", passed=False, message="fail", severity="error"),
            SafeguardCheck(name="Warning", passed=False, message="warn", severity="warning"),
        ]
        result = SafeguardResult(passed=False, checks=checks)

        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.errors[0].name == "Error"
        assert result.warnings[0].name == "Warning"

    def test_summary_passed(self):
        """Test summary when all checks pass."""
        checks = [
            SafeguardCheck(name="A", passed=True, message="ok"),
            SafeguardCheck(name="B", passed=True, message="ok"),
        ]
        result = SafeguardResult(passed=True, checks=checks)

        summary = result.summary()
        assert "2 safeguard checks passed" in summary

    def test_summary_failed(self):
        """Test summary when checks fail."""
        checks = [
            SafeguardCheck(name="Error", passed=False, message="fail", severity="error"),
        ]
        result = SafeguardResult(passed=False, checks=checks)

        summary = result.summary()
        assert "1 errors" in summary
        assert "Error" in summary


class TestLiveTradingSafeguards:
    """Tests for LiveTradingSafeguards class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings()

    @pytest.fixture
    def safeguards(self, settings):
        """Create safeguards instance."""
        return LiveTradingSafeguards(settings)

    def test_init(self, safeguards):
        """Test initialization."""
        assert safeguards._min_paper_trades == 30
        assert safeguards._min_balance_usdt == 100.0

    def test_set_min_paper_trades(self, safeguards):
        """Test setting min paper trades."""
        safeguards.set_min_paper_trades(50)
        assert safeguards._min_paper_trades == 50

        safeguards.set_min_paper_trades(-10)
        assert safeguards._min_paper_trades == 0  # clamped

    def test_set_min_balance(self, safeguards):
        """Test setting min balance."""
        safeguards.set_min_balance(200.0)
        assert safeguards._min_balance_usdt == 200.0

        safeguards.set_min_balance(-50.0)
        assert safeguards._min_balance_usdt == 0.0  # clamped


class TestSafeguardsAPICredentials:
    """Tests for API credentials check."""

    @pytest.fixture
    def settings_no_creds(self, monkeypatch):
        """Settings without credentials."""
        import keryxflow.config as config_module

        monkeypatch.setenv("BINANCE_API_KEY", "")
        monkeypatch.setenv("BINANCE_API_SECRET", "")
        monkeypatch.setenv("KERYXFLOW_BINANCE_API_KEY", "")
        monkeypatch.setenv("KERYXFLOW_BINANCE_API_SECRET", "")
        config_module._settings = None
        return Settings()

    @pytest.fixture
    def settings_with_creds(self):
        """Settings with credentials."""
        settings = Settings()
        # These would normally come from .env
        settings.binance_api_key = SecretStr("test_key")
        settings.binance_api_secret = SecretStr("test_secret")
        return settings

    def test_no_credentials_fails(self, settings_no_creds):
        """Test that missing credentials fail check."""
        safeguards = LiveTradingSafeguards(settings_no_creds)
        check = safeguards._check_api_credentials()

        assert check.passed is False
        assert "not configured" in check.message.lower()

    def test_with_credentials_passes(self, settings_with_creds):
        """Test that valid credentials pass check."""
        safeguards = LiveTradingSafeguards(settings_with_creds)
        check = safeguards._check_api_credentials()

        assert check.passed is True


class TestSafeguardsBalanceCheck:
    """Tests for balance check."""

    @pytest.fixture
    def safeguards(self):
        """Create safeguards with default settings."""
        return LiveTradingSafeguards(Settings())

    def test_low_balance_fails(self, safeguards):
        """Test that low balance fails."""
        check = safeguards._check_balance_minimum(50.0)

        assert check.passed is False
        assert "below minimum" in check.message.lower()

    def test_sufficient_balance_passes(self, safeguards):
        """Test that sufficient balance passes."""
        check = safeguards._check_balance_minimum(500.0)

        assert check.passed is True


class TestSafeguardsPaperHistory:
    """Tests for paper trading history check."""

    @pytest.fixture
    def safeguards(self):
        """Create safeguards with default settings."""
        return LiveTradingSafeguards(Settings())

    def test_insufficient_trades_warning(self, safeguards):
        """Test that insufficient paper trades gives warning."""
        check = safeguards._check_paper_trading_history(10)

        assert check.passed is False
        assert check.severity == "warning"
        assert "10" in check.message

    def test_sufficient_trades_passes(self, safeguards):
        """Test that sufficient paper trades pass."""
        check = safeguards._check_paper_trading_history(50)

        assert check.passed is True


class TestSafeguardsCircuitBreaker:
    """Tests for circuit breaker check."""

    @pytest.fixture
    def safeguards(self):
        """Create safeguards with default settings."""
        return LiveTradingSafeguards(Settings())

    def test_active_cb_fails(self, safeguards):
        """Test that active circuit breaker fails."""
        check = safeguards._check_circuit_breaker(True)

        assert check.passed is False
        assert check.severity == "error"

    def test_inactive_cb_passes(self, safeguards):
        """Test that inactive circuit breaker passes."""
        check = safeguards._check_circuit_breaker(False)

        assert check.passed is True


class TestSafeguardsRiskSettings:
    """Tests for risk settings check."""

    def test_default_settings_pass(self):
        """Test that default risk settings pass."""
        settings = Settings()
        safeguards = LiveTradingSafeguards(settings)
        check = safeguards._check_risk_settings()

        assert check.passed is True

    def test_high_risk_per_trade_warning(self):
        """Test that high risk per trade gives warning."""
        settings = Settings()
        settings.risk.risk_per_trade = 0.05  # 5%
        safeguards = LiveTradingSafeguards(settings)
        check = safeguards._check_risk_settings()

        assert check.passed is False
        assert check.severity == "warning"
        assert "risk_per_trade" in check.message


class TestSafeguardsVerifyReady:
    """Integration tests for verify_ready_for_live."""

    @pytest.fixture
    def settings_with_creds(self):
        """Settings with credentials."""
        settings = Settings()
        settings.binance_api_key = SecretStr("test_key")
        settings.binance_api_secret = SecretStr("test_secret")
        settings.env = "production"
        return settings

    @pytest.mark.asyncio
    async def test_all_checks_pass(self, settings_with_creds):
        """Test when all checks pass."""
        safeguards = LiveTradingSafeguards(settings_with_creds)
        safeguards.set_min_paper_trades(0)  # Skip this check

        result = await safeguards.verify_ready_for_live(
            current_balance=500.0,
            paper_trade_count=50,
            circuit_breaker_active=False,
        )

        assert result.passed is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_missing_credentials_fails(self, monkeypatch):
        """Test that missing credentials cause failure."""
        import keryxflow.config as config_module

        monkeypatch.setenv("BINANCE_API_KEY", "")
        monkeypatch.setenv("BINANCE_API_SECRET", "")
        monkeypatch.setenv("KERYXFLOW_BINANCE_API_KEY", "")
        monkeypatch.setenv("KERYXFLOW_BINANCE_API_SECRET", "")
        config_module._settings = None
        settings = Settings()
        safeguards = LiveTradingSafeguards(settings)

        result = await safeguards.verify_ready_for_live(
            current_balance=500.0,
            paper_trade_count=50,
            circuit_breaker_active=False,
        )

        assert result.passed is False
        assert any(c.name == "API Credentials" for c in result.errors)

    @pytest.mark.asyncio
    async def test_circuit_breaker_fails(self, settings_with_creds):
        """Test that active circuit breaker causes failure."""
        safeguards = LiveTradingSafeguards(settings_with_creds)

        result = await safeguards.verify_ready_for_live(
            current_balance=500.0,
            paper_trade_count=50,
            circuit_breaker_active=True,
        )

        assert result.passed is False
        assert any(c.name == "Circuit Breaker" for c in result.errors)

    @pytest.mark.asyncio
    async def test_low_balance_fails(self, settings_with_creds):
        """Test that low balance causes failure."""
        safeguards = LiveTradingSafeguards(settings_with_creds)

        result = await safeguards.verify_ready_for_live(
            current_balance=10.0,  # Below minimum
            paper_trade_count=50,
            circuit_breaker_active=False,
        )

        assert result.passed is False
        assert any(c.name == "Minimum Balance" for c in result.errors)

    @pytest.mark.asyncio
    async def test_returns_all_checks(self, settings_with_creds):
        """Test that all checks are returned."""
        safeguards = LiveTradingSafeguards(settings_with_creds)

        result = await safeguards.verify_ready_for_live(
            current_balance=500.0,
            paper_trade_count=50,
            circuit_breaker_active=False,
        )

        check_names = {c.name for c in result.checks}
        expected = {
            "API Credentials",
            "Minimum Balance",
            "Paper Trading History",
            "Risk Settings",
            "Circuit Breaker",
            "Environment",
        }

        assert check_names == expected
