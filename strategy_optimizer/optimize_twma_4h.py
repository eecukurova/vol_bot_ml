#!/usr/bin/env python3
"""
TWMA 4H Trend Strategy Optimizer
4H Zaman Ağırlıklı Trend Stratejisi Optimizasyonu
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

from src.strategy.twma_trend import TWMATrendStrategy


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


def optimize_twma_4h(symbol: str = "BTCUSDT", timeframe: str = "4h"):
    """
    Optimize TWMA 4H Trend Strategy
    
    Args:
        symbol: Trading symbol (default: BTCUSDT)
        timeframe: Timeframe (default: 4h)
    """
    print(f"\n{'='*70}")
    print(f"🚀 TWMA 4H Trend Strategy Optimizer")
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
    
    # Parameter ranges to test
    twma_lens = [10, 15, 20, 25, 30]  # TWMA periods
    atr_lens = [10, 14, 20]  # ATR periods
    sl_atr_mults = [0.3, 0.5, 0.7, 1.0]  # Stop Loss ATR multipliers
    tp_atr_mults = [0.8, 1.0, 1.5, 2.0]  # Take Profit ATR multipliers
    pivot_lens = [3, 5, 7, 10]  # Pivot lengths
    
    total_combinations = (len(twma_lens) * len(atr_lens) * len(sl_atr_mults) * 
                         len(tp_atr_mults) * len(pivot_lens))
    
    print(f"\n📊 Testing {total_combinations:,} parameter combinations...")
    print(f"⚠️  This will take approximately {total_combinations * 0.15 / 60:.1f} minutes...")
    
    all_results = []
    best_result = None
    best_score = -float('inf')
    
    combination_count = 0
    start_time = time.time()
    
    for (twma_len, atr_len, sl_mult, tp_mult, pivot_len) in product(
        twma_lens, atr_lens, sl_atr_mults, tp_atr_mults, pivot_lens
    ):
        combination_count += 1
        
        if combination_count % 50 == 0:
            elapsed = time.time() - start_time
            if combination_count > 0:
                remaining = (total_combinations - combination_count) * (elapsed / combination_count)
                print(f"Progress: {combination_count}/{total_combinations} ({combination_count/total_combinations*100:.1f}%) | "
                      f"Elapsed: {elapsed/60:.1f}m | Remaining: {remaining/60:.1f}m | "
                      f"Best Score: {best_score:.2f}")
        
        params = {
            'twma_len': twma_len,
            'atr_len': atr_len,
            'sl_atr_mult': sl_mult,
            'tp_atr_mult': tp_mult,
            'pivot_len': pivot_len,
            'leverage': 5.0,
            'commission': 0.0005,
            'slippage': 0.0002,
        }
        
        try:
            strategy = TWMATrendStrategy(params)
            results = strategy.run_backtest(df)
            
            # Filter results
            if results['total_trades'] < 5 or results['total_trades'] > 500:
                continue
            
            # Calculate score
            capped_return = min(results['total_return_pct'], 10000)
            score = (
                results['profit_factor'] * 30 +
                results['win_rate'] * 2.0 +
                capped_return * 0.2 -
                results['max_drawdown_pct'] * 1.5 +
                (results['total_trades'] / 10) * 0.15
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
                print(f"   TWMA: {twma_len} | ATR: {atr_len} | SL: {sl_mult}× | TP: {tp_mult}× | Pivot: {pivot_len}")
        
        except Exception as e:
            continue
    
    # Sort results by score
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"twma_4h_optimization_{symbol}_{timestamp}.json"
    
    # Convert to JSON-serializable format
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
    
    print(f"\n📊 Top 20 Results:")
    print(f"{'='*70}")
    
    for i, result in enumerate(all_results[:20], 1):
        r = result['results']
        p = result['params']
        print(f"\n{i}. Score: {result['score']:.2f}")
        print(f"   📈 Trades: {r['total_trades']} | Win Rate: {r['win_rate']:.2f}%")
        print(f"   💰 Profit Factor: {r['profit_factor']:.2f}")
        print(f"   📊 Return: {r['total_return_pct']:.2f}% (5x leverage)")
        print(f"   ⚠️  Max Drawdown: {r['max_drawdown_pct']:.2f}%")
        print(f"   📉 Avg Win: {r['avg_win_pct']:.2f}% | Avg Loss: {r['avg_loss_pct']:.2f}%")
        print(f"   ⚙️  Parameters:")
        print(f"      TWMA: {p['twma_len']} | ATR: {p['atr_len']}")
        print(f"      SL: {p['sl_atr_mult']}× ATR | TP: {p['tp_atr_mult']}× ATR")
        print(f"      Pivot: {p['pivot_len']}")
    
    if best_result:
        print(f"\n{'='*70}")
        print(f"🏆 BEST RESULT:")
        print(f"{'='*70}")
        r = best_result['results']
        p = best_result['params']
        print(f"Score: {best_result['score']:.2f}")
        print(f"\n📊 Performance Metrics:")
        print(f"  Total Trades: {r['total_trades']}")
        print(f"  Win Rate: {r['win_rate']:.2f}%")
        print(f"  Profit Factor: {r['profit_factor']:.2f}")
        print(f"  Total Return: {r['total_return_pct']:.2f}% (5x leverage)")
        print(f"  Max Drawdown: {r['max_drawdown_pct']:.2f}%")
        print(f"  Avg Win: {r['avg_win_pct']:.2f}%")
        print(f"  Avg Loss: {r['avg_loss_pct']:.2f}%")
        print(f"  Gross Profit: {r['gross_profit']:.2f}%")
        print(f"  Gross Loss: {r['gross_loss']:.2f}%")
        print(f"  Final Equity: ${r['final_equity']:.2f}")
        
        print(f"\n⚙️  Optimal Parameters for {symbol} {timeframe}:")
        print(f"  TWMA Length: {p['twma_len']}")
        print(f"  ATR Length: {p['atr_len']}")
        print(f"  Stop Loss: {p['sl_atr_mult']}× ATR")
        print(f"  Take Profit: {p['tp_atr_mult']}× ATR")
        print(f"  Pivot Length: {p['pivot_len']}")
        print(f"  Leverage: {p['leverage']}×")
        print(f"  Commission: {p['commission']*100:.2f}%")
        print(f"  Slippage: {p['slippage']*100:.2f}%")
    
    return best_result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='TWMA 4H Trend Strategy Optimizer')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='Trading symbol (default: BTCUSDT)')
    parser.add_argument('--timeframe', type=str, default='4h', help='Timeframe (default: 4h)')
    
    args = parser.parse_args()
    
    optimize_twma_4h(symbol=args.symbol, timeframe=args.timeframe)

