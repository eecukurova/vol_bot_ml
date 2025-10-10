"""
Test filter logic
"""
import pytest
from core.filters import StockFilter, is_common_stock


class TestStockFilter:
    """Test stock filtering logic"""
    
    def test_price_filter(self):
        """Test price range filtering"""
        filter_obj = StockFilter(min_price=0.30, max_price=1.00)
        
        # Test valid price
        stock = {'lastClose': 0.50}
        assert filter_obj._price_filter(stock) == True
        
        # Test price too low
        stock = {'lastClose': 0.20}
        assert filter_obj._price_filter(stock) == False
        
        # Test price too high
        stock = {'lastClose': 1.50}
        assert filter_obj._price_filter(stock) == False
    
    def test_volume_filter(self):
        """Test volume filtering"""
        filter_obj = StockFilter(min_volume=500000)
        
        # Test valid volume
        stock = {'lastVolume': 1000000}
        assert filter_obj._volume_filter(stock) == True
        
        # Test volume too low
        stock = {'lastVolume': 100000}
        assert filter_obj._volume_filter(stock) == False
    
    def test_rsi_filter(self):
        """Test RSI range filtering"""
        filter_obj = StockFilter(rsi_min=30.0, rsi_max=45.0)
        
        # Test valid RSI
        stock = {'rsi14': 35.0}
        assert filter_obj._rsi_filter(stock) == True
        
        # Test RSI too low
        stock = {'rsi14': 25.0}
        assert filter_obj._rsi_filter(stock) == False
        
        # Test RSI too high
        stock = {'rsi14': 50.0}
        assert filter_obj._rsi_filter(stock) == False
        
        # Test boundary values
        stock = {'rsi14': 30.0}  # Should pass
        assert filter_obj._rsi_filter(stock) == True
        
        stock = {'rsi14': 45.0}  # Should pass
        assert filter_obj._rsi_filter(stock) == True
    
    def test_adx_filter(self):
        """Test ADX filtering"""
        filter_obj = StockFilter(adx_max=25.0)
        
        # Test valid ADX
        stock = {'adx14': 20.0}
        assert filter_obj._adx_filter(stock) == True
        
        # Test ADX too high
        stock = {'adx14': 30.0}
        assert filter_obj._adx_filter(stock) == False
    
    def test_consecutive_days_filter(self):
        """Test consecutive days below $1 filtering"""
        filter_obj = StockFilter(max_consec_below1=60)
        
        # Test valid consecutive days
        stock = {'daysConsecBelow1': 30}
        assert filter_obj._consecutive_days_filter(stock) == True
        
        # Test too many consecutive days
        stock = {'daysConsecBelow1': 70}
        assert filter_obj._consecutive_days_filter(stock) == False
        
        # Test boundary value
        stock = {'daysConsecBelow1': 60}  # Should pass
        assert filter_obj._consecutive_days_filter(stock) == True
    
    def test_drawdown_filter(self):
        """Test drawdown filtering"""
        filter_obj = StockFilter(min_drawdown=70.0)
        
        # Test valid drawdown
        stock = {'drawdownFromHigh': 80.0}
        assert filter_obj._drawdown_filter(stock) == True
        
        # Test drawdown too low
        stock = {'drawdownFromHigh': 50.0}
        assert filter_obj._drawdown_filter(stock) == False


class TestSymbolHygiene:
    """Test symbol hygiene filtering"""
    
    def test_common_stock_acceptance(self):
        """Test that common stocks are accepted"""
        assert is_common_stock("AAPL") == True
        assert is_common_stock("MSFT") == True
        assert is_common_stock("GOOGL") == True
    
    def test_warrant_exclusion(self):
        """Test that warrants are excluded"""
        assert is_common_stock("AAPLW") == False  # Warrant suffix
        assert is_common_stock("MSFT WS") == False  # Warrant in name
    
    def test_unit_exclusion(self):
        """Test that units are excluded"""
        assert is_common_stock("SPACU") == False  # Unit suffix
        assert is_common_stock("COMPANY UNIT") == False  # Unit in name
    
    def test_etf_exclusion(self):
        """Test that ETFs are excluded"""
        assert is_common_stock("SPY") == True  # Common stock
        assert is_common_stock("SPY ETF") == False  # ETF in name
        assert is_common_stock("TRUST FUND") == False  # Trust/Fund in name
    
    def test_spac_exclusion(self):
        """Test that SPACs are excluded"""
        assert is_common_stock("SPAC") == False  # SPAC in name
        assert is_common_stock("SPECIAL PURPOSE ACQUISITION") == False
