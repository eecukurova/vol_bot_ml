"""Dataset creation for sliding windows."""

import numpy as np
import pandas as pd
import torch
from typing import Tuple, List


def make_windows(
    df: pd.DataFrame,
    feature_cols: List[str],
    y_col: str,
    win: int,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Create sliding windows for sequence classification.

    Args:
        df: DataFrame with features and labels
        feature_cols: List of feature column names
        y_col: Label column name
        win: Window length (sequence length)

    Returns:
        (X, Y, feature_cols)
        X: (N, T=win, F) numpy array
        Y: (N,) numpy array
    """
    # Extract feature matrix
    feature_matrix = df[feature_cols].values
    
    # Extract labels
    y = df[y_col].values
    
    n, f = feature_matrix.shape
    
    # Create windows
    X_list = []
    Y_list = []
    
    for i in range(win, n):
        X_window = feature_matrix[i-win:i]  # (win, f)
        X_list.append(X_window)
        Y_list.append(y[i])  # Label at end of window
    
    X = np.array(X_list)  # (N, win, f)
    Y = np.array(Y_list)  # (N,)
    
    return X, Y, feature_cols


class SequenceDataset:
    """PyTorch Dataset for sequences."""
    
    def __init__(self, X: np.ndarray, Y: np.ndarray):
        """
        Initialize dataset.

        Args:
            X: (N, T, F) numpy array
            Y: (N,) numpy array
        """
        self.X = torch.FloatTensor(X)
        self.Y = torch.LongTensor(Y)
    
    def __len__(self) -> int:
        return len(self.Y)
    
    def __getitem__(self, idx: int):
        return self.X[idx], self.Y[idx]
