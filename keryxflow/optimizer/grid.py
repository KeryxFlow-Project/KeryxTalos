"""Parameter grid generation for optimization."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import product
from typing import Any


@dataclass
class ParameterRange:
    """Define range for a parameter to optimize.

    Attributes:
        name: Parameter name (e.g., 'rsi_period', 'risk_per_trade')
        values: List of discrete values to test
        category: Parameter category ('oracle' or 'risk')
    """

    name: str
    values: list[Any]
    category: str = "oracle"  # 'oracle' or 'risk'

    def __post_init__(self):
        """Validate parameter range."""
        if not self.values:
            raise ValueError(f"Parameter '{self.name}' must have at least one value")

        if self.category not in ("oracle", "risk"):
            raise ValueError(f"Category must be 'oracle' or 'risk', got '{self.category}'")

    def __len__(self) -> int:
        """Return number of values."""
        return len(self.values)


@dataclass
class ParameterGrid:
    """Grid of parameter combinations to test.

    Example:
        grid = ParameterGrid([
            ParameterRange("rsi_period", [7, 14, 21], "oracle"),
            ParameterRange("risk_per_trade", [0.005, 0.01, 0.02], "risk"),
        ])

        for params in grid.combinations():
            print(params)
            # {'oracle': {'rsi_period': 7}, 'risk': {'risk_per_trade': 0.005}}
            # {'oracle': {'rsi_period': 7}, 'risk': {'risk_per_trade': 0.01}}
            # ...
    """

    ranges: list[ParameterRange] = field(default_factory=list)

    def add(self, param_range: ParameterRange) -> "ParameterGrid":
        """Add a parameter range to the grid.

        Returns self for chaining.
        """
        self.ranges.append(param_range)
        return self

    def combinations(self) -> Iterator[dict[str, dict[str, Any]]]:
        """Generate all parameter combinations.

        Yields:
            Dict with 'oracle' and 'risk' keys containing parameter dicts.
        """
        if not self.ranges:
            yield {"oracle": {}, "risk": {}}
            return

        # Get names, values, and categories
        names = [r.name for r in self.ranges]
        value_lists = [r.values for r in self.ranges]
        categories = [r.category for r in self.ranges]

        # Generate all combinations
        for combination in product(*value_lists):
            result: dict[str, dict[str, Any]] = {"oracle": {}, "risk": {}}

            for name, value, category in zip(names, combination, categories, strict=True):
                result[category][name] = value

            yield result

    def flat_combinations(self) -> Iterator[dict[str, Any]]:
        """Generate flat parameter combinations (without category grouping).

        Yields:
            Dict with parameter name -> value pairs.
        """
        if not self.ranges:
            yield {}
            return

        names = [r.name for r in self.ranges]
        value_lists = [r.values for r in self.ranges]

        for combination in product(*value_lists):
            yield dict(zip(names, combination, strict=True))

    def __len__(self) -> int:
        """Return total number of combinations."""
        if not self.ranges:
            return 1

        total = 1
        for r in self.ranges:
            total *= len(r)
        return total

    def __repr__(self) -> str:
        """Return string representation."""
        params = ", ".join(f"{r.name}({len(r)})" for r in self.ranges)
        return f"ParameterGrid({params}) -> {len(self)} combinations"

    @classmethod
    def default_oracle_grid(cls) -> "ParameterGrid":
        """Create a default grid for oracle (technical analysis) parameters.

        Returns grid with:
            - rsi_period: [7, 14, 21]
            - macd_fast: [8, 12, 15]
            - macd_slow: [21, 26, 30]
            - bbands_std: [1.5, 2.0, 2.5]
        """
        return cls(
            [
                ParameterRange("rsi_period", [7, 14, 21], "oracle"),
                ParameterRange("macd_fast", [8, 12, 15], "oracle"),
                ParameterRange("macd_slow", [21, 26, 30], "oracle"),
                ParameterRange("bbands_std", [1.5, 2.0, 2.5], "oracle"),
            ]
        )

    @classmethod
    def default_risk_grid(cls) -> "ParameterGrid":
        """Create a default grid for risk parameters.

        Returns grid with:
            - risk_per_trade: [0.005, 0.01, 0.02]
            - min_risk_reward: [1.0, 1.5, 2.0]
            - atr_multiplier: [1.5, 2.0, 2.5]
        """
        return cls(
            [
                ParameterRange("risk_per_trade", [0.005, 0.01, 0.02], "risk"),
                ParameterRange("min_risk_reward", [1.0, 1.5, 2.0], "risk"),
                ParameterRange("atr_multiplier", [1.5, 2.0, 2.5], "risk"),
            ]
        )

    @classmethod
    def quick_grid(cls) -> "ParameterGrid":
        """Create a quick 9-combination grid for testing.

        Returns grid with:
            - rsi_period: [7, 14, 21]
            - risk_per_trade: [0.005, 0.01, 0.02]
            - min_risk_reward: [1.0, 1.5, 2.0]
        """
        return cls(
            [
                ParameterRange("rsi_period", [7, 14, 21], "oracle"),
                ParameterRange("risk_per_trade", [0.005, 0.01, 0.02], "risk"),
                ParameterRange("min_risk_reward", [1.0, 1.5, 2.0], "risk"),
            ]
        )
