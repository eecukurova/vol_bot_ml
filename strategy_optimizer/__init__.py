"""
VWMA ARB Strategy Optimizer

A Python package for optimizing VWMA trading strategies for ARB.
"""

__version__ = "1.0.0"

from .src.config import get_config, Config
from .src.data.loader import create_data_loader
from .src.strategy.backtester import run_backtest, Backtester
from .src.strategy.vwma_arb_simple import VWMAARBSimpleStrategy
from .src.strategy.vwma_arb_enhanced import VWMAARBEnhancedStrategy
from .src.optimize.metrics import calculate_all_metrics
from .src.reporting.reporter import create_reporter, ResultsReporter
from .src.reporting.plots import create_visualizer, ResultsVisualizer

__all__ = [
    'get_config',
    'Config',
    'create_data_loader',
    'run_backtest',
    'Backtester',
    'VWMAARBSimpleStrategy',
    'VWMAARBEnhancedStrategy',
    'calculate_all_metrics',
    'create_reporter',
    'ResultsReporter',
    'create_visualizer',
    'ResultsVisualizer',
]
