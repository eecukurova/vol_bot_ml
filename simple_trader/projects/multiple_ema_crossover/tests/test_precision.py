"""
Test precision helpers for production-ready EMA crossover trader
Tests amount and price quantization functions
"""

import unittest
import sys
import os
from unittest.mock import Mock, MagicMock

# Add common module to path
current_dir = os.path.dirname(os.path.abspath(__file__))
common_dir = os.path.join(os.path.dirname(current_dir), 'common')
sys.path.insert(0, common_dir)

from utils import quantize_amount, quantize_price


class TestPrecision(unittest.TestCase):
    """Test precision quantization functions"""
    
    def setUp(self):
        """Setup mock exchange"""
        self.mock_exchange = Mock()
        
        # Mock market data for BTC/USDT:USDT
        self.mock_exchange.markets = {
            'BTC/USDT:USDT': {
                'precision': {
                    'amount': 0.00001,  # 5 decimal places
                    'price': 0.01       # 2 decimal places
                },
                'limits': {
                    'amount': {
                        'min': 0.001,
                        'max': 9000
                    },
                    'price': {
                        'min': 0.01,
                        'max': 1000000
                    }
                }
            }
        }
        
        # Mock precision methods
        def mock_amount_to_precision(symbol, amount):
            precision = self.mock_exchange.markets[symbol]['precision']['amount']
            return round(amount, 5)
        
        def mock_price_to_precision(symbol, price):
            precision = self.mock_exchange.markets[symbol]['precision']['price']
            return round(price, 2)
        
        self.mock_exchange.amount_to_precision = mock_amount_to_precision
        self.mock_exchange.price_to_precision = mock_price_to_precision
    
    def test_quantize_amount_basic(self):
        """Test basic amount quantization"""
        symbol = 'BTC/USDT:USDT'
        amount = 0.123456789
        
        result = quantize_amount(self.mock_exchange, symbol, amount)
        
        # Should be rounded to 5 decimal places
        self.assertEqual(result, 0.12346)
        self.assertIsInstance(result, float)
    
    def test_quantize_amount_edge_cases(self):
        """Test amount quantization edge cases"""
        symbol = 'BTC/USDT:USDT'
        
        # Very small amount
        small_amount = 0.000001
        result_small = quantize_amount(self.mock_exchange, symbol, small_amount)
        self.assertEqual(result_small, 0.00000)
        
        # Large amount
        large_amount = 1234.56789
        result_large = quantize_amount(self.mock_exchange, symbol, large_amount)
        self.assertEqual(result_large, 1234.56789)
        
        # Zero amount
        zero_amount = 0.0
        result_zero = quantize_amount(self.mock_exchange, symbol, zero_amount)
        self.assertEqual(result_zero, 0.0)
    
    def test_quantize_price_basic(self):
        """Test basic price quantization"""
        symbol = 'BTC/USDT:USDT'
        price = 123.456789
        
        result = quantize_price(self.mock_exchange, symbol, price)
        
        # Should be rounded to 2 decimal places
        self.assertEqual(result, 123.46)
        self.assertIsInstance(result, float)
    
    def test_quantize_price_edge_cases(self):
        """Test price quantization edge cases"""
        symbol = 'BTC/USDT:USDT'
        
        # Very small price
        small_price = 0.001
        result_small = quantize_price(self.mock_exchange, symbol, small_price)
        self.assertEqual(result_small, 0.00)
        
        # Large price
        large_price = 123456.789
        result_large = quantize_price(self.mock_exchange, symbol, large_price)
        self.assertEqual(result_large, 123456.79)
        
        # Zero price
        zero_price = 0.0
        result_zero = quantize_price(self.mock_exchange, symbol, zero_price)
        self.assertEqual(result_zero, 0.0)
    
    def test_quantize_error_handling(self):
        """Test quantization error handling"""
        # Mock exchange that raises exception
        error_exchange = Mock()
        error_exchange.amount_to_precision.side_effect = Exception("API Error")
        error_exchange.price_to_precision.side_effect = Exception("API Error")
        
        # Should return original value on error
        amount = 0.123456
        price = 123.456
        
        result_amount = quantize_amount(error_exchange, 'BTC/USDT:USDT', amount)
        result_price = quantize_price(error_exchange, 'BTC/USDT:USDT', price)
        
        self.assertEqual(result_amount, amount)
        self.assertEqual(result_price, price)
    
    def test_quantize_different_symbols(self):
        """Test quantization with different symbols"""
        # Mock different symbol with different precision
        self.mock_exchange.markets['ETH/USDT:USDT'] = {
            'precision': {
                'amount': 0.001,   # 3 decimal places
                'price': 0.1        # 1 decimal place
            }
        }
        
        def mock_amount_to_precision_eth(symbol, amount):
            if symbol == 'ETH/USDT:USDT':
                return round(amount, 3)
            return round(amount, 5)
        
        def mock_price_to_precision_eth(symbol, price):
            if symbol == 'ETH/USDT:USDT':
                return round(price, 1)
            return round(price, 2)
        
        self.mock_exchange.amount_to_precision = mock_amount_to_precision_eth
        self.mock_exchange.price_to_precision = mock_price_to_precision_eth
        
        # Test BTC (5 decimal places)
        btc_amount = quantize_amount(self.mock_exchange, 'BTC/USDT:USDT', 0.123456)
        self.assertEqual(btc_amount, 0.12346)
        
        # Test ETH (3 decimal places)
        eth_amount = quantize_amount(self.mock_exchange, 'ETH/USDT:USDT', 0.123456)
        self.assertEqual(eth_amount, 0.123)
        
        # Test BTC price (2 decimal places)
        btc_price = quantize_price(self.mock_exchange, 'BTC/USDT:USDT', 123.456)
        self.assertEqual(btc_price, 123.46)
        
        # Test ETH price (1 decimal place)
        eth_price = quantize_price(self.mock_exchange, 'ETH/USDT:USDT', 123.456)
        self.assertEqual(eth_price, 123.5)
    
    def test_quantize_precision_consistency(self):
        """Test that quantization is consistent"""
        symbol = 'BTC/USDT:USDT'
        amount = 0.123456789
        price = 123.456789
        
        # Multiple calls should return same result
        result1_amount = quantize_amount(self.mock_exchange, symbol, amount)
        result2_amount = quantize_amount(self.mock_exchange, symbol, amount)
        self.assertEqual(result1_amount, result2_amount)
        
        result1_price = quantize_price(self.mock_exchange, symbol, price)
        result2_price = quantize_price(self.mock_exchange, symbol, price)
        self.assertEqual(result1_price, result2_price)
    
    def test_quantize_with_negative_values(self):
        """Test quantization with negative values"""
        symbol = 'BTC/USDT:USDT'
        
        # Negative amount (shouldn't happen in practice, but test robustness)
        negative_amount = -0.123456
        result_amount = quantize_amount(self.mock_exchange, symbol, negative_amount)
        self.assertEqual(result_amount, -0.12346)
        
        # Negative price (shouldn't happen in practice, but test robustness)
        negative_price = -123.456
        result_price = quantize_price(self.mock_exchange, symbol, negative_price)
        self.assertEqual(result_price, -123.46)
    
    def test_quantize_with_string_input(self):
        """Test quantization with string input"""
        symbol = 'BTC/USDT:USDT'
        
        # String amount
        string_amount = "0.123456"
        result_amount = quantize_amount(self.mock_exchange, symbol, string_amount)
        self.assertEqual(result_amount, 0.12346)
        
        # String price
        string_price = "123.456"
        result_price = quantize_price(self.mock_exchange, symbol, string_price)
        self.assertEqual(result_price, 123.46)


if __name__ == '__main__':
    unittest.main()
