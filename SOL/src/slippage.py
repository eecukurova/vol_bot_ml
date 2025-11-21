"""Dynamic slippage model based on volatility and volume."""

import pandas as pd
import numpy as np
from typing import Optional


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range.
    
    Args:
        df: DataFrame with OHLCV data
        period: ATR period
        
    Returns:
        Series with ATR values
    """
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift(1))
    low_close = abs(df["low"] - df["close"].shift(1))
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period, min_periods=1).mean()
    
    return atr


def calculate_dynamic_slippage(
    df: pd.DataFrame,
    price: float,
    atr: Optional[pd.Series] = None,
    atr_beta: float = 0.5,
    volume_alpha: float = 0.3,
    base_slippage: float = 0.0002,  # 0.02% base slippage
) -> float:
    """
    Calculate dynamic slippage based on ATR and volume.
    
    Formula: slippage = base + (ATR_beta * ATR_pct) + (volume_alpha * (1 / vol_normalized))
    
    Args:
        df: DataFrame with recent bars (for volume calculation)
        price: Current price
        atr: Pre-calculated ATR series (if None, will calculate)
        atr_beta: ATR contribution factor
        volume_alpha: Volume contribution factor
        base_slippage: Base slippage percentage
        
    Returns:
        Slippage as decimal (e.g., 0.0005 = 0.05%)
    """
    if atr is None:
        atr = calculate_atr(df, period=14)
    
    # ATR as % of price
    atr_pct = (atr.iloc[-1] / price) if len(atr) > 0 else 0.001
    
    # Volume normalization (lower volume = higher slippage)
    vol_mean = df["volume"].rolling(20, min_periods=1).mean().iloc[-1]
    current_vol = df["volume"].iloc[-1]
    vol_normalized = current_vol / vol_mean if vol_mean > 0 else 1.0
    
    # Inverse volume factor (low volume = high slippage)
    vol_factor = volume_alpha * max(0.5, 1.0 / max(vol_normalized, 0.5))
    
    # Calculate dynamic slippage
    slippage = base_slippage + (atr_beta * atr_pct) + vol_factor
    
    # Cap at reasonable maximum (0.5%)
    slippage = min(slippage, 0.005)
    
    return slippage


def apply_slippage_to_price(
    price: float,
    side: str,
    slippage: float,
) -> float:
    """
    Apply slippage to price based on order side.
    
    Args:
        price: Original price
        side: "LONG" (buy) or "SHORT" (sell)
        slippage: Slippage as decimal (e.g., 0.0005)
        
    Returns:
        Adjusted price after slippage
    """
    if side == "LONG":
        # Buy orders: pay more (price * (1 + slippage))
        return price * (1 + slippage)
    elif side == "SHORT":
        # Sell orders: receive less (price * (1 - slippage))
        return price * (1 - slippage)
    else:
        return price

