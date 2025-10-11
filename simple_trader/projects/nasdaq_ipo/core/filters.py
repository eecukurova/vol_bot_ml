"""
Filter logic for NASDAQ Post-IPO Sub-$1 Rebound Screener
"""
import logging
from typing import Dict, List
from datetime import datetime, timedelta

from .utils import parse_date, days_ago

logger = logging.getLogger(__name__)

# Symbol hygiene filters - exclude non-common stocks
EXCLUDE_TOKENS = (" W", " WS", "WARRANT", " RIGHT", " UNIT", " SPAC", " ETF", " TRUST", " FUND", " ADR", " ADS", "SPECIAL PURPOSE ACQUISITION")


def is_common_stock(symbol: str, name: str = "") -> bool:
    """Check if symbol represents common stock (exclude warrants, units, etc.)"""
    s = (symbol or "").upper()
    n = (name or "").upper()
    
    # Quick exclusion for common suffixes
    if s.endswith(("W", "U", "R")):
        return False
    
    # Check for exact symbol matches first
    if s in ["SPAC", "ETF", "TRUST", "FUND"]:
        return False
    
    # Check for exclusion tokens in symbol or name
    haystack = f"{s} {n}"
    return not any(token in haystack for token in EXCLUDE_TOKENS)


class StockFilter:
    """Apply filters to stock analysis results"""
    
    def __init__(self, 
                 min_price: float = 0.30,
                 max_price: float = 1.00,
                 min_volume: int = 500_000,
                 rsi_min: float = 30.0,
                 rsi_max: float = 45.0,
                 adx_max: float = 25.0,
                 max_consec_below1: int = 60,
                 min_drawdown: float = 70.0,
                 ipo_days_back: int = 180):
        
        self.min_price = min_price
        self.max_price = max_price
        self.min_volume = min_volume
        self.rsi_min = rsi_min
        self.rsi_max = rsi_max
        self.adx_max = adx_max
        self.max_consec_below1 = max_consec_below1
        self.min_drawdown = min_drawdown
        self.ipo_days_back = ipo_days_back
    
    def apply_filters(self, stocks: List[Dict]) -> List[Dict]:
        """Apply all filters to stock list"""
        logger.info(f"Applying filters to {len(stocks)} stocks")
        
        filtered_stocks = []
        filter_stats = {
            'total': len(stocks),
            'symbol_hygiene_filter': 0,
            'price_filter': 0,
            'volume_filter': 0,
            'rsi_filter': 0,
            'adx_filter': 0,
            'consecutive_filter': 0,
            'drawdown_filter': 0,
            'ipo_date_filter': 0,
            'passed': 0
        }
        
        for stock in stocks:
            # Track original count
            original_count = len(filtered_stocks)
            
            # Apply symbol hygiene filter first
            if not self._symbol_hygiene_filter(stock):
                filter_stats['symbol_hygiene_filter'] += 1
                continue
            
            # Apply each filter
            if not self._price_filter(stock):
                filter_stats['price_filter'] += 1
                continue
            
            if not self._volume_filter(stock):
                filter_stats['volume_filter'] += 1
                continue
            
            if not self._rsi_filter(stock):
                filter_stats['rsi_filter'] += 1
                continue
            
            if not self._adx_filter(stock):
                filter_stats['adx_filter'] += 1
                continue
            
            if not self._consecutive_days_filter(stock):
                filter_stats['consecutive_filter'] += 1
                continue
            
            if not self._drawdown_filter(stock):
                filter_stats['drawdown_filter'] += 1
                continue
            
            if not self._ipo_date_filter(stock):
                filter_stats['ipo_date_filter'] += 1
                continue
            
            # Stock passed all filters
            filtered_stocks.append(stock)
            filter_stats['passed'] += 1
        
        # Log filter statistics
        self._log_filter_stats(filter_stats)
        
        logger.info(f"Filtered to {len(filtered_stocks)} stocks")
        return filtered_stocks
    
    def _symbol_hygiene_filter(self, stock: Dict) -> bool:
        """Filter out non-common stocks (warrants, units, etc.)"""
        symbol = stock.get('symbol', '')
        name = stock.get('name', '')  # If available from yfinance
        return is_common_stock(symbol, name)
    
    def _price_filter(self, stock: Dict) -> bool:
        """Filter by price range: 0.30 - 1.00 USD"""
        price = stock.get('lastClose', 0)
        return self.min_price <= price <= self.max_price
    
    def _volume_filter(self, stock: Dict) -> bool:
        """Filter by minimum daily volume"""
        volume = stock.get('lastVolume', 0)
        return volume >= self.min_volume
    
    def _rsi_filter(self, stock: Dict) -> bool:
        """Filter by RSI range: 30-45 (oversold recovery band)"""
        rsi = stock.get('rsi14', 0)
        return self.rsi_min <= rsi <= self.rsi_max
    
    def _adx_filter(self, stock: Dict) -> bool:
        """Filter by ADX: < 25 (weak trend -> reversal potential)"""
        adx = stock.get('adx14', 0)
        return adx < self.adx_max
    
    def _consecutive_days_filter(self, stock: Dict) -> bool:
        """Filter by consecutive days below $1: max 60 days"""
        consecutive_days = stock.get('daysConsecBelow1', 0)
        return consecutive_days <= self.max_consec_below1
    
    def _drawdown_filter(self, stock: Dict) -> bool:
        """Filter by drawdown from high: >= 70%"""
        drawdown = stock.get('drawdownFromHigh', 0)
        return drawdown >= self.min_drawdown
    
    def _ipo_date_filter(self, stock: Dict) -> bool:
        """Filter by IPO date: last 180 days"""
        ipo_date_str = stock.get('ipoDate', '')
        if not ipo_date_str or ipo_date_str == 'Unknown':
            return False
        
        ipo_date = parse_date(ipo_date_str)
        if not ipo_date:
            return False
        
        cutoff_date = days_ago(self.ipo_days_back)
        return ipo_date >= cutoff_date
    
    def _log_filter_stats(self, stats: Dict) -> None:
        """Log filter statistics"""
        logger.info("Filter Statistics:")
        logger.info(f"  Total stocks: {stats['total']}")
        logger.info(f"  Price filter ({self.min_price}-{self.max_price}): {stats['price_filter']} removed")
        logger.info(f"  Volume filter (>{self.min_volume:,}): {stats['volume_filter']} removed")
        logger.info(f"  RSI filter ({self.rsi_min}-{self.rsi_max}): {stats['rsi_filter']} removed")
        logger.info(f"  ADX filter (<{self.adx_max}): {stats['adx_filter']} removed")
        logger.info(f"  Consecutive days filter (<={self.max_consec_below1}): {stats['consecutive_filter']} removed")
        logger.info(f"  Drawdown filter (>={self.min_drawdown}%): {stats['drawdown_filter']} removed")
        logger.info(f"  IPO date filter (last {self.ipo_days_back}d): {stats['ipo_date_filter']} removed")
        logger.info(f"  Passed all filters: {stats['passed']}")


def get_filter_summary(min_price: float = 0.30,
                      max_price: float = 1.00,
                      min_volume: int = 500_000,
                      rsi_min: float = 30.0,
                      rsi_max: float = 45.0,
                      adx_max: float = 25.0,
                      max_consec_below1: int = 60,
                      min_drawdown: float = 70.0,
                      ipo_days_back: int = 180) -> str:
    """Get human-readable filter summary"""
    return (f"IPO&lt;={ipo_days_back}d, Px {min_price}-{max_price}, "
            f"Vol&gt;{min_volume:,}, RSI {rsi_min}-{rsi_max}, ADX&lt;{adx_max}, "
            f"&lt;={max_consec_below1}d &lt;USD1, DD&gt;={min_drawdown}%")
