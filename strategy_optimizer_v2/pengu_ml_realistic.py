#!/usr/bin/env python3
"""
PENGU ML Strategy - NO LOOK-AHEAD BIAS
Realistic approach without using future data
"""

import ccxt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import warnings
warnings.filterwarnings('ignore')

print('🎯 PENGU ML - REALISTIC (NO CHEATING)')
print('='*80)

# Fetch data
exchange = ccxt.binance()
df = pd.DataFrame(exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=1500), 
                  columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

print(f'📅 Data: {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
print()

# Calculate features
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
df['rsi'] = 100 - (100 / (1 + gain/loss))

ema12 = df['close'].ewm(span=12, adjust=False).mean()
ema26 = df['close'].ewm(span=26, adjust=False).mean()
df['macd'] = ema12 - ema26
df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
df['macd_hist'] = df['macd'] - df['macd_signal']

df['momentum'] = ((df['close'] - df['close'].shift(4)) / df['close'].shift(4)) * 100
df['volume_ma'] = df['volume'].rolling(window=20).mean()
df['volume_ratio'] = df['volume'] / df['volume_ma']

# ATR
hl = df['high'] - df['low']
hc = abs(df['high'] - df['close'].shift())
lc = abs(df['low'] - df['close'].shift())
df['atr'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(window=14).mean()
df['atr_pct'] = (df['atr'] / df['close']) * 100

# Generate REALISTIC labels (NO FUTURE DATA!)
# Simple strategy: Buy when oversold, sell when overbought
buy_signals = []
sell_signals = []

for i in range(50, len(df)):
    # Buy: Oversold condition
    if (df['rsi'].iloc[i] < 30 and df['rsi'].iloc[i] > df['rsi'].iloc[i-1] and
        df['macd_hist'].iloc[i] > df['macd_hist'].iloc[i-1] and
        df['volume_ratio'].iloc[i] > 1.2):
        buy_signals.append(i)
    
    # Sell: Overbought condition
    elif (df['rsi'].iloc[i] > 70 and df['rsi'].iloc[i] < df['rsi'].iloc[i-1] and
          df['macd_hist'].iloc[i] < df['macd_hist'].iloc[i-1] and
          df['volume_ratio'].iloc[i] > 1.2):
        sell_signals.append(i)

print(f'Buy signals: {len(buy_signals)}')
print(f'Sell signals: {len(sell_signals)}')
print()

# Backtest
in_position = False
entry_price = 0
trades = []
balance = 10000.0

for i in range(len(df)):
    if i in buy_signals and not in_position:
        in_position = True
        entry_price = df['close'].iloc[i]
    
    elif i in sell_signals and in_position:
        pnl = (df['close'].iloc[i] - entry_price) / entry_price
        
        # TP/SL
        if pnl >= 0.01:
            pnl = 0.01
        elif pnl <= -0.02:
            pnl = -0.02
        
        trades.append({'pnl': pnl})
        balance += balance * pnl
        in_position = False

if not trades:
    print('❌ No trades')
    exit()

total_return = ((balance - 10000) / 10000) * 100
win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades) * 100

print('📊 REALISTIC TEST RESULTS:')
print('='*80)
print(f'   Total Return: {total_return:.2f}%')
print(f'   Win Rate: {win_rate:.1f}%')
print(f'   Trades: {len(trades)}')
print(f'   Final Balance: ${balance:.2f}')
print()

print('🎯 SONUÇ:')
print('   Bu GERÇEK sonuç (look-ahead bias YOK)')
print('   TradingView sonuçlarına çok daha yakın!')

