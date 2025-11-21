"""Triple-barrier first-touch labeling for Volensy LLM."""

import pandas as pd
import numpy as np
from typing import Tuple


def make_barrier_labels(
    df: pd.DataFrame,
    tp_pct: float,
    sl_pct: float,
    horizon: int,
) -> pd.DataFrame:
    """
    Apply triple-barrier first-touch labeling.

    For each bar, look ahead up to 'horizon' bars:
    - If TP touched before SL: Long (1)
    - If SL touched before TP: Flat (0)
    - For short: opposite of above

    Args:
        df: DataFrame with close prices
        tp_pct: Take-profit percentage (e.g., 0.005 for 0.5%)
        sl_pct: Stop-loss percentage (e.g., 0.008 for 0.8%)
        horizon: Maximum look-ahead bars

    Returns:
        DataFrame with 'y_long', 'y_short' columns
    """
    df = df.copy()
    n = len(df)
    
    y_long = np.zeros(n, dtype=int)
    y_short = np.zeros(n, dtype=int)
    
    close = df["close"].values
    
    for i in range(n):
        if i + horizon >= n:
            # Not enough future data
            y_long[i] = 0
            y_short[i] = 0
            continue
        
        entry = close[i]
        
        # Long barrier: entry * (1 + tp_pct) and entry * (1 - sl_pct)
        tp_long = entry * (1 + tp_pct)
        sl_long = entry * (1 - sl_pct)
        
        # Short barrier: entry * (1 - tp_pct) and entry * (1 + sl_pct)
        tp_short = entry * (1 - tp_pct)
        sl_short = entry * (1 + sl_pct)
        
        # Look ahead
        future_high = df["high"].iloc[i+1:i+1+horizon].values
        future_low = df["low"].iloc[i+1:i+1+horizon].values
        
        # Long label
        for j in range(len(future_high)):
            if future_high[j] >= tp_long:
                y_long[i] = 1  # TP touched first
                break
            elif future_low[j] <= sl_long:
                y_long[i] = 0  # SL touched first
                break
        
        # Short label
        for j in range(len(future_high)):
            if future_low[j] <= tp_short:
                y_short[i] = 2  # TP touched first
                break
            elif future_high[j] >= sl_short:
                y_short[i] = 0  # SL touched first
                break
    
    df["y_long"] = y_long
    df["y_short"] = y_short
    
    # For actual training, use combined: 0=Flat, 1=Long, 2=Short
    # Prefer long if both touch, else prefer short
    df["y"] = y_long.copy()
    df.loc[(y_long == 0) & (y_short == 2), "y"] = 2
    
    return df


def get_class_weights(y: np.ndarray) -> np.ndarray:
    """
    Calculate class weights for imbalanced dataset.

    Args:
        y: Array of class labels (0=Flat, 1=Long, 2=Short)

    Returns:
        Array of class weights
    """
    unique, counts = np.unique(y, return_counts=True)
    total = len(y)
    weights = np.zeros(len(unique))
    for i, cls in enumerate(unique):
        weights[int(cls)] = total / (len(unique) * counts[i])
    return weights
