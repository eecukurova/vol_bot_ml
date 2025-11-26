#!/usr/bin/env python3
"""
Optimize Regression Channel Strategy specifically for ARBUSDT
ARB için özel optimizasyon - 75%+ win rate hedefi
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import time
from itertools import product
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.strategy.regression_channel import RegressionChannelStrategy
from optimize_regression_channel_crypto import download_binance_futures_klines

def optimize_arb():
    print("\n" + "="*70)
    print("🚀 ARBUSDT Regression Channel Optimizer")
    print("Target: 75%+ Win Rate")
    print("="*70)
    
    # Test multiple timeframes
    timeframes = ["15m", "1h", "4h"]
    
    for timeframe in timeframes:
        print(f"\n{'='*70}")
        print(f"📊 Testing {timeframe} timeframe")
        print(f"{'='*70}")
        
        df = download_binance_futures_klines("ARBUSDT", timeframe, days=180)
        if df is None or len(df) < 200:
            print(f"❌ Failed to download ARBUSDT {timeframe} data")
            continue
        
        print(f"✅ Downloaded {len(df)} bars")
        
        # Focused parameter ranges for high win rate
        reg_lens = [75, 100, 125]
        outer_mults = [1.5, 1.8, 2.0, 2.5]
        stoch_lens = [10, 14, 20]
        ob_levels = [75, 80, 85]
        os_levels = [15, 20, 25]
        tp_pcts = [0.015, 0.02, 0.025]
        sl_pcts = [0.008, 0.01, 0.012]
        use_trend_filters = [False, True]
        sma_lens = [14, 20, 26]
        
        total = len(reg_lens) * len(outer_mults) * len(stoch_lens) * len(ob_levels) * len(os_levels) * len(tp_pcts) * len(sl_pcts) * len(use_trend_filters) * len(sma_lens)
        print(f"📊 Testing {total:,} combinations...")
        
        best_result = None
        best_score = -float('inf')
        high_wr_results = []
        
        count = 0
        start_time = time.time()
        
        for (reg_len, outer_mult, stoch_len, ob_level, os_level, tp_pct, sl_pct, use_trend, sma_len) in product(
            reg_lens, outer_mults, stoch_lens, ob_levels, os_levels, tp_pcts, sl_pcts, use_trend_filters, sma_lens
        ):
            count += 1
            if count % 100 == 0:
                elapsed = time.time() - start_time
                remaining = (total - count) * (elapsed / count)
                print(f"Progress: {count}/{total} ({count/total*100:.1f}%) | "
                      f"Elapsed: {elapsed/60:.1f}m | Remaining: {remaining/60:.1f}m | "
                      f"Found {len(high_wr_results)} with 75%+ WR")
            
            params = {
                'reg_len': reg_len,
                'inner_mult': 1.0,
                'outer_mult': outer_mult,
                'sma_len': sma_len,
                'use_trend_filter': use_trend,
                'stoch_len': stoch_len,
                'smooth_k': 3,
                'smooth_d': 3,
                'ob_level': float(ob_level),
                'os_level': float(os_level),
                'tp_pct': tp_pct,
                'sl_pct': sl_pct,
            }
            
            try:
                strategy = RegressionChannelStrategy(params)
                result = strategy.run_backtest(df, commission=0.0005, slippage=0.0002)
                
                if result['total_trades'] < 10 or result['total_trades'] > 500:
                    continue
                
                if result['win_rate'] >= 75:
                    score = result['win_rate'] * 10 + result['profit_factor'] * 5 + result['total_return_pct'] * 0.1
                    high_wr_results.append({
                        'timeframe': timeframe,
                        'params': params,
                        'results': result,
                        'score': score
                    })
                    
                    if score > best_score:
                        best_score = score
                        best_result = {
                            'timeframe': timeframe,
                            'params': params,
                            'results': result
                        }
                        print(f"\n⭐ New Best: WR={result['win_rate']:.1f}%, "
                              f"Trades={result['total_trades']}, PF={result['profit_factor']:.2f}, "
                              f"Return={result['total_return_pct']:.1f}%")
            except:
                continue
        
        if high_wr_results:
            print(f"\n✅ Found {len(high_wr_results)} strategies with 75%+ Win Rate on {timeframe}!")
            high_wr_results.sort(key=lambda x: x['score'], reverse=True)
            
            print(f"\nTop 5 Results for {timeframe}:")
            for i, r in enumerate(high_wr_results[:5], 1):
                res = r['results']
                p = r['params']
                print(f"\n{i}. Win Rate: {res['win_rate']:.1f}% ⭐")
                print(f"   Trades: {res['total_trades']}, PF: {res['profit_factor']:.2f}, "
                      f"Return: {res['total_return_pct']:.1f}%")
                print(f"   Params: reg={p['reg_len']}, outer={p['outer_mult']}, "
                      f"stoch={p['stoch_len']}, ob={p['ob_level']}, os={p['os_level']}")
                print(f"   TP={p['tp_pct']*100:.1f}%, SL={p['sl_pct']*100:.1f}%, "
                      f"trend_filter={p['use_trend_filter']}")
        else:
            print(f"\n⚠️  No 75%+ win rate found on {timeframe}")
    
    # Final summary
    print("\n" + "="*70)
    print("📊 FINAL SUMMARY")
    print("="*70)
    
    if best_result:
        res = best_result['results']
        p = best_result['params']
        print(f"\n✅ Best Overall Result:")
        print(f"   Timeframe: {best_result['timeframe']}")
        print(f"   Win Rate: {res['win_rate']:.1f}% ⭐")
        print(f"   Trades: {res['total_trades']}")
        print(f"   Profit Factor: {res['profit_factor']:.2f}")
        print(f"   Return: {res['total_return_pct']:.1f}%")
        print(f"   Max DD: {res['max_drawdown_pct']:.1f}%")
        print(f"\n   Optimized Parameters:")
        print(f"     reg_len={p['reg_len']}")
        print(f"     outer_mult={p['outer_mult']}")
        print(f"     stoch_len={p['stoch_len']}")
        print(f"     ob_level={p['ob_level']}")
        print(f"     os_level={p['os_level']}")
        print(f"     tp_pct={p['tp_pct']*100:.1f}%")
        print(f"     sl_pct={p['sl_pct']*100:.1f}%")
        print(f"     use_trend_filter={p['use_trend_filter']}")
        print(f"     sma_len={p['sma_len']}")
    else:
        print("\n⚠️  No 75%+ win rate found on any timeframe")
        print("This strategy type may not be suitable for 75%+ win rate target")

if __name__ == "__main__":
    optimize_arb()

