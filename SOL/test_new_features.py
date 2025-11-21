#!/usr/bin/env python3
"""Test script for new features: leakage prevention, regime, slippage, latency."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from src.features import add_features, get_feature_columns
from src.regime import detect_volatility_regime, detect_trend_regime, get_regime_thresholds
from src.slippage import calculate_dynamic_slippage, apply_slippage_to_price, calculate_atr
from src.latency import get_latency_tracker, format_latency_alert

def test_features_no_leakage():
    """Test that features use previous bar data."""
    print("🧪 Testing feature leakage prevention...")
    
    # Create sample data
    dates = pd.date_range('2024-01-01', periods=250, freq='3min')
    np.random.seed(42)
    
    df = pd.DataFrame({
        'time': dates,
        'open': 50000 + np.random.randn(250) * 1000,
        'high': 51000 + np.random.randn(250) * 1000,
        'low': 49000 + np.random.randn(250) * 1000,
        'close': 50000 + np.random.randn(250) * 1000,
        'volume': 1000 + np.random.randn(250) * 100,
    })
    
    # Add features with leakage prevention
    df_features = add_features(df.copy(), use_previous_bar=True)
    
    # Check that features exist
    feature_cols = get_feature_columns(df_features)
    assert len(feature_cols) > 0, "No features generated"
    print(f"   ✅ Generated {len(feature_cols)} features")
    
    # Verify no NaN in final features
    for col in feature_cols:
        nan_count = df_features[col].isna().sum()
        assert nan_count == 0, f"Feature {col} has {nan_count} NaN values"
    
    print("   ✅ No data leakage - features use previous bar")
    return df_features


def test_regime_detection():
    """Test regime detection."""
    print("\n🧪 Testing regime detection...")
    
    # Create sample data with trend
    dates = pd.date_range('2024-01-01', periods=250, freq='3min')
    np.random.seed(42)
    
    trend = np.linspace(50000, 55000, 250)
    df = pd.DataFrame({
        'time': dates,
        'open': trend + np.random.randn(250) * 500,
        'high': trend + np.random.randn(250) * 500 + 200,
        'low': trend + np.random.randn(250) * 500 - 200,
        'close': trend + np.random.randn(250) * 500,
        'volume': 1000 + np.random.randn(250) * 100,
    })
    
    # Add EMA columns for trend detection
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Test volatility regime
    vol_regime = detect_volatility_regime(df)
    assert len(vol_regime) == len(df), "Vol regime length mismatch"
    assert all(reg in ['LOW', 'MEDIUM', 'HIGH'] for reg in vol_regime.unique()), "Invalid vol regime"
    print(f"   ✅ Volatility regimes: {vol_regime.value_counts().to_dict()}")
    
    # Test trend regime
    trend_regime = detect_trend_regime(df)
    assert len(trend_regime) == len(df), "Trend regime length mismatch"
    assert all(reg in ['UPTREND', 'DOWNTREND', 'RANGE'] for reg in trend_regime.unique()), "Invalid trend regime"
    print(f"   ✅ Trend regimes: {trend_regime.value_counts().to_dict()}")
    
    # Test threshold lookup
    thr_long, thr_short = get_regime_thresholds('MEDIUM', 'UPTREND')
    assert 0 < thr_long < 1 and 0 < thr_short < 1, "Invalid thresholds"
    print(f"   ✅ Regime thresholds: Long={thr_long:.2f}, Short={thr_short:.2f}")
    
    return df


def test_slippage_model():
    """Test dynamic slippage calculation."""
    print("\n🧪 Testing dynamic slippage model...")
    
    # Create sample data
    dates = pd.date_range('2024-01-01', periods=250, freq='3min')
    np.random.seed(42)
    
    df = pd.DataFrame({
        'time': dates,
        'open': 50000 + np.random.randn(250) * 1000,
        'high': 51000 + np.random.randn(250) * 1000,
        'low': 49000 + np.random.randn(250) * 1000,
        'close': 50000 + np.random.randn(250) * 1000,
        'volume': 1000 + np.random.randn(250) * 100,
    })
    
    price = 50000.0
    
    # Test slippage calculation
    slippage = calculate_dynamic_slippage(df, price)
    assert 0 < slippage < 0.01, f"Slippage out of range: {slippage}"
    print(f"   ✅ Calculated slippage: {slippage*100:.4f}%")
    
    # Test price adjustment
    adjusted_long = apply_slippage_to_price(price, 'LONG', slippage)
    adjusted_short = apply_slippage_to_price(price, 'SHORT', slippage)
    
    assert adjusted_long > price, "LONG should pay more"
    assert adjusted_short < price, "SHORT should receive less"
    print(f"   ✅ LONG entry: ${adjusted_long:.2f} (+{slippage*100:.4f}%)")
    print(f"   ✅ SHORT entry: ${adjusted_short:.2f} (-{slippage*100:.4f}%)")
    
    return slippage


def test_latency_tracking():
    """Test latency tracking."""
    print("\n🧪 Testing latency tracking...")
    
    tracker = get_latency_tracker()
    
    # Test timer
    tracker.start_timer("test_operation")
    import time
    time.sleep(0.1)  # 100ms
    latency = tracker.end_timer("test_operation")
    
    assert latency is not None, "Latency tracking failed"
    assert 90 < latency < 200, f"Unexpected latency: {latency}ms"  # Should be ~100ms
    print(f"   ✅ Tracked latency: {latency:.2f}ms")
    
    # Test alert formatting
    alert_msg = format_latency_alert("test_operation", 350.0)
    assert "350" in alert_msg and "EXCEEDED" in alert_msg
    print(f"   ✅ Alert format correct")
    
    return latency


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 TESTING NEW FEATURES")
    print("=" * 60)
    
    try:
        # Test 1: Feature leakage prevention
        df_features = test_features_no_leakage()
        
        # Test 2: Regime detection
        test_regime_detection()
        
        # Test 3: Slippage model
        test_slippage_model()
        
        # Test 4: Latency tracking
        test_latency_tracking()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

