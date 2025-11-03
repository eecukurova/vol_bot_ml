#!/usr/bin/env python3
"""
Test Chart Patterns on PENGU
- Head & Shoulders
- Inverse Head & Shoulders
- Flags & Pennants
- Triangles
- Double Tops/Bottoms
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

def detect_head_shoulders(high, low):
    """Detect Head & Shoulders pattern"""
    signals = []
    for i in range(20, len(high) - 20):
        # Left shoulder
        l_shoulder = high[i-10:i].max()
        # Head
        head = high[i: i+10].max()
        # Right shoulder
        r_shoulder = high[i+10:i+20].max()
        
        # Neckline (support level)
        neckline = (low[i-10:i].min() + low[i+10:i+20].min()) / 2
        
        # Pattern conditions
        if head > l_shoulder and head > r_shoulder:
            if l_shoulder > neckline and r_shoulder > neckline:
                if abs(l_shoulder - r_shoulder) / head < 0.05:  # Similar shoulders
                    signals.append(i + 10)  # Sell signal
    
    return signals

def detect_inverse_head_shoulders(low, high):
    """Detect Inverse Head & Shoulders pattern"""
    signals = []
    for i in range(20, len(low) - 20):
        # Left shoulder
        l_shoulder = low[i-10:i].min()
        # Head
        head = low[i: i+10].min()
        # Right shoulder
        r_shoulder = low[i+10:i+20].min()
        
        # Neckline (resistance level)
        neckline = (high[i-10:i].max() + high[i+10:i+20].max()) / 2
        
        # Pattern conditions
        if head < l_shoulder and head < r_shoulder:
            if l_shoulder < neckline and r_shoulder < neckline:
                if abs(l_shoulder - r_shoulder) / abs(head) < 0.05:
                    signals.append(i + 10)  # Buy signal
    
    return signals

def detect_flag_pennant(df, lookback=20):
    """Detect Flag & Pennant patterns"""
    buy_signals = []
    sell_signals = []
    
    for i in range(lookback, len(df) - lookback):
        # Flag/Pennant detection
        recent_high = df['high'][i-lookback:i].max()
        recent_low = df['low'][i-lookback:i].min()
        recent_range = recent_high - recent_low
        
        # Consolidation check (narrowing range)
        if recent_range < df['close'][i-lookback:i].std() * 1.5:
            # Uptrend flag (buy)
            if df['close'][i] > df['close'][i-lookback]:
                buy_signals.append(i)
            # Downtrend flag (sell)
            elif df['close'][i] < df['close'][i-lookback]:
                sell_signals.append(i)
    
    return buy_signals, sell_signals

def detect_double_top_bottom(high, low, close):
    """Detect Double Top/Bottom patterns"""
    buy_signals = []
    sell_signals = []
    
    for i in range(40, len(close) - 40):
        # Look for double top (bearish)
        first_top = high[i-20:i-5].max()
        valley = low[i-10:i].min()
        second_top = high[i:i+15].max()
        
        # Double top: two similar peaks with valley in between
        if abs(first_top - second_top) / first_top < 0.02:  # Similar peaks
            if valley < (first_top + second_top) / 2 * 0.95:  # Clear valley
                sell_signals.append(i + 15)
        
        # Look for double bottom (bullish)
        first_bottom = low[i-20:i-5].min()
        peak = high[i-10:i].max()
        second_bottom = low[i:i+15].min()
        
        if abs(first_bottom - second_bottom) / abs(first_bottom) < 0.02:
            if peak > (first_bottom + second_bottom) / 2 * 1.05:
                buy_signals.append(i + 15)
    
    return buy_signals, sell_signals

def backtest_pattern(df, buy_signals, sell_signals, pattern_name, tp=0.01, sl=0.02):
    """Backtest chart pattern strategy"""
    in_position = False
    entry_price = 0
    trades = []
    balance = 10000.0
    
    for i in range(len(df)):
        current_price = df['close'].iloc[i]
        
        # Enter position
        if not in_position and i in buy_signals:
            in_position = True
            entry_price = current_price
        
        # Exit position
        if in_position:
            pnl_pct = (current_price - entry_price) / entry_price
            
            # TP/SL check
            if pnl_pct >= tp:
                trades.append({'pnl': tp, 'type': 'TP'})
                balance += balance * tp
                in_position = False
            elif pnl_pct <= -sl:
                trades.append({'pnl': -sl, 'type': 'SL'})
                balance += balance * (-sl)
                in_position = False
            elif i in sell_signals:
                trades.append({'pnl': pnl_pct, 'type': 'Signal'})
                balance += balance * pnl_pct
                in_position = False
    
    if not trades:
        return None
    
    total_return = ((balance - 10000) / 10000) * 100
    win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades) * 100
    
    return {
        'name': pattern_name,
        'trades': len(trades),
        'win_rate': win_rate,
        'total_return': total_return
    }

def main():
    print('🎯 CHART PATTERNS TESTER - PENGU')
    print('='*80)
    
    # Fetch PENGU data
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=2000)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f'✅ Fetched {len(df)} candles')
    print(f'📅 {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
    print()
    
    print('🔍 Testing chart patterns...')
    results = []
    
    # 1. Head & Shoulders
    hs_signals = detect_head_shoulders(df['high'], df['low'])
    ihs_signals = detect_inverse_head_shoulders(df['low'], df['high'])
    hs_result = backtest_pattern(df, ihs_signals, hs_signals, 'Head & Shoulders')
    if hs_result:
        results.append(hs_result)
    
    # 2. Flags & Pennants
    flag_buy, flag_sell = detect_flag_pennant(df)
    flag_result = backtest_pattern(df, flag_buy, flag_sell, 'Flags & Pennants')
    if flag_result:
        results.append(flag_result)
    
    # 3. Double Tops/Bottoms
    dt_buy, dt_sell = detect_double_top_bottom(df['high'], df['low'], df['close'])
    dt_result = backtest_pattern(df, dt_buy, dt_sell, 'Double Tops/Bottoms')
    if dt_result:
        results.append(dt_result)
    
    # Display results
    if results:
        results.sort(key=lambda x: x['total_return'], reverse=True)
        
        print('📊 PATTERN TEST RESULTS:')
        print('='*80)
        for r in results:
            print(f'{r["name"]:25s} | Trades={r["trades"]:3d} | WR={r["win_rate"]:5.1f}% | Return={r["total_return"]:6.2f}%')
    else:
        print('❌ No patterns detected or all results negative')
    
    print()
    print('💡 Not: Chart patterns require longer lookback periods')
    print('   Consider testing with daily timeframe instead of hourly')

if __name__ == "__main__":
    main()

