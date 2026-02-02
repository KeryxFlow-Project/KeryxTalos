"""Tests for the parameter grid module."""

import pytest

from keryxflow.optimizer.grid import ParameterGrid, ParameterRange


class TestParameterRange:
    """Tests for ParameterRange dataclass."""

    def test_create_parameter_range(self):
        """Test creating a parameter range."""
        param = ParameterRange("rsi_period", [7, 14, 21], "oracle")

        assert param.name == "rsi_period"
        assert param.values == [7, 14, 21]
        assert param.category == "oracle"
        assert len(param) == 3

    def test_default_category(self):
        """Test default category is oracle."""
        param = ParameterRange("rsi_period", [7, 14, 21])

        assert param.category == "oracle"

    def test_empty_values_raises(self):
        """Test empty values list raises ValueError."""
        with pytest.raises(ValueError, match="must have at least one value"):
            ParameterRange("rsi_period", [])

    def test_invalid_category_raises(self):
        """Test invalid category raises ValueError."""
        with pytest.raises(ValueError, match="Category must be"):
            ParameterRange("rsi_period", [7, 14], "invalid")


class TestParameterGrid:
    """Tests for ParameterGrid class."""

    def test_empty_grid(self):
        """Test empty grid returns single empty combination."""
        grid = ParameterGrid()

        combinations = list(grid.combinations())

        assert len(combinations) == 1
        assert combinations[0] == {"oracle": {}, "risk": {}}

    def test_single_parameter(self):
        """Test grid with single parameter."""
        grid = ParameterGrid([
            ParameterRange("rsi_period", [7, 14, 21], "oracle"),
        ])

        combinations = list(grid.combinations())

        assert len(combinations) == 3
        assert len(grid) == 3
        assert combinations[0] == {"oracle": {"rsi_period": 7}, "risk": {}}
        assert combinations[1] == {"oracle": {"rsi_period": 14}, "risk": {}}
        assert combinations[2] == {"oracle": {"rsi_period": 21}, "risk": {}}

    def test_multiple_parameters(self):
        """Test grid with multiple parameters."""
        grid = ParameterGrid([
            ParameterRange("rsi_period", [7, 14], "oracle"),
            ParameterRange("risk_per_trade", [0.01, 0.02], "risk"),
        ])

        combinations = list(grid.combinations())

        assert len(combinations) == 4
        assert len(grid) == 4

        # Check all combinations are present
        expected = [
            {"oracle": {"rsi_period": 7}, "risk": {"risk_per_trade": 0.01}},
            {"oracle": {"rsi_period": 7}, "risk": {"risk_per_trade": 0.02}},
            {"oracle": {"rsi_period": 14}, "risk": {"risk_per_trade": 0.01}},
            {"oracle": {"rsi_period": 14}, "risk": {"risk_per_trade": 0.02}},
        ]
        assert combinations == expected

    def test_flat_combinations(self):
        """Test flat combinations without category grouping."""
        grid = ParameterGrid([
            ParameterRange("rsi_period", [7, 14], "oracle"),
            ParameterRange("risk_per_trade", [0.01, 0.02], "risk"),
        ])

        combinations = list(grid.flat_combinations())

        assert len(combinations) == 4
        assert combinations[0] == {"rsi_period": 7, "risk_per_trade": 0.01}
        assert combinations[3] == {"rsi_period": 14, "risk_per_trade": 0.02}

    def test_add_method(self):
        """Test adding parameters with add method."""
        grid = ParameterGrid()
        grid.add(ParameterRange("rsi_period", [7, 14], "oracle"))
        grid.add(ParameterRange("risk_per_trade", [0.01, 0.02], "risk"))

        assert len(grid) == 4
        assert len(grid.ranges) == 2

    def test_add_returns_self(self):
        """Test add method returns self for chaining."""
        grid = ParameterGrid()
        result = grid.add(ParameterRange("rsi_period", [7, 14], "oracle"))

        assert result is grid

    def test_repr(self):
        """Test string representation."""
        grid = ParameterGrid([
            ParameterRange("rsi_period", [7, 14, 21], "oracle"),
            ParameterRange("risk_per_trade", [0.01, 0.02], "risk"),
        ])

        repr_str = repr(grid)

        assert "rsi_period(3)" in repr_str
        assert "risk_per_trade(2)" in repr_str
        assert "6 combinations" in repr_str

    def test_quick_grid(self):
        """Test quick grid preset."""
        grid = ParameterGrid.quick_grid()

        assert len(grid) == 27  # 3 x 3 x 3
        assert len(grid.ranges) == 3

        param_names = [r.name for r in grid.ranges]
        assert "rsi_period" in param_names
        assert "risk_per_trade" in param_names
        assert "min_risk_reward" in param_names

    def test_default_oracle_grid(self):
        """Test default oracle grid preset."""
        grid = ParameterGrid.default_oracle_grid()

        assert len(grid) == 81  # 3 x 3 x 3 x 3
        assert all(r.category == "oracle" for r in grid.ranges)

    def test_default_risk_grid(self):
        """Test default risk grid preset."""
        grid = ParameterGrid.default_risk_grid()

        assert len(grid) == 27  # 3 x 3 x 3
        assert all(r.category == "risk" for r in grid.ranges)

    def test_large_grid_count(self):
        """Test counting combinations in large grid."""
        grid = ParameterGrid([
            ParameterRange("a", [1, 2, 3, 4, 5], "oracle"),
            ParameterRange("b", [1, 2, 3, 4, 5], "oracle"),
            ParameterRange("c", [1, 2, 3, 4, 5], "oracle"),
        ])

        assert len(grid) == 125  # 5 x 5 x 5
