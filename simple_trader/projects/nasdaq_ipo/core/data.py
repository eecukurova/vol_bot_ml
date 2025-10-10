"""
Market data fetching with yfinance and technical indicators
"""
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import time
from datetime import datetime, timedelta

from .utils import safe_divide

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetch market data and calculate technical indicators"""
    
    def __init__(self, batch_size: int = 10, delay: float = 0.1):
        self.batch_size = batch_size
        self.delay = delay
    
    def fetch_stock_data(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Fetch stock data for a single symbol"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                logger.warning(f"No data found for {symbol}")
                return None
            
            # Ensure we have required columns
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in data.columns for col in required_cols):
                logger.warning(f"Missing required columns for {symbol}")
                return None
            
            logger.debug(f"Fetched {len(data)} days of data for {symbol}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def fetch_multiple_stocks(self, symbols: List[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols with batching and delays"""
        results = {}
        
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i + self.batch_size]
            logger.info(f"Processing batch {i//self.batch_size + 1}: {batch}")
            
            for symbol in batch:
                data = self.fetch_stock_data(symbol, period)
                if data is not None:
                    results[symbol] = data
                
                # Add delay to avoid rate limiting
                time.sleep(self.delay)
        
        logger.info(f"Successfully fetched data for {len(results)}/{len(symbols)} symbols")
        return results


class TechnicalIndicators:
    """Calculate technical indicators"""
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return 0.0
        
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = safe_divide(gain.iloc[-1], loss.iloc[-1])
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return 0.0
    
    @staticmethod
    def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Calculate simplified ADX (Average Directional Index)"""
        if len(high) < period + 1:
            return 0.0
        
        try:
            # Simplified ADX calculation based on volatility
            price_change = abs(close.diff().rolling(window=period).mean())
            price_range = (high - low).rolling(window=period).mean()
            
            # ADX approximation based on volatility
            if price_range.iloc[-1] > 0:
                adx = (price_change.iloc[-1] / price_range.iloc[-1]) * 100
                return min(adx, 100.0)  # Cap at 100
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error calculating ADX: {e}")
            return 0.0
    
    @staticmethod
    def calculate_volume_sma(volume: pd.Series, period: int = 7) -> float:
        """Calculate Simple Moving Average of volume"""
        if len(volume) < period:
            return 0.0
        
        try:
            return volume.rolling(window=period).mean().iloc[-1]
        except Exception as e:
            logger.error(f"Error calculating volume SMA: {e}")
            return 0.0
    
    @staticmethod
    def calculate_volume_spike_ratio(current_volume: float, volume_sma: float) -> float:
        """Calculate volume spike ratio"""
        return safe_divide(current_volume, volume_sma)


class StockAnalyzer:
    """Analyze individual stock data"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def analyze_stock(self, symbol: str, data: pd.DataFrame, ipo_date: Optional[str] = None) -> Dict:
        """Analyze a single stock and return all metrics"""
        try:
            if data.empty:
                return self._empty_result(symbol)
            
            # Basic price data
            last_close = data['Close'].iloc[-1]
            last_volume = int(data['Volume'].iloc[-1])
            
            # Technical indicators
            rsi = self.indicators.calculate_rsi(data['Close'])
            adx = self.indicators.calculate_adx(data['High'], data['Low'], data['Close'])
            
            # Volume analysis
            volume_sma_7 = self.indicators.calculate_volume_sma(data['Volume'])
            volume_spike_ratio = self.indicators.calculate_volume_spike_ratio(last_volume, volume_sma_7)
            
            # Consecutive days below $1
            consecutive_below_1 = self._calculate_consecutive_days_below(data['Close'], 1.0)
            
            # Drawdown from high since IPO
            drawdown_from_high = self._calculate_drawdown_from_high(data['Close'])
            
            # Market cap (if available)
            market_cap = self._get_market_cap(symbol, last_close)
            
            result = {
                'symbol': symbol,
                'lastClose': last_close,
                'lastVolume': last_volume,
                'rsi14': rsi,
                'adx14': adx,
                'volSMA7': volume_sma_7,
                'volSpikeRatio': volume_spike_ratio,
                'daysConsecBelow1': consecutive_below_1,
                'drawdownFromHigh': drawdown_from_high,
                'marketCap': market_cap,
                'ipoDate': ipo_date or 'Unknown'
            }
            
            logger.debug(f"Analyzed {symbol}: Close=${last_close:.2f}, RSI={rsi:.1f}, ADX={adx:.1f}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return self._empty_result(symbol)
    
    def _empty_result(self, symbol: str) -> Dict:
        """Return empty result for failed analysis"""
        return {
            'symbol': symbol,
            'lastClose': 0.0,
            'lastVolume': 0,
            'rsi14': 0.0,
            'adx14': 0.0,
            'volSMA7': 0.0,
            'volSpikeRatio': 0.0,
            'daysConsecBelow1': 0,
            'drawdownFromHigh': 0.0,
            'marketCap': None,
            'ipoDate': 'Unknown'
        }
    
    def _calculate_consecutive_days_below(self, prices: pd.Series, threshold: float) -> int:
        """Calculate maximum consecutive days below threshold"""
        if prices.empty:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for price in prices:
            if price < threshold:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_drawdown_from_high(self, prices: pd.Series) -> float:
        """Calculate drawdown from highest point"""
        if prices.empty:
            return 0.0
        
        highest = prices.max()
        current = prices.iloc[-1]
        
        if highest == 0:
            return 0.0
        
        return ((highest - current) / highest) * 100
    
    def _get_market_cap(self, symbol: str, price: float) -> Optional[float]:
        """Get market cap if available"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            shares_outstanding = info.get('sharesOutstanding')
            if shares_outstanding:
                return price * shares_outstanding
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not get market cap for {symbol}: {e}")
            return None


def analyze_stocks(symbols: List[str], ipo_dates: Optional[Dict[str, str]] = None) -> List[Dict]:
    """Analyze multiple stocks"""
    fetcher = MarketDataFetcher()
    analyzer = StockAnalyzer()
    
    # Fetch data for all symbols
    stock_data = fetcher.fetch_multiple_stocks(symbols)
    
    # Analyze each stock
    results = []
    for symbol in symbols:
        if symbol in stock_data:
            ipo_date = ipo_dates.get(symbol) if ipo_dates else None
            analysis = analyzer.analyze_stock(symbol, stock_data[symbol], ipo_date)
            results.append(analysis)
        else:
            logger.warning(f"No data available for {symbol}")
    
    return results
