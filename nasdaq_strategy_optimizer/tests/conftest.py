"""
Test configuration for pytest.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Configure logging for tests
import logging
logging.basicConfig(level=logging.WARNING)

# Test fixtures and utilities
@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    import pandas as pd
    import numpy as np
    
    dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
    
    # Create realistic price data
    np.random.seed(42)
    base_price = 100
    trend = np.linspace(0, 10, 100)
    noise = np.random.normal(0, 1, 100)
    close_prices = base_price + trend + noise
    
    high_prices = close_prices + np.random.uniform(0, 2, 100)
    low_prices = close_prices - np.random.uniform(0, 2, 100)
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = close_prices[0]
    
    volumes = np.random.uniform(1000, 10000, 100)
    
    return pd.DataFrame({
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    }, index=dates)

@pytest.fixture
def sample_strategy_params():
    """Sample strategy parameters for testing."""
    return {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 60,
        'atr_sl_mult': 2.0,
        'atr_rr': 2.0,
    }

@pytest.fixture
def sample_optimization_results():
    """Sample optimization results for testing."""
    return [
        {
            'symbol': 'BTC/USDT',
            'timeframe': '1h',
            'params': {'a': 2.0, 'c': 10, 'st_factor': 1.5},
            'metrics': {
                'profit_factor': 2.5,
                'total_return_pct': 15.0,
                'max_drawdown_pct': -5.0,
                'sharpe_ratio': 1.8,
                'num_trades': 25
            },
            'num_trades': 25,
            'success': True
        },
        {
            'symbol': 'ETH/USDT',
            'timeframe': '4h',
            'params': {'a': 1.5, 'c': 14, 'st_factor': 2.0},
            'metrics': {
                'profit_factor': 1.8,
                'total_return_pct': 12.0,
                'max_drawdown_pct': -8.0,
                'sharpe_ratio': 1.2,
                'num_trades': 15
            },
            'num_trades': 15,
            'success': True
        }
    ]

# Test markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
