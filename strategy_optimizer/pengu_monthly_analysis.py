#!/usr/bin/env python3
"""
PENGU EMA20 Strategy - Monthly Analysis
Shows exactly why the month's result is not visible in TradingView
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

print('📊 PENGU EMA20 - Monthly Detailed Analysis')
print('='*80)

# Initialize exchange
exchange = ccxt.binance()

# Fetch data
print('📥 Fetching PENGU/USDT 1h data from Binance...')
ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=2000)
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

print(f'✅ Fetched {len(df)} candles')
print(f'📅 From: {df["datetime"].iloc[0]}')
print(f'📅 To: {df["datetime"].iloc[-1]}')
print()

# Calculate Heikin Ashi
ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
ha_open_list = [0.0] * len(df)
ha_open_list[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2

for i in range(1, len(df)):
    ha_open_list[i] = (ha_open_list[i-1] + ha_close.iloc[i-1]) / 2

df['ha_close'] = ha_close
df['ha_open'] = pd.Series(ha_open_list)

# EMA 20
df['ema20'] = df['ha_close'].ewm(span=20, adjust=False).mean()

# Signals
df['buy_signal'] = (df['ha_close'] > df['ema20']) & (df['ha_close'].shift(1) <= df['ema20'].shift(1))
df['sell_signal'] = (df['ha_close'] < df['ema20']) & (df['ha_close'].shift(1) >= df['ema20'].shift(1))

# Trading simulation
in_position = False
entry_price = 0.0
entry_idx = 0
trades = []
trades_by_month = {}

balance = 10000.0
equity_curve = []

for i in range(20, len(df)):
    current_price = df['close'].iloc[i]
    
    if not in_position:
        if df['buy_signal'].iloc[i]:
            in_position = True
            entry_price = current_price
            entry_idx = i
    else:
        current_return = ((current_price - entry_price) / entry_price) * 100
        
        # Check TP/SL
        if current_return >= 1.0:
            # TP Hit
            balance += balance * (current_return / 100)
            trade = {
                'entry_date': df['datetime'].iloc[entry_idx],
                'exit_date': df['datetime'].iloc[i],
                'entry_price': entry_price,
                'exit_price': current_price,
                'return': current_return,
                'exit_reason': 'TP'
            }
            trades.append(trade)
            
            # Track by month
            month_key = df['datetime'].iloc[i].strftime('%Y-%m')
            if month_key not in trades_by_month:
                trades_by_month[month_key] = {'trades': [], 'total_return': 0.0}
            trades_by_month[month_key]['trades'].append(trade)
            trades_by_month[month_key]['total_return'] += current_return
            
            in_position = False
            
        elif current_return <= -2.0:
            # SL Hit
            balance += balance * (current_return / 100)
            trade = {
                'entry_date': df['datetime'].iloc[entry_idx],
                'exit_date': df['datetime'].iloc[i],
                'entry_price': entry_price,
                'exit_price': current_price,
                'return': current_return,
                'exit_reason': 'SL'
            }
            trades.append(trade)
            
            month_key = df['datetime'].iloc[i].strftime('%Y-%m')
            if month_key not in trades_by_month:
                trades_by_month[month_key] = {'trades': [], 'total_return': 0.0}
            trades_by_month[month_key]['trades'].append(trade)
            trades_by_month[month_key]['total_return'] += current_return
            
            in_position = False
            
        elif df['sell_signal'].iloc[i]:
            # Sell signal
            balance += balance * (current_return / 100)
            trade = {
                'entry_date': df['datetime'].iloc[entry_idx],
                'exit_date': df['datetime'].iloc[i],
                'entry_price': entry_price,
                'exit_price': current_price,
                'return': current_return,
                'exit_reason': 'Sell Signal'
            }
            trades.append(trade)
            
            month_key = df['datetime'].iloc[i].strftime('%Y-%m')
            if month_key not in trades_by_month:
                trades_by_month[month_key] = {'trades': [], 'total_return': 0.0}
            trades_by_month[month_key]['trades'].append(trade)
            trades_by_month[month_key]['total_return'] += current_return
            
            in_position = False
    
    equity_curve.append({'date': df['datetime'].iloc[i], 'balance': balance})

# Convert to DataFrame
equity_df = pd.DataFrame(equity_curve)
equity_df['month'] = equity_df['date'].dt.strftime('%Y-%m')

print('📊 OVERALL RESULTS:')
print(f'   Total Trades: {len(trades)}')
print(f'   Win Rate: {len([t for t in trades if t["return"] > 0]) / len(trades) * 100:.1f}%' if trades else '   Win Rate: 0%')
print(f'   Total Return: {((balance - 10000) / 10000) * 100:.2f}%')
print(f'   Final Balance: ${balance:.2f}')
print()

print('📅 MONTHLY BREAKDOWN:')
print()

for month in sorted(trades_by_month.keys()):
    stats = trades_by_month[month]
    month_trades = stats['trades']
    wins = len([t for t in month_trades if t['return'] > 0])
    total_return = stats['total_return']
    
    print(f'📆 {month}:')
    print(f'   Trades: {len(month_trades)}')
    print(f'   Wins: {wins}')
    print(f'   Win Rate: {wins / len(month_trades) * 100:.1f}%' if month_trades else '   Win Rate: 0%')
    print(f'   Total Return: {total_return:.2f}%')
    print()
    
    # Show first few trades
    for i, trade in enumerate(month_trades[:3]):
        print(f'   Trade {i+1}:')
        print(f'      Entry: {trade["entry_date"]} @ ${trade["entry_price"]:.6f}')
        print(f'      Exit: {trade["exit_date"]} @ ${trade["exit_price"]:.6f}')
        print(f'      Return: {trade["return"]:.2f}% ({trade["exit_reason"]})')
        print()
    
    if len(month_trades) > 3:
        print(f'   ... and {len(month_trades) - 3} more trades')
        print()

print('='*80)
print('❓ WHY CAN\'T YOU SEE MONTHLY RESULTS IN TRADINGVIEW?')
print('='*80)
print()
print('TradingView\'s "Genel Bakış" (Overview) tab shows CUMULATIVE results')
print('for the entire backtest period. To see monthly breakdown, you need to:')
print()
print('1. Click on "Performans" (Performance) tab')
print('2. Or "İşlem analizi" (Trade analysis) tab')
print('3. Look for monthly/filter options')
print()
print('The chart shows the EQUITY CURVE over time, but the summary')
print('statistics are always for the ENTIRE period from start to end.')
print()

