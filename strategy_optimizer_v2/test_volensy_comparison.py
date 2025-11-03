#!/usr/bin/env python3
"""
Volensy vs RSI+Volume comparison for PENGU
"""

import ccxt
import pandas as pd
import numpy as np

def calculate_volensy(df, chg_pct, vol_mult, break_period):
    """Calculate Volensy signals"""
    df['pct_change'] = ((df['close'] / df['close'].shift(1)) - 1) * 100
    df['volume_ma'] = df['volume'].rolling(window=10).mean()
    df['vol_ratio'] = df['volume'] / df['volume_ma']
    df['highest'] = df['close'].shift(1).rolling(window=break_period).max()
    
    # Signals
    df['buy_signal'] = (
        (df['pct_change'] > chg_pct) &
        (df['vol_ratio'] > vol_mult) &
        (df['close'] > df['highest']) &
        (df['volume'] > 100000)
    )
    
    return df

def backtest_strategy(df, tp_pct=5.0, sl_pct=2.5):
    """Backtest with TP/SL"""
    df = df.copy()
    df['position'] = 0
    df['entry_price'] = 0.0
    df['tp_price'] = 0.0
    df['sl_price'] = 0.0
    
    initial_capital = 100000
    capital = initial_capital
    
    for i in range(len(df)):
        row = df.iloc[i]
        
        # Entry
        if row['buy_signal'] and df.loc[i-1 if i > 0 else 0, 'position'] == 0:
            df.loc[i, 'position'] = 1
            df.loc[i, 'entry_price'] = row['close']
            df.loc[i, 'tp_price'] = row['close'] * (1 + tp_pct/100)
            df.loc[i, 'sl_price'] = row['close'] * (1 - sl_pct/100)
        
        # Carry position
        elif i > 0 and df.loc[i-1, 'position'] == 1:
            entry = df.loc[i-1, 'entry_price']
            current_price = row['close']
            
            df.loc[i, 'position'] = 1
            df.loc[i, 'entry_price'] = entry
            df.loc[i, 'tp_price'] = df.loc[i-1, 'tp_price']
            df.loc[i, 'sl_price'] = df.loc[i-1, 'sl_price']
            
            # Check TP/SL
            if current_price >= df.loc[i-1, 'tp_price']:
                pnl_pct = ((current_price - entry) / entry) * 100
                capital = capital * (1 + pnl_pct/100)
                df.loc[i, 'position'] = 0
            elif current_price <= df.loc[i-1, 'sl_price']:
                pnl_pct = ((current_price - entry) / entry) * 100
                capital = capital * (1 + pnl_pct/100)
                df.loc[i, 'position'] = 0
    
    return df, capital

print("🎯 VOLENSY vs RSI STRATEGY COMPARISON")
print("="*80)

# Fetch data
exchange = ccxt.binance()
df = pd.DataFrame(exchange.fetch_ohlcv('PENGU/USDT', '1d', limit=500),
                  columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

# Test Volensy configurations
configs = [
    {'name': 'Volensy Original (TV)', 'chg': 2.0, 'vol': 1.5, 'break': 50},
    {'name': 'Volensy Aggressive', 'chg': 1.5, 'vol': 1.2, 'break': 50},
    {'name': 'Volensy Conservative', 'chg': 3.0, 'vol': 1.8, 'break': 100},
]

print("\n📊 VOLENSY STRATEGY RESULTS:")
print("-"*80)

best_volensy = None
best_return = -999

for config in configs:
    df_test = calculate_volensy(df.copy(), config['chg'], config['vol'], config['break'])
    df_backtest, final_capital = backtest_strategy(df_test)
    
    signals = df_test['buy_signal'].sum()
    trades = (df_backtest['position'].diff() == 1).sum()
    
    if trades > 0:
        return_pct = ((final_capital - 100000) / 100000) * 100
    else:
        return_pct = 0
    
    print(f"\n✅ {config['name']}:")
    print(f"   Signals: {signals}")
    print(f"   Trades: {trades}")
    print(f"   Return: {return_pct:.2f}%")
    
    if return_pct > best_return:
        best_return = return_pct
        best_volensy = config

# Compare with RSI+Volume
print("\n📊 RSI+Volume STRATEGY (for comparison):")
print("-"*80)

df['rsi'] = 100 - (100 / (1 + df['close'].diff().fillna(0).rolling(window=14).apply(lambda x: np.sum(x[x > 0]) / np.sum(-x[x < 0]) if np.sum(-x[x < 0]) > 0 else 50)))
df['volume_ma'] = df['volume'].rolling(20).mean()
df['vol_ratio'] = df['volume'] / df['volume_ma']
df['buy_signal'] = (df['rsi'] > 65) & (df['rsi'] < 85) & (df['vol_ratio'] > 1.5)

df_rsi, final_capital_rsi = backtest_strategy(df, tp_pct=5.0, sl_pct=2.5)
signals_rsi = df['buy_signal'].sum()
trades_rsi = (df_rsi['position'].diff() == 1).sum()

if trades_rsi > 0:
    return_rsi = ((final_capital_rsi - 100000) / 100000) * 100
else:
    return_rsi = 0

print(f"   Signals: {signals_rsi}")
print(f"   Trades: {trades_rsi}")
print(f"   Return: {return_rsi:.2f}%")

print("\n" + "="*80)
print("🏆 WINNER:")
print("="*80)

if best_return > return_rsi:
    print(f"\n🎯 VOLENSY WINS!")
    print(f"   Strategy: {best_volensy['name']}")
    print(f"   Return: +{best_return:.2f}% (vs RSI: +{return_rsi:.2f}%)")
    print(f"   Difference: {best_return - return_rsi:.2f}%")
else:
    print(f"\n🎯 RSI WINS!")
    print(f"   Return: +{return_rsi:.2f}% (vs Volensy: +{best_return:.2f}%)")
    print(f"   Difference: {return_rsi - best_return:.2f}%")

print("\n" + "="*80)

