#!/usr/bin/env python3
"""
Test Heikin Ashi + RSI + Bollinger Hybrid Strategy
Based on the provided Pine Script
"""

import ccxt
import pandas as pd
import numpy as np

def calculate_heikin_ashi(open_p, high, low, close):
    """Calculate Heikin Ashi"""
    ha_close = (open_p + high + low + close) / 4
    ha_open = pd.Series(index=close.index, dtype='float64')
    ha_open.iloc[0] = (open_p.iloc[0] + close.iloc[0]) / 2
    
    for i in range(1, len(close)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
    
    ha_high = pd.concat([high, ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([low, ha_open, ha_close], axis=1).min(axis=1)
    
    return ha_open, ha_high, ha_low, ha_close

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def backtest_heikin_hybrid(df, tp_pct=1.0, sl_pct=2.0):
    """Backtest the Heikin Ashi Hybrid strategy"""
    # Calculate indicators on Heikin Ashi
    ha_open, ha_high, ha_low, ha_close = calculate_heikin_ashi(df['open'], df['high'], df['low'], df['close'])
    
    # RSI
    rsi = calculate_rsi(ha_close, 15)
    
    # Bollinger Bands
    bb_length = 20
    bb_std_dev = 2.0
    bb_middle = ha_close.rolling(window=bb_length).mean()
    bb_std = ha_close.rolling(window=bb_length).std()
    bb_upper = bb_middle + (bb_std * bb_std_dev)
    bb_lower = bb_middle - (bb_std * bb_std_dev)
    
    # EMAs
    ema_fast = ha_close.ewm(span=12, adjust=False).mean()
    ema_slow = ha_close.ewm(span=26, adjust=False).mean()
    
    # Volume
    volume_ma = df['volume'].rolling(window=20).mean()
    volume_ratio = df['volume'] / volume_ma
    
    # Momentum
    momentum_length = 4
    price_mom = ((ha_close - ha_close.shift(momentum_length)) / ha_close.shift(momentum_length)) * 100
    
    # Heikin Ashi direction
    ha_up = ha_close > ha_open
    ha_down = ha_close < ha_open
    
    # Signals
    rsi_oversold = 25
    rsi_overbought = 70
    volume_threshold = 1.0
    momentum_threshold = 0.6
    
    # Long conditions
    long_c1 = (rsi < rsi_oversold) & (ha_close <= bb_lower * 1.02) & (volume_ratio > volume_threshold) & \
              (ema_fast > ema_slow) & (price_mom > -momentum_threshold) & ha_up
    
    long_c2 = (ha_close > bb_lower) & (ha_close.shift(1) <= bb_lower.shift(1)) & (rsi > rsi.shift(1)) & \
              (volume_ratio > volume_threshold) & (ema_fast > ema_slow) & ha_up
    
    long_c3 = (price_mom > momentum_threshold) & (volume_ratio > volume_threshold * 1.5) & \
              (ema_fast > ema_slow) & (rsi > 30) & (rsi < 70) & ha_up
    
    # Short conditions
    short_c1 = (rsi > rsi_overbought) & (ha_close >= bb_upper * 0.98) & (volume_ratio > volume_threshold) & \
               (ema_fast < ema_slow) & (price_mom < momentum_threshold) & ha_down
    
    short_c2 = (ha_close < bb_upper) & (ha_close.shift(1) >= bb_upper.shift(1)) & (rsi < rsi.shift(1)) & \
               (volume_ratio > volume_threshold) & (ema_fast < ema_slow) & ha_down
    
    short_c3 = (price_mom < -momentum_threshold) & (volume_ratio > volume_threshold * 1.5) & \
               (ema_fast < ema_slow) & (rsi > 30) & (rsi < 70) & ha_down
    
    long_signal = long_c1 | long_c2 | long_c3
    short_signal = short_c1 | short_c2 | short_c3
    
    # Cooldown
    cooldown_bars = 2
    filtered_long = [False] * len(df)
    filtered_short = [False] * len(df)
    last_sig = -999
    
    for i in range(len(df)):
        if long_signal.iloc[i] and (i - last_sig >= cooldown_bars):
            filtered_long[i] = True
            last_sig = i
        elif short_signal.iloc[i] and (i - last_sig >= cooldown_bars):
            filtered_short[i] = True
            last_sig = i
    
    # Backtest
    in_position = False
    entry_price = 0
    is_long = False
    trades = []
    balance = 10000.0
    
    for i in range(50, len(df)):  # Start after enough data
        current_price = df['close'].iloc[i]
        
        # Entry
        if not in_position and filtered_long[i]:
            in_position = True
            is_long = True
            entry_price = current_price
        elif not in_position and filtered_short[i]:
            in_position = True
            is_long = False
            entry_price = current_price
        
        # Exit
        if in_position:
            if is_long:
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price
            
            # TP
            if pnl_pct >= tp_pct / 100:
                trades.append({'pnl': tp_pct / 100, 'type': 'TP', 'direction': 'L' if is_long else 'S'})
                balance += balance * (tp_pct / 100)
                in_position = False
            # SL
            elif pnl_pct <= -sl_pct / 100:
                trades.append({'pnl': -sl_pct / 100, 'type': 'SL', 'direction': 'L' if is_long else 'S'})
                balance += balance * (-sl_pct / 100)
                in_position = False
            # Opposite signal
            elif (is_long and filtered_short[i]) or (not is_long and filtered_long[i]):
                trades.append({'pnl': pnl_pct, 'type': 'Signal', 'direction': 'L' if is_long else 'S'})
                balance += balance * pnl_pct
                in_position = False
    
    if not trades:
        return None
    
    total_return = ((balance - 10000) / 10000) * 100
    winning = [t for t in trades if t['pnl'] > 0]
    win_rate = len(winning) / len(trades) * 100
    long_trades = len([t for t in trades if t['direction'] == 'L'])
    short_trades = len([t for t in trades if t['direction'] == 'S'])
    
    return {
        'trades': len(trades),
        'win_rate': win_rate,
        'total_return': total_return,
        'avg_return': sum(t['pnl'] for t in trades) / len(trades) * 100,
        'long_trades': long_trades,
        'short_trades': short_trades,
        'balance': balance
    }

def main():
    print('🎯 HEIKIN ASHI HYBRID STRATEGY TEST - PENGU')
    print('='*80)
    
    # Fetch data
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=1500)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f'✅ {len(df)} candles')
    print(f'📅 {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
    print()
    
    # Test with different TP/SL
    configs = [
        {'tp': 1.0, 'sl': 2.0},
        {'tp': 1.5, 'sl': 3.0},
        {'tp': 0.8, 'sl': 1.6},
        {'tp': 2.0, 'sl': 4.0},
    ]
    
    results = []
    for config in configs:
        result = backtest_heikin_hybrid(df, config['tp'], config['sl'])
        if result:
            result['tp'] = config['tp']
            result['sl'] = config['sl']
            results.append(result)
    
    if results:
        results.sort(key=lambda x: x['total_return'], reverse=True)
        
        print('📊 RESULTS:')
        print('='*80)
        for r in results:
            print(f'TP={r["tp"]:.1f}% SL={r["sl"]:.1f}% | '
                  f'Trades={r["trades"]:3d} | WR={r["win_rate"]:5.1f}% | '
                  f'Return={r["total_return"]:6.2f}% | '
                  f'Long={r["long_trades"]:2d} Short={r["short_trades"]:2d}')
        
        print()
        print('🏆 BEST CONFIGURATION:')
        best = results[0]
        print(f'   TP: {best["tp"]}%, SL: {best["sl"]}%')
        print(f'   Total Return: {best["total_return"]:.2f}%')
        print(f'   Win Rate: {best["win_rate"]:.1f}%')
        print(f'   Trades: {best["trades"]} ({best["long_trades"]} Long, {best["short_trades"]} Short)')
    else:
        print('❌ No profitable trades found')

if __name__ == "__main__":
    main()

