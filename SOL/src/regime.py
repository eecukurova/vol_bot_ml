"""Regime detection for volatility and trend."""

import pandas as pd
import numpy as np
from typing import Dict, Tuple


def detect_volatility_regime(df: pd.DataFrame, lookback: int = 50) -> pd.Series:
    """
    Detect volatility regime using ATR-based classification.
    
    Args:
        df: DataFrame with OHLCV data
        lookback: Lookback period for ATR calculation
        
    Returns:
        Series with regime labels: "LOW", "MEDIUM", "HIGH"
    """
    # Calculate ATR
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift(1))
    low_close = abs(df["low"] - df["close"].shift(1))
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(lookback, min_periods=1).mean()
    atr_pct = (atr / df["close"]) * 100  # ATR as % of price
    
    # Classify into regimes (33rd and 67th percentiles)
    low_threshold = atr_pct.rolling(200, min_periods=1).quantile(0.33)
    high_threshold = atr_pct.rolling(200, min_periods=1).quantile(0.67)
    
    regime = pd.Series("MEDIUM", index=df.index)
    regime[atr_pct < low_threshold] = "LOW"
    regime[atr_pct > high_threshold] = "HIGH"
    
    return regime


def detect_trend_regime(df: pd.DataFrame) -> pd.Series:
    """
    Detect trend regime using EMA slopes.
    
    Args:
        df: DataFrame with EMA columns (ema50, ema200)
        
    Returns:
        Series with regime labels: "UPTREND", "DOWNTREND", "RANGE"
    """
    if "ema50" not in df.columns or "ema200" not in df.columns:
        return pd.Series("RANGE", index=df.index)
    
    # EMA relationship
    ema50_above_200 = df["ema50"] > df["ema200"]
    ema50_slope = df["ema50"].diff(5) / df["ema50"]  # 5-bar slope
    
    regime = pd.Series("RANGE", index=df.index)
    regime[ema50_above_200 & (ema50_slope > 0)] = "UPTREND"
    regime[~ema50_above_200 & (ema50_slope < 0)] = "DOWNTREND"
    
    return regime


def get_regime_table() -> Dict[Tuple[str, str], Dict[str, float]]:
    """
    Return regime-based threshold table.
    
    Format: {(vol_regime, trend_regime): {thr_long, thr_short}}
    
    Returns:
        Dictionary mapping (vol_regime, trend_regime) to thresholds
    """
    return {
        ("LOW", "UPTREND"): {"thr_long": 0.55, "thr_short": 0.70},
        ("LOW", "DOWNTREND"): {"thr_long": 0.70, "thr_short": 0.55},
        ("LOW", "RANGE"): {"thr_long": 0.60, "thr_short": 0.60},
        
        ("MEDIUM", "UPTREND"): {"thr_long": 0.60, "thr_short": 0.70},
        ("MEDIUM", "DOWNTREND"): {"thr_long": 0.70, "thr_short": 0.60},
        ("MEDIUM", "RANGE"): {"thr_long": 0.65, "thr_short": 0.65},
        
        ("HIGH", "UPTREND"): {"thr_long": 0.65, "thr_short": 0.75},
        ("HIGH", "DOWNTREND"): {"thr_long": 0.75, "thr_short": 0.65},
        ("HIGH", "RANGE"): {"thr_long": 0.70, "thr_short": 0.70},
    }


def get_regime_thresholds(
    vol_regime: str,
    trend_regime: str,
    default_long: float = 0.60,
    default_short: float = 0.60
) -> Tuple[float, float]:
    """
    Get regime-based thresholds.
    
    Args:
        vol_regime: "LOW", "MEDIUM", or "HIGH"
        trend_regime: "UPTREND", "DOWNTREND", or "RANGE"
        default_long: Default long threshold if regime not found
        default_short: Default short threshold if regime not found
        
    Returns:
        (thr_long, thr_short)
    """
    table = get_regime_table()
    key = (vol_regime, trend_regime)
    
    if key in table:
        return table[key]["thr_long"], table[key]["thr_short"]
    
    return default_long, default_short

