"""
Strategy module for ATR + SuperTrend Strategy Optimizer.

This module provides the core strategy implementation and backtesting functionality.
"""

from .atr_st_core import ATRSuperTrendStrategy, create_strategy, validate_strategy_params
from .backtester import Backtester, run_backtest, Trade, BacktestResult

__all__ = [
    'ATRSuperTrendStrategy',
    'create_strategy',
    'validate_strategy_params',
    'Backtester',
    'run_backtest',
    'Trade',
    'BacktestResult',
]
