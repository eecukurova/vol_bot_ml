#!/usr/bin/env python3
"""
Quick test of ORB strategy for AVAX
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import requests
import time

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


def main():
    """Quick test"""
    print("🚀 ORB Strategy Quick Test for AVAX")
    
    # Download data
    print("\n📥 Downloading AVAXUSDT 4h data...")
    df = download_binance_futures_klines("AVAXUSDT", "4h", days=180)
    if df is None:
        print("❌ Failed to download data")
        return
    
    print(f"✅ Downloaded {len(df)} bars")
    
    # Test parameters
    params = {
        'orb_minutes': 15,
        'breakout_buffer_pct': 0.2,
        'min_bars_outside': 2,
        'enable_volume_filter': False,
        'enable_trend_filter': False,
        'tp1_pct': 1.0,
        'tp2_pct': 2.0,
        'tp3_pct': 3.0,
        'stop_mode': 'Smart Adaptive',
        'atr_length': 14,
        'atr_multiplier': 1.5,
        'max_stop_loss_pct': 2.5,
        'leverage': 5.0,
        'commission': 0.0004,
        'slippage': 0.0002,
    }
    
    print(f"\n📊 Testing with default parameters...")
    strategy = ORBBreakoutStrategy(params)
    results = strategy.run_backtest(df)
    
    print(f"\n📈 Results:")
    print(f"  Total Trades: {results['total_trades']}")
    print(f"  Win Rate: {results['win_rate']:.2f}%")
    print(f"  Profit Factor: {results['profit_factor']:.2f}")
    print(f"  Total Return: {results['total_return_pct']:.2f}% (5x leverage)")
    print(f"  Max Drawdown: {results['max_drawdown_pct']:.2f}%")
    print(f"  Avg Win: {results['avg_win_pct']:.2f}%")
    print(f"  Avg Loss: {results['avg_loss_pct']:.2f}%")


if __name__ == "__main__":
    main()

