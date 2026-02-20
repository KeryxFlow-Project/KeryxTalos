"""Hermes widgets for the TUI."""

from keryxflow.hermes.widgets.aegis import AegisWidget
from keryxflow.hermes.widgets.agent import AgentWidget
from keryxflow.hermes.widgets.backtest import BacktestResultsWidget
from keryxflow.hermes.widgets.balance import BalanceWidget
from keryxflow.hermes.widgets.chart import ChartWidget
from keryxflow.hermes.widgets.help import HelpModal
from keryxflow.hermes.widgets.logs import LogsWidget
from keryxflow.hermes.widgets.oracle import OracleWidget
from keryxflow.hermes.widgets.positions import PositionsWidget
from keryxflow.hermes.widgets.splash import SplashScreen
from keryxflow.hermes.widgets.stats import StatsWidget

__all__ = [
    "AgentWidget",
    "BacktestResultsWidget",
    "BalanceWidget",
    "ChartWidget",
    "PositionsWidget",
    "OracleWidget",
    "AegisWidget",
    "StatsWidget",
    "LogsWidget",
    "HelpModal",
    "SplashScreen",
]
