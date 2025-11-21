#!/usr/bin/env python3
"""
Test Simple VWMA Strategy for ARB with optimized parameters
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import requests
import time

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


def test_params(params, name):
    """Test specific parameters"""
    print(f"\n{'='*70}")
    print(f"📊 Testing: {name}")
    print(f"{'='*70}")
    print(f"VWMA: {params['vwma_length']} | RSI: {params['rsi_oversold']}/{params['rsi_overbought']}")
    print(f"TP/SL: {params['tp_pct']}%/{params['sl_pct']}%")
    print(f"Trailing: {params['trailing_activation_pct']}%/{params['trailing_distance_pct']}%")
    
    df = download_binance_futures_klines("ARBUSDT", "4h", days=180)
    if df is None:
        print("❌ Failed to download data")
        return None
    
    strategy = VWMAARBSimpleStrategy(params)
    results = strategy.run_backtest(df)
    
    print(f"\n📈 Results:")
    print(f"  Total Trades: {results['total_trades']}")
    print(f"  Win Rate: {results['win_rate']:.2f}%")
    print(f"  Profit Factor: {results['profit_factor']:.2f}")
    print(f"  Total Return: {results['total_return_pct']:.2f}% (5x leverage)")
    print(f"  Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    print(f"  Avg Win: {results['avg_win_pct']:.2f}%")
    print(f"  Avg Loss: {results['avg_loss_pct']:.2f}%")
    
    if results['profit_factor'] > 1.5 and results['win_rate'] > 55:
        print(f"  ✅ GOOD RESULT!")
    elif results['profit_factor'] > 1.0:
        print(f"  ⚠️  MARGINAL")
    else:
        print(f"  ❌ POOR RESULT")
    
    return results


def main():
    """Test multiple parameter sets"""
    print("🚀 ARB Simple VWMA Strategy - Parameter Testing")
    
    # Test 1: Previous best (from optimization)
    params1 = {
        'vwma_length': 30,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'tp_pct': 0.8,
        'sl_pct': 0.6,
        'trailing_activation_pct': 0.5,
        'trailing_distance_pct': 0.5,
        'leverage': 5.0,
        'commission': 0.0004,
        'slippage': 0.0002,
    }
    test_params(params1, "Previous Best (VWMA=30, RSI=30/70, TP=0.8%, SL=0.6%)")
    
    # Test 2: More conservative
    params2 = {
        'vwma_length': 30,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'tp_pct': 1.0,
        'sl_pct': 0.8,
        'trailing_activation_pct': 0.5,
        'trailing_distance_pct': 0.5,
        'leverage': 5.0,
        'commission': 0.0004,
        'slippage': 0.0002,
    }
    test_params(params2, "Conservative (VWMA=30, RSI=35/65, TP=1.0%, SL=0.8%)")
    
    # Test 3: More aggressive
    params3 = {
        'vwma_length': 25,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'tp_pct': 0.6,
        'sl_pct': 0.5,
        'trailing_activation_pct': 0.3,
        'trailing_distance_pct': 0.3,
        'leverage': 5.0,
        'commission': 0.0004,
        'slippage': 0.0002,
    }
    test_params(params3, "Aggressive (VWMA=25, RSI=30/70, TP=0.6%, SL=0.5%)")
    
    # Test 4: Balanced
    params4 = {
        'vwma_length': 30,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'tp_pct': 1.0,
        'sl_pct': 0.6,
        'trailing_activation_pct': 0.5,
        'trailing_distance_pct': 0.5,
        'leverage': 5.0,
        'commission': 0.0004,
        'slippage': 0.0002,
    }
    test_params(params4, "Balanced (VWMA=30, RSI=30/70, TP=1.0%, SL=0.6%)")


if __name__ == "__main__":
    main()

