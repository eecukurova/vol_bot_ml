"""Enhanced labeling with early reversal detection."""

import pandas as pd
import numpy as np
from typing import Tuple, List


def make_early_reversal_labels(
    df: pd.DataFrame,
    tp_pct: float,
    sl_pct: float,
    horizon: int,
    early_bars: int = 5,
) -> pd.DataFrame:
    """
    Apply early reversal labeling - label bars BEFORE trend reversal happens.
    
    Strategy:
    1. Detect trend reversal points
    2. Label bars 5-10 bars BEFORE reversal as entry signals
    3. This helps model learn to predict reversals early
    
    Args:
        df: DataFrame with OHLCV and features
        tp_pct: Take-profit percentage
        sl_pct: Stop-loss percentage
        horizon: Maximum look-ahead bars
        early_bars: Number of bars before reversal to label (default: 5)
        
    Returns:
        DataFrame with 'y_long', 'y_short', 'y' columns
    """
    df = df.copy()
    n = len(df)
    
    y_long = np.zeros(n, dtype=int)
    y_short = np.zeros(n, dtype=int)
    
    # First, detect trend reversals
    reversals = detect_trend_reversals(df, horizon)
    
    # For each reversal, label bars BEFORE it
    for rev_idx, rev_type in reversals:
        # Label bars before reversal
        start_idx = max(0, rev_idx - early_bars)
        
        if rev_type == "BEARISH":  # Price peak, expect SHORT
            # Label bars before peak as SHORT signals
            for i in range(start_idx, rev_idx):
                if i < n:
                    # Check if SHORT would be profitable
                    entry = df["close"].iloc[i]
                    tp_short = entry * (1 - tp_pct)
                    sl_short = entry * (1 + sl_pct)
                    
                    # Check future bars
                    future_low = df["low"].iloc[i+1:min(i+1+horizon, n)].values
                    future_high = df["high"].iloc[i+1:min(i+1+horizon, n)].values
                    
                    for j in range(len(future_low)):
                        if future_low[j] <= tp_short:
                            y_short[i] = 2  # SHORT profitable
                            break
                        elif future_high[j] >= sl_short:
                            y_short[i] = 0  # SHORT stopped out
                            break
        
        elif rev_type == "BULLISH":  # Price trough, expect LONG
            # Label bars before trough as LONG signals
            for i in range(start_idx, rev_idx):
                if i < n:
                    # Check if LONG would be profitable
                    entry = df["close"].iloc[i]
                    tp_long = entry * (1 + tp_pct)
                    sl_long = entry * (1 - sl_pct)
                    
                    # Check future bars
                    future_high = df["high"].iloc[i+1:min(i+1+horizon, n)].values
                    future_low = df["low"].iloc[i+1:min(i+1+horizon, n)].values
                    
                    for j in range(len(future_high)):
                        if future_high[j] >= tp_long:
                            y_long[i] = 1  # LONG profitable
                            break
                        elif future_low[j] <= sl_long:
                            y_long[i] = 0  # LONG stopped out
                            break
    
    # Also apply standard triple-barrier labeling for non-reversal bars
    df_standard = make_barrier_labels(df, tp_pct, sl_pct, horizon)
    
    # Combine: Prefer early reversal labels, fallback to standard
    for i in range(n):
        if y_long[i] > 0 or y_short[i] > 0:
            # Keep early reversal label
            pass
        else:
            # Use standard label
            y_long[i] = df_standard["y_long"].iloc[i]
            y_short[i] = df_standard["y_short"].iloc[i]
    
    df["y_long"] = y_long
    df["y_short"] = y_short
    
    # Combined label
    df["y"] = y_long.copy()
    df.loc[(y_long == 0) & (y_short == 2), "y"] = 2
    
    return df


def detect_trend_reversals(df: pd.DataFrame, lookback: int = 50) -> list:
    """
    Detect trend reversal points.
    
    Returns:
        List of (index, reversal_type) tuples
        reversal_type: "BEARISH" (peak) or "BULLISH" (trough)
    """
    reversals = []
    n = len(df)
    
    # Use EMA crossover to detect reversals
    if "ema50" not in df.columns or "ema200" not in df.columns:
        return reversals
    
    ema50 = df["ema50"].values
    ema200 = df["ema200"].values
    
    # Detect EMA crossovers
    for i in range(1, n):
        # Bearish reversal: EMA50 crosses below EMA200
        if ema50[i-1] >= ema200[i-1] and ema50[i] < ema200[i]:
            # Find the peak price before this crossover
            peak_idx = i - 1
            for j in range(max(0, i - lookback), i):
                if df["high"].iloc[j] > df["high"].iloc[peak_idx]:
                    peak_idx = j
            reversals.append((peak_idx, "BEARISH"))
        
        # Bullish reversal: EMA50 crosses above EMA200
        elif ema50[i-1] <= ema200[i-1] and ema50[i] > ema200[i]:
            # Find the trough price before this crossover
            trough_idx = i - 1
            for j in range(max(0, i - lookback), i):
                if df["low"].iloc[j] < df["low"].iloc[trough_idx]:
                    trough_idx = j
            reversals.append((trough_idx, "BULLISH"))
    
    return reversals


def make_barrier_labels(
    df: pd.DataFrame,
    tp_pct: float,
    sl_pct: float,
    horizon: int,
) -> pd.DataFrame:
    """
    Standard triple-barrier labeling (for fallback).
    """
    df = df.copy()
    n = len(df)
    
    y_long = np.zeros(n, dtype=int)
    y_short = np.zeros(n, dtype=int)
    
    close = df["close"].values
    
    for i in range(n):
        if i + horizon >= n:
            y_long[i] = 0
            y_short[i] = 0
            continue
        
        entry = close[i]
        tp_long = entry * (1 + tp_pct)
        sl_long = entry * (1 - sl_pct)
        tp_short = entry * (1 - tp_pct)
        sl_short = entry * (1 + sl_pct)
        
        future_high = df["high"].iloc[i+1:i+1+horizon].values
        future_low = df["low"].iloc[i+1:i+1+horizon].values
        
        for j in range(len(future_high)):
            if future_high[j] >= tp_long:
                y_long[i] = 1
                break
            elif future_low[j] <= sl_long:
                y_long[i] = 0
                break
        
        for j in range(len(future_high)):
            if future_low[j] <= tp_short:
                y_short[i] = 2
                break
            elif future_high[j] >= sl_short:
                y_short[i] = 0
                break
    
    df["y_long"] = y_long
    df["y_short"] = y_short
    df["y"] = y_long.copy()
    df.loc[(y_long == 0) & (y_short == 2), "y"] = 2
    
    return df

