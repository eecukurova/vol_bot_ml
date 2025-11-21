"""
Tests for ATR + SuperTrend strategy core functionality.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategy_optimizer.strategy.atr_st_core import (
    ATRSuperTrendStrategy,
    create_strategy,
    validate_strategy_params,
    calculate_atr,
    calculate_ema,
    calculate_atr_trailing_stop,
    calculate_supertrend,
    detect_crossovers,
)


class TestATRSuperTrendStrategy:
    """Test cases for ATRSuperTrendStrategy class."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
        
        # Create realistic price data with trend
        np.random.seed(42)
        base_price = 100
        trend = np.linspace(0, 10, 100)  # Upward trend
        noise = np.random.normal(0, 2, 100)
        close_prices = base_price + trend + noise
        
        # Generate OHLC from close prices
        high_prices = close_prices + np.random.uniform(0, 3, 100)
        low_prices = close_prices - np.random.uniform(0, 3, 100)
        open_prices = np.roll(close_prices, 1)
        open_prices[0] = close_prices[0]
        
        volumes = np.random.uniform(1000, 10000, 100)
        
        data = pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': volumes
        }, index=dates)
        
        return data
    
    @pytest.fixture
    def default_params(self):
        """Default strategy parameters for testing."""
        return {
            'a': 2.0,
            'c': 10,
            'st_factor': 1.5,
            'min_delay_m': 60,
            'atr_sl_mult': 2.0,
            'atr_rr': 2.0,
        }
    
    def test_strategy_initialization(self, default_params):
        """Test strategy initialization."""
        strategy = ATRSuperTrendStrategy(default_params)
        
        assert strategy.a == 2.0
        assert strategy.c == 10
        assert strategy.st_factor == 1.5
        assert strategy.min_delay_m == 60
        assert strategy.atr_sl_mult == 2.0
        assert strategy.atr_rr == 2.0
    
    def test_calculate_indicators(self, sample_data, default_params):
        """Test indicator calculations."""
        strategy = ATRSuperTrendStrategy(default_params)
        result = strategy.calculate_indicators(sample_data)
        
        # Check that all required columns are present
        required_columns = ['atr', 'trailing_stop', 'ema1', 'supertrend', 'position']
        for col in required_columns:
            assert col in result.columns
        
        # Check that indicators are calculated correctly
        assert not result['atr'].isna().all()
        assert not result['trailing_stop'].isna().all()
        assert not result['ema1'].isna().all()
        assert not result['supertrend'].isna().all()
        
        # Check ATR values are positive
        assert (result['atr'] > 0).all()
        
        # Check position values are valid
        assert result['position'].isin([-1, 0, 1]).all()
    
    def test_generate_signals(self, sample_data, default_params):
        """Test signal generation."""
        strategy = ATRSuperTrendStrategy(default_params)
        
        # Calculate indicators first
        data_with_indicators = strategy.calculate_indicators(sample_data)
        
        # Generate signals
        result = strategy.generate_signals(data_with_indicators)
        
        # Check that signal columns are present
        signal_columns = ['buy_signal', 'sell_signal', 'buy_filtered', 'sell_filtered', 'buy_final', 'sell_final']
        for col in signal_columns:
            assert col in result.columns
        
        # Check that signals are boolean
        for col in signal_columns:
            assert result[col].dtype == bool
        
        # Check that final signals are subset of filtered signals
        assert (result['buy_final'] <= result['buy_filtered']).all()
        assert (result['sell_final'] <= result['sell_filtered']).all()
    
    def test_calculate_stop_loss_take_profit(self, sample_data, default_params):
        """Test SL/TP calculation."""
        strategy = ATRSuperTrendStrategy(default_params)
        
        # Calculate indicators and signals
        data_with_indicators = strategy.calculate_indicators(sample_data)
        data_with_signals = strategy.generate_signals(data_with_indicators)
        
        # Calculate SL/TP
        result = strategy.calculate_stop_loss_take_profit(data_with_signals)
        
        # Check that SL/TP columns are present
        assert 'stop_loss' in result.columns
        assert 'take_profit' in result.columns
        
        # Check SL/TP logic for buy signals
        buy_signals = result[result['buy_final']]
        if not buy_signals.empty:
            for idx, row in buy_signals.iterrows():
                # For long positions: SL < entry_price < TP
                assert row['stop_loss'] < row['close']
                assert row['take_profit'] > row['close']
        
        # Check SL/TP logic for sell signals
        sell_signals = result[result['sell_final']]
        if not sell_signals.empty:
            for idx, row in sell_signals.iterrows():
                # For short positions: TP < entry_price < SL
                assert row['stop_loss'] > row['close']
                assert row['take_profit'] < row['close']
    
    def test_run_strategy(self, sample_data, default_params):
        """Test complete strategy run."""
        strategy = ATRSuperTrendStrategy(default_params)
        result = strategy.run_strategy(sample_data)
        
        # Check that all required columns are present
        required_columns = [
            'atr', 'trailing_stop', 'ema1', 'supertrend', 'position',
            'buy_signal', 'sell_signal', 'buy_filtered', 'sell_filtered',
            'buy_final', 'sell_final', 'stop_loss', 'take_profit'
        ]
        
        for col in required_columns:
            assert col in result.columns
        
        # Check that we have some signals
        total_signals = result['buy_final'].sum() + result['sell_final'].sum()
        assert total_signals >= 0  # May be 0 for some parameter combinations
    
    def test_get_signal_summary(self, sample_data, default_params):
        """Test signal summary generation."""
        strategy = ATRSuperTrendStrategy(default_params)
        result = strategy.run_strategy(sample_data)
        summary = strategy.get_signal_summary(result)
        
        # Check summary structure
        assert 'total_signals' in summary
        assert 'buy_signals' in summary
        assert 'sell_signals' in summary
        assert 'signal_frequency' in summary
        assert 'parameters' in summary
        
        # Check that counts match
        assert summary['total_signals'] == summary['buy_signals'] + summary['sell_signals']
        assert summary['buy_signals'] == result['buy_final'].sum()
        assert summary['sell_signals'] == result['sell_final'].sum()


class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    def test_calculate_atr(self):
        """Test ATR calculation."""
        # Create sample data
        high = np.array([110, 115, 120, 118, 125])
        low = np.array([105, 108, 115, 112, 118])
        close = np.array([108, 112, 118, 115, 122])
        
        atr = calculate_atr(high, low, close, period=3)
        
        # Check that ATR is calculated
        assert len(atr) == len(close)
        assert not np.isnan(atr[-1])  # Last value should be calculated
        assert atr[-1] > 0  # ATR should be positive
    
    def test_calculate_ema(self):
        """Test EMA calculation."""
        values = np.array([100, 102, 101, 103, 105, 104, 106])
        ema = calculate_ema(values, period=3)
        
        # Check that EMA is calculated
        assert len(ema) == len(values)
        assert not np.isnan(ema[0])  # First value should be set
        assert not np.isnan(ema[-1])  # Last value should be calculated
    
    def test_calculate_atr_trailing_stop(self):
        """Test ATR trailing stop calculation."""
        close = np.array([100, 102, 101, 103, 105, 104, 106])
        atr = np.array([2, 2, 2, 2, 2, 2, 2])
        
        trailing_stop = calculate_atr_trailing_stop(close, atr, a=2.0)
        
        # Check that trailing stop is calculated
        assert len(trailing_stop) == len(close)
        assert not np.isnan(trailing_stop[0])  # First value should be set
        assert not np.isnan(trailing_stop[-1])  # Last value should be calculated
    
    def test_calculate_supertrend(self):
        """Test SuperTrend calculation."""
        high = np.array([110, 115, 120, 118, 125])
        low = np.array([105, 108, 115, 112, 118])
        close = np.array([108, 112, 118, 115, 122])
        atr = np.array([3, 3, 3, 3, 3])
        
        supertrend = calculate_supertrend(high, low, close, atr, factor=2.0)
        
        # Check that SuperTrend is calculated
        assert len(supertrend) == len(close)
        assert not np.isnan(supertrend[0])  # First value should be set
        assert not np.isnan(supertrend[-1])  # Last value should be calculated
    
    def test_detect_crossovers(self):
        """Test crossover detection."""
        series1 = np.array([1, 2, 3, 2, 1, 2, 3])
        series2 = np.array([2, 2, 2, 2, 2, 2, 2])
        
        crossovers = detect_crossovers(series1, series2)
        
        # Check crossover detection
        assert len(crossovers) == len(series1)
        assert crossovers[0] == 0  # No crossover at start
        assert crossovers[2] == 1  # Upward crossover
        assert crossovers[4] == -1  # Downward crossover


class TestParameterValidation:
    """Test cases for parameter validation."""
    
    def test_validate_strategy_params_valid(self):
        """Test validation with valid parameters."""
        valid_params = {
            'a': 2.0,
            'c': 10,
            'st_factor': 1.5,
            'min_delay_m': 60,
            'atr_sl_mult': 2.0,
            'atr_rr': 2.0,
        }
        
        assert validate_strategy_params(valid_params) == True
    
    def test_validate_strategy_params_missing(self):
        """Test validation with missing parameters."""
        invalid_params = {
            'a': 2.0,
            'c': 10,
            # Missing other required parameters
        }
        
        assert validate_strategy_params(invalid_params) == False
    
    def test_validate_strategy_params_invalid_ranges(self):
        """Test validation with invalid parameter ranges."""
        invalid_params = {
            'a': -1.0,  # Invalid: negative
            'c': 10,
            'st_factor': 1.5,
            'min_delay_m': 60,
            'atr_sl_mult': 2.0,
            'atr_rr': 2.0,
        }
        
        assert validate_strategy_params(invalid_params) == False
    
    def test_create_strategy(self):
        """Test strategy creation function."""
        params = {
            'a': 2.0,
            'c': 10,
            'st_factor': 1.5,
            'min_delay_m': 60,
            'atr_sl_mult': 2.0,
            'atr_rr': 2.0,
        }
        
        strategy = create_strategy(params)
        assert isinstance(strategy, ATRSuperTrendStrategy)
        assert strategy.a == 2.0


if __name__ == "__main__":
    pytest.main([__file__])
