"""
Data module for ATR + SuperTrend Strategy Optimizer.

This module provides data fetching, caching, and management functionality.
"""

from .ccxt_client import CCXTClient, create_client_from_config
from .cache import DataCache, ohlcv_to_dataframe, merge_ohlcv_data
from .loader import DataLoader, create_data_loader, get_historical_data

__all__ = [
    'CCXTClient',
    'create_client_from_config',
    'DataCache',
    'ohlcv_to_dataframe',
    'merge_ohlcv_data',
    'DataLoader',
    'create_data_loader',
    'get_historical_data',
]
