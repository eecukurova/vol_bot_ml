"""Load and integrate hard negative examples into training data."""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def load_hard_negatives(hn_file: Path = Path("models/hard_negatives.json")) -> List[Dict]:
    """
    Load hard negative examples from JSON file.
    
    Args:
        hn_file: Path to hard negatives JSON file
    
    Returns:
        List of hard negative examples
    """
    if not hn_file.exists():
        logger.warning(f"Hard negatives file not found: {hn_file}")
        return []
    
    try:
        with open(hn_file) as f:
            data = json.load(f)
        examples = data.get('hard_negatives', [])
        logger.info(f"📋 Loaded {len(examples)} hard negative examples")
        return examples
    except Exception as e:
        logger.error(f"❌ Failed to load hard negatives: {e}")
        return []


def integrate_hard_negatives(
    df: pd.DataFrame,
    hard_negatives: List[Dict],
    feature_cols: List[str],
    window: int,
    y_col: str = "y"
) -> tuple[np.ndarray, np.ndarray]:
    """
    Integrate hard negatives into training data by duplicating matching windows.
    
    Strategy: For each hard negative, find the matching timestamp in df,
    duplicate the window containing that timestamp (weight times),
    and ensure the label is SL (negative class).
    
    Args:
        df: DataFrame with features and labels
        hard_negatives: List of hard negative examples
        feature_cols: List of feature column names
        window: Window length
        y_col: Label column name
    
    Returns:
        (X_extra, Y_extra) - Additional windows to add to training data
    """
    if not hard_negatives:
        return np.array([]), np.array([])
    
    # Convert df index to datetime if needed
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns:
            df = df.set_index('time')
        elif 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
        else:
            logger.warning("Cannot find time column in df, skipping hard negatives integration")
            return np.array([]), np.array([])
    
    X_extra_list = []
    Y_extra_list = []
    
    # Label mapping: SL -> 0 (FLAT), but we'll use the actual label from df
    # Actually, we want to ensure these are labeled as the negative outcome
    # For triple-barrier: 0=FLAT, 1=LONG, 2=SHORT
    # If hard negative hit SL, it means the prediction was wrong
    # So we should label it as the opposite of what was predicted
    
    for hn in hard_negatives:
        try:
            timestamp_str = hn.get('timestamp', '')
            if not timestamp_str:
                continue
            
            # Parse timestamp
            timestamp = pd.to_datetime(timestamp_str)
            
            # Find matching row in df
            matching_rows = df[df.index >= timestamp]
            if len(matching_rows) == 0:
                continue
            
            # Get the first matching row (closest to timestamp)
            match_idx = df.index.get_loc(matching_rows.index[0])
            
            # Ensure we have enough history for window
            if match_idx < window:
                continue
            
            # Extract window
            window_start = match_idx - window
            window_end = match_idx
            
            # Get window data
            window_data = df[feature_cols].iloc[window_start:window_end].values  # (window, features)
            
            # Get label at the end of window
            label = df[y_col].iloc[window_end]
            
            # Get weight (how many times to duplicate)
            weight = int(hn.get('weight', 1.0))
            
            # Duplicate this window (weight times)
            for _ in range(weight):
                X_extra_list.append(window_data)
                Y_extra_list.append(label)
            
        except Exception as e:
            logger.warning(f"Failed to integrate hard negative {hn.get('timestamp', 'unknown')}: {e}")
            continue
    
    if X_extra_list:
        X_extra = np.array(X_extra_list)  # (N_extra, window, features)
        Y_extra = np.array(Y_extra_list)  # (N_extra,)
        logger.info(f"✅ Added {len(X_extra)} hard negative windows to training data")
        return X_extra, Y_extra
    else:
        return np.array([]), np.array([])


def add_hard_negatives_to_training(
    X_train: np.ndarray,
    Y_train: np.ndarray,
    df: pd.DataFrame,
    feature_cols: List[str],
    window: int,
    y_col: str = "y",
    hn_file: Path = Path("models/hard_negatives.json")
) -> tuple[np.ndarray, np.ndarray]:
    """
    Add hard negatives to training data.
    
    Args:
        X_train: Original training windows
        Y_train: Original training labels
        df: DataFrame with features and labels
        feature_cols: List of feature column names
        window: Window length
        y_col: Label column name
        hn_file: Path to hard negatives JSON file
    
    Returns:
        (X_train_enhanced, Y_train_enhanced) - Training data with hard negatives
    """
    # Load hard negatives
    hard_negatives = load_hard_negatives(hn_file)
    
    if not hard_negatives:
        logger.info("No hard negatives found, using original training data")
        return X_train, Y_train
    
    # Integrate hard negatives
    X_extra, Y_extra = integrate_hard_negatives(
        df, hard_negatives, feature_cols, window, y_col
    )
    
    if len(X_extra) == 0:
        logger.info("No hard negatives could be integrated, using original training data")
        return X_train, Y_train
    
    # Concatenate
    X_train_enhanced = np.concatenate([X_train, X_extra], axis=0)
    Y_train_enhanced = np.concatenate([Y_train, Y_extra], axis=0)
    
    logger.info(f"📊 Enhanced training data: {len(X_train)} -> {len(X_train_enhanced)} (+{len(X_extra)})")
    
    return X_train_enhanced, Y_train_enhanced

