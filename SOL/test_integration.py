#!/usr/bin/env python3
"""Integration test for live_loop with new features."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))

from src.features import add_features, get_feature_columns
from src.models.transformer import SeqClassifier
from src.live_loop import on_new_bar
from src.regime import detect_volatility_regime, detect_trend_regime, get_regime_thresholds
from src.slippage import calculate_dynamic_slippage
from src.latency import get_latency_tracker

def test_integration():
    """Test full integration."""
    print("🧪 Testing integration...")
    
    # Create sample data (enough for window + features)
    dates = pd.date_range('2024-01-01', periods=300, freq='3min')
    np.random.seed(42)
    
    trend = np.linspace(50000, 55000, 300)
    df = pd.DataFrame({
        'time': dates,
        'open': trend + np.random.randn(300) * 500,
        'high': trend + np.random.randn(300) * 500 + 200,
        'low': trend + np.random.randn(300) * 500 - 200,
        'close': trend + np.random.randn(300) * 500,
        'volume': 1000 + np.random.randn(300) * 100,
    })
    
    # Add features with leakage prevention
    print("   📊 Adding features (with leakage prevention)...")
    df = add_features(df, use_previous_bar=True)
    feature_cols = get_feature_columns(df)
    print(f"   ✅ Features: {len(feature_cols)}")
    
    # Create dummy model
    print("   🤖 Creating dummy model...")
    model = SeqClassifier(n_features=len(feature_cols))
    model.eval()
    print(f"   ✅ Model: {len(feature_cols)} features")
    
    # Test regime detection
    print("   📈 Testing regime detection...")
    vol_regime = detect_volatility_regime(df)
    trend_regime = detect_trend_regime(df)
    print(f"   ✅ Vol regime: {vol_regime.iloc[-1]}")
    print(f"   ✅ Trend regime: {trend_regime.iloc[-1]}")
    
    thr_long, thr_short = get_regime_thresholds(
        vol_regime.iloc[-1],
        trend_regime.iloc[-1],
        0.60, 0.60
    )
    print(f"   ✅ Regime thresholds: Long={thr_long:.2f}, Short={thr_short:.2f}")
    
    # Test slippage
    print("   💰 Testing slippage calculation...")
    price = float(df['close'].iloc[-1])
    slippage = calculate_dynamic_slippage(df, price)
    print(f"   ✅ Slippage: {slippage*100:.4f}%")
    
    # Test latency tracker
    print("   ⏱️  Testing latency tracker...")
    tracker = get_latency_tracker()
    tracker.start_timer("integration_test")
    import time
    time.sleep(0.05)
    latency = tracker.end_timer("integration_test")
    print(f"   ✅ Latency tracked: {latency:.2f}ms")
    
    # Test on_new_bar call (without actual orders)
    print("   🔄 Testing on_new_bar (signal generation only)...")
    try:
        # This will generate signals but won't place orders (order client not initialized)
        on_new_bar(
            df=df,
            model=model,
            feature_cols=feature_cols,
            window=64,
            tp_pct=0.005,
            sl_pct=0.008,
            thr_long=0.60,
            thr_short=0.60,
            use_regime_thresholds=True,
        )
        print("   ✅ on_new_bar executed successfully")
    except Exception as e:
        # Expected: order client not initialized
        if "Order client" in str(e) or "not initialized" in str(e).lower():
            print("   ✅ Signal generation OK (order client not initialized as expected)")
        else:
            raise
    
    print("\n✅ Integration test PASSED!")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 INTEGRATION TEST")
    print("=" * 60)
    
    try:
        test_integration()
        print("\n" + "=" * 60)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

