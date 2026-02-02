"""Live trading safeguards - Verification checks before enabling live mode."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from keryxflow.core.logging import get_logger

if TYPE_CHECKING:
    from keryxflow.config import Settings

logger = get_logger(__name__)


@dataclass
class SafeguardCheck:
    """Result of a single safeguard check."""

    name: str
    passed: bool
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class SafeguardResult:
    """Result of all safeguard checks."""

    passed: bool
    checks: list[SafeguardCheck] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def failed_checks(self) -> list[SafeguardCheck]:
        """Get list of failed checks."""
        return [c for c in self.checks if not c.passed]

    @property
    def warnings(self) -> list[SafeguardCheck]:
        """Get list of warning checks."""
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    @property
    def errors(self) -> list[SafeguardCheck]:
        """Get list of error checks."""
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    def summary(self) -> str:
        """Get human-readable summary."""
        if self.passed:
            return f"All {len(self.checks)} safeguard checks passed."

        lines = [f"Safeguard checks failed: {len(self.errors)} errors, {len(self.warnings)} warnings"]
        for check in self.failed_checks:
            icon = "!" if check.severity == "error" else "?"
            lines.append(f"  [{icon}] {check.name}: {check.message}")
        return "\n".join(lines)


class LiveTradingSafeguards:
    """Verification checks before enabling live trading mode.

    These checks help prevent accidental losses by ensuring the system
    is properly configured before trading with real money.
    """

    def __init__(self, settings: "Settings"):
        """Initialize safeguards.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._min_paper_trades = 30
        self._min_balance_usdt = 100.0

    async def verify_ready_for_live(
        self,
        current_balance: float = 0.0,
        paper_trade_count: int = 0,
        circuit_breaker_active: bool = False,
    ) -> SafeguardResult:
        """Run all safeguard checks for live trading.

        Args:
            current_balance: Current exchange balance in USDT
            paper_trade_count: Number of completed paper trades
            circuit_breaker_active: Whether circuit breaker is currently tripped

        Returns:
            SafeguardResult with all check results
        """
        checks: list[SafeguardCheck] = []

        # Check 1: API Credentials
        checks.append(self._check_api_credentials())

        # Check 2: Minimum Balance
        checks.append(self._check_balance_minimum(current_balance))

        # Check 3: Paper Trading History
        checks.append(self._check_paper_trading_history(paper_trade_count))

        # Check 4: Risk Settings
        checks.append(self._check_risk_settings())

        # Check 5: Circuit Breaker
        checks.append(self._check_circuit_breaker(circuit_breaker_active))

        # Check 6: Environment
        checks.append(self._check_environment())

        # Overall result - fail if any error-level check failed
        errors = [c for c in checks if not c.passed and c.severity == "error"]
        passed = len(errors) == 0

        result = SafeguardResult(passed=passed, checks=checks)

        if passed:
            logger.info("live_safeguards_passed", checks_count=len(checks))
        else:
            logger.warning(
                "live_safeguards_failed",
                errors=len(errors),
                warnings=len(result.warnings),
            )

        return result

    def _check_api_credentials(self) -> SafeguardCheck:
        """Check if Binance API credentials are configured."""
        if not self.settings.has_binance_credentials:
            return SafeguardCheck(
                name="API Credentials",
                passed=False,
                message="Binance API key and secret not configured. Set BINANCE_API_KEY and BINANCE_API_SECRET in .env",
                severity="error",
            )

        return SafeguardCheck(
            name="API Credentials",
            passed=True,
            message="Binance credentials configured",
        )

    def _check_balance_minimum(self, current_balance: float) -> SafeguardCheck:
        """Check if exchange balance meets minimum requirement."""
        if current_balance < self._min_balance_usdt:
            return SafeguardCheck(
                name="Minimum Balance",
                passed=False,
                message=f"Balance {current_balance:.2f} USDT below minimum {self._min_balance_usdt:.2f} USDT",
                severity="error",
            )

        return SafeguardCheck(
            name="Minimum Balance",
            passed=True,
            message=f"Balance {current_balance:.2f} USDT meets minimum requirement",
        )

    def _check_paper_trading_history(self, paper_trade_count: int) -> SafeguardCheck:
        """Check if user has enough paper trading experience."""
        if paper_trade_count < self._min_paper_trades:
            return SafeguardCheck(
                name="Paper Trading History",
                passed=False,
                message=f"Only {paper_trade_count} paper trades completed. Minimum {self._min_paper_trades} required",
                severity="warning",
            )

        return SafeguardCheck(
            name="Paper Trading History",
            passed=True,
            message=f"{paper_trade_count} paper trades completed",
        )

    def _check_risk_settings(self) -> SafeguardCheck:
        """Check if risk settings are conservative enough for live trading."""
        issues = []

        # Risk per trade should not be too high
        if self.settings.risk.risk_per_trade > 0.02:
            issues.append(f"risk_per_trade={self.settings.risk.risk_per_trade:.1%} is high (recommended: 1-2%)")

        # Daily drawdown should have a limit
        if self.settings.risk.max_daily_drawdown > 0.10:
            issues.append(f"max_daily_drawdown={self.settings.risk.max_daily_drawdown:.0%} is high (recommended: 5-10%)")

        # Must have stop loss
        if self.settings.risk.stop_loss_type not in ("atr", "fixed", "percentage"):
            issues.append("stop_loss_type not configured")

        if issues:
            return SafeguardCheck(
                name="Risk Settings",
                passed=False,
                message="; ".join(issues),
                severity="warning",
            )

        return SafeguardCheck(
            name="Risk Settings",
            passed=True,
            message="Risk parameters within safe limits",
        )

    def _check_circuit_breaker(self, circuit_breaker_active: bool) -> SafeguardCheck:
        """Check if circuit breaker is in a safe state."""
        if circuit_breaker_active:
            return SafeguardCheck(
                name="Circuit Breaker",
                passed=False,
                message="Circuit breaker is currently tripped. Reset required before live trading",
                severity="error",
            )

        return SafeguardCheck(
            name="Circuit Breaker",
            passed=True,
            message="Circuit breaker not active",
        )

    def _check_environment(self) -> SafeguardCheck:
        """Check environment configuration."""
        if self.settings.env == "development":
            return SafeguardCheck(
                name="Environment",
                passed=False,
                message="Running in development mode. Set env=production for live trading",
                severity="warning",
            )

        return SafeguardCheck(
            name="Environment",
            passed=True,
            message="Running in production mode",
        )

    def set_min_paper_trades(self, count: int) -> None:
        """Set minimum paper trades requirement.

        Args:
            count: Minimum number of paper trades required
        """
        self._min_paper_trades = max(0, count)

    def set_min_balance(self, amount: float) -> None:
        """Set minimum balance requirement.

        Args:
            amount: Minimum balance in USDT
        """
        self._min_balance_usdt = max(0.0, amount)
