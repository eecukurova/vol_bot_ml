#!/usr/bin/env python3
"""
Test Volensy Breakout Strategy on PENGU
Daily conditions, volume-based, breakout pattern
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

print('🎯 VOLENSY BREAKOUT STRATEGY TEST - PENGU')
print('='*80)

# Fetch data
exchange = ccxt.binance()

# Daily data for breakout strategy
daily_df = pd.DataFrame(exchange.fetch_ohlcv('PENGU/USDT', '1d', limit=500),
                        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

# Also fetch 1h for timing
hourly_df = pd.DataFrame(exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=2000),
                         columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

print(f'Daily: {len(daily_df)} candles')
print(f'Hourly: {len(hourly_df)} candles')
print()

# Strategy parameters
chgPctMin = 4.0  # Min %4 kapanış farkı
volKatsayi = 1.4  # Volume katsayı
lenVolMa = 10  # 10 bar volume MA
lenBreak = 250  # Breakout kapsamı
absVolMin = 100000  # Min mutlak volume

tpPct = 5.0
slPct = 2.5

print('📊 STRATEGY LOGIC:')
print('='*80)
print('Conditions for LONG:')
print('  1. Close change > 4%')
print('  2. Volume > Volume MA * 1.4')
print('  3. Close > Highest of prev 250 closes')
print('  4. Volume > 100,000')
print()

# Calculate indicators
daily_df['datetime'] = pd.to_datetime(daily_df['timestamp'], unit='ms')
daily_df['pct_change'] = ((daily_df['close'] / daily_df['close'].shift(1)) - 1) * 100
daily_df['volume_ma'] = daily_df['volume'].rolling(window=lenVolMa).mean()
daily_df['vol_ratio'] = daily_df['volume'] / daily_df['volume_ma']
daily_df['highest_prev'] = daily_df['close'].shift(1).rolling(window=lenBreak).max()

# Conditions
daily_df['cond_price'] = daily_df['pct_change'] > chgPctMin
daily_df['cond_vol'] = daily_df['vol_ratio'] > volKatsayi
daily_df['cond_break'] = daily_df['close'] > daily_df['highest_prev']
daily_df['cond_abs_vol'] = daily_df['volume'] > absVolMin

daily_df['long_signal'] = daily_df['cond_price'] & daily_df['cond_vol'] & daily_df['cond_break'] & daily_df['cond_abs_vol']

# Count signals
signal_count = daily_df['long_signal'].sum()
print(f'✅ Daily signals generated: {signal_count}')
print()

# Show signals
print('📈 SIGNALS:')
signals_df = daily_df[daily_df['long_signal']].copy()
for idx, row in signals_df.head(10).iterrows():
    print(f'   {row["datetime"]}: Close=${row["close"]:.6f}, Change={row["pct_change"]:.2f}%, Volume={row["volume"]:.0f}')
if len(signals_df) > 10:
    print(f'   ... and {len(signals_df) - 10} more')
print()

# Backtest
if signal_count > 0:
    balance = 10000.0
    trades = []
    
    for i in range(len(daily_df)):
        if daily_df['long_signal'].iloc[i]:
            entry_price = daily_df['close'].iloc[i]
            entry_date = daily_df['datetime'].iloc[i]
            
            # Look for TP/SL in future days
            for j in range(i+1, min(i+50, len(daily_df))):
                current_price = daily_df['close'].iloc[j]
                pnl = ((current_price - entry_price) / entry_price) * 100
                
                if pnl >= tpPct:
                    trades.append({
                        'entry': entry_date,
                        'exit': daily_df['datetime'].iloc[j],
                        'pnl': tpPct,
                        'type': 'TP',
                        'days': j-i
                    })
                    balance += balance * (tpPct / 100)
                    break
                elif pnl <= -slPct:
                    trades.append({
                        'entry': entry_date,
                        'exit': daily_df['datetime'].iloc[j],
                        'pnl': -slPct,
                        'type': 'SL',
                        'days': j-i
                    })
                    balance += balance * (-slPct / 100)
                    break
                elif j == min(i+49, len(daily_df)-1):
                    # Timeout (close at end)
                    actual_pnl = pnl
                    trades.append({
                        'entry': entry_date,
                        'exit': daily_df['datetime'].iloc[j],
                        'pnl': actual_pnl,
                        'type': 'Timeout',
                        'days': j-i
                    })
                    balance += balance * (actual_pnl / 100)
    
    if trades:
        total_return = ((balance - 10000) / 10000) * 100
        win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades) * 100
        
        print('📊 BACKTEST RESULTS:')
        print('='*80)
        print(f'   Total Return: {total_return:.2f}%')
        print(f'   Win Rate: {win_rate:.1f}%')
        print(f'   Trades: {len(trades)}')
        print(f'   Final Balance: ${balance:.2f}')
        print()
        
        print('   First 5 trades:')
        for i, t in enumerate(trades[:5], 1):
            print(f'   {i}. Entry: {t["entry"]}')
            print(f'      Exit: {t["exit"]}')
            print(f'      Return: {t["pnl"]:.2f}% ({t["type"]}) in {t["days"]} days')
    else:
        print('❌ No trades executed')
else:
    print('❌ No signals generated!')
    print()
    print('⚠️  This strategy may not work for PENGU because:')
    print('   - Needs %4+ daily move (very rare)')
    print('   - Needs breakout of 250-day high')
    print('   - Needs high volume')

