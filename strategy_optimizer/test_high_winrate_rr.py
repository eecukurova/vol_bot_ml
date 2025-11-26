#!/usr/bin/env python3
"""
Test High Win Rate with High Risk/Reward Ratio
Strategy: Small SL, Large TP to achieve 75%+ win rate
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from src.strategy.regression_channel import RegressionChannelStrategy
from optimize_regression_channel_crypto import download_binance_futures_klines

def test_high_rr():
    print("\n" + "="*70)
    print("🚀 High Win Rate Test - High Risk/Reward Strategy")
    print("Strategy: Small SL (0.5-1%), Large TP (2-4%)")
    print("Target: 75%+ Win Rate")
    print("="*70)
    
    df = download_binance_futures_klines("BTCUSDT", "15m", days=180)
    if df is None or len(df) < 200:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars")
    
    # Test with high R:R ratios (small SL, large TP)
    # This should naturally increase win rate
    test_params = [
        # Very tight SL, moderate TP
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
            'tp_pct': 0.02,  # 2% TP
            'sl_pct': 0.005,  # 0.5% SL - 4:1 R:R
        },
        {
            'reg_len': 100,
            'inner_mult': 1.0,
            'outer_mult': 1.8,
            'sma_len': 14,
            'use_trend_filter': False,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 75.0,
            'os_level': 25.0,
            'tp_pct': 0.03,  # 3% TP
            'sl_pct': 0.01,   # 1% SL - 3:1 R:R
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
            'tp_pct': 0.025,  # 2.5% TP
            'sl_pct': 0.008,  # 0.8% SL - ~3:1 R:R
        },
        {
            'reg_len': 100,
            'inner_mult': 1.0,
            'outer_mult': 1.5,
            'sma_len': 20,
            'use_trend_filter': True,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 75.0,
            'os_level': 25.0,
            'tp_pct': 0.04,  # 4% TP
            'sl_pct': 0.01,   # 1% SL - 4:1 R:R
        },
    ]
    
    print(f"\n📊 Testing {len(test_params)} high R:R combinations...")
    print("="*70)
    
    results = []
    for i, params in enumerate(test_params, 1):
        rr = params['tp_pct'] / params['sl_pct']
        print(f"\n{i}. Testing R:R = {rr:.1f}:1 (TP={params['tp_pct']*100:.1f}%, SL={params['sl_pct']*100:.1f}%)")
        print(f"   reg_len={params['reg_len']}, outer_mult={params['outer_mult']}")
        
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
                    actual_rr = result['avg_win_pct'] / result['avg_loss_pct']
                    print(f"      Actual R:R: {actual_rr:.2f}:1")
            
            if result['win_rate'] >= 75:
                print(f"      ✅ FOUND 75%+ WIN RATE!")
                results.append({'params': params, 'results': result, 'rr': rr})
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    if results:
        print("\n" + "="*70)
        print("✅ SUCCESS - Found strategies with 75%+ Win Rate!")
        print("="*70)
        results.sort(key=lambda x: x['results']['win_rate'], reverse=True)
        for i, r in enumerate(results, 1):
            res = r['results']
            p = r['params']
            print(f"\n{i}. Win Rate: {res['win_rate']:.1f}% ⭐")
            print(f"   Trades: {res['total_trades']}")
            print(f"   PF: {res['profit_factor']:.2f}")
            print(f"   Return: {res['total_return_pct']:.1f}%")
            print(f"   R:R: {r['rr']:.1f}:1 (TP={p['tp_pct']*100:.1f}%, SL={p['sl_pct']*100:.1f}%)")
            print(f"   Params: reg={p['reg_len']}, outer={p['outer_mult']}, stoch={p['stoch_len']}")
    else:
        print("\n⚠️  No 75%+ win rate found")
        print("Trying with even tighter SL...")

if __name__ == "__main__":
    test_high_rr()

