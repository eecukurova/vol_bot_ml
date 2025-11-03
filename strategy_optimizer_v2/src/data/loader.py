"""
Data loader module that provides a unified interface for fetching OHLCV data.
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
import logging
from datetime import datetime, timedelta
from pathlib import Path

from .ccxt_client import CCXTClient, create_client_from_config, ohlcv_to_dataframe, merge_ohlcv_data
from .cache import DataCache, filter_data_by_date_range, validate_ohlcv_data
from ..config import get_config

logger = logging.getLogger(__name__)


class DataLoader:
    """Unified data loader with caching and fallback support."""
    
    def __init__(self, cache_dir: Optional[str] = None, use_cache: bool = True):
        """
        Initialize data loader.
        
        Args:
            cache_dir: Cache directory path
            use_cache: Whether to use caching
        """
        self.config = get_config()
        self.use_cache = use_cache
        
        # Initialize cache
        if use_cache:
            cache_path = cache_dir or self.config.data.cache_dir
            self.cache = DataCache(cache_path)
        else:
            self.cache = None
        
        # Initialize CCXT client
        self.client = create_client_from_config()
        
        # CSV fallback support
        self.csv_fallback_dir = None
    
    def set_csv_fallback(self, csv_dir: str):
        """
        Set CSV fallback directory for offline mode.
        
        Args:
            csv_dir: Directory containing CSV files
        """
        self.csv_fallback_dir = Path(csv_dir)
        logger.info(f"CSV fallback directory set to: {csv_dir}")
    
    def get_ohlcv(self, symbol: str, timeframe: str, since: Optional[datetime] = None,
                 until: Optional[datetime] = None, limit: Optional[int] = None,
                 use_cache: bool = True) -> pd.DataFrame:
        """
        Get OHLCV data for symbol and timeframe.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1h', '4h', '1d')
            since: Start date
            until: End date
            limit: Maximum number of candles
            use_cache: Whether to use cache
            
        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Loading data for {symbol} {timeframe}")
        
        # Try cache first
        if use_cache and self.cache:
            cached_data = self.cache.get_cached_data(symbol, timeframe)
            if cached_data is not None:
                # Filter by date range if specified
                if since or until:
                    cached_data = filter_data_by_date_range(cached_data, since or datetime.min, until or datetime.max)
                
                if not cached_data.empty:
                    logger.info(f"Using cached data for {symbol} {timeframe}: {len(cached_data)} candles")
                    return cached_data
        
        # Try CSV fallback
        if self.csv_fallback_dir:
            csv_data = self._load_from_csv(symbol, timeframe)
            if csv_data is not None:
                logger.info(f"Using CSV data for {symbol} {timeframe}: {len(csv_data)} candles")
                return csv_data
        
        # Fetch from exchange
        try:
            # Convert datetime to timestamp
            since_timestamp = None
            if since:
                since_timestamp = int(since.timestamp() * 1000)
            
            # Fetch data
            ohlcv = self.client.fetch_ohlcv(symbol, timeframe, since_timestamp, limit)
            
            if not ohlcv:
                logger.warning(f"No data received for {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = ohlcv_to_dataframe(ohlcv)
            
            # Validate data
            if not validate_ohlcv_data(df):
                logger.error(f"Invalid data received for {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Filter by date range if specified
            if since or until:
                df = filter_data_by_date_range(df, since or datetime.min, until or datetime.max)
            
            # Save to cache
            if use_cache and self.cache:
                self.cache.save_data(symbol, timeframe, df)
            
            logger.info(f"Fetched {len(df)} candles for {symbol} {timeframe}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def get_multiple_symbols(self, symbols: List[str], timeframe: str,
                           since: Optional[datetime] = None, until: Optional[datetime] = None,
                           limit: Optional[int] = None) -> Dict[str, pd.DataFrame]:
        """
        Get OHLCV data for multiple symbols.
        
        Args:
            symbols: List of trading pair symbols
            timeframe: Timeframe
            since: Start date
            until: End date
            limit: Maximum number of candles per symbol
            
        Returns:
            Dictionary mapping symbols to DataFrames
        """
        results = {}
        
        for symbol in symbols:
            try:
                df = self.get_ohlcv(symbol, timeframe, since, until, limit)
                results[symbol] = df
            except Exception as e:
                logger.error(f"Failed to load data for {symbol}: {e}")
                results[symbol] = pd.DataFrame()
        
        return results
    
    def _load_from_csv(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Load data from CSV file (fallback mode).
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            
        Returns:
            DataFrame or None if file not found
        """
        if not self.csv_fallback_dir:
            return None
        
        # Try different CSV file naming patterns
        patterns = [
            f"{symbol.replace('/', '_')}_{timeframe}.csv",
            f"{symbol}_{timeframe}.csv",
            f"{symbol.replace('/', '')}_{timeframe}.csv",
        ]
        
        for pattern in patterns:
            csv_file = self.csv_fallback_dir / pattern
            if csv_file.exists():
                try:
                    df = pd.read_csv(csv_file)
                    
                    # Ensure proper column names
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df.set_index('timestamp', inplace=True)
                    elif 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'])
                        df.set_index('datetime', inplace=True)
                    else:
                        # Assume first column is timestamp
                        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
                        df.set_index(df.columns[0], inplace=True)
                    
                    # Ensure required columns
                    required_columns = ['open', 'high', 'low', 'close', 'volume']
                    if not all(col in df.columns for col in required_columns):
                        logger.error(f"CSV file {csv_file} missing required columns")
                        continue
                    
                    # Validate data
                    if validate_ohlcv_data(df):
                        logger.info(f"Loaded CSV data from {csv_file}: {len(df)} candles")
                        return df
                    else:
                        logger.error(f"Invalid data in CSV file {csv_file}")
                        continue
                        
                except Exception as e:
                    logger.error(f"Failed to load CSV file {csv_file}: {e}")
                    continue
        
        return None
    
    def update_data(self, symbol: str, timeframe: str, days_back: int = 1) -> pd.DataFrame:
        """
        Update data by fetching recent candles.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            days_back: Number of days to look back for updates
            
        Returns:
            Updated DataFrame
        """
        logger.info(f"Updating data for {symbol} {timeframe}")
        
        # Get existing cached data
        existing_data = pd.DataFrame()
        if self.cache:
            existing_data = self.cache.get_cached_data(symbol, timeframe) or pd.DataFrame()
        
        # Calculate start date for update
        if existing_data.empty:
            start_date = datetime.now() - timedelta(days=days_back)
        else:
            # Start from last candle
            start_date = existing_data.index[-1]
        
        # Fetch new data
        new_data = self.get_ohlcv(symbol, timeframe, since=start_date, use_cache=False)
        
        if new_data.empty:
            logger.warning(f"No new data available for {symbol} {timeframe}")
            return existing_data
        
        # Merge with existing data
        if not existing_data.empty:
            merged_data = merge_ohlcv_data(existing_data, new_data)
        else:
            merged_data = new_data
        
        # Save updated data to cache
        if self.cache:
            self.cache.save_data(symbol, timeframe, merged_data)
        
        logger.info(f"Updated data for {symbol} {timeframe}: {len(merged_data)} total candles")
        return merged_data
    
    def get_data_info(self) -> Dict[str, Any]:
        """Get information about available data."""
        info = {
            'client_info': self.client.get_exchange_info(),
            'cache_info': self.cache.get_cache_info() if self.cache else None,
            'csv_fallback': str(self.csv_fallback_dir) if self.csv_fallback_dir else None,
        }
        return info
    
    def clear_cache(self, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        """Clear cache for specific symbol/timeframe or all."""
        if self.cache:
            self.cache.clear_cache(symbol, timeframe)


def create_data_loader(cache_dir: Optional[str] = None, use_cache: bool = True) -> DataLoader:
    """
    Create a data loader instance.
    
    Args:
        cache_dir: Cache directory path
        use_cache: Whether to use caching
        
    Returns:
        DataLoader instance
    """
    return DataLoader(cache_dir, use_cache)


def get_historical_data(symbol: str, timeframe: str, days: int = 365,
                       cache_dir: Optional[str] = None) -> pd.DataFrame:
    """
    Convenience function to get historical data.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe
        days: Number of days of historical data
        cache_dir: Cache directory
        
    Returns:
        DataFrame with historical data
    """
    loader = create_data_loader(cache_dir)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    return loader.get_ohlcv(symbol, timeframe, start_date, end_date)


def validate_symbols(symbols: List[str]) -> List[str]:
    """
    Validate symbols against exchange.
    
    Args:
        symbols: List of symbols to validate
        
    Returns:
        List of valid symbols
    """
    loader = create_data_loader(use_cache=False)
    valid_symbols = []
    
    for symbol in symbols:
        if loader.client.validate_symbol(symbol):
            valid_symbols.append(symbol)
        else:
            logger.warning(f"Invalid symbol: {symbol}")
    
    return valid_symbols