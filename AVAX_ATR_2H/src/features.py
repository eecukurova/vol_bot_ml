"""Feature engineering for Volensy LLM."""

import pandas as pd
import numpy as np
from typing import List


def add_features(df: pd.DataFrame, use_previous_bar: bool = True) -> pd.DataFrame:
    """
    Add engineered features to OHLCV DataFrame.
    
    CRITICAL: If use_previous_bar=True, features are calculated using previous bar
    to prevent data leakage (no lookahead bias).

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
        use_previous_bar: If True, use previous bar's OHLC for current bar features
                         (prevents data leakage). If False, use current bar (legacy).

    Returns:
        DataFrame with added feature columns
    """
    df = df.copy()
    
    # DATA LEAKAGE PREVENTION: Use previous bar's close for calculations
    # This ensures features don't include information from the current bar
    if use_previous_bar:
        # Shift close prices forward so we use previous bar's close
        close_for_calc = df["close"].shift(1).fillna(df["close"].iloc[0])
    else:
        close_for_calc = df["close"]
    
    # Log returns (multiple periods) - uses previous bar
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
    df["log_ret_3"] = df["log_ret"].rolling(3).sum()
    df["log_ret_5"] = df["log_ret"].rolling(5).sum()
    
    # HL range and body - use PREVIOUS bar's high/low/open/close
    if use_previous_bar:
        prev_high = df["high"].shift(1).fillna(df["high"].iloc[0])
        prev_low = df["low"].shift(1).fillna(df["low"].iloc[0])
        prev_open = df["open"].shift(1).fillna(df["open"].iloc[0])
        prev_close = df["close"].shift(1).fillna(df["close"].iloc[0])
        
        df["hl_range"] = prev_high - prev_low
        df["body"] = abs(prev_close - prev_open)
        df["hl_range_norm"] = df["hl_range"] / prev_close
        df["body_norm"] = df["body"] / prev_close
        
        # Upper/lower wick ratios - use previous bar
        prev_max_oc = pd.concat([prev_open, prev_close], axis=1).max(axis=1)
        prev_min_oc = pd.concat([prev_open, prev_close], axis=1).min(axis=1)
        df["upper_wick"] = prev_high - prev_max_oc
        df["lower_wick"] = prev_min_oc - prev_low
    else:
        # Legacy: use current bar (may cause data leakage)
        df["hl_range"] = df["high"] - df["low"]
        df["body"] = abs(df["close"] - df["open"])
        df["hl_range_norm"] = df["hl_range"] / df["close"]
        df["body_norm"] = df["body"] / df["close"]
        
        df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
        df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    
    df["upper_wick_ratio"] = np.where(df["hl_range"] > 0, df["upper_wick"] / df["hl_range"], 0)
    df["lower_wick_ratio"] = np.where(df["hl_range"] > 0, df["lower_wick"] / df["hl_range"], 0)
    
    # EMA distances and slopes - use previous bar's close for distance
    # Note: EMA itself can use all historical data, but distance calculation uses previous bar
    for period in [10, 20, 50, 200]:
        # EMA can use current close (it's a lagging indicator)
        ema = df["close"].ewm(span=period, adjust=False).mean()
        df[f"ema{period}"] = ema
        # Distance uses previous bar's close to prevent leakage
        df[f"ema{period}_dist"] = (close_for_calc - ema.shift(1).fillna(ema.iloc[0])) / close_for_calc  # Relative distance
        df[f"ema{period}_slope"] = ema.diff(3) / ema  # 3-bar slope
    
    # RSI(14) - uses previous bar's close for delta calculation
    delta = close_for_calc.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # Volume spike - use previous bar's volume to prevent leakage
    if use_previous_bar:
        prev_volume = df["volume"].shift(1).fillna(df["volume"].iloc[0])
        vol_mean = prev_volume.rolling(20, min_periods=1).mean()
        df["vol_spike"] = np.where(vol_mean > 0, prev_volume / vol_mean, 0)
    else:
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
