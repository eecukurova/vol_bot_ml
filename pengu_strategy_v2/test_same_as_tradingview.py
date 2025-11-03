#!/usr/bin/env python3
"""
Test CCI strategy with EXACT same logic as TradingView
Based on the CSV file results
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

print('🎯 CCI STRATEGY - TRADINGVIEW İLE BİREBİR AYNI TEST')
print('='*80)

# Read TradingView CSV to understand exact logic
tv_csv = pd.read_csv('/Users/ahmet/Downloads/PENGU_CCI_BINANCE_PENGUUSDT.P_2025-10-26.csv')

entries = tv_csv[tv_csv['Tip'] == 'Giriş uzun']
exits = tv_csv[tv_csv['Tip'] == 'Uzunu kapat']

print('📊 TRADINGVIEW SONUÇLARI (CSV\'den):')
tv_return = exits['Net K&Z %'].sum()
tv_wins = (exits['Net K&Z %'] > 0).sum()
tv_wr = (tv_wins / len(exits)) * 100

print(f'   Total Return: {tv_return:.2f}%')
print(f'   Win Rate: {tv_wr:.1f}%')
print(f'   Trades: {len(exits)}')
print()

# Fetch data for Aug 6 to Oct 24
print('📥 Gerçek veriyi çekiyorum (2025-08-01 to 2025-10-25)...')

exchange = ccxt.binance()
ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=2500)
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

# Filter to TradingView date range
df = df[(df['datetime'] >= '2025-08-01') & (df['datetime'] <= '2025-10-25')]

print(f'✅ {len(df)} mum veri çekildi')
print(f'📅 {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
print()

# Calculate CCI with EXACT TradingView formula
tp = (df['high'] + df['low'] + df['close']) / 3
tp_sma = tp.rolling(window=20).mean()

# Mean Absolute Deviation (MAD)
tp_mad = tp.rolling(window=20).apply(lambda x: np.abs(x - x.mean()).mean())
cci = (tp - tp_sma) / (0.015 * tp_mad)

df['cci'] = cci

# Generate signals
df['buy_signal'] = (cci.shift(1) <= -100) & (cci > -100)
df['sell_signal'] = (cci.shift(1) >= 100) & (cci < 100)

buy_count = df['buy_signal'].sum()
sell_count = df['sell_signal'].sum()

print(f'Buy signals: {buy_count}')
print(f'Sell signals: {sell_count}')
print()

# Backtest with EXACT same logic
in_position = False
entry_price = 0
entry_idx = 0
trades = []
balance = 10000.0

for i in range(20, len(df)):  # Start after 20 periods for CCI
    current_price = df['close'].iloc[i]
    
    # ENTER POSITION
    if not in_position and df['buy_signal'].iloc[i]:
        in_position = True
        entry_price = current_price
        entry_idx = i
        entry_time = df['datetime'].iloc[i]
    
    # MANAGE POSITION (check TP/SL every bar)
    if in_position:
        pnl_pct = (current_price - entry_price) / entry_price
        
        # TAKE PROFIT (1%)
        if pnl_pct >= 0.01:
            trades.append({
                'entry_time': entry_time,
                'exit_time': df['datetime'].iloc[i],
                'entry_price': entry_price,
                'exit_price': current_price,
                'pnl': 0.01,
                'type': 'TP',
                'entry_idx': entry_idx,
                'exit_idx': i
            })
            balance += balance * 0.01
            in_position = False
        
        # STOP LOSS (2%)
        elif pnl_pct <= -0.02:
            trades.append({
                'entry_time': entry_time,
                'exit_time': df['datetime'].iloc[i],
                'entry_price': entry_price,
                'exit_price': current_price,
                'pnl': -0.02,
                'type': 'SL',
                'entry_idx': entry_idx,
                'exit_idx': i
            })
            balance += balance * (-0.02)
            in_position = False
        
        # SELL SIGNAL EXIT
        elif df['sell_signal'].iloc[i]:
            actual_pnl = pnl_pct
            trades.append({
                'entry_time': entry_time,
                'exit_time': df['datetime'].iloc[i],
                'entry_price': entry_price,
                'exit_price': current_price,
                'pnl': actual_pnl,
                'type': 'Signal',
                'entry_idx': entry_idx,
                'exit_idx': i
            })
            balance += balance * actual_pnl
            in_position = False

# Calculate final stats
total_return = ((balance - 10000) / 10000) * 100
winning = [t for t in trades if t['pnl'] > 0]
win_rate = (len(winning) / len(trades)) * 100 if trades else 0

print('='*80)
print('📊 BENİM TEST SONUÇLARI:')
print(f'   Total Return: {total_return:.2f}%')
print(f'   Win Rate: {win_rate:.1f}%')
print(f'   Trades: {len(trades)}')
print(f'   Winning: {len(winning)}')
print(f'   Losing: {len(trades) - len(winning)}')
print()

# Compare with TradingView
print('='*80)
print('📊 KARŞILAŞTIRMA:')
print(f'   Total Return: {total_return:.2f}% vs {tv_return:.2f}% (TradingView)')
print(f'   Win Rate: {win_rate:.1f}% vs {tv_wr:.1f}% (TradingView)')
print(f'   Trades: {len(trades)} vs {len(exits)} (TradingView)')
print()

# Show first few trades
print('İlk 5 İşlem:')
for i in range(min(5, len(trades))):
    t = trades[i]
    print(f'  {i+1}. Entry: {t["entry_time"]} @ ${t["entry_price"]:.6f}')
    print(f'     Exit: {t["exit_time"]} @ ${t["exit_price"]:.6f}')
    print(f'     Return: {t["pnl"]*100:.2f}% ({t["type"]})')
    print()

# Show TP/SL breakdown
tp_count = len([t for t in trades if t['type'] == 'TP'])
sl_count = len([t for t in trades if t['type'] == 'SL'])
sig_count = len([t for t in trades if t['type'] == 'Signal'])

print('İşlem Dağılımı:')
print(f'   TP: {tp_count}')
print(f'   SL: {sl_count}')
print(f'   Sell Signal: {sig_count}')

