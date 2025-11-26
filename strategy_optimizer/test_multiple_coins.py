#!/usr/bin/env python3
"""
Test Regression Channel Strategy on Multiple Coins
ARB, AVAX, SOL, ETH gibi altcoinlerde test ediyoruz
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from src.strategy.regression_channel import RegressionChannelStrategy
from optimize_regression_channel_crypto import download_binance_futures_klines

def test_multiple_coins():
    print("\n" + "="*70)
    print("🚀 Multi-Coin Test - Regression Channel Strategy")
    print("Target: 75%+ Win Rate")
    print("="*70)
    
    coins = ["ARBUSDT", "AVAXUSDT", "SOLUSDT", "ETHUSDT", "BTCUSDT"]
    timeframe = "15m"
    
    # Test parameters - moderate settings
    test_params = [
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
            'tp_pct': 0.02,
            'sl_pct': 0.01,
        },
        {
            'reg_len': 75,
            'inner_mult': 1.0,
            'outer_mult': 1.5,
            'sma_len': 14,
            'use_trend_filter': False,
            'stoch_len': 10,
            'smooth_k': 2,
            'smooth_d': 2,
            'ob_level': 70.0,
            'os_level': 20.0,
            'tp_pct': 0.015,
            'sl_pct': 0.01,
        },
        {
            'reg_len': 100,
            'inner_mult': 1.0,
            'outer_mult': 2.0,
            'sma_len': 20,
            'use_trend_filter': True,
            'stoch_len': 14,
            'smooth_k': 3,
            'smooth_d': 3,
            'ob_level': 80.0,
            'os_level': 20.0,
            'tp_pct': 0.025,
            'sl_pct': 0.012,
        },
    ]
    
    all_results = []
    
    for coin in coins:
        print(f"\n{'='*70}")
        print(f"📊 Testing {coin}")
        print(f"{'='*70}")
        
        df = download_binance_futures_klines(coin, timeframe, days=180)
        if df is None or len(df) < 200:
            print(f"❌ Failed to download {coin} data")
            continue
        
        print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        
        for i, params in enumerate(test_params, 1):
            print(f"\n  Test {i}: reg_len={params['reg_len']}, outer_mult={params['outer_mult']}, "
                  f"tp={params['tp_pct']*100:.1f}%, sl={params['sl_pct']*100:.1f}%")
            
            try:
                strategy = RegressionChannelStrategy(params)
                result = strategy.run_backtest(df, commission=0.0005, slippage=0.0002)
                
                if result['total_trades'] > 0:
                    print(f"    Trades: {result['total_trades']} | "
                          f"WR: {result['win_rate']:.1f}% {'⭐' if result['win_rate'] >= 75 else ''} | "
                          f"PF: {result['profit_factor']:.2f} | "
                          f"Return: {result['total_return_pct']:.1f}%")
                    
                    if result['win_rate'] >= 75:
                        print(f"    ✅ FOUND 75%+ WIN RATE on {coin}!")
                        all_results.append({
                            'coin': coin,
                            'params': params,
                            'results': result
                        })
                else:
                    print(f"    No trades generated")
            except Exception as e:
                print(f"    ❌ Error: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY - Multi-Coin Results")
    print("="*70)
    
    if all_results:
        print(f"\n✅ Found {len(all_results)} strategies with 75%+ Win Rate:")
        print("="*70)
        
        all_results.sort(key=lambda x: x['results']['win_rate'], reverse=True)
        
        for i, r in enumerate(all_results, 1):
            res = r['results']
            p = r['params']
            print(f"\n{i}. {r['coin']} - Win Rate: {res['win_rate']:.1f}% ⭐")
            print(f"   Trades: {res['total_trades']}")
            print(f"   Profit Factor: {res['profit_factor']:.2f}")
            print(f"   Return: {res['total_return_pct']:.1f}%")
            print(f"   Max DD: {res['max_drawdown_pct']:.1f}%")
            print(f"   Parameters:")
            print(f"     reg_len={p['reg_len']}, outer_mult={p['outer_mult']}")
            print(f"     stoch_len={p['stoch_len']}, ob_level={p['ob_level']}, os_level={p['os_level']}")
            print(f"     tp={p['tp_pct']*100:.1f}%, sl={p['sl_pct']*100:.1f}%")
            print(f"     trend_filter={p['use_trend_filter']}, sma_len={p['sma_len']}")
    else:
        print("\n⚠️  No strategies found with 75%+ Win Rate on any coin")
        print("Testing with different parameters...")
        
        # Try with even more selective parameters
        print("\n" + "="*70)
        print("🔄 Testing with more selective parameters...")
        print("="*70)
        
        selective_params = [
            {
                'reg_len': 125,
                'inner_mult': 1.0,
                'outer_mult': 2.0,
                'sma_len': 20,
                'use_trend_filter': True,
                'stoch_len': 14,
                'smooth_k': 3,
                'smooth_d': 3,
                'ob_level': 80.0,
                'os_level': 20.0,
                'tp_pct': 0.02,
                'sl_pct': 0.01,
            },
        ]
        
        for coin in ["ARBUSDT", "AVAXUSDT", "SOLUSDT"]:
            print(f"\n📊 Testing {coin} with selective params...")
            df = download_binance_futures_klines(coin, timeframe, days=180)
            if df is None:
                continue
            
            for params in selective_params:
                try:
                    strategy = RegressionChannelStrategy(params)
                    result = strategy.run_backtest(df, commission=0.0005, slippage=0.0002)
                    
                    if result['total_trades'] > 0:
                        print(f"  {coin}: Trades={result['total_trades']}, "
                              f"WR={result['win_rate']:.1f}%, "
                              f"PF={result['profit_factor']:.2f}, "
                              f"Return={result['total_return_pct']:.1f}%")
                        
                        if result['win_rate'] >= 75:
                            print(f"  ✅ FOUND 75%+ WIN RATE on {coin}!")
                            all_results.append({
                                'coin': coin,
                                'params': params,
                                'results': result
                            })
                except:
                    pass
    
    print("\n" + "="*70)

if __name__ == "__main__":
    test_multiple_coins()

