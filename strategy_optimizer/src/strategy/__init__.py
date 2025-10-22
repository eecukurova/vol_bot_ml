"""
Strategy module for ATR + SuperTrend Strategy Optimizer.

This module provides the core strategy implementation and backtesting functionality.
"""

from .atr_st_core import ATRSuperTrendStrategy, create_strategy, validate_strategy_params
from .volensy_macd_trend import VolensyMacdTrendStrategy, create_strategy as create_volensy_strategy
from .atr_supertrend import ATRSuperTrendStrategy as ATRSuperTrendStrategyNew, create_strategy as create_atr_supertrend_strategy
from .backtester import Backtester, run_backtest, Trade, BacktestResult

__all__ = [
    'ATRSuperTrendStrategy',
    'VolensyMacdTrendStrategy',
    'ATRSuperTrendStrategyNew',
    'create_strategy',
    'create_volensy_strategy',
    'create_atr_supertrend_strategy',
    'validate_strategy_params',
    'Backtester',
    'run_backtest',
    'Trade',
    'BacktestResult',
]
