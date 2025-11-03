#!/usr/bin/env python3
"""
Test if Pine Script signals match Python expectations
"""

import ccxt
import pandas as pd
import numpy as np

print('🔍 Testing Pine Script Signal Logic')
print('='*80)

# Fetch data
exchange = ccxt.binance()
ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=1000)
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

# Calculate indicators (as in Pine Script)
df['rsi'] = df['close'].apply(lambda x: pd.Series([0]*len(df)))  # Will calculate below
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

# MACD
ema_12 = df['close'].ewm(span=12, adjust=False).mean()
ema_26 = df['close'].ewm(span=26, adjust=False).mean()
df['macd'] = ema_12 - ema_26
df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
df['macd_hist'] = df['macd'] - df['macd_signal']

# Momentum
df['momentum'] = ((df['close'] - df['close'].shift(4)) / df['close'].shift(4)) * 100

# Volume
df['volume_ma'] = df['volume'].rolling(window=20).mean()
df['volume_ratio'] = df['volume'] / df['volume_ma']

# ATR
high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
ranges = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df['atr'] = ranges.rolling(window=14).mean()
df['atr_pct'] = (df['atr'] / df['close']) * 100

# Generate signals (as in Pine Script)
df['buy_signal'] = (
    (df['macd_hist'] > 0) & 
    (df['macd_hist'] > df['macd_hist'].shift(1)) &
    (df['momentum'] > -1.0) &
    (df['volume_ratio'] > 1.0) &
    (df['rsi'] > 25) & (df['rsi'] < 75) &
    (df['atr_pct'] > 0.5)
)

df['sell_signal'] = (
    (df['macd_hist'] < 0) & 
    (df['macd_hist'] < df['macd_hist'].shift(1)) &
    (df['momentum'] < 1.0) &
    (df['volume_ratio'] > 1.0) &
    (df['rsi'] > 25) & (df['rsi'] < 75) &
    (df['atr_pct'] > 0.5)
)

buy_count = df['buy_signal'].sum()
sell_count = df['sell_signal'].sum()

print(f'Buy signals: {buy_count}')
print(f'Sell signals: {sell_count}')
print(f'Total signals: {buy_count + sell_count}')
print()

# Check signal frequency
print('Signal frequency:')
for i in range(len(df)):
    if df['buy_signal'].iloc[i] or df['sell_signal'].iloc[i]:
        print(f'  {df["datetime"].iloc[i]}: Buy={df["buy_signal"].iloc[i]}, Sell={df["sell_signal"].iloc[i]}')
        if i > 20:
            print('  ... (too many signals)')
            break

print()
print('❓ Problem: Too many signals!')
print('   This explains why TradingView has 190 trades vs 70 expected')

