#!/usr/bin/env python3
"""
Quick test for High Win Rate Regression Channel Strategy
Tests parameters focused on achieving 75%+ win rate
"""

import sys
from pathlib import Path
import pandas as pd
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.strategy.regression_channel import RegressionChannelStrategy
from optimize_regression_channel_crypto import download_binance_futures_klines

def test_high_winrate():
    print("\n" + "="*70)
    print("🚀 High Win Rate Test - Regression Channel Strategy")
    print("Target: 75%+ Win Rate")
    print("="*70)
    
    # Download data
    print("\n📥 Downloading BTCUSDT 15m data...")
    df = download_binance_futures_klines("BTCUSDT", "15m", days=180)
    if df is None or len(df) < 200:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Test parameters focused on high win rate
    # Strategy: Wider bands, longer periods, more selective signals
    test_params = [
        {
            'reg_len': 150,
            'inner_mult': 1.2,
            'outer_mult': 2.5,
            'sma_len': 26,
            'use_trend_filter': True,
            'stoch_len': 20,
            'smooth_k': 5,
            'smooth_d': 5,
            'ob_level': 85.0,
            'os_level': 15.0,
            'tp_pct': 0.025,
            'sl_pct': 0.012,
        },
        {
            'reg_len': 125,
            'inner_mult': 1.0,
            'outer_mult': 3.0,
            'sma_len': 30,
            'use_trend_filter': True,
            'stoch_len': 20,
            'smooth_k': 5,
            'smooth_d': 5,
            'ob_level': 90.0,
            'os_level': 10.0,
            'tp_pct': 0.03,
            'sl_pct': 0.01,
        },
        {
            'reg_len': 100,
            'inner_mult': 1.2,
            'outer_mult': 2.0,
            'sma_len': 20,
            'use_trend_filter': False,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 80.0,
            'os_level': 20.0,
            'tp_pct': 0.02,
            'sl_pct': 0.015,
        },
        {
            'reg_len': 150,
            'inner_mult': 1.0,
            'outer_mult': 2.5,
            'sma_len': 26,
            'use_trend_filter': False,
            'stoch_len': 20,
            'smooth_k': 5,
            'smooth_d': 5,
            'ob_level': 85.0,
            'os_level': 15.0,
            'tp_pct': 0.025,
            'sl_pct': 0.012,
        },
    ]
    
    print(f"\n📊 Testing {len(test_params)} high-selectivity parameter combinations...")
    print("="*70)
    
    results = []
    for i, params in enumerate(test_params, 1):
        print(f"\n{i}. Testing parameters:")
        print(f"   reg_len={params['reg_len']}, outer_mult={params['outer_mult']}, "
              f"stoch_len={params['stoch_len']}, ob_level={params['ob_level']}, "
              f"os_level={params['os_level']}, tp={params['tp_pct']*100:.1f}%, sl={params['sl_pct']*100:.1f}%")
        print(f"   trend_filter={params['use_trend_filter']}, sma_len={params['sma_len']}")
        
        try:
            strategy = RegressionChannelStrategy(params)
            result = strategy.run_backtest(df, commission=0.0005, slippage=0.0002)
            
            print(f"   ✅ Results:")
            print(f"      Trades: {result['total_trades']}")
            print(f"      Win Rate: {result['win_rate']:.1f}% {'⭐' if result['win_rate'] >= 75 else ''}")
            print(f"      Profit Factor: {result['profit_factor']:.2f}")
            print(f"      Return: {result['total_return_pct']:.1f}%")
            print(f"      Max DD: {result['max_drawdown_pct']:.1f}%")
            
            if result['total_trades'] > 0:
                print(f"      Avg Win: {result['avg_win_pct']:.2f}% | Avg Loss: {result['avg_loss_pct']:.2f}%")
                if result['avg_loss_pct'] > 0:
                    rr = result['avg_win_pct'] / result['avg_loss_pct']
                    print(f"      Risk/Reward: {rr:.2f}:1")
            
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
    print("📊 SUMMARY - High Win Rate Focus")
    print("="*70)
    
    if results:
        # Filter for 75%+ win rate
        high_wr_results = [r for r in results if r['results']['win_rate'] >= 75]
        
        if high_wr_results:
            # Sort by win rate
            high_wr_results.sort(key=lambda x: x['results']['win_rate'], reverse=True)
            
            print(f"\n✅ Found {len(high_wr_results)} strategies with 75%+ Win Rate:")
            print("="*70)
            
            for i, best in enumerate(high_wr_results[:5], 1):
                r = best['results']
                p = best['params']
                print(f"\n{i}. Win Rate: {r['win_rate']:.1f}% ⭐")
                print(f"   Trades: {r['total_trades']}")
                print(f"   Profit Factor: {r['profit_factor']:.2f}")
                print(f"   Return: {r['total_return_pct']:.1f}%")
                print(f"   Max DD: {r['max_drawdown_pct']:.1f}%")
                print(f"   Parameters:")
                print(f"     reg_len={p['reg_len']}, outer_mult={p['outer_mult']}")
                print(f"     stoch_len={p['stoch_len']}, ob_level={p['ob_level']}, os_level={p['os_level']}")
                print(f"     tp={p['tp_pct']*100:.1f}%, sl={p['sl_pct']*100:.1f}%")
                print(f"     trend_filter={p['use_trend_filter']}, sma_len={p['sma_len']}")
        else:
            print("\n⚠️  No strategies found with 75%+ Win Rate")
            print("Trying to find best available...")
            
            # Sort by win rate
            results.sort(key=lambda x: x['results']['win_rate'], reverse=True)
            
            print("\nBest available:")
            best = results[0]
            r = best['results']
            p = best['params']
            print(f"  Win Rate: {r['win_rate']:.1f}%")
            print(f"  Trades: {r['total_trades']}")
            print(f"  Profit Factor: {r['profit_factor']:.2f}")
            print(f"  Return: {r['total_return_pct']:.1f}%")
    else:
        print("❌ No successful tests")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    test_high_winrate()

