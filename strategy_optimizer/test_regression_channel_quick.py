#!/usr/bin/env python3
"""
Quick test for Regression Channel Strategy
Tests a few parameter combinations to verify it works
"""

import sys
from pathlib import Path
import pandas as pd
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.strategy.regression_channel import RegressionChannelStrategy
from optimize_regression_channel_crypto import download_binance_futures_klines

def quick_test():
    print("\n" + "="*70)
    print("🚀 Quick Test - Regression Channel Strategy")
    print("="*70)
    
    # Download data
    print("\n📥 Downloading BTCUSDT 15m data...")
    df = download_binance_futures_klines("BTCUSDT", "15m", days=90)  # Just 90 days for quick test
    if df is None or len(df) < 200:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Test a few parameter combinations
    test_params = [
        {
            'reg_len': 100,
            'inner_mult': 1.0,
            'outer_mult': 1.5,
            'sma_len': 14,
            'use_trend_filter': False,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 75.0,
            'os_level': 25.0,
            'tp_pct': 0.015,
            'sl_pct': 0.015,
        },
        {
            'reg_len': 75,
            'inner_mult': 1.0,
            'outer_mult': 1.8,
            'sma_len': 14,
            'use_trend_filter': False,
            'stoch_len': 10,
            'smooth_k': 2,
            'smooth_d': 2,
            'ob_level': 70.0,
            'os_level': 20.0,
            'tp_pct': 0.01,
            'sl_pct': 0.01,
        },
        {
            'reg_len': 100,
            'inner_mult': 1.0,
            'outer_mult': 2.0,
            'sma_len': 20,
            'use_trend_filter': False,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 80.0,
            'os_level': 30.0,
            'tp_pct': 0.02,
            'sl_pct': 0.02,
        },
    ]
    
    print(f"\n📊 Testing {len(test_params)} parameter combinations...")
    print("="*70)
    
    results = []
    for i, params in enumerate(test_params, 1):
        print(f"\n{i}. Testing parameters:")
        print(f"   reg_len={params['reg_len']}, outer_mult={params['outer_mult']}, "
              f"stoch_len={params['stoch_len']}, ob_level={params['ob_level']}, "
              f"os_level={params['os_level']}, tp={params['tp_pct']*100:.1f}%, sl={params['sl_pct']*100:.1f}%")
        
        try:
            strategy = RegressionChannelStrategy(params)
            result = strategy.run_backtest(df, commission=0.0005, slippage=0.0002)
            
            print(f"   ✅ Results:")
            print(f"      Trades: {result['total_trades']}")
            print(f"      Win Rate: {result['win_rate']:.1f}%")
            print(f"      Profit Factor: {result['profit_factor']:.2f}")
            print(f"      Return: {result['total_return_pct']:.1f}%")
            print(f"      Max DD: {result['max_drawdown_pct']:.1f}%")
            
            results.append({
                'params': params,
                'results': result
            })
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    
    if results:
        # Sort by win rate
        results.sort(key=lambda x: x['results']['win_rate'], reverse=True)
        
        print("\nBest by Win Rate:")
        best = results[0]
        r = best['results']
        p = best['params']
        print(f"  Win Rate: {r['win_rate']:.1f}%")
        print(f"  Trades: {r['total_trades']}")
        print(f"  Profit Factor: {r['profit_factor']:.2f}")
        print(f"  Return: {r['total_return_pct']:.1f}%")
        print(f"  Parameters:")
        print(f"    reg_len={p['reg_len']}, outer_mult={p['outer_mult']}")
        print(f"    stoch_len={p['stoch_len']}, ob_level={p['ob_level']}, os_level={p['os_level']}")
        print(f"    tp={p['tp_pct']*100:.1f}%, sl={p['sl_pct']*100:.1f}%")
        
        # Check if any strategy generates signals
        total_signals = sum([r['results']['total_trades'] for r in results])
        print(f"\n✅ Total signals generated: {total_signals}")
        if total_signals > 0:
            print("✅ Strategy is working and generating signals!")
        else:
            print("⚠️  No signals generated - parameters may need adjustment")
    else:
        print("❌ No successful tests")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    quick_test()

