#!/usr/bin/env python3
"""
Test High Win Rate Strategy with improved selectivity
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from src.strategy.regression_channel import RegressionChannelStrategy
from optimize_regression_channel_crypto import download_binance_futures_klines

def test_v2():
    print("\n" + "="*70)
    print("🚀 High Win Rate Test V2 - Improved Selectivity")
    print("Target: 75%+ Win Rate")
    print("="*70)
    
    df = download_binance_futures_klines("BTCUSDT", "15m", days=180)
    if df is None or len(df) < 200:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars")
    
    # Test with moderate parameters but improved selectivity logic
    test_params = [
        {
            'reg_len': 100,
            'inner_mult': 1.0,
            'outer_mult': 1.8,
            'sma_len': 20,
            'use_trend_filter': True,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 75.0,
            'os_level': 25.0,
            'tp_pct': 0.02,
            'sl_pct': 0.01,
        },
        {
            'reg_len': 100,
            'inner_mult': 1.0,
            'outer_mult': 2.0,
            'sma_len': 26,
            'use_trend_filter': True,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 80.0,
            'os_level': 20.0,
            'tp_pct': 0.025,
            'sl_pct': 0.012,
        },
        {
            'reg_len': 125,
            'inner_mult': 1.0,
            'outer_mult': 1.8,
            'sma_len': 20,
            'use_trend_filter': True,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 75.0,
            'os_level': 25.0,
            'tp_pct': 0.02,
            'sl_pct': 0.01,
        },
    ]
    
    print(f"\n📊 Testing {len(test_params)} combinations with improved selectivity...")
    print("="*70)
    
    results = []
    for i, params in enumerate(test_params, 1):
        print(f"\n{i}. Testing...")
        try:
            strategy = RegressionChannelStrategy(params)
            result = strategy.run_backtest(df, commission=0.0005, slippage=0.0002)
            
            print(f"   Trades: {result['total_trades']}")
            print(f"   Win Rate: {result['win_rate']:.1f}% {'⭐' if result['win_rate'] >= 75 else ''}")
            print(f"   Profit Factor: {result['profit_factor']:.2f}")
            print(f"   Return: {result['total_return_pct']:.1f}%")
            
            if result['win_rate'] >= 75:
                print(f"   ✅ FOUND 75%+ WIN RATE!")
                results.append({'params': params, 'results': result})
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    if results:
        print("\n" + "="*70)
        print("✅ SUCCESS - Found strategies with 75%+ Win Rate!")
        print("="*70)
        for i, r in enumerate(results, 1):
            res = r['results']
            p = r['params']
            print(f"\n{i}. Win Rate: {res['win_rate']:.1f}%")
            print(f"   Trades: {res['total_trades']}")
            print(f"   PF: {res['profit_factor']:.2f}")
            print(f"   Return: {res['total_return_pct']:.1f}%")
            print(f"   Params: reg={p['reg_len']}, outer={p['outer_mult']}, tp={p['tp_pct']*100:.1f}%, sl={p['sl_pct']*100:.1f}%")
    else:
        print("\n⚠️  No 75%+ win rate found with current parameters")

if __name__ == "__main__":
    test_v2()

