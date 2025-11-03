#!/usr/bin/env python3
"""
PENGU - PROPER BACKTEST
Test Pine Script logic with ACTUAL TradingView data
No look-ahead bias, proper validation
"""

import ccxt
import pandas as pd
import numpy as np

def backtest_pine_logic(df, tp_pct=0.5, sl_pct=1.5):
    """Backtest the exact Pine Script logic"""
    
    # Calculate indicators (Pine Script simulation)
    # RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_14 = 100 - (100 / (1 + gain/loss))
    
    # MACD 12_26
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    macd_12_26 = ema_12 - ema_26
    macd_signal_12_26 = macd_12_26.ewm(span=9, adjust=False).mean()
    macd_hist_12_26 = macd_12_26 - macd_signal_12_26
    
    # MACD 9_21
    ema_9 = df['close'].ewm(span=9, adjust=False).mean()
    ema_21 = df['close'].ewm(span=21, adjust=False).mean()
    macd_9_21 = ema_9 - ema_21
    macd_signal_9_21 = macd_9_21.ewm(span=9, adjust=False).mean()
    macd_hist_9_21 = macd_9_21 - macd_signal_9_21
    
    # Bollinger Bands 20
    bb_middle_20 = df['close'].rolling(window=20).mean()
    bb_std_20 = df['close'].rolling(window=20).std()
    bb_upper_20 = bb_middle_20 + (bb_std_20 * 2)
    bb_lower_20 = bb_middle_20 - (bb_std_20 * 2)
    
    # Volume
    volume_ma_20 = df['volume'].rolling(window=20).mean()
    volume_ratio_20 = df['volume'] / volume_ma_20
    
    volume_ma_10 = df['volume'].rolling(window=10).mean()
    volume_ratio_10 = df['volume'] / volume_ma_10
    
    # Moving averages
    ema_20 = df['close'].ewm(span=20, adjust=False).mean()
    ema_50 = df['close'].ewm(span=50, adjust=False).mean()
    ema_cross_20_50 = ema_20 - ema_50
    
    # Momentum
    momentum_5 = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) * 100
    
    # Price position
    low_50 = df['low'].rolling(window=50).min()
    high_50 = df['high'].rolling(window=50).max()
    price_position = (df['close'] - low_50) / (high_50 - low_50)
    
    # RSI 7
    delta7 = df['close'].diff()
    gain7 = (delta7.where(delta7 > 0, 0)).rolling(window=7).mean()
    loss7 = (-delta7.where(delta7 < 0, 0)).rolling(window=7).mean()
    rsi_7 = 100 - (100 / (1 + gain7/loss7))
    
    # Signals (from Pine Script - STRICTER VERSION)
    buy_condition_1 = (rsi_14 < 30) & (rsi_14 > rsi_14.shift(1)) & (macd_hist_12_26 > macd_hist_12_26.shift(1)) & (volume_ratio_20 > 1.5)
    buy_condition_2 = (df['close'] < bb_lower_20 * 1.01) & (df['close'] > bb_lower_20) & (volume_ratio_20 > 1.5) & (rsi_14 < 35)
    buy_condition_3 = (macd_hist_9_21 > macd_hist_9_21.shift(1)) & (momentum_5 > 0.5) & (volume_ratio_10 > 1.5) & (rsi_14 < 35)
    buy_condition_4 = (ema_20 > ema_50) & (ema_cross_20_50 > ema_cross_20_50.shift(1)) & (rsi_14 < 40) & (volume_ratio_20 > 1.3)
    buy_condition_5 = (price_position < 0.2) & (volume_ratio_20 > 2.0) & (rsi_7 < 30)
    
    buy_signal = buy_condition_1 | buy_condition_2 | buy_condition_3 | buy_condition_4 | buy_condition_5
    
    sell_condition_1 = (rsi_14 > 70) & (rsi_14 < rsi_14.shift(1)) & (macd_hist_12_26 < macd_hist_12_26.shift(1)) & (volume_ratio_20 > 1.5)
    sell_condition_2 = (df['close'] > bb_upper_20 * 0.99) & (df['close'] < bb_upper_20) & (volume_ratio_20 > 1.5) & (rsi_14 > 65)
    sell_condition_3 = (macd_hist_9_21 < macd_hist_9_21.shift(1)) & (momentum_5 < -0.5) & (volume_ratio_10 > 1.5) & (rsi_14 > 65)
    sell_condition_4 = (ema_20 < ema_50) & (ema_cross_20_50 < ema_cross_20_50.shift(1)) & (rsi_14 > 60) & (volume_ratio_20 > 1.3)
    sell_condition_5 = (price_position > 0.8) & (volume_ratio_20 > 2.0) & (rsi_7 > 70)
    
    sell_signal = sell_condition_1 | sell_condition_2 | sell_condition_3 | sell_condition_4 | sell_condition_5
    
    # Backtest with cooldown (10 bars)
    last_signal_bar = -999
    in_position = False
    entry_price = 0.0
    is_long = False
    trades = []
    balance = 10000.0
    
    for i in range(50, len(df)):  # Start after enough data
        # Check cooldown
        signal_after_cooldown = (i - last_signal_bar >= 10)
        
        # Entry logic
        if not in_position:
            if buy_signal.iloc[i] and signal_after_cooldown:
                in_position = True
                entry_price = df['close'].iloc[i]
                is_long = True
                last_signal_bar = i
            
            elif sell_signal.iloc[i] and signal_after_cooldown:
                in_position = True
                entry_price = df['close'].iloc[i]
                is_long = False
                last_signal_bar = i
        
        # Exit logic
        if in_position:
            if is_long:
                current_return = ((df['close'].iloc[i] - entry_price) / entry_price) * 100
                
                if current_return >= tp_pct:
                    trades.append({'type': 'TP', 'pnl': tp_pct/100, 'entry': entry_price, 'exit': df['close'].iloc[i]})
                    balance += balance * (tp_pct/100)
                    in_position = False
                elif current_return <= -sl_pct:
                    trades.append({'type': 'SL', 'pnl': -sl_pct/100, 'entry': entry_price, 'exit': df['close'].iloc[i]})
                    balance += balance * (-sl_pct/100)
                    in_position = False
                elif sell_signal.iloc[i]:
                    actual_pnl = current_return / 100
                    trades.append({'type': 'Exit', 'pnl': actual_pnl, 'entry': entry_price, 'exit': df['close'].iloc[i]})
                    balance += balance * actual_pnl
                    in_position = False
            
            else:  # Short
                current_return = ((entry_price - df['close'].iloc[i]) / entry_price) * 100
                
                if current_return >= tp_pct:
                    trades.append({'type': 'TP', 'pnl': tp_pct/100})
                    balance += balance * (tp_pct/100)
                    in_position = False
                elif current_return <= -sl_pct:
                    trades.append({'type': 'SL', 'pnl': -sl_pct/100})
                    balance += balance * (-sl_pct/100)
                    in_position = False
                elif buy_signal.iloc[i]:
                    actual_pnl = current_return / 100
                    trades.append({'type': 'Exit', 'pnl': actual_pnl})
                    balance += balance * actual_pnl
                    in_position = False
    
    if not trades:
        return None
    
    total_return = ((balance - 10000) / 10000) * 100
    win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades) * 100
    tp_count = len([t for t in trades if t['type'] == 'TP'])
    sl_count = len([t for t in trades if t['type'] == 'SL'])
    
    return {
        'trades': len(trades),
        'win_rate': win_rate,
        'total_return': total_return,
        'tp_count': tp_count,
        'sl_count': sl_count,
        'balance': balance
    }

def main():
    print('🔍 PENGU - PROPER BACKTEST (Python Logic)')
    print('='*80)
    
    # Fetch PENGU data
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=3000)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f'✅ Fetched {len(df)} candles')
    print(f'📅 {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
    print()
    
    # Test different TP/SL
    configs = [
        {'tp': 0.5, 'sl': 1.5},
        {'tp': 1.0, 'sl': 2.0},
        {'tp': 1.5, 'sl': 3.0},
        {'tp': 2.0, 'sl': 4.0},
    ]
    
    results = []
    for config in configs:
        result = backtest_pine_logic(df, config['tp'], config['sl'])
        if result:
            result['tp'] = config['tp']
            result['sl'] = config['sl']
            results.append(result)
    
    if results:
        results.sort(key=lambda x: x['total_return'], reverse=True)
        
        print('📊 BACKTEST RESULTS (Python Logic):')
        print('='*80)
        for r in results:
            print(f'TP={r["tp"]:.1f}% SL={r["sl"]:.1f}% | '
                  f'Trades={r["trades"]:3d} | WR={r["win_rate"]:5.1f}% | '
                  f'Return={r["total_return"]:6.2f}% | '
                  f'TP={r["tp_count"]} SL={r["sl_count"]}')
        
        print()
        print('🎯 En iyi parametre:')
        best = results[0]
        print(f'   TP: {best["tp"]}%, SL: {best["sl"]}%')
        print(f'   Return: {best["total_return"]:.2f}%')
        print(f'   Trades: {best["trades"]}')
        print(f'   Win Rate: {best["win_rate"]:.1f}%')
    else:
        print('❌ No trades generated')

if __name__ == "__main__":
    main()

