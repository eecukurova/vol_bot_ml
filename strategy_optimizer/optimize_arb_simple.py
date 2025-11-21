#!/usr/bin/env python3
"""
ARB için basit ve etkili VWMA stratejisi optimize et
Gerçek veri ile backtest
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

from src.strategy.vwma_arb_simple import VWMAARBSimpleStrategy


def download_binance_futures_klines(symbol: str, interval: str, days: int = 180):
    """Download Binance Futures klines"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    base_url = "https://fapi.binance.com/fapi/v1/klines"
    all_klines = []
    current = start_date
    
    while current < end_date and len(all_klines) < 2000:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": int(current.timestamp() * 1000),
            "limit": min(1000, 2000 - len(all_klines)),
        }
        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()
            if not klines:
                break
            all_klines.extend(klines)
            last_time = klines[-1][0] / 1000
            current = datetime.fromtimestamp(last_time) + timedelta(minutes=1)
            time.sleep(0.5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)
    
    if not all_klines:
        return None
    
    df = pd.DataFrame(all_klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df[["open", "high", "low", "close", "volume"]].copy()
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df = df.sort_index().drop_duplicates()
    return df


def optimize_arb_strategy():
    """Optimize ARB strategy with real data"""
    print(f"\n{'='*70}")
    print(f"🚀 ARB Simple VWMA Strategy Optimizer")
    print(f"{'='*70}")
    
    # Download data
    print(f"\n📥 Downloading ARBUSDT 4h data...")
    df = download_binance_futures_klines("ARBUSDT", "4h", days=180)
    if df is None or len(df) < 100:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Parameter ranges - ARB için optimize edilmiş
    vwma_lengths = [25, 30, 35]
    rsi_oversold = [25, 30, 35]
    rsi_overbought = [65, 70, 75]
    tp_pcts = [0.6, 0.8, 1.0, 1.2]
    sl_pcts = [0.5, 0.6, 0.8, 1.0]
    trailing_activation = [0.3, 0.5, 0.7]
    trailing_distance = [0.3, 0.5, 0.7]
    
    total_combinations = (len(vwma_lengths) * len(rsi_oversold) * len(rsi_overbought) * 
                         len(tp_pcts) * len(sl_pcts) * len(trailing_activation) * len(trailing_distance))
    print(f"\n📊 Testing {total_combinations} parameter combinations...")
    
    all_results = []
    best_result = None
    best_score = -float('inf')
    
    combination_count = 0
    for (vwma_len, rsi_os, rsi_ob, tp_pct, sl_pct, trail_act, trail_dist) in product(
        vwma_lengths, rsi_oversold, rsi_overbought, tp_pcts, sl_pcts, trailing_activation, trailing_distance
    ):
        combination_count += 1
        
        if combination_count % 50 == 0:
            print(f"   Progress: {combination_count}/{total_combinations} ({combination_count/total_combinations*100:.1f}%)")
        
        params = {
            'vwma_length': vwma_len,
            'rsi_oversold': rsi_os,
            'rsi_overbought': rsi_ob,
            'tp_pct': tp_pct,
            'sl_pct': sl_pct,
            'trailing_activation_pct': trail_act,
            'trailing_distance_pct': trail_dist,
            'leverage': 5.0,
            'commission': 0.0004,
            'slippage': 0.0002,
        }
        
        try:
            strategy = VWMAARBSimpleStrategy(params)
            results = strategy.run_backtest(df)
            
            # Filter: reasonable trade count
            if results['total_trades'] < 20 or results['total_trades'] > 300:
                continue
            
            # Filter: must be profitable
            if results['profit_factor'] < 1.3:
                continue
            
            # Filter: reasonable win rate
            if results['win_rate'] < 45:
                continue
            
            # Score: prioritize profit factor, win rate, and reasonable return
            # Cap return at 10000% to avoid outliers
            capped_return = min(results['total_return_pct'], 10000)
            score = (
                results['profit_factor'] * 15 +
                results['win_rate'] * 0.8 +
                capped_return * 0.05 -
                results['max_drawdown_pct'] * 0.5
            )
            
            result = {
                'vwma_length': vwma_len,
                'rsi_oversold': rsi_os,
                'rsi_overbought': rsi_ob,
                'tp_pct': tp_pct,
                'sl_pct': sl_pct,
                'trailing_activation_pct': trail_act,
                'trailing_distance_pct': trail_dist,
                'score': score,
                **results
            }
            all_results.append(result)
            
            if score > best_score:
                best_score = score
                best_result = result
        except Exception as e:
            continue
    
    # Sort by score
    all_results.sort(key=lambda x: x['score'], reverse=True)
    top_results = all_results[:20]
    
    # Print results
    print(f"\n{'='*70}")
    print(f"🏆 TOP 20 RESULTS")
    print(f"{'='*70}")
    
    for i, result in enumerate(top_results, 1):
        print(f"\n{i}. VWMA={result['vwma_length']} | RSI={result['rsi_oversold']}/{result['rsi_overbought']} | TP={result['tp_pct']}% | SL={result['sl_pct']}%")
        print(f"   Trail: {result['trailing_activation_pct']}%/{result['trailing_distance_pct']}%")
        print(f"   Trades: {result['total_trades']} | Win Rate: {result['win_rate']:.2f}% | PF: {result['profit_factor']:.2f}")
        print(f"   Return: {result['total_return_pct']:.2f}% | DD: {result['max_drawdown_pct']:.2f}% | Score: {result['score']:.2f}")
    
    if best_result:
        print(f"\n{'='*70}")
        print(f"🏆 BEST RESULT FOR ARB")
        print(f"{'='*70}")
        print(f"VWMA Length: {best_result['vwma_length']}")
        print(f"RSI Levels: {best_result['rsi_oversold']}/{best_result['rsi_overbought']}")
        print(f"TP/SL: {best_result['tp_pct']}%/{best_result['sl_pct']}%")
        print(f"Trailing: {best_result['trailing_activation_pct']}%/{best_result['trailing_distance_pct']}%")
        print(f"\nPerformance:")
        print(f"  Total Trades: {best_result['total_trades']}")
        print(f"  Win Rate: {best_result['win_rate']:.2f}%")
        print(f"  Profit Factor: {best_result['profit_factor']:.2f}")
        print(f"  Total Return: {best_result['total_return_pct']:.2f}% (5x leverage)")
        print(f"  Max Drawdown: {best_result['max_drawdown_pct']:.2f}%")
        print(f"  Avg Win: {best_result['avg_win_pct']:.2f}%")
        print(f"  Avg Loss: {best_result['avg_loss_pct']:.2f}%")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"arb_simple_optimization_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump({
            'best_result': best_result,
            'top_20': top_results,
            'all_results': all_results[:100],  # Top 100
            'timestamp': timestamp
        }, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to {filename}")
    
    return best_result


if __name__ == "__main__":
    optimize_arb_strategy()

