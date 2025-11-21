"""
NASDAQ Strategy Optimizer

A comprehensive Python package for optimizing trading strategies on NASDAQ stocks
with Yahoo Finance data integration, grid search optimization, and walk-forward analysis.
"""

__version__ = "1.0.0"
__author__ = "Quant Developer"
__email__ = "dev@example.com"

from .src.config import get_config, Config
from .src.data.loader import create_data_loader
from .src.strategy.atr_st_core import create_strategy, ATRSuperTrendStrategy
from .src.strategy.backtester import run_backtest, Backtester
from .src.optimize.grid_search import run_grid_search, GridSearchOptimizer
from .src.optimize.walk_forward import run_walk_forward, WalkForwardOptimizer
from .src.optimize.metrics import calculate_all_metrics
from .src.reporting.reporter import create_reporter, ResultsReporter
from .src.reporting.plots import create_visualizer, ResultsVisualizer

__all__ = [
    'get_config',
    'Config',
    'create_data_loader',
    'create_strategy',
    'ATRSuperTrendStrategy',
    'run_backtest',
    'Backtester',
    'run_grid_search',
    'GridSearchOptimizer',
    'run_walk_forward',
    'WalkForwardOptimizer',
    'calculate_all_metrics',
    'create_reporter',
    'ResultsReporter',
    'create_visualizer',
    'ResultsVisualizer',
]
