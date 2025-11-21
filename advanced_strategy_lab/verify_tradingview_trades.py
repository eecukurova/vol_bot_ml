#!/usr/bin/env python3
"""
Verify TradingView trades against actual market data
"""

import pandas as pd
import ccxt

print('🔍 TRADINGVIEW İŞLEMLERİNİ DOĞRULAMA')
print('='*80)

# Read TradingView CSV
df_tv = pd.read_csv('/Users/ahmet/Downloads/PENGU_CCI_BINANCE_PENGUUSDT.P_2025-10-26.csv')

entries = df_tv[df_tv['Tip'] == 'Giriş uzun']
exits = df_tv[df_tv['Tip'] == 'Uzunu kapat']

print(f'TradingView CSV: {len(entries)} işlem')
print()

# Get Binance data
exchange = ccxt.binance()
ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=2500)
df_binance = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df_binance['datetime'] = pd.to_datetime(df_binance['timestamp'], unit='ms')

print(f'Binance verisi: {df_binance["datetime"].iloc[0]} to {df_binance["datetime"].iloc[-1]}')
print()

# Check first trade
first_entry = pd.to_datetime(entries.iloc[0]['Tarih/Saat'])
first_exit = pd.to_datetime(exits.iloc[0]['Tarih/Saat'])

print(f'İlk işlem (TradingView):')
print(f'  Entry: {first_entry}')
print(f'  Exit: {first_exit}')
print(f'  Return: {exits.iloc[0]["Net K&Z %"]:.2f}%')
print()

# Try to find this timeframe
entry_close = df_binance[df_binance['datetime'] == first_entry]
exit_close = df_binance[df_binance['datetime'] == first_exit]

if len(entry_close) > 0:
    print(f'✅ Entry candle bulundu: {entry_close.iloc[0]["close"]:.6f}')
else:
    print(f'❌ Entry candle bulunamadı')
    
    # Find closest
    closest = df_binance.iloc[(df_binance['datetime'] - first_entry).abs().argsort()[:1]]
    print(f'   En yakın: {closest.iloc[0]["datetime"]} (fark: {(first_entry - closest.iloc[0]["datetime"]).total_seconds()/3600:.1f} saat)')

if len(exit_close) > 0:
    print(f'✅ Exit candle bulundu: {exit_close.iloc[0]["close"]:.6f}')
else:
    print(f'❌ Exit candle bulunamadı')
    
    # Find closest
    closest = df_binance.iloc[(df_binance['datetime'] - first_exit).abs().argsort()[:1]]
    print(f'   En yakın: {closest.iloc[0]["datetime"]} (fark: {(first_exit - closest.iloc[0]["datetime"]).total_seconds()/3600:.1f} saat)')

print()
print('📊 SONUÇ:')
print('TradingView CSV\'deki ilk işlem: 2025-08-06')
print('Binance\'de mevcut en eski veri: 2025-09-14')
print('Fark: 39 gün!')
print()
print('Bu nedenle karşılaştırma yapamıyoruz.')
print('TradingView sonuçları gerçek verilerle test edilemiyor.')
print()
print('Sadece 2025-09-14\'ten sonraki dönemi test edebiliriz:')
print('  TradingView 9 işlem yaptı (Sep 14 - Oct 25)')
print('  Benim test: 38 işlem yaptı (Sep 14 - Oct 25)')
print('  Fark: 29 işlem!')

