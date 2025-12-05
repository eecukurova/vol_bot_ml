"""Utility functions for Volensy LLM."""

import json
import random
import numpy as np
import torch
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def set_seed(seed: int = 42) -> None:
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def time_based_split(
    df,
    val_ratio: float = 0.2,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Split DataFrame into train/validation by time.

    Args:
        df: DataFrame with time index
        val_ratio: Fraction for validation

    Returns:
        (train_end_idx, val_start_idx) indices
    """
    total = len(df)
    val_start = int(total * (1 - val_ratio))
    return val_start, val_start


def calculate_profit_factor(pnl: np.ndarray) -> float:
    """Calculate profit factor: sum of profits / abs sum of losses."""
    profits = pnl[pnl > 0].sum()
    losses = abs(pnl[pnl < 0].sum())
    return profits / losses if losses > 0 else np.inf


def calculate_drawdown(equity: np.ndarray) -> Dict[str, float]:
    """
    Calculate max drawdown from equity curve.

    Returns:
        {"max_dd": float, "max_dd_pct": float}
    """
    running_max = np.maximum.accumulate(equity)
    drawdown = equity - running_max
    max_dd = abs(drawdown.min())
    peak = running_max[np.argmin(drawdown)]
    max_dd_pct = (max_dd / peak * 100) if peak > 0 else 0.0
    return {"max_dd": max_dd, "max_dd_pct": max_dd_pct}


def save_feat_cols(feature_cols: List[str], path: Path) -> None:
    """Save feature column names to JSON."""
    with open(path, "w") as f:
        json.dump(feature_cols, f)


def load_feat_cols(path: Path) -> List[str]:
    """Load feature column names from JSON."""
    with open(path, "r") as f:
        return json.load(f)
