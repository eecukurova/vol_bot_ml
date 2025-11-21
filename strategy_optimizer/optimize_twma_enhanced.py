#!/usr/bin/env python3
"""
TWMA 4H Trend Strategy Enhanced Optimizer
Filtrelerle Geliştirilmiş TWMA Stratejisi Optimizasyonu
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
from itertools import product
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.strategy.twma_trend_enhanced import TWMATrendEnhancedStrategy
from optimize_twma_4h import download_binance_futures_klines


def optimize_twma_enhanced(symbol: str = "BTCUSDT", timeframe: str = "4h"):
    """
    Optimize Enhanced TWMA 4H Trend Strategy with Filters
    
    Args:
        symbol: Trading symbol (default: BTCUSDT)
        timeframe: Timeframe (default: 4h)
    """
    print(f"\n{'='*70}")
    print(f"🚀 TWMA 4H Enhanced Strategy Optimizer (with Filters)")
    print(f"{'='*70}")
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    
    # Download data
    print(f"\n📥 Downloading {symbol} {timeframe} data...")
    df = download_binance_futures_klines(symbol, timeframe, days=180)
    if df is None or len(df) < 100:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Base parameters (optimized values)
    base_twma_len = 15
    base_atr_len = 14
    base_sl_atr_mult = 1.0
    base_tp_atr_mult = 1.5
    base_pivot_len = 3
    
    # Filter parameters to test
    use_rsi = [True, False]
    rsi_oversold = [25, 30, 35]
    rsi_overbought = [65, 70, 75]
    
    use_macd = [True, False]
    
    use_volume = [True, False]
    volume_multipliers = [1.0, 1.2, 1.5]
    
    use_ema = [True, False]
    
    use_adx = [True, False]
    adx_thresholds = [15, 20, 25]
    
    total_combinations = (len(use_rsi) * len(rsi_oversold) * len(rsi_overbought) *
                         len(use_macd) * len(use_volume) * len(volume_multipliers) *
                         len(use_ema) * len(use_adx) * len(adx_thresholds))
    
    print(f"\n📊 Testing {total_combinations:,} filter combinations...")
    print(f"⚠️  This will take approximately {total_combinations * 0.2 / 60:.1f} minutes...")
    
    all_results = []
    best_result = None
    best_score = -float('inf')
    
    combination_count = 0
    start_time = time.time()
    
    for (rsi_enabled, rsi_os, rsi_ob, macd_enabled, vol_enabled, vol_mult,
         ema_enabled, adx_enabled, adx_thresh) in product(
        use_rsi, rsi_oversold, rsi_overbought,
        use_macd,
        use_volume, volume_multipliers,
        use_ema,
        use_adx, adx_thresholds
    ):
        combination_count += 1
        
        if combination_count % 20 == 0:
            elapsed = time.time() - start_time
            if combination_count > 0:
                remaining = (total_combinations - combination_count) * (elapsed / combination_count)
                print(f"Progress: {combination_count}/{total_combinations} ({combination_count/total_combinations*100:.1f}%) | "
                      f"Elapsed: {elapsed/60:.1f}m | Remaining: {remaining/60:.1f}m | "
                      f"Best Score: {best_score:.2f} | Best WR: {best_result['results']['win_rate']:.1f}% if best_result else 0")
        
        params = {
            # Base TWMA parameters (optimized)
            'twma_len': base_twma_len,
            'atr_len': base_atr_len,
            'sl_atr_mult': base_sl_atr_mult,
            'tp_atr_mult': base_tp_atr_mult,
            'pivot_len': base_pivot_len,
            
            # Filters
            'use_rsi_filter': rsi_enabled,
            'rsi_length': 14,
            'rsi_oversold': rsi_os,
            'rsi_overbought': rsi_ob,
            
            'use_macd_filter': macd_enabled,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            
            'use_volume_filter': vol_enabled,
            'volume_ma_length': 20,
            'volume_multiplier': vol_mult,
            
            'use_ema_filter': ema_enabled,
            'ema_fast': 12,
            'ema_slow': 26,
            
            'use_adx_filter': adx_enabled,
            'adx_length': 14,
            'adx_threshold': adx_thresh,
            
            'leverage': 5.0,
            'commission': 0.0005,
            'slippage': 0.0002,
        }
        
        try:
            strategy = TWMATrendEnhancedStrategy(params)
            results = strategy.run_backtest(df)
            
            # Filter results - want better win rate
            if results['total_trades'] < 10 or results['total_trades'] > 500:
                continue
            
            # Calculate score - prioritize win rate improvement
            capped_return = min(results['total_return_pct'], 10000)
            score = (
                results['win_rate'] * 3.0 +  # Win rate'e daha fazla ağırlık
                results['profit_factor'] * 25 +
                capped_return * 0.15 -
                results['max_drawdown_pct'] * 1.0 +
                (results['total_trades'] / 10) * 0.1
            )
            
            result_entry = {
                'params': params,
                'results': results,
                'score': score
            }
            all_results.append(result_entry)
            
            if score > best_score:
                best_score = score
                best_result = result_entry
                print(f"\n⭐ New Best Score: {score:.2f}")
                print(f"   Trades: {results['total_trades']} | WR: {results['win_rate']:.1f}% | PF: {results['profit_factor']:.2f}")
                print(f"   Return: {results['total_return_pct']:.1f}% | DD: {results['max_drawdown_pct']:.1f}%")
                print(f"   Filters: RSI={rsi_enabled}, MACD={macd_enabled}, Vol={vol_enabled}, EMA={ema_enabled}, ADX={adx_enabled}")
                if results.get('total_signals', 0) > 0:
                    filter_rate = results.get('filter_rate', 0)
                    print(f"   Filtered: {results.get('filtered_signals', 0)}/{results.get('total_signals', 0)} ({filter_rate:.1f}%)")
        
        except Exception as e:
            continue
    
    # Sort results by score
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"twma_enhanced_optimization_{symbol}_{timestamp}.json"
    
    json_results = []
    for r in all_results[:100]:  # Top 100
        json_results.append({
            'params': r['params'],
            'results': {k: v for k, v in r['results'].items() if k != 'trades'},
            'score': r['score']
        })
    
    with open(results_file, 'w') as f:
        json.dump(json_results, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"✅ Optimization Complete!")
    print(f"{'='*70}")
    print(f"\n📊 Total Valid Results: {len(all_results)}")
    print(f"💾 Results saved to: {results_file}")
    
    if len(all_results) == 0:
        print(f"\n⚠️  WARNING: No results passed filters!")
        return None
    
    print(f"\n📊 Top 20 Results (Win Rate Focus):")
    print(f"{'='*70}")
    
    for i, result in enumerate(all_results[:20], 1):
        r = result['results']
        p = result['params']
        print(f"\n{i}. Score: {result['score']:.2f}")
        print(f"   📈 Trades: {r['total_trades']} | Win Rate: {r['win_rate']:.2f}% ⭐")
        print(f"   💰 Profit Factor: {r['profit_factor']:.2f}")
        print(f"   📊 Return: {r['total_return_pct']:.2f}%")
        print(f"   ⚠️  Max Drawdown: {r['max_drawdown_pct']:.2f}%")
        print(f"   🔍 Filters:")
        print(f"      RSI: {p.get('use_rsi_filter', False)} (OS:{p.get('rsi_oversold')}, OB:{p.get('rsi_overbought')})")
        print(f"      MACD: {p.get('use_macd_filter', False)}")
        print(f"      Volume: {p.get('use_volume_filter', False)} (×{p.get('volume_multiplier', 1.0)})")
        print(f"      EMA: {p.get('use_ema_filter', False)}")
        print(f"      ADX: {p.get('use_adx_filter', False)} (≥{p.get('adx_threshold', 20)})")
        if r.get('total_signals', 0) > 0:
            print(f"      Filtered Signals: {r.get('filtered_signals', 0)}/{r.get('total_signals', 0)} ({r.get('filter_rate', 0):.1f}%)")
    
    if best_result:
        print(f"\n{'='*70}")
        print(f"🏆 BEST RESULT (Win Rate Focus):")
        print(f"{'='*70}")
        r = best_result['results']
        p = best_result['params']
        print(f"Score: {best_result['score']:.2f}")
        print(f"\n📊 Performance Metrics:")
        print(f"  Total Trades: {r['total_trades']}")
        print(f"  Win Rate: {r['win_rate']:.2f}% ⭐ (Önceki: 44.29%)")
        print(f"  Profit Factor: {r['profit_factor']:.2f}")
        print(f"  Total Return: {r['total_return_pct']:.2f}%")
        print(f"  Max Drawdown: {r['max_drawdown_pct']:.2f}%")
        if r.get('total_signals', 0) > 0:
            print(f"  Filtered Signals: {r.get('filtered_signals', 0)}/{r.get('total_signals', 0)} ({r.get('filter_rate', 0):.1f}%)")
        
        print(f"\n⚙️  Optimal Filter Configuration:")
        print(f"  RSI Filter: {p.get('use_rsi_filter', False)}")
        if p.get('use_rsi_filter'):
            print(f"    Oversold: {p.get('rsi_oversold')}, Overbought: {p.get('rsi_overbought')}")
        print(f"  MACD Filter: {p.get('use_macd_filter', False)}")
        print(f"  Volume Filter: {p.get('use_volume_filter', False)}")
        if p.get('use_volume_filter'):
            print(f"    Multiplier: {p.get('volume_multiplier')}×")
        print(f"  EMA Filter: {p.get('use_ema_filter', False)}")
        print(f"  ADX Filter: {p.get('use_adx_filter', False)}")
        if p.get('use_adx_filter'):
            print(f"    Threshold: {p.get('adx_threshold')}")
    
    return best_result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='TWMA 4H Enhanced Strategy Optimizer')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='Trading symbol')
    parser.add_argument('--timeframe', type=str, default='4h', help='Timeframe')
    
    args = parser.parse_args()
    
    optimize_twma_enhanced(symbol=args.symbol, timeframe=args.timeframe)

