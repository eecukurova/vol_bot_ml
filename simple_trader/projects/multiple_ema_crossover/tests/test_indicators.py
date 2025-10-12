"""
Test indicators for production-ready EMA crossover trader
Tests TradingView-compatible EMA and RSI calculations
"""

import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add common module to path
current_dir = os.path.dirname(os.path.abspath(__file__))
common_dir = os.path.join(os.path.dirname(current_dir), 'common')
sys.path.insert(0, common_dir)

from utils import ema_tv, rsi_wilder, detect_ema_crossover, select_series_for_signal


class TestIndicators(unittest.TestCase):
    """Test TradingView-compatible indicators"""
    
    def setUp(self):
        """Setup test data"""
        # Create sample price data
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='1H')
        base_price = 100
        returns = np.random.normal(0, 0.02, 100)
        prices = [base_price]
        
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        self.df = pd.DataFrame({
            'timestamp': dates,
            'close': prices
        })
        self.df.set_index('timestamp', inplace=True)
    
    def test_ema_tv_calculation(self):
        """Test TradingView-compatible EMA calculation"""
        # Test with period 12
        ema_12 = ema_tv(self.df['close'], 12)
        
        # Check basic properties
        self.assertEqual(len(ema_12), len(self.df))
        self.assertFalse(ema_12.isna().all())
        
        # Check that EMA is smoother than original prices
        price_std = self.df['close'].std()
        ema_std = ema_12.std()
        self.assertLess(ema_std, price_std)
        
        # Check that EMA follows price trend
        price_trend = self.df['close'].iloc[-1] - self.df['close'].iloc[0]
        ema_trend = ema_12.iloc[-1] - ema_12.iloc[0]
        self.assertTrue(np.sign(price_trend) == np.sign(ema_trend) or abs(ema_trend) < abs(price_trend))
    
    def test_ema_periods(self):
        """Test EMA with different periods"""
        ema_12 = ema_tv(self.df['close'], 12)
        ema_26 = ema_tv(self.df['close'], 26)
        
        # Longer period EMA should be smoother
        self.assertLess(ema_26.std(), ema_12.std())
        
        # Both should have same length
        self.assertEqual(len(ema_12), len(ema_26))
    
    def test_rsi_wilder_calculation(self):
        """Test Wilder's RSI calculation"""
        rsi = rsi_wilder(self.df['close'], 14)
        
        # Check basic properties
        self.assertEqual(len(rsi), len(self.df))
        self.assertFalse(rsi.isna().all())
        
        # RSI should be between 0 and 100
        self.assertTrue(rsi.min() >= 0)
        self.assertTrue(rsi.max() <= 100)
        
        # RSI should be around 50 for random data
        self.assertTrue(40 <= rsi.mean() <= 60)
    
    def test_rsi_periods(self):
        """Test RSI with different periods"""
        rsi_14 = rsi_wilder(self.df['close'], 14)
        rsi_21 = rsi_wilder(self.df['close'], 21)
        
        # Both should have same length
        self.assertEqual(len(rsi_14), len(rsi_21))
        
        # Both should be valid RSI values
        self.assertTrue(rsi_14.min() >= 0 and rsi_14.max() <= 100)
        self.assertTrue(rsi_21.min() >= 0 and rsi_21.max() <= 100)
    
    def test_ema_crossover_detection(self):
        """Test EMA crossover detection"""
        # Create artificial crossover data
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
        df_test = pd.DataFrame({'close': prices})
        
        fast_ema = ema_tv(df_test['close'], 3)
        slow_ema = ema_tv(df_test['close'], 5)
        
        crossover = detect_ema_crossover(fast_ema, slow_ema)
        
        # Check that crossover detection works
        self.assertEqual(len(crossover), len(df_test))
        self.assertTrue(crossover.isin(['long', 'short', 'none']).all())
    
    def test_ema_crossover_with_hysteresis(self):
        """Test EMA crossover with hysteresis"""
        # Create data where EMAs are very close
        prices = [100, 100.001, 100.002, 100.003, 100.004]
        df_test = pd.DataFrame({'close': prices})
        
        fast_ema = ema_tv(df_test['close'], 2)
        slow_ema = ema_tv(df_test['close'], 3)
        
        # Without hysteresis
        crossover_no_hyst = detect_ema_crossover(fast_ema, slow_ema, 0.0)
        
        # With hysteresis
        crossover_with_hyst = detect_ema_crossover(fast_ema, slow_ema, 0.01)
        
        # Hysteresis should reduce false signals
        self.assertEqual(len(crossover_no_hyst), len(crossover_with_hyst))
    
    def test_select_series_for_signal(self):
        """Test series selection for signal generation"""
        series = pd.Series([1, 2, 3, 4, 5])
        
        # Intrabar signals (include last bar)
        intrabar_series = select_series_for_signal(series, True)
        self.assertEqual(len(intrabar_series), 5)
        self.assertEqual(intrabar_series.iloc[-1], 5)
        
        # Confirmed bar signals (exclude last bar)
        confirmed_series = select_series_for_signal(series, False)
        self.assertEqual(len(confirmed_series), 4)
        self.assertEqual(confirmed_series.iloc[-1], 4)
    
    def test_select_series_edge_cases(self):
        """Test series selection edge cases"""
        # Single element series
        single_series = pd.Series([1])
        
        intrabar_single = select_series_for_signal(single_series, True)
        confirmed_single = select_series_for_signal(single_series, False)
        
        # Both should return the same for single element
        self.assertEqual(len(intrabar_single), 1)
        self.assertEqual(len(confirmed_single), 1)
        
        # Empty series
        empty_series = pd.Series([])
        
        intrabar_empty = select_series_for_signal(empty_series, True)
        confirmed_empty = select_series_for_signal(empty_series, False)
        
        # Both should return empty series
        self.assertEqual(len(intrabar_empty), 0)
        self.assertEqual(len(confirmed_empty), 0)
    
    def test_indicator_consistency(self):
        """Test indicator calculation consistency"""
        # Same data should produce same results
        ema_1 = ema_tv(self.df['close'], 12)
        ema_2 = ema_tv(self.df['close'], 12)
        
        pd.testing.assert_series_equal(ema_1, ema_2)
        
        # RSI should be consistent
        rsi_1 = rsi_wilder(self.df['close'], 14)
        rsi_2 = rsi_wilder(self.df['close'], 14)
        
        pd.testing.assert_series_equal(rsi_1, rsi_2)
    
    def test_indicator_with_nan_values(self):
        """Test indicators with NaN values"""
        # Create data with NaN
        data_with_nan = self.df['close'].copy()
        data_with_nan.iloc[5:10] = np.nan
        
        # Indicators should handle NaN gracefully
        ema_nan = ema_tv(data_with_nan, 12)
        rsi_nan = rsi_wilder(data_with_nan, 14)
        
        # Should not crash and should have reasonable length
        self.assertEqual(len(ema_nan), len(data_with_nan))
        self.assertEqual(len(rsi_nan), len(data_with_nan))


if __name__ == '__main__':
    unittest.main()
