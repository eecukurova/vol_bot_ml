"""
Test technical indicators calculations
"""
import pytest
import pandas as pd
import numpy as np
from core.data import TechnicalIndicators


class TestTechnicalIndicators:
    """Test technical indicator calculations"""
    
    def test_rsi_calculation(self):
        """Test RSI calculation with known values"""
        # Create test data with known RSI result
        prices = pd.Series([44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.85, 46.08, 45.89, 46.03, 46.83, 46.69, 46.45, 46.30])
        
        rsi = TechnicalIndicators.calculate_rsi(prices, period=14)
        
        # RSI should be between 0 and 100
        assert 0 <= rsi <= 100
        
        # With this data, RSI should be around 70-80 (overbought)
        assert rsi > 50
    
    def test_rsi_insufficient_data(self):
        """Test RSI with insufficient data"""
        prices = pd.Series([44, 44.34, 44.09])  # Only 3 values, need 15 for RSI(14)
        
        rsi = TechnicalIndicators.calculate_rsi(prices, period=14)
        
        # Should return 0 for insufficient data
        assert rsi == 0.0
    
    def test_adx_calculation(self):
        """Test ADX calculation"""
        # Create test OHLC data
        high = pd.Series([48.70, 48.72, 48.90, 48.87, 48.82, 49.05, 49.20, 49.35, 49.92, 50.19, 50.12, 49.66, 49.88, 50.19, 50.36])
        low = pd.Series([47.79, 48.14, 48.39, 48.37, 48.24, 48.64, 48.94, 48.86, 49.50, 49.87, 49.20, 48.90, 49.43, 49.73, 49.26])
        close = pd.Series([48.16, 48.61, 48.75, 48.63, 48.74, 49.03, 49.07, 49.32, 49.91, 50.13, 49.53, 49.50, 49.75, 50.30, 50.14])
        
        adx = TechnicalIndicators.calculate_adx(high, low, close, period=14)
        
        # ADX should be between 0 and 100
        assert 0 <= adx <= 100
    
    def test_adx_insufficient_data(self):
        """Test ADX with insufficient data"""
        high = pd.Series([48.70, 48.72, 48.90])
        low = pd.Series([47.79, 48.14, 48.39])
        close = pd.Series([48.16, 48.61, 48.75])
        
        adx = TechnicalIndicators.calculate_adx(high, low, close, period=14)
        
        # Should return 0 for insufficient data
        assert adx == 0.0
    
    def test_volume_sma(self):
        """Test volume SMA calculation"""
        volumes = pd.Series([1000, 2000, 1500, 3000, 2500, 1800, 2200])
        
        sma = TechnicalIndicators.calculate_volume_sma(volumes, period=7)
        
        # Should calculate average of all 7 values
        expected = (1000 + 2000 + 1500 + 3000 + 2500 + 1800 + 2200) / 7
        assert abs(sma - expected) < 0.01
    
    def test_volume_spike_ratio(self):
        """Test volume spike ratio calculation"""
        current_volume = 10000
        volume_sma = 5000
        
        ratio = TechnicalIndicators.calculate_volume_spike_ratio(current_volume, volume_sma)
        
        # Should be 2.0 (10000/5000)
        assert abs(ratio - 2.0) < 0.01
    
    def test_volume_spike_ratio_zero_sma(self):
        """Test volume spike ratio with zero SMA"""
        current_volume = 10000
        volume_sma = 0
        
        ratio = TechnicalIndicators.calculate_volume_spike_ratio(current_volume, volume_sma)
        
        # Should return 0 for zero SMA
        assert ratio == 0.0
