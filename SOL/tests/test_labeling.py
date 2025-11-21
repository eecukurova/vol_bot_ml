"""Test triple-barrier labeling."""

import numpy as np
import pandas as pd
import pytest

from src.labeling import make_barrier_labels


def test_labeling_basic():
    """Test basic labeling with artificial data."""
    # Create simple ascending price series
    n = 100
    prices = np.linspace(100, 110, n)
    
    df = pd.DataFrame({
        "open": prices * 0.999,
        "high": prices * 1.001,
        "low": prices * 0.999,
        "close": prices,
    })
    
    # Apply labeling
    tp_pct = 0.005  # 0.5%
    sl_pct = 0.010  # 1%
    horizon = 50
    
    df_labeled = make_barrier_labels(df, tp_pct, sl_pct, horizon)
    
    # Check columns exist
    assert "y_long" in df_labeled.columns
    assert "y_short" in df_labeled.columns
    assert "y" in df_labeled.columns
    
    # Check values are valid
    assert df_labeled["y"].isin([0, 1, 2]).all()


def test_labeling_tp_vs_sl():
    """Test that TP/SL are correctly identified."""
    # Create data where TP will be hit first
    n = 100
    base_price = 100.0
    prices = [base_price]
    
    for i in range(1, n):
        # Gentle upward trend
        prices.append(prices[-1] * 1.001)
    
    df = pd.DataFrame({
        "open": np.array(prices) * 0.999,
        "high": np.array(prices) * 1.002,
        "low": np.array(prices) * 0.999,
        "close": np.array(prices),
    })
    
    df_labeled = make_barrier_labels(
        df,
        tp_pct=0.005,
        sl_pct=0.020,
        horizon=50,
    )
    
    # Early bars should label as long (trending up)
    early_labels = df_labeled["y_long"].iloc[:20]
    assert (early_labels == 1).sum() > 0  # Some longs expected


if __name__ == "__main__":
    test_labeling_basic()
    test_labeling_tp_vs_sl()
    print("✓ All labeling tests passed")
