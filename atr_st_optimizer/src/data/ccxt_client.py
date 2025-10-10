"""
CCXT client for fetching OHLCV data with retry logic and rate limiting.
"""

import ccxt
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
import time
import logging
from datetime import datetime, timedelta
import os
from pathlib import Path

from config import get_config

logger = logging.getLogger(__name__)


class CCXTClient:
    """CCXT client with retry logic and rate limiting."""
    
    def __init__(self, exchange_name: str = "binance", api_key: Optional[str] = None, 
                 secret: Optional[str] = None, proxy_url: Optional[str] = None,
                 sandbox: bool = False):
        """
        Initialize CCXT client.
        
        Args:
            exchange_name: Name of the exchange
            api_key: API key (optional for public data)
            secret: API secret (optional for public data)
            proxy_url: Proxy URL (optional)
            sandbox: Use sandbox mode
        """
        self.exchange_name = exchange_name
        self.api_key = api_key
        self.secret = secret
        self.proxy_url = proxy_url
        self.sandbox = sandbox
        
        # Initialize exchange
        self._init_exchange()
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
        
    def _init_exchange(self):
        """Initialize the exchange instance."""
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            
            config = {
                'sandbox': self.sandbox,
                'enableRateLimit': True,
                'rateLimit': 1200,  # 1200ms between requests
            }
            
            if self.api_key and self.secret:
                config.update({
                    'apiKey': self.api_key,
                    'secret': self.secret,
                })
            
            if self.proxy_url:
                config['proxies'] = {
                    'http': self.proxy_url,
                    'https': self.proxy_url,
                }
            
            self.exchange = exchange_class(config)
            
            # Test connection
            if hasattr(self.exchange, 'fetch_status'):
                status = self.exchange.fetch_status()
                logger.info(f"Connected to {self.exchange_name}: {status.get('status', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.exchange_name}: {e}")
            raise
    
    def _rate_limit(self):
        """Apply rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, since: Optional[datetime] = None,
                   until: Optional[datetime] = None, limit: Optional[int] = None, retries: int = 3) -> List[List]:
        """
        Fetch OHLCV data with retry logic.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1h', '4h', '1d')
            since: Start datetime
            until: End datetime
            limit: Number of candles to fetch
            retries: Number of retry attempts
            
        Returns:
            List of OHLCV data
        """
        for attempt in range(retries + 1):
            try:
                self._rate_limit()
                
                logger.info(f"Fetching {symbol} {timeframe} data (attempt {attempt + 1})")
                
                # Convert datetime to milliseconds if provided
                since_ms = None
                if since is not None:
                    since_ms = int(since.timestamp() * 1000)
                
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since_ms,
                    limit=limit
                )
                
                logger.info(f"Fetched {len(ohlcv)} candles for {symbol} {timeframe}")
                return ohlcv
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {symbol} {timeframe}: {e}")
                
                if attempt == retries:
                    logger.error(f"All attempts failed for {symbol} {timeframe}")
                    raise
                
                # Exponential backoff
                sleep_time = 2 ** attempt
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
        
        return []
    
    def ohlcv_to_dataframe(self, ohlcv: List[List]) -> pd.DataFrame:
        """
        Convert OHLCV data to DataFrame.
        
        Args:
            ohlcv: List of OHLCV data
            
        Returns:
            DataFrame with OHLCV data
        """
        if not ohlcv:
            return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def fetch_multiple_symbols(self, symbols: List[str], timeframe: str,
                             since: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, List[List]]:
        """
        Fetch OHLCV data for multiple symbols.
        
        Args:
            symbols: List of trading pair symbols
            timeframe: Timeframe
            since: Start timestamp in milliseconds
            limit: Number of candles to fetch
            
        Returns:
            Dictionary mapping symbols to OHLCV data
        """
        results = {}
        
        for symbol in symbols:
            try:
                ohlcv = self.fetch_ohlcv(symbol, timeframe, since, limit)
                results[symbol] = ohlcv
            except Exception as e:
                logger.error(f"Failed to fetch data for {symbol}: {e}")
                results[symbol] = []
        
        return results
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information."""
        try:
            return {
                'name': self.exchange_name,
                'has': self.exchange.has,
                'rateLimit': self.exchange.rateLimit,
                'timeframes': self.exchange.timeframes,
            }
        except Exception as e:
            logger.error(f"Failed to get exchange info: {e}")
            return {}
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol exists on the exchange."""
        try:
            markets = self.exchange.load_markets()
            return symbol in markets
        except Exception as e:
            logger.error(f"Failed to validate symbol {symbol}: {e}")
            return False
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol information."""
        try:
            markets = self.exchange.load_markets()
            return markets.get(symbol)
        except Exception as e:
            logger.error(f"Failed to get symbol info for {symbol}: {e}")
            return None


def create_client_from_config() -> CCXTClient:
    """Create CCXT client from configuration."""
    config = get_config()
    
    return CCXTClient(
        exchange_name=config.data.exchange,
        api_key=config.data.api_key,
        secret=config.data.secret,
        proxy_url=config.data.proxy_url,
        sandbox=config.data.sandbox_mode
    )


def timestamp_to_datetime(timestamp: int) -> datetime:
    """Convert timestamp to datetime."""
    return datetime.fromtimestamp(timestamp / 1000)


def datetime_to_timestamp(dt: datetime) -> int:
    """Convert datetime to timestamp in milliseconds."""
    return int(dt.timestamp() * 1000)


def get_timeframe_ms(timeframe: str) -> int:
    """Convert timeframe string to milliseconds."""
    timeframe_map = {
        '1m': 60 * 1000,
        '3m': 3 * 60 * 1000,
        '5m': 5 * 60 * 1000,
        '15m': 15 * 60 * 1000,
        '30m': 30 * 60 * 1000,
        '1h': 60 * 60 * 1000,
        '2h': 2 * 60 * 60 * 1000,
        '4h': 4 * 60 * 60 * 1000,
        '6h': 6 * 60 * 60 * 1000,
        '8h': 8 * 60 * 60 * 1000,
        '12h': 12 * 60 * 60 * 1000,
        '1d': 24 * 60 * 60 * 1000,
        '3d': 3 * 24 * 60 * 60 * 1000,
        '1w': 7 * 24 * 60 * 60 * 1000,
        '1M': 30 * 24 * 60 * 60 * 1000,
    }
    
    return timeframe_map.get(timeframe, 60 * 60 * 1000)  # Default to 1h


def calculate_candles_needed(start_date: datetime, end_date: datetime, timeframe: str) -> int:
    """Calculate number of candles needed for date range."""
    timeframe_ms = get_timeframe_ms(timeframe)
    total_ms = (end_date - start_date).total_seconds() * 1000
    return int(total_ms / timeframe_ms) + 1


def ohlcv_to_dataframe(ohlcv_data: List[List]) -> pd.DataFrame:
    """
    Convert CCXT OHLCV data to DataFrame.
    
    Args:
        ohlcv_data: List of OHLCV arrays from CCXT
        
    Returns:
        DataFrame with OHLCV data
    """
    if not ohlcv_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    
    return df


def merge_ohlcv_data(existing_data: pd.DataFrame, new_data: pd.DataFrame) -> pd.DataFrame:
    """
    Merge new OHLCV data with existing data, removing duplicates.
    
    Args:
        existing_data: Existing DataFrame
        new_data: New DataFrame to merge
        
    Returns:
        Merged DataFrame
    """
    if existing_data.empty:
        return new_data
    
    if new_data.empty:
        return existing_data
    
    # Combine and remove duplicates
    combined = pd.concat([existing_data, new_data])
    combined = combined[~combined.index.duplicated(keep='last')]
    combined = combined.sort_index()
    
    return combined


def validate_symbol(symbol: str) -> bool:
    """
    Validate if symbol exists on exchange.
    
    Args:
        symbol: Symbol to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        config = get_config()
        exchange = config.data.exchange
        client = CCXTClient(exchange)
        markets = client._get_exchange().load_markets()
        return symbol in markets
    except Exception:
        return False


