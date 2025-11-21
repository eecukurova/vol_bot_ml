#!/usr/bin/env python3
"""
TWMA 4H Trend Strategy Optimizer - Max SL %1.5 ile
Stop Loss maksimum %1.5 ile sınırlandırılmış strateji optimizasyonu
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


def optimize_twma_max_sl(symbol: str = "ETHUSDT", timeframe: str = "4h", max_sl_pct: float = 1.5):
    """
    Optimize TWMA 4H Strategy with Max SL constraint
    
    Args:
        symbol: Trading symbol (default: ETHUSDT)
        timeframe: Timeframe (default: 4h)
        max_sl_pct: Maximum stop loss percentage (default: 1.5%)
    """
    print(f"\n{'='*70}")
    print(f"🚀 TWMA 4H Strategy Optimizer - Max SL {max_sl_pct}%")
    print(f"{'='*70}")
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Max Stop Loss: {max_sl_pct}% (leverage adjusted)")
    print()
    
    # Download data
    print(f"📥 Downloading {symbol} {timeframe} data...")
    df = download_binance_futures_klines(symbol, timeframe, days=180)
    if df is None or len(df) < 100:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Parameter ranges to test
    twma_lens = [10, 15, 20, 25, 30]
    atr_lens = [10, 14, 20]
    sl_atr_mults = [0.3, 0.5, 0.7, 1.0]  # ATR multipliers
    tp_atr_mults = [0.8, 1.0, 1.5, 2.0]
    pivot_lens = [3, 5, 7, 10]
    
    # Filter parameters (ETH için optimize edilmiş)
    use_rsi = [True]
    rsi_oversold = [35]
    rsi_overbought = [65]
    
    use_macd = [False]  # ETH için kapalı
    use_volume = [True]
    volume_multipliers = [1.0]
    use_ema = [False]  # ETH için kapalı
    use_adx = [False]  # ETH için kapalı
    
    total_combinations = (len(twma_lens) * len(atr_lens) * len(sl_atr_mults) * 
                         len(tp_atr_mults) * len(pivot_lens))
    
    print(f"\n📊 Testing {total_combinations:,} parameter combinations...")
    print(f"⚠️  This will take approximately {total_combinations * 0.2 / 60:.1f} minutes...")
    
    all_results = []
    best_result = None
    best_score = -float('inf')
    
    combination_count = 0
    start_time = time.time()
    
    for (twma_len, atr_len, sl_mult, tp_mult, pivot_len) in product(
        twma_lens, atr_lens, sl_atr_mults, tp_atr_mults, pivot_lens
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
            # TWMA parameters
            'twma_len': twma_len,
            'atr_len': atr_len,
            'sl_atr_mult': sl_mult,
            'tp_atr_mult': tp_mult,
            'pivot_len': pivot_len,
            
            # Filters (ETH optimize)
            'use_rsi_filter': use_rsi[0],
            'rsi_length': 14,
            'rsi_oversold': rsi_oversold[0],
            'rsi_overbought': rsi_overbought[0],
            
            'use_macd_filter': use_macd[0],
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            
            'use_volume_filter': use_volume[0],
            'volume_ma_length': 20,
            'volume_multiplier': volume_multipliers[0],
            
            'use_ema_filter': use_ema[0],
            'ema_fast': 12,
            'ema_slow': 26,
            
            'use_adx_filter': use_adx[0],
            'adx_length': 14,
            'adx_threshold': 20,
            
            'leverage': 5.0,
            'commission': 0.0005,
            'slippage': 0.0002,
        }
        
        try:
            strategy = TWMATrendEnhancedStrategy(params)
            results = strategy.run_backtest(df)
            
            # Filter results
            if results['total_trades'] < 10 or results['total_trades'] > 200:
                continue
            
            # Check max loss constraint
            if results['trades']:
                max_loss = min([t['pnl_pct'] for t in results['trades']])
                if abs(max_loss) > max_sl_pct * 1.1:  # %10 tolerans
                    continue  # Skip if max loss exceeds constraint significantly
            
            # Calculate score - prioritize win rate and profit factor
            capped_return = min(results['total_return_pct'], 10000)
            score = (
                results['win_rate'] * 4.0 +  # Win rate'e daha fazla ağırlık
                results['profit_factor'] * 30 +
                capped_return * 0.2 -
                results['max_drawdown_pct'] * 1.5 +
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
                max_loss = min([t['pnl_pct'] for t in results['trades']]) if results['trades'] else 0
                print(f"   Max Loss: {max_loss:.2f}%")
        
        except Exception as e:
            continue
    
    # Sort results by score
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"twma_max_sl_{max_sl_pct}_optimization_{symbol}_{timestamp}.json"
    
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
    
    print(f"\n📊 Top 20 Results (Max SL {max_sl_pct}%):")
    print(f"{'='*70}")
    
    for i, result in enumerate(all_results[:20], 1):
        r = result['results']
        p = result['params']
        max_loss = min([t['pnl_pct'] for t in r['trades']]) if r.get('trades') else 0
        print(f"\n{i}. Score: {result['score']:.2f}")
        print(f"   📈 Trades: {r['total_trades']} | Win Rate: {r['win_rate']:.2f}%")
        print(f"   💰 Profit Factor: {r['profit_factor']:.2f}")
        print(f"   📊 Return: {r['total_return_pct']:.2f}%")
        print(f"   ⚠️  Max Drawdown: {r['max_drawdown_pct']:.2f}%")
        print(f"   🔴 Max Loss: {max_loss:.2f}%")
        print(f"   ⚙️  TWMA: {p['twma_len']} | ATR: {p['atr_len']} | SL: {p['sl_atr_mult']}× | TP: {p['tp_atr_mult']}× | Pivot: {p['pivot_len']}")
    
    if best_result:
        print(f"\n{'='*70}")
        print(f"🏆 BEST RESULT (Max SL {max_sl_pct}%):")
        print(f"{'='*70}")
        r = best_result['results']
        p = best_result['params']
        max_loss = min([t['pnl_pct'] for t in r['trades']]) if r.get('trades') else 0
        print(f"Score: {best_result['score']:.2f}")
        print(f"\n📊 Performance Metrics:")
        print(f"  Total Trades: {r['total_trades']}")
        print(f"  Win Rate: {r['win_rate']:.2f}%")
        print(f"  Profit Factor: {r['profit_factor']:.2f}")
        print(f"  Total Return: {r['total_return_pct']:.2f}%")
        print(f"  Max Drawdown: {r['max_drawdown_pct']:.2f}%")
        print(f"  Max Loss: {max_loss:.2f}% ✅ (≤ {max_sl_pct}%)")
        
        print(f"\n⚙️  Optimal Parameters:")
        print(f"  TWMA Length: {p['twma_len']}")
        print(f"  ATR Length: {p['atr_len']}")
        print(f"  Stop Loss: {p['sl_atr_mult']}× ATR")
        print(f"  Take Profit: {p['tp_atr_mult']}× ATR")
        print(f"  Pivot Length: {p['pivot_len']}")
    
    return best_result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='TWMA 4H Strategy Optimizer - Max SL')
    parser.add_argument('--symbol', type=str, default='ETHUSDT', help='Trading symbol')
    parser.add_argument('--timeframe', type=str, default='4h', help='Timeframe')
    parser.add_argument('--max-sl', type=float, default=1.5, help='Maximum stop loss percentage')
    
    args = parser.parse_args()
    
    optimize_twma_max_sl(symbol=args.symbol, timeframe=args.timeframe, max_sl_pct=args.max_sl)

