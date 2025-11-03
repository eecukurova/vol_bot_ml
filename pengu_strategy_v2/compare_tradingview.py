#!/usr/bin/env python3
"""
Compare TradingView CSV results with actual data
"""

import pandas as pd
import ccxt
import numpy as np

print('🔍 TRADINGVIEW vs GERÇEK VERİ KARŞILAŞTIRMASI')
print('='*80)

# Read TradingView CSV
df = pd.read_csv('/Users/ahmet/Downloads/PENGU_CCI_BINANCE_PENGUUSDT.P_2025-10-26.csv')

entries = df[df['Tip'] == 'Giriş uzun']
exits = df[df['Tip'] == 'Uzunu kapat']

print('📊 TRADINGVIEW CSV:')
print(f'   Total Return: {exits["Net K&Z %"].sum():.2f}%')
print(f'   Win Rate: {(exits["Net K&Z %"] > 0).sum() / len(exits) * 100:.1f}%')
print(f'   Trades: {len(exits)}')
print()

# Show first trade details
print('İlk İşlem Detayları:')
print(f'  Entry: {entries.iloc[0]["Tarih/Saat"]} @ ${entries.iloc[0]["Fiyat USDT"]:.6f}')
print(f'  Exit: {exits.iloc[0]["Tarih/Saat"]} @ ${exits.iloc[0]["Fiyat USDT"]:.6f}')
print(f'  Return: {exits.iloc[0]["Net K&Z %"]:.2f}%')
print()

# Check actual data
print('📥 Gerçek veriyi çekiyorum...')
exchange = ccxt.binance()
ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=3000)
real_df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
real_df['datetime'] = pd.to_datetime(real_df['timestamp'], unit='ms')

print(f'Gerçek veri: {real_df["datetime"].iloc[0]} to {real_df["datetime"].iloc[-1]}')
print()

# Check if we have the exact candle times
entry_time = pd.to_datetime(entries.iloc[0]['Tarih/Saat'])
exit_time = pd.to_datetime(exits.iloc[0]['Tarih/Saat'])

# Find matching candles
entry_candle = real_df[real_df['datetime'] == entry_time]
exit_candle = real_df[real_df['datetime'] == exit_time]

print(f'Entry candle var mı? {len(entry_candle) > 0}')
print(f'Exit candle var mı? {len(exit_candle) > 0}')
print()

if len(entry_candle) > 0 and len(exit_candle) > 0:
    real_entry_price = entry_candle.iloc[0]['close']
    real_exit_price = exit_candle.iloc[0]['close']
    real_return = ((real_exit_price - real_entry_price) / real_entry_price) * 100
    
    print(f'Gerçek Entry: ${real_entry_price:.6f}')
    print(f'Gerçek Exit: ${real_exit_price:.6f}')
    print(f'Gerçek Return: {real_return:.2f}%')
    print(f'TradingView Return: {exits.iloc[0]["Net K&Z %"]:.2f}%')
    
    if abs(real_return - exits.iloc[0]["Net K&Z %"]) > 1:
        print()
        print('⚠️ FARK VAR! TradingView farklı bir hesaplama kullanıyor olabilir.')
        print('   Olası nedenler:')
        print('   1. Komisyon (0.1%)')
        print('   2. Slippage')
        print('   3. Pyramiding açık')
        print('   4. Farklı entry/exit fiyatı')

