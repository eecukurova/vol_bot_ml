#!/usr/bin/env python3
"""
ARB Enhanced Strategy Optimizer
Multiple indicators + Risk/Reward optimization
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

from src.strategy.vwma_arb_enhanced import VWMAARBEnhancedStrategy


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


def optimize_enhanced_strategy():
    """Optimize enhanced strategy with multiple indicators"""
    print(f"\n{'='*70}")
    print(f"🚀 ARB Enhanced VWMA Strategy Optimizer")
    print(f"{'='*70}")
    
    # Download data
    print(f"\n📥 Downloading ARBUSDT 4h data...")
    df = download_binance_futures_klines("ARBUSDT", "4h", days=180)
    if df is None or len(df) < 100:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Parameter ranges - Focus on better risk/reward (reduced for speed)
    vwma_lengths = [25, 30]
    rsi_oversold = [30]
    rsi_overbought = [70]
    
    # Better risk/reward ratios - Focus on good ratios
    tp_pcts = [0.8, 1.0, 1.2]
    sl_pcts = [0.5, 0.6]
    
    # Indicator combinations - Test key combinations
    use_macd_options = [True]
    use_bollinger_options = [True, False]
    use_atr_options = [True, False]
    min_indicators_options = [4, 5]  # Higher threshold for better signals
    
    trailing_activation = [0.5]
    trailing_distance = [0.5]
    
    all_results = []
    best_result = None
    best_score = -float('inf')
    
    combination_count = 0
    total_combinations = (len(vwma_lengths) * len(rsi_oversold) * len(rsi_overbought) * 
                         len(tp_pcts) * len(sl_pcts) * len(use_macd_options) * 
                         len(use_bollinger_options) * len(use_atr_options) * 
                         len(min_indicators_options) * len(trailing_activation) * len(trailing_distance))
    
    print(f"\n📊 Testing {total_combinations} parameter combinations...")
    print(f"   Focus: Better Risk/Reward + Higher Win Rate\n")
    
    for (vwma_len, rsi_os, rsi_ob, tp_pct, sl_pct, use_macd, use_bb, use_atr, 
         min_ind, trail_act, trail_dist) in product(
        vwma_lengths, rsi_oversold, rsi_overbought, tp_pcts, sl_pcts,
        use_macd_options, use_bollinger_options, use_atr_options,
        min_indicators_options, trailing_activation, trailing_distance
    ):
        combination_count += 1
        
        if combination_count % 100 == 0:
            print(f"   Progress: {combination_count}/{total_combinations} ({combination_count/total_combinations*100:.1f}%)")
        
        # Skip bad risk/reward ratios
        risk_reward = sl_pct / tp_pct
        if risk_reward > 1.5:  # Skip if risk/reward worse than 1:1.5
            continue
        
        params = {
            'vwma_length': vwma_len,
            'rsi_oversold': rsi_os,
            'rsi_overbought': rsi_ob,
            'tp_pct': tp_pct,
            'sl_pct': sl_pct,
            'trailing_activation_pct': trail_act,
            'trailing_distance_pct': trail_dist,
            'use_macd': use_macd,
            'use_bollinger': use_bb,
            'use_atr': use_atr,
            'min_indicators': min_ind,
            'leverage': 5.0,
            'commission': 0.0004,
            'slippage': 0.0002,
        }
        
        try:
            strategy = VWMAARBEnhancedStrategy(params)
            results = strategy.run_backtest(df)
            
            if results['total_trades'] < 20 or results['total_trades'] > 200:
                continue
            
            if results['win_rate'] < 50:  # Minimum 50% win rate
                continue
            
            if results['profit_factor'] < 1.5:  # Minimum 1.5 profit factor
                continue
            
            # Calculate required win rate for this risk/reward
            required_wr = (risk_reward / (1 + risk_reward)) * 100
            
            # Score: prioritize win rate, profit factor, and meeting required win rate
            score = (
                results['win_rate'] * 2.0 +  # Win rate is critical
                results['profit_factor'] * 10.0 +
                (results['win_rate'] - required_wr) * 5.0 +  # Bonus if exceeds required
                results['total_return_pct'] * 0.01 -
                results['max_drawdown_pct'] * 0.3
            )
            
            result = {
                'vwma_length': vwma_len,
                'rsi_oversold': rsi_os,
                'rsi_overbought': rsi_ob,
                'tp_pct': tp_pct,
                'sl_pct': sl_pct,
                'risk_reward': risk_reward,
                'required_wr': required_wr,
                'use_macd': use_macd,
                'use_bollinger': use_bb,
                'use_atr': use_atr,
                'min_indicators': min_ind,
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
        indicators = []
        if result['use_macd']:
            indicators.append("MACD")
        if result['use_bollinger']:
            indicators.append("BB")
        if result['use_atr']:
            indicators.append("ATR")
        indicators_str = ", ".join(indicators) if indicators else "None"
        
        print(f"\n{i}. VWMA={result['vwma_length']} | RSI={result['rsi_oversold']}/{result['rsi_overbought']} | TP={result['tp_pct']}% | SL={result['sl_pct']}%")
        print(f"   Indicators: {indicators_str} | Min: {result['min_indicators']}")
        print(f"   Risk/Reward: 1:{result['risk_reward']:.2f} | Required WR: {result['required_wr']:.2f}%")
        print(f"   Trades: {result['total_trades']} | Win Rate: {result['win_rate']:.2f}% | PF: {result['profit_factor']:.2f}")
        print(f"   Return: {result['total_return_pct']:.2f}% | DD: {result['max_drawdown_pct']:.2f}% | Score: {result['score']:.2f}")
    
    if best_result:
        print(f"\n{'='*70}")
        print(f"🏆 BEST RESULT FOR ARB")
        print(f"{'='*70}")
        print(f"VWMA Length: {best_result['vwma_length']}")
        print(f"RSI Levels: {best_result['rsi_oversold']}/{best_result['rsi_overbought']}")
        print(f"TP/SL: {best_result['tp_pct']}%/{best_result['sl_pct']}%")
        print(f"Risk/Reward: 1:{best_result['risk_reward']:.2f}")
        print(f"Required Win Rate: {best_result['required_wr']:.2f}%")
        print(f"\nIndicators:")
        print(f"  MACD: {best_result['use_macd']}")
        print(f"  Bollinger: {best_result['use_bollinger']}")
        print(f"  ATR: {best_result['use_atr']}")
        print(f"  Min Indicators: {best_result['min_indicators']}")
        print(f"\nPerformance:")
        print(f"  Total Trades: {best_result['total_trades']}")
        print(f"  Win Rate: {best_result['win_rate']:.2f}% (Required: {best_result['required_wr']:.2f}%)")
        print(f"  Profit Factor: {best_result['profit_factor']:.2f}")
        print(f"  Total Return: {best_result['total_return_pct']:.2f}% (5x leverage)")
        print(f"  Max Drawdown: {best_result['max_drawdown_pct']:.2f}%")
        print(f"  Avg Win: {best_result['avg_win_pct']:.2f}%")
        print(f"  Avg Loss: {best_result['avg_loss_pct']:.2f}%")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"arb_enhanced_optimization_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump({
            'best_result': best_result,
            'top_20': top_results,
            'all_results': all_results[:100],
            'timestamp': timestamp
        }, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to {filename}")
    
    return best_result


if __name__ == "__main__":
    optimize_enhanced_strategy()

