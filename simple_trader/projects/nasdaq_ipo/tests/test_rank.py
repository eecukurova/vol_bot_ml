"""
Test ranking logic
"""
import pytest
from core.rank import StockRanker, safe_mcap


class TestStockRanker:
    """Test stock ranking logic"""
    
    def test_empty_stocks(self):
        """Test ranking with empty stock list"""
        ranker = StockRanker()
        result = ranker.rank_stocks([])
        assert result == []
    
    def test_single_stock(self):
        """Test ranking with single stock"""
        ranker = StockRanker()
        stocks = [{
            'symbol': 'TEST',
            'volSpikeRatio': 2.0,
            'drawdownFromHigh': 80.0,
            'marketCap': 1000000,
            'rsi14': 30.0
        }]
        result = ranker.rank_stocks(stocks)
        assert len(result) == 1
        assert result[0]['symbol'] == 'TEST'
    
    def test_volume_spike_priority(self):
        """Test that higher volume spike gets priority"""
        ranker = StockRanker()
        stocks = [
            {
                'symbol': 'LOW_SPIKE',
                'volSpikeRatio': 1.0,
                'drawdownFromHigh': 80.0,
                'marketCap': 1000000,
                'rsi14': 30.0
            },
            {
                'symbol': 'HIGH_SPIKE',
                'volSpikeRatio': 3.0,
                'drawdownFromHigh': 80.0,
                'marketCap': 1000000,
                'rsi14': 30.0
            }
        ]
        result = ranker.rank_stocks(stocks)
        assert result[0]['symbol'] == 'HIGH_SPIKE'
        assert result[1]['symbol'] == 'LOW_SPIKE'
    
    def test_drawdown_tie_breaker(self):
        """Test drawdown as tie-breaker when volume spike is equal"""
        ranker = StockRanker()
        stocks = [
            {
                'symbol': 'LOW_DD',
                'volSpikeRatio': 2.0,
                'drawdownFromHigh': 60.0,
                'marketCap': 1000000,
                'rsi14': 30.0
            },
            {
                'symbol': 'HIGH_DD',
                'volSpikeRatio': 2.0,
                'drawdownFromHigh': 80.0,
                'marketCap': 1000000,
                'rsi14': 30.0
            }
        ]
        result = ranker.rank_stocks(stocks)
        assert result[0]['symbol'] == 'HIGH_DD'
        assert result[1]['symbol'] == 'LOW_DD'
    
    def test_market_cap_tie_breaker(self):
        """Test market cap as tie-breaker"""
        ranker = StockRanker()
        stocks = [
            {
                'symbol': 'LARGE_CAP',
                'volSpikeRatio': 2.0,
                'drawdownFromHigh': 80.0,
                'marketCap': 10000000,
                'rsi14': 30.0
            },
            {
                'symbol': 'SMALL_CAP',
                'volSpikeRatio': 2.0,
                'drawdownFromHigh': 80.0,
                'marketCap': 1000000,
                'rsi14': 30.0
            }
        ]
        result = ranker.rank_stocks(stocks)
        assert result[0]['symbol'] == 'SMALL_CAP'  # Smaller cap = better
        assert result[1]['symbol'] == 'LARGE_CAP'
    
    def test_rsi_tie_breaker(self):
        """Test RSI as final tie-breaker"""
        ranker = StockRanker()
        stocks = [
            {
                'symbol': 'HIGH_RSI',
                'volSpikeRatio': 2.0,
                'drawdownFromHigh': 80.0,
                'marketCap': 1000000,
                'rsi14': 50.0
            },
            {
                'symbol': 'LOW_RSI',
                'volSpikeRatio': 2.0,
                'drawdownFromHigh': 80.0,
                'marketCap': 1000000,
                'rsi14': 30.0
            }
        ]
        result = ranker.rank_stocks(stocks)
        assert result[0]['symbol'] == 'LOW_RSI'  # Lower RSI = better
        assert result[1]['symbol'] == 'HIGH_RSI'
    
    def test_top_n_limit(self):
        """Test top N limiting"""
        ranker = StockRanker()
        stocks = [
            {'symbol': f'STOCK{i}', 'volSpikeRatio': i, 'drawdownFromHigh': 80.0, 
             'marketCap': 1000000, 'rsi14': 30.0}
            for i in range(10)
        ]
        result = ranker.rank_stocks(stocks, top_n=5)
        assert len(result) == 5
        # Should be sorted by volSpikeRatio descending
        assert result[0]['volSpikeRatio'] == 9
        assert result[4]['volSpikeRatio'] == 5


class TestSafeMcap:
    """Test safe market cap handling"""
    
    def test_valid_market_cap(self):
        """Test with valid market cap"""
        assert safe_mcap(1000000) == 1000000.0
        assert safe_mcap(500000000) == 500000000.0
    
    def test_none_market_cap(self):
        """Test with None market cap"""
        assert safe_mcap(None) == float('inf')
    
    def test_zero_market_cap(self):
        """Test with zero market cap"""
        assert safe_mcap(0) == float('inf')
        assert safe_mcap(0.0) == float('inf')
    
    def test_negative_market_cap(self):
        """Test with negative market cap"""
        assert safe_mcap(-1000) == float('inf')
