"""
Caching module for OHLCV data using Parquet format.
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
import os
from pathlib import Path
import logging
from datetime import datetime, timedelta
import pyarrow as pa
import pyarrow.parquet as pq
import hashlib

from ..config import get_config

logger = logging.getLogger(__name__)


class DataCache:
    """Cache for OHLCV data using Parquet format."""
    
    def __init__(self, cache_dir: str = "./cache"):
        """
        Initialize data cache.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache metadata file
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata."""
        if self.metadata_file.exists():
            try:
                import json
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache metadata: {e}")
        
        return {}
    
    def _save_metadata(self):
        """Save cache metadata."""
        try:
            import json
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")
    
    def _get_cache_key(self, symbol: str, timeframe: str) -> str:
        """Generate cache key for symbol and timeframe."""
        key_string = f"{symbol}_{timeframe}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cache_file(self, symbol: str, timeframe: str) -> Path:
        """Get cache file path for symbol and timeframe."""
        cache_key = self._get_cache_key(symbol, timeframe)
        return self.cache_dir / f"{cache_key}.parquet"
    
    def _is_cache_valid(self, symbol: str, timeframe: str, max_age_hours: int = 24) -> bool:
        """Check if cache is valid."""
        cache_file = self._get_cache_file(symbol, timeframe)
        
        if not cache_file.exists():
            return False
        
        # Check file age
        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age.total_seconds() > max_age_hours * 3600:
            return False
        
        # Check metadata
        cache_key = self._get_cache_key(symbol, timeframe)
        if cache_key not in self.metadata:
            return False
        
        return True
    
    def get_cached_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get cached data for symbol and timeframe.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            
        Returns:
            Cached DataFrame or None if not available
        """
        if not self._is_cache_valid(symbol, timeframe):
            return None
        
        try:
            cache_file = self._get_cache_file(symbol, timeframe)
            df = pd.read_parquet(cache_file)
            
            # Ensure proper column names and types
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"Loaded cached data for {symbol} {timeframe}: {len(df)} candles")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load cached data for {symbol} {timeframe}: {e}")
            return None
    
    def save_data(self, symbol: str, timeframe: str, data: pd.DataFrame):
        """
        Save data to cache.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            data: DataFrame with OHLCV data
        """
        try:
            cache_file = self._get_cache_file(symbol, timeframe)
            
            # Prepare data for saving
            df_to_save = data.copy()
            df_to_save.reset_index(inplace=True)
            df_to_save['timestamp'] = df_to_save['timestamp'].astype('int64') // 10**6  # Convert to milliseconds
            
            # Save to parquet
            df_to_save.to_parquet(cache_file, index=False)
            
            # Update metadata
            cache_key = self._get_cache_key(symbol, timeframe)
            self.metadata[cache_key] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'cached_at': datetime.now().isoformat(),
                'rows': len(data),
                'start_date': data.index.min().isoformat(),
                'end_date': data.index.max().isoformat(),
            }
            
            self._save_metadata()
            
            logger.info(f"Saved {len(data)} candles to cache for {symbol} {timeframe}")
            
        except Exception as e:
            logger.error(f"Failed to save data to cache for {symbol} {timeframe}: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information."""
        cache_files = list(self.cache_dir.glob("*.parquet"))
        
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'cache_dir': str(self.cache_dir),
            'total_files': len(cache_files),
            'total_size_mb': total_size / (1024 * 1024),
            'metadata_entries': len(self.metadata),
        }
    
    def clear_cache(self, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        """
        Clear cache for specific symbol/timeframe or all.
        
        Args:
            symbol: Specific symbol to clear (optional)
            timeframe: Specific timeframe to clear (optional)
        """
        if symbol and timeframe:
            # Clear specific symbol/timeframe
            cache_file = self._get_cache_file(symbol, timeframe)
            if cache_file.exists():
                cache_file.unlink()
                
            cache_key = self._get_cache_key(symbol, timeframe)
            if cache_key in self.metadata:
                del self.metadata[cache_key]
                self._save_metadata()
                
            logger.info(f"Cleared cache for {symbol} {timeframe}")
        else:
            # Clear all cache
            cache_files = list(self.cache_dir.glob("*.parquet"))
            for cache_file in cache_files:
                cache_file.unlink()
            
            self.metadata.clear()
            self._save_metadata()
            
            logger.info(f"Cleared all cache ({len(cache_files)} files)")


def ohlcv_to_dataframe(ohlcv: List[List]) -> pd.DataFrame:
    """
    Convert OHLCV data to DataFrame.
    
    Args:
        ohlcv: List of OHLCV data from ccxt
        
    Returns:
        DataFrame with proper columns and index
    """
    if not ohlcv:
        return pd.DataFrame()
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Ensure numeric types
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Remove any rows with NaN values
    df.dropna(inplace=True)
    
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
    combined.sort_index(inplace=True)
    
    return combined


def filter_data_by_date_range(data: pd.DataFrame, start_date: datetime, 
                            end_date: datetime) -> pd.DataFrame:
    """
    Filter data by date range.
    
    Args:
        data: DataFrame with datetime index
        start_date: Start date
        end_date: End date
        
    Returns:
        Filtered DataFrame
    """
    return data[(data.index >= start_date) & (data.index <= end_date)]


def validate_ohlcv_data(data: pd.DataFrame) -> bool:
    """
    Validate OHLCV data integrity.
    
    Args:
        data: DataFrame to validate
        
    Returns:
        True if data is valid
    """
    if data.empty:
        return False
    
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Check required columns
    if not all(col in data.columns for col in required_columns):
        logger.error("Missing required columns")
        return False
    
    # Check for NaN values
    if data[required_columns].isnull().any().any():
        logger.error("Data contains NaN values")
        return False
    
    # Check OHLC relationships
    invalid_ohlc = (
        (data['high'] < data['low']) |
        (data['high'] < data['open']) |
        (data['high'] < data['close']) |
        (data['low'] > data['open']) |
        (data['low'] > data['close'])
    )
    
    if invalid_ohlc.any():
        logger.error("Invalid OHLC relationships found")
        return False
    
    # Check volume
    if (data['volume'] < 0).any():
        logger.error("Negative volume values found")
        return False
    
    return True


def resample_data(data: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Resample data to different timeframe.
    
    Args:
        data: DataFrame with OHLCV data
        timeframe: Target timeframe
        
    Returns:
        Resampled DataFrame
    """
    if data.empty:
        return data
    
    # Map timeframe to pandas frequency
    freq_map = {
        '1m': '1T',
        '3m': '3T',
        '5m': '5T',
        '15m': '15T',
        '30m': '30T',
        '1h': '1H',
        '2h': '2H',
        '4h': '4H',
        '6h': '6H',
        '8h': '8H',
        '12h': '12H',
        '1d': '1D',
        '3d': '3D',
        '1w': '1W',
        '1M': '1M',
    }
    
    freq = freq_map.get(timeframe, '1H')
    
    # Resample OHLCV data
    resampled = data.resample(freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
    })
    
    # Remove rows with NaN values
    resampled.dropna(inplace=True)
    
    return resampled


def filter_data_by_date_range(data: pd.DataFrame, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Filter data by date range."""
    return data[(data.index >= start_date) & (data.index <= end_date)]


def validate_ohlcv_data(data: pd.DataFrame) -> bool:
    """Validate OHLCV data structure."""
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    return all(col in data.columns for col in required_columns) and not data.empty
