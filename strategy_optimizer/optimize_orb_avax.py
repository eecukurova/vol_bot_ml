#!/usr/bin/env python3
"""
ORB Breakout Strategy Optimizer for AVAX
Gerçek veri ile optimize et
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

from src.strategy.orb_breakout import ORBBreakoutStrategy


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


def optimize_orb_avax():
    """Optimize ORB strategy for AVAX with real data"""
    print(f"\n{'='*70}")
    print(f"🚀 ORB Breakout Strategy Optimizer for AVAX")
    print(f"{'='*70}")
    
    # Download data
    print(f"\n📥 Downloading AVAXUSDT 4h data...")
    df = download_binance_futures_klines("AVAXUSDT", "4h", days=180)
    if df is None or len(df) < 100:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Parameter ranges - AVAX için optimize edilmiş (hızlı optimizasyon)
    orb_minutes = [15, 30]  # ORB periods (4h için mantıklı olanlar)
    breakout_buffer_pcts = [0.1, 0.2, 0.3]
    min_bars_outside = [1, 2]
    
    # Filters
    enable_volume_filter = [False, True]
    volume_multipliers = [1.5, 2.0]
    
    enable_trend_filter = [False, True]
    trend_modes = ["VWAP", "EMA"]
    
    # Exit parameters
    tp1_pcts = [1.0, 1.5, 2.0]
    tp2_pcts = [2.0, 2.5, 3.0]
    tp3_pcts = [3.0, 4.0, 5.0]
    stop_modes = ["Smart Adaptive", "% Based"]
    atr_multipliers = [1.0, 1.5]
    
    total_combinations = (len(orb_minutes) * len(breakout_buffer_pcts) * len(min_bars_outside) *
                         len(enable_volume_filter) * len(volume_multipliers) *
                         len(enable_trend_filter) * len(trend_modes) *
                         len(tp1_pcts) * len(tp2_pcts) * len(tp3_pcts) *
                         len(stop_modes) * len(atr_multipliers))
    
    print(f"\n📊 Testing {total_combinations} parameter combinations...")
    print(f"⚠️  This may take a while...")
    
    all_results = []
    best_result = None
    best_score = -float('inf')
    
    combination_count = 0
    for (orb_min, buf_pct, min_bars, vol_filter, vol_mult, trend_filter, trend_mode,
         tp1, tp2, tp3, stop_mode, atr_mult) in product(
        orb_minutes, breakout_buffer_pcts, min_bars_outside,
        enable_volume_filter, volume_multipliers,
        enable_trend_filter, trend_modes,
        tp1_pcts, tp2_pcts, tp3_pcts,
        stop_modes, atr_multipliers
    ):
        combination_count += 1
        
        if combination_count % 100 == 0:
            print(f"Progress: {combination_count}/{total_combinations} ({combination_count/total_combinations*100:.1f}%)")
        
        params = {
            'orb_minutes': orb_min,
            'breakout_buffer_pct': buf_pct,
            'min_bars_outside': min_bars,
            'enable_volume_filter': vol_filter,
            'volume_ma_length': 20,
            'volume_multiplier': vol_mult,
            'enable_trend_filter': trend_filter,
            'trend_mode': trend_mode,
            'trend_ema_length': 12,
            'tp1_pct': tp1,
            'tp2_pct': tp2,
            'tp3_pct': tp3,
            'stop_mode': stop_mode,
            'atr_length': 14,
            'atr_multiplier': atr_mult,
            'max_stop_loss_pct': 2.5,  # Maksimum %2.5
            'leverage': 5.0,
            'commission': 0.0004,
            'slippage': 0.0002,
        }
        
        try:
            strategy = ORBBreakoutStrategy(params)
            results = strategy.run_backtest(df)
            
            # Filter: reasonable trade count
            if results['total_trades'] < 3 or results['total_trades'] > 500:
                continue
            
            # Filter: must be profitable or close (gevşetildi)
            if results['profit_factor'] < 0.8:
                continue
            
            # Filter: reasonable win rate (gevşetildi)
            if results['win_rate'] < 30:
                continue
            
            # Score: prioritize profit factor, win rate, and reasonable return
            capped_return = min(results['total_return_pct'], 10000)
            score = (
                results['profit_factor'] * 20 +
                results['win_rate'] * 1.0 +
                capped_return * 0.1 -
                results['max_drawdown_pct'] * 0.8
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
                print(f"   ORB: {orb_min}min | Buffer: {buf_pct}% | TP: {tp1}/{tp2}/{tp3}%")
        
        except Exception as e:
            # Silently skip errors
            continue
    
    # Sort results by score
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"orb_avax_optimization_{timestamp}.json"
    
    # Convert to JSON-serializable format
    json_results = []
    for r in all_results[:50]:  # Top 50
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
    print(f"\n📊 Top 10 Results:")
    print(f"{'='*70}")
    
    for i, result in enumerate(all_results[:10], 1):
        r = result['results']
        p = result['params']
        print(f"\n{i}. Score: {result['score']:.2f}")
        print(f"   Trades: {r['total_trades']} | Win Rate: {r['win_rate']:.2f}%")
        print(f"   Profit Factor: {r['profit_factor']:.2f}")
        print(f"   Return: {r['total_return_pct']:.2f}% (5x leverage)")
        print(f"   Max Drawdown: {r['max_drawdown_pct']:.2f}%")
        print(f"   Avg Win: {r['avg_win_pct']:.2f}% | Avg Loss: {r['avg_loss_pct']:.2f}%")
        print(f"   Parameters:")
        print(f"     ORB: {p['orb_minutes']}min | Buffer: {p['breakout_buffer_pct']}%")
        print(f"     Min Bars: {p['min_bars_outside']} | Volume Filter: {p['enable_volume_filter']}")
        print(f"     Trend Filter: {p['enable_trend_filter']} ({p.get('trend_mode', 'N/A')})")
        print(f"     TP: {p['tp1_pct']}/{p['tp2_pct']}/{p['tp3_pct']}%")
        print(f"     Stop: {p['stop_mode']} (ATR×{p['atr_multiplier']})")
    
    if best_result:
        print(f"\n{'='*70}")
        print(f"🏆 BEST RESULT:")
        print(f"{'='*70}")
        r = best_result['results']
        p = best_result['params']
        print(f"Score: {best_result['score']:.2f}")
        print(f"Total Trades: {r['total_trades']}")
        print(f"Win Rate: {r['win_rate']:.2f}%")
        print(f"Profit Factor: {r['profit_factor']:.2f}")
        print(f"Total Return: {r['total_return_pct']:.2f}% (5x leverage)")
        print(f"Max Drawdown: {r['max_drawdown_pct']:.2f}%")
        print(f"\nOptimal Parameters:")
        print(f"  ORB Minutes: {p['orb_minutes']}")
        print(f"  Breakout Buffer: {p['breakout_buffer_pct']}%")
        print(f"  Min Bars Outside: {p['min_bars_outside']}")
        print(f"  Volume Filter: {p['enable_volume_filter']} (×{p['volume_multiplier']})")
        print(f"  Trend Filter: {p['enable_trend_filter']} ({p.get('trend_mode', 'N/A')})")
        print(f"  TP1: {p['tp1_pct']}% | TP2: {p['tp2_pct']}% | TP3: {p['tp3_pct']}%")
        print(f"  Stop Mode: {p['stop_mode']} | ATR Multiplier: {p['atr_multiplier']}")
        print(f"  Max Stop Loss: {p['max_stop_loss_pct']}% (HARD LIMIT)")
    
    print(f"\n💾 Results saved to: {results_file}")
    return best_result


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    optimize_orb_avax()

