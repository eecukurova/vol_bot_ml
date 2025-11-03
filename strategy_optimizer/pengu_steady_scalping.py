#!/usr/bin/env python3
"""
PENGU Steady Scalping Strategy
Goal: Small but consistent profits, frequent trades
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def test_scalping_strategy(timeframe='15m', tp_pct=0.3, sl_pct=0.5):
    """Test scalping strategy with small TP/SL"""
    print(f'📊 Testing: {timeframe} timeframe')
    print(f'   TP: {tp_pct}%, SL: {sl_pct}%')
    print('='*80)
    
    exchange = ccxt.binance()
    
    # Fetch data
    limit = 2000 if timeframe in ['1m', '5m', '15m'] else 1000
    ohlcv = exchange.fetch_ohlcv('PENGU/USDT', timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f'✅ {len(df)} candles fetched')
    print(f'📅 {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
    print()
    
    # Calculate indicators
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    macd, signal = calculate_macd(df['close'], 9, 21, 9)
    df['macd'] = macd
    df['macd_signal'] = signal
    
    # Scalping signals
    # Buy: RSI < 40 and MACD crosses above
    df['buy_signal'] = (
        (df['rsi'] < 40) & 
        (df['macd'] > df['macd_signal']) & 
        (df['macd'].shift(1) <= df['macd_signal'].shift(1))
    ) | (
        (df['close'] > df['ema20']) & (df['close'].shift(1) <= df['ema20'].shift(1)) &
        (df['rsi'] < 50)
    )
    
    # Sell: RSI > 60 or EMA crossover
    df['sell_signal'] = (
        (df['rsi'] > 60) |
        ((df['close'] < df['ema20']) & (df['close'].shift(1) >= df['ema20'].shift(1)))
    )
    
    # Backtest
    in_position = False
    entry_price = 0
    entry_idx = 0
    trades = []
    balance = 10000.0
    
    for i in range(50, len(df)):  # Start after enough data for indicators
        current_price = df['close'].iloc[i]
        
        # Enter position
        if not in_position and df['buy_signal'].iloc[i]:
            in_position = True
            entry_price = current_price
            entry_idx = i
        
        # Exit position
        if in_position:
            pnl_pct = (current_price - entry_price) / entry_price
            
            # TP
            if pnl_pct >= tp_pct / 100:
                trades.append({
                    'entry': entry_idx,
                    'exit': i,
                    'pnl': tp_pct / 100,
                    'type': 'TP',
                    'entry_price': entry_price,
                    'exit_price': current_price
                })
                balance += balance * (tp_pct / 100)
                in_position = False
            
            # SL
            elif pnl_pct <= -sl_pct / 100:
                trades.append({
                    'entry': entry_idx,
                    'exit': i,
                    'pnl': -sl_pct / 100,
                    'type': 'SL',
                    'entry_price': entry_price,
                    'exit_price': current_price
                })
                balance += balance * (-sl_pct / 100)
                in_position = False
            
            # Sell signal
            elif df['sell_signal'].iloc[i]:
                trades.append({
                    'entry': entry_idx,
                    'exit': i,
                    'pnl': pnl_pct,
                    'type': 'Signal',
                    'entry_price': entry_price,
                    'exit_price': current_price
                })
                balance += balance * pnl_pct
                in_position = False
    
    if not trades:
        return None
    
    total_return = ((balance - 10000) / 10000) * 100
    winning = [t for t in trades if t['pnl'] > 0]
    win_rate = len(winning) / len(trades) * 100
    avg_return = sum(t['pnl'] for t in trades) / len(trades) * 100
    
    # Calculate max drawdown
    equity = [10000.0]
    for trade in trades:
        equity.append(equity[-1] * (1 + trade['pnl']))
    
    peak = equity[0]
    max_dd = 0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak
        if dd > max_dd:
            max_dd = dd
    
    return {
        'timeframe': timeframe,
        'tp': tp_pct,
        'sl': sl_pct,
        'trades': len(trades),
        'win_rate': win_rate,
        'total_return': total_return,
        'avg_return': avg_return,
        'max_dd': max_dd * 100,
        'balance': balance
    }

def main():
    print('🎯 PENGU STEADY SCALPING - SMALL & CONSISTENT')
    print('='*80)
    print()
    
    # Test different timeframes and TP/SL combinations
    configs = [
        {'tf': '15m', 'tp': 0.5, 'sl': 1.0},
        {'tf': '15m', 'tp': 0.3, 'sl': 0.6},
        {'tf': '15m', 'tp': 0.2, 'sl': 0.4},
        {'tf': '5m', 'tp': 0.3, 'sl': 0.6},
        {'tf': '5m', 'tp': 0.2, 'sl': 0.4},
        {'tf': '1h', 'tp': 0.5, 'sl': 1.0},
        {'tf': '1h', 'tp': 0.3, 'sl': 0.6},
    ]
    
    results = []
    
    for config in configs:
        result = test_scalping_strategy(config['tf'], config['tp'], config['sl'])
        if result:
            results.append(result)
    
    # Display results
    if results:
        # Sort by consistency score (return / trades * win_rate)
        results.sort(key=lambda x: x['total_return'] / max(x['trades'], 1) * x['win_rate'], reverse=True)
        
        print('🏆 TOP STEADY SCALPING STRATEGIES:')
        print('='*80)
        
        for r in results[:10]:
            consistency = (r['total_return'] / max(r['trades'], 1)) * r['win_rate'] / 100
            print(f'{r["timeframe"]:5s} | TP={r["tp"]:4.1f}% SL={r["sl"]:4.1f}% | '
                  f'Trades={r["trades"]:3d} | WR={r["win_rate"]:5.1f}% | '
                  f'Return={r["total_return"]:6.2f}% | '
                  f'DD={r["max_dd"]:5.2f}% | '
                  f'Consistency={consistency:.4f}')
        
        print()
        print('🎯 BEST FOR STEADY PROFITS:')
        best = results[0]
        print(f'   Timeframe: {best["timeframe"]}')
        print(f'   TP: {best["tp"]}%')
        print(f'   SL: {best["sl"]}%')
        print(f'   Expected: {best["trades"]} trades with {best["win_rate"]:.1f}% win rate')
        print(f'   Total Return: {best["total_return"]:.2f}%')
        print(f'   Max Drawdown: {best["max_dd"]:.2f}%')
    else:
        print('❌ No profitable strategies found with scalping approach')

if __name__ == "__main__":
    main()

