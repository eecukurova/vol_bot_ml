"""Perpetual futures-specific features: funding rate, open interest, basis."""

import pandas as pd
import numpy as np
import requests
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def fetch_funding_rate(symbol: str = "BTCUSDT", exchange=None) -> Optional[float]:
    """
    Fetch current funding rate from Binance.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        exchange: ccxt exchange instance (optional)
        
    Returns:
        Funding rate as decimal (e.g., 0.0001 = 0.01%)
    """
    try:
        if exchange:
            # Use ccxt if available
            funding = exchange.fetch_funding_rate(symbol)
            return float(funding.get('fundingRate', 0.0))
        else:
            # Fallback to direct API call
            url = "https://fapi.binance.com/fapi/v1/premiumIndex"
            params = {"symbol": symbol}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            return float(data.get('lastFundingRate', 0.0))
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch funding rate: {e}")
        return None


def fetch_open_interest(symbol: str = "BTCUSDT", exchange=None) -> Optional[float]:
    """
    Fetch open interest from Binance.
    
    Args:
        symbol: Trading symbol
        exchange: ccxt exchange instance (optional)
        
    Returns:
        Open interest in USD
    """
    try:
        if exchange:
            # Try ccxt first
            try:
                oi = exchange.fetch_open_interest(symbol)
                return float(oi.get('openInterestAmount', 0.0))
            except:
                pass
        
        # Fallback to direct API
        url = "https://fapi.binance.com/fapi/v1/openInterest"
        params = {"symbol": symbol}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return float(data.get('openInterestValue', 0.0))  # In USD
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch open interest: {e}")
        return None


def calculate_basis(
    perp_price: float,
    spot_price: float,
) -> float:
    """
    Calculate perpetual-spot basis.
    
    Args:
        perp_price: Perpetual futures price
        spot_price: Spot price
        
    Returns:
        Basis as percentage (positive = premium, negative = discount)
    """
    if spot_price == 0:
        return 0.0
    return (perp_price - spot_price) / spot_price


def calculate_oi_change_rate(
    current_oi: float,
    historical_oi: list,
    window: int = 24,
) -> float:
    """
    Calculate open interest change rate.
    
    Args:
        current_oi: Current open interest
        historical_oi: List of historical OI values
        window: Window size for comparison
        
    Returns:
        Change rate as percentage
    """
    if not historical_oi or len(historical_oi) < window:
        return 0.0
    
    avg_oi = np.mean(historical_oi[-window:])
    if avg_oi == 0:
        return 0.0
    
    return (current_oi - avg_oi) / avg_oi


def add_perp_features(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    exchange=None,
    use_cached: bool = True,
) -> pd.DataFrame:
    """
    Add perpetual futures-specific features to DataFrame.
    
    Features added:
    - funding_rate: Current funding rate
    - funding_rate_ma: Moving average of funding rate
    - basis: Perp-spot basis (if spot price available)
    - oi_change_rate: Open interest change rate
    
    Args:
        df: DataFrame with OHLCV data
        symbol: Trading symbol
        exchange: ccxt exchange instance (optional)
        use_cached: Use cached values for historical data
        
    Returns:
        DataFrame with added perp features
    """
    df = df.copy()
    
    # Try to fetch funding rate (for latest bar only)
    funding_rate = fetch_funding_rate(symbol, exchange)
    
    if funding_rate is not None:
        # Add funding rate column (use same value for all bars if historical not available)
        df['funding_rate'] = funding_rate
        
        # Calculate funding rate moving average (if we have historical data)
        if len(df) >= 8:
            # Assume funding rate is relatively stable, use simple average
            df['funding_rate_ma'] = df['funding_rate'].rolling(8, min_periods=1).mean()
        else:
            df['funding_rate_ma'] = df['funding_rate']
        
        # Funding rate z-score
        if len(df) >= 50:
            df['funding_rate_z'] = (
                (df['funding_rate'] - df['funding_rate'].rolling(50, min_periods=1).mean()) /
                (df['funding_rate'].rolling(50, min_periods=1).std() + 1e-8)
            )
        else:
            df['funding_rate_z'] = 0.0
    else:
        df['funding_rate'] = 0.0
        df['funding_rate_ma'] = 0.0
        df['funding_rate_z'] = 0.0
    
    # Try to fetch open interest
    oi = fetch_open_interest(symbol, exchange)
    
    if oi is not None:
        # Add OI column (use same value if historical not available)
        df['open_interest'] = oi
        
        # Calculate OI change rate (simplified - using current vs recent average)
        if len(df) >= 24:
            df['oi_change_rate'] = (
                (df['open_interest'] - df['open_interest'].rolling(24, min_periods=1).mean()) /
                (df['open_interest'].rolling(24, min_periods=1).mean() + 1e-8)
            )
        else:
            df['oi_change_rate'] = 0.0
    else:
        df['open_interest'] = 0.0
        df['oi_change_rate'] = 0.0
    
    # Basis calculation (would need spot price - simplified here)
    # In production, fetch spot price from exchange
    df['basis'] = 0.0  # Placeholder - needs spot price data
    
    # Fill NaN
    df = df.fillna(0).replace([np.inf, -np.inf], 0)
    
    return df


def get_perp_feature_columns(df: pd.DataFrame) -> list:
    """Get perpetual futures feature column names."""
    perp_features = [
        'funding_rate_z',
        'funding_rate_ma',
        'oi_change_rate',
        'basis',
    ]
    return [col for col in perp_features if col in df.columns]

