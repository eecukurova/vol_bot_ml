"""Feature engineering for Volensy LLM."""

import pandas as pd
import numpy as np
from typing import List


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add engineered features to OHLCV DataFrame.

    Features:
    - Log returns (multiple periods)
    - Rolling sums (3 periods)
    - HL range and body
    - Upper/lower wick ratios
    - EMA(10/20/50/200) distances and slopes
    - RSI(14)
    - Volume spike (vol / rolling mean(20))
    - 200-period rolling z-score for all features

    Args:
        df: DataFrame with open, high, low, close, volume

    Returns:
        DataFrame with added feature columns
    """
    df = df.copy()
    
    # Log returns (multiple periods)
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
    df["log_ret_3"] = df["log_ret"].rolling(3).sum()
    df["log_ret_5"] = df["log_ret"].rolling(5).sum()
    
    # HL range and body
    df["hl_range"] = df["high"] - df["low"]
    df["body"] = abs(df["close"] - df["open"])
    df["hl_range_norm"] = df["hl_range"] / df["close"]
    df["body_norm"] = df["body"] / df["close"]
    
    # Upper/lower wick ratios
    df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    df["upper_wick_ratio"] = np.where(df["hl_range"] > 0, df["upper_wick"] / df["hl_range"], 0)
    df["lower_wick_ratio"] = np.where(df["hl_range"] > 0, df["lower_wick"] / df["hl_range"], 0)
    
    # EMA distances and slopes
    for period in [10, 20, 50, 200]:
        ema = df["close"].ewm(span=period, adjust=False).mean()
        df[f"ema{period}"] = ema
        df[f"ema{period}_dist"] = (df["close"] - ema) / df["close"]  # Relative distance
        df[f"ema{period}_slope"] = ema.diff(3) / ema  # 3-bar slope
    
    # RSI(14)
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # Volume spike
    vol_mean = df["volume"].rolling(20).mean()
    df["vol_spike"] = np.where(vol_mean > 0, df["volume"] / vol_mean, 0)
    
    # 200-period rolling z-score normalization for all features
    feature_cols = [
        "log_ret", "log_ret_3", "log_ret_5",
        "hl_range_norm", "body_norm",
        "upper_wick_ratio", "lower_wick_ratio",
        "ema10_dist", "ema10_slope",
        "ema20_dist", "ema20_slope",
        "ema50_dist", "ema50_slope",
        "ema200_dist", "ema200_slope",
        "rsi",
        "vol_spike"
    ]
    
    for col in feature_cols:
        if col in df.columns:
            rolling_mean = df[col].rolling(200, min_periods=1).mean()
            rolling_std = df[col].rolling(200, min_periods=1).std()
            df[f"{col}_z"] = np.where(
                rolling_std > 0,
                (df[col] - rolling_mean) / rolling_std,
                0
            )
    
    # Clean NaN
    df = df.fillna(0).replace([np.inf, -np.inf], 0)
    
    return df


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """
    Extract feature column names (ending with _z).

    Args:
        df: DataFrame with engineered features

    Returns:
        List of feature column names
    """
    return [col for col in df.columns if col.endswith("_z")]


def prepare_feature_matrix(df: pd.DataFrame, feature_cols: List[str]) -> np.ndarray:
    """
    Extract feature matrix from DataFrame.

    Args:
        df: DataFrame with features
        feature_cols: List of feature column names

    Returns:
        (N, F) numpy array
    """
    feature_df = df[feature_cols].copy()
    # Fill any remaining NaN/Inf
    feature_df = feature_df.fillna(0).replace([np.inf, -np.inf], 0)
    return feature_df.values
