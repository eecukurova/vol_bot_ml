"""
Test utility functions
"""
import pytest
from core.utils import consecutive_days_below_threshold, calculate_drawdown_from_high, safe_divide


class TestConsecutiveDaysBelowThreshold:
    """Test consecutive days below threshold calculation"""
    
    def test_no_prices(self):
        """Test with empty price list"""
        assert consecutive_days_below_threshold([]) == 0
    
    def test_all_above_threshold(self):
        """Test when all prices are above threshold"""
        prices = [1.5, 2.0, 1.8, 2.2, 1.9]
        assert consecutive_days_below_threshold(prices, 1.0) == 0
    
    def test_all_below_threshold(self):
        """Test when all prices are below threshold"""
        prices = [0.5, 0.8, 0.6, 0.7, 0.9]
        assert consecutive_days_below_threshold(prices, 1.0) == 5
    
    def test_mixed_prices(self):
        """Test with mixed prices"""
        prices = [1.2, 0.8, 0.9, 0.7, 1.1, 0.6, 0.5, 1.3, 0.4, 0.3]
        # Longest consecutive below $1: 0.4, 0.3 (2 days) - but 0.8, 0.9, 0.7 (3 days) is longer
        assert consecutive_days_below_threshold(prices, 1.0) == 3
    
    def test_boundary_value(self):
        """Test boundary value (exactly $1)"""
        prices = [1.0, 0.9, 1.0, 0.8, 0.7, 1.0]
        # 0.8, 0.7 are below $1 (2 consecutive)
        assert consecutive_days_below_threshold(prices, 1.0) == 2
    
    def test_61_days_fail(self):
        """Test 61 consecutive days (should fail delist filter)"""
        prices = [1.2] + [0.8] * 61 + [1.1]
        assert consecutive_days_below_threshold(prices, 1.0) == 61
    
    def test_58_days_pass(self):
        """Test 58 consecutive days (should pass delist filter)"""
        prices = [1.2] + [0.8] * 58 + [1.1]
        assert consecutive_days_below_threshold(prices, 1.0) == 58


class TestDrawdownCalculation:
    """Test drawdown from high calculation"""
    
    def test_no_prices(self):
        """Test with empty price list"""
        assert calculate_drawdown_from_high([]) == 0.0
    
    def test_single_price(self):
        """Test with single price"""
        prices = [100.0]
        assert calculate_drawdown_from_high(prices) == 0.0
    
    def test_ascending_prices(self):
        """Test with ascending prices (no drawdown)"""
        prices = [100.0, 110.0, 120.0, 130.0]
        assert calculate_drawdown_from_high(prices) == 0.0
    
    def test_descending_prices(self):
        """Test with descending prices"""
        prices = [100.0, 80.0, 60.0, 40.0]
        # Drawdown = (100 - 40) / 100 * 100 = 60%
        assert calculate_drawdown_from_high(prices) == 60.0
    
    def test_mixed_prices(self):
        """Test with mixed prices"""
        prices = [50.0, 80.0, 60.0, 100.0, 70.0, 30.0]
        # Highest: 100, Current: 30, Drawdown = (100-30)/100*100 = 70%
        assert calculate_drawdown_from_high(prices) == 70.0
    
    def test_zero_high(self):
        """Test with zero high price"""
        prices = [0.0, 10.0, 5.0]
        # Highest: 10.0, Current: 5.0, Drawdown = (10-5)/10*100 = 50%
        assert calculate_drawdown_from_high(prices) == 50.0


class TestSafeDivide:
    """Test safe division function"""
    
    def test_normal_division(self):
        """Test normal division"""
        assert safe_divide(10.0, 2.0) == 5.0
        assert safe_divide(7.5, 3.0) == 2.5
    
    def test_division_by_zero(self):
        """Test division by zero"""
        assert safe_divide(10.0, 0.0) == 0.0
        assert safe_divide(10.0, 0.0, default=999.0) == 999.0
    
    def test_zero_numerator(self):
        """Test zero numerator"""
        assert safe_divide(0.0, 5.0) == 0.0
    
    def test_custom_default(self):
        """Test custom default value"""
        assert safe_divide(10.0, 0.0, default=-1.0) == -1.0
