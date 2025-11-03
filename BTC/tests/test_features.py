"""Test feature engineering."""

import numpy as np
import pandas as pd
import pytest

from src.features import add_features, get_feature_columns


def test_add_features():
    """Test feature addition."""
    # Create synthetic OHLCV data
    n = 300
    np.random.seed(42)
    
    prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    
    df = pd.DataFrame({
        "open": prices,
        "high": prices * 1.002,
        "low": prices * 0.998,
        "close": prices * 1.001,
        "volume": np.random.uniform(1000, 10000, n),
    })
    
    # Add features
    df_feat = add_features(df)
    
    # Check no NaN in numeric columns
    numeric_cols = df_feat.select_dtypes(include=[np.number]).columns
    assert df_feat[numeric_cols].isna().sum().sum() == 0
    
    # Check feature columns exist
    assert "ema10" in df_feat.columns
    assert "ema200" in df_feat.columns
    assert "rsi" in df_feat.columns
    assert "vol_spike" in df_feat.columns
    
    # Check z-score features
    feat_cols = get_feature_columns(df_feat)
    assert len(feat_cols) > 0
    for col in feat_cols:
        assert col.endswith("_z")
        assert col in df_feat.columns


if __name__ == "__main__":
    test_add_features()
    print("✓ All feature tests passed")
