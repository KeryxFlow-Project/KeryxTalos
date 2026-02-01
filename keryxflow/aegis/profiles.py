"""Risk profiles for different user experience levels."""

from dataclasses import dataclass
from typing import Literal

from keryxflow.core.models import ExperienceLevel, RiskProfile


@dataclass(frozen=True)
class RiskProfileConfig:
    """Configuration for a risk profile."""

    name: str
    risk_per_trade: float
    max_daily_drawdown: float
    max_open_positions: int
    min_risk_reward: float
    stop_loss_type: Literal["atr", "fixed", "percentage"]
    atr_multiplier: float

    # User-facing descriptions
    description: str
    simple_description: str
    warning: str | None = None


# Pre-defined risk profiles
RISK_PROFILES: dict[RiskProfile, RiskProfileConfig] = {
    RiskProfile.CONSERVATIVE: RiskProfileConfig(
        name="Conservative",
        risk_per_trade=0.005,  # 0.5%
        max_daily_drawdown=0.02,  # 2%
        max_open_positions=2,
        min_risk_reward=2.0,
        stop_loss_type="atr",
        atr_multiplier=2.5,
        description="Safety first. Slow and steady growth with minimal risk exposure.",
        simple_description="For learning. Very small trades, quick stops on losses.",
        warning=None,
    ),
    RiskProfile.BALANCED: RiskProfileConfig(
        name="Balanced",
        risk_per_trade=0.01,  # 1%
        max_daily_drawdown=0.05,  # 5%
        max_open_positions=3,
        min_risk_reward=1.5,
        stop_loss_type="atr",
        atr_multiplier=2.0,
        description="Moderate risk for moderate returns. Good balance of safety and growth.",
        simple_description="For steady growth. Medium-sized trades with reasonable stops.",
        warning=None,
    ),
    RiskProfile.AGGRESSIVE: RiskProfileConfig(
        name="Aggressive",
        risk_per_trade=0.02,  # 2%
        max_daily_drawdown=0.10,  # 10%
        max_open_positions=5,
        min_risk_reward=1.0,
        stop_loss_type="atr",
        atr_multiplier=1.5,
        description="Higher risk tolerance for growth. Larger position sizes and more trades.",
        simple_description="For growth. Larger trades, accepts bigger swings.",
        warning="Higher risk means higher potential losses. Only use if you understand the risks.",
    ),
}


# Experience level to suggested risk profile mapping
EXPERIENCE_TO_PROFILE: dict[ExperienceLevel, RiskProfile] = {
    ExperienceLevel.BEGINNER: RiskProfile.CONSERVATIVE,
    ExperienceLevel.INTERMEDIATE: RiskProfile.BALANCED,
    ExperienceLevel.ADVANCED: RiskProfile.BALANCED,  # Default, but can choose
}


@dataclass(frozen=True)
class ExperienceLevelConfig:
    """Configuration for an experience level."""

    name: str
    description: str
    suggested_profile: RiskProfile
    show_technical_details: bool
    log_verbosity: Literal["simple", "mixed", "technical"]
    show_help_hints: bool


# Experience level configurations
EXPERIENCE_LEVELS: dict[ExperienceLevel, ExperienceLevelConfig] = {
    ExperienceLevel.BEGINNER: ExperienceLevelConfig(
        name="Beginner",
        description="I'm completely new to trading",
        suggested_profile=RiskProfile.CONSERVATIVE,
        show_technical_details=False,
        log_verbosity="simple",
        show_help_hints=True,
    ),
    ExperienceLevel.INTERMEDIATE: ExperienceLevelConfig(
        name="Intermediate",
        description="I know the basics (buy low, sell high)",
        suggested_profile=RiskProfile.BALANCED,
        show_technical_details=True,
        log_verbosity="mixed",
        show_help_hints=True,
    ),
    ExperienceLevel.ADVANCED: ExperienceLevelConfig(
        name="Advanced",
        description="I'm an experienced trader",
        suggested_profile=RiskProfile.BALANCED,
        show_technical_details=True,
        log_verbosity="technical",
        show_help_hints=False,
    ),
}


def get_risk_profile(profile: RiskProfile | str) -> RiskProfileConfig:
    """
    Get a risk profile configuration.

    Args:
        profile: The risk profile to get

    Returns:
        RiskProfileConfig for the profile
    """
    if isinstance(profile, str):
        profile = RiskProfile(profile.lower())
    return RISK_PROFILES[profile]


def get_experience_config(level: ExperienceLevel | str) -> ExperienceLevelConfig:
    """
    Get an experience level configuration.

    Args:
        level: The experience level to get

    Returns:
        ExperienceLevelConfig for the level
    """
    if isinstance(level, str):
        level = ExperienceLevel(level.lower())
    return EXPERIENCE_LEVELS[level]


def get_suggested_profile(level: ExperienceLevel) -> RiskProfile:
    """
    Get the suggested risk profile for an experience level.

    Args:
        level: The experience level

    Returns:
        Suggested RiskProfile
    """
    return EXPERIENCE_TO_PROFILE[level]


def format_profile_summary(profile: RiskProfile) -> str:
    """
    Format a risk profile summary for display.

    Args:
        profile: The risk profile to format

    Returns:
        Formatted string summary
    """
    config = get_risk_profile(profile)

    lines = [
        f"📊 {config.name} Profile",
        "",
        f"   {config.simple_description}",
        "",
        f"   • Risk per trade: {config.risk_per_trade:.1%}",
        f"   • Daily loss limit: {config.max_daily_drawdown:.0%}",
        f"   • Max open trades: {config.max_open_positions}",
    ]

    if config.warning:
        lines.extend([
            "",
            f"   ⚠️ {config.warning}",
        ])

    return "\n".join(lines)


def validate_profile_for_balance(
    profile: RiskProfile,
    balance: float,
    min_trade_size: float = 10.0,
) -> tuple[bool, str]:
    """
    Validate if a risk profile is suitable for a given balance.

    Args:
        profile: The risk profile to validate
        balance: The account balance
        min_trade_size: Minimum trade size allowed

    Returns:
        Tuple of (is_valid, message)
    """
    config = get_risk_profile(profile)
    max_loss_per_trade = balance * config.risk_per_trade

    if max_loss_per_trade < min_trade_size:
        return (
            False,
            f"With ${balance:,.0f} balance, {config.name} profile would risk "
            f"${max_loss_per_trade:.2f} per trade, which is below the "
            f"minimum trade size of ${min_trade_size:.2f}. "
            f"Consider a larger balance or a more aggressive profile.",
        )

    return (True, f"Profile is suitable for ${balance:,.0f} balance.")
