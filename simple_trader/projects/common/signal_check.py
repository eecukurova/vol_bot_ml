#!/usr/bin/env python3
"""
Sinyal Yapısı Kontrol Script
Gerçek zamanlı sinyal üretimini test et
"""

import ccxt
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

def get_latest_data(symbol, timeframe='1h', limit=50):
    """Son veriyi al"""
    exchange = ccxt.binance()
    
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    
    return df

def calculate_atr(df, period=14):
    """ATR hesapla"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = np.maximum(high_low, np.maximum(high_close, low_close))
    return tr.rolling(period).mean()

def calculate_supertrend(df, period=14, multiplier=1.5):
    """SuperTrend hesapla"""
    atr_val = calculate_atr(df, period)
    hl2 = (df['high'] + df['low']) / 2
    upper = hl2 + (atr_val * multiplier)
    lower = hl2 - (atr_val * multiplier)
    
    st = pd.Series(index=df.index, dtype=float)
    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = lower.iloc[i]
        else:
            if df['close'].iloc[i] > st.iloc[i-1]:
                st.iloc[i] = max(lower.iloc[i], st.iloc[i-1])
            else:
                st.iloc[i] = min(upper.iloc[i], st.iloc[i-1])
    return st

def generate_signal(df):
    """Sinyal üret"""
    st = calculate_supertrend(df)
    ema1 = df['close'].ewm(span=1).mean()
    
    # Son 2 bar'ı al
    close = df['close'].iloc[-1]
    st_val = st.iloc[-1]
    ema1_val = ema1.iloc[-1]
    prev_ema1 = ema1.iloc[-2]
    prev_st = st.iloc[-2]
    
    signal = 'HOLD'
    signal_strength = 0
    
    if close > st_val and ema1_val > st_val and prev_ema1 <= prev_st:
        signal = 'BUY'
        signal_strength = abs(close - st_val) / close * 100
    elif close < st_val and ema1_val < st_val and prev_ema1 >= prev_st:
        signal = 'SELL'
        signal_strength = abs(close - st_val) / close * 100
    
    return {
        'signal': signal,
        'strength': signal_strength,
        'price': close,
        'supertrend': st_val,
        'ema1': ema1_val,
        'timestamp': df.index[-1]
    }

def check_signal_quality(symbol, timeframe='1h'):
    """Sinyal kalitesini kontrol et"""
    print(f"🔍 {symbol} - {timeframe} Sinyal Kalitesi Kontrolü")
    print("=" * 60)
    
    # Son veriyi al
    df = get_latest_data(symbol, timeframe)
    print(f"📊 Son {len(df)} bar veri çekildi")
    print(f"📅 Son bar: {df.index[-1]}")
    print(f"💰 Son fiyat: ${df['close'].iloc[-1]:.4f}")
    
    # Sinyal üret
    signal_data = generate_signal(df)
    
    print(f"\n🎯 SİNYAL ANALİZİ:")
    print("-" * 40)
    print(f"📈 Sinyal: {signal_data['signal']}")
    print(f"💪 Güç: {signal_data['strength']:.2f}%")
    print(f"💰 Fiyat: ${signal_data['price']:.4f}")
    print(f"📊 SuperTrend: ${signal_data['supertrend']:.4f}")
    print(f"📈 EMA(1): ${signal_data['ema1']:.4f}")
    print(f"⏰ Zaman: {signal_data['timestamp']}")
    
    # Sinyal detayları
    if signal_data['signal'] == 'BUY':
        print(f"\n✅ BUY SİNYALİ:")
        print(f"   • Close > SuperTrend: ${signal_data['price']:.4f} > ${signal_data['supertrend']:.4f}")
        print(f"   • EMA(1) > SuperTrend: ${signal_data['ema1']:.4f} > ${signal_data['supertrend']:.4f}")
        print(f"   • EMA(1) crossover: {signal_data['ema1']:.4f} > {signal_data['supertrend']:.4f}")
        
    elif signal_data['signal'] == 'SELL':
        print(f"\n❌ SELL SİNYALİ:")
        print(f"   • Close < SuperTrend: ${signal_data['price']:.4f} < ${signal_data['supertrend']:.4f}")
        print(f"   • EMA(1) < SuperTrend: ${signal_data['ema1']:.4f} < ${signal_data['supertrend']:.4f}")
        print(f"   • EMA(1) crossunder: {signal_data['ema1']:.4f} < {signal_data['supertrend']:.4f}")
        
    else:
        print(f"\n⏸️ HOLD SİNYALİ:")
        print(f"   • Trend belirsiz veya crossover yok")
    
    return signal_data

def test_multiple_coins():
    """Birden fazla coin için sinyal testi"""
    coins = ['SOL/USDT', 'EIGEN/USDT', 'BTC/USDT']
    timeframe = '1h'
    
    print(f"🚀 ÇOKLU COİN SİNYAL TESTİ")
    print("=" * 80)
    
    results = {}
    
    for coin in coins:
        try:
            signal_data = check_signal_quality(coin, timeframe)
            results[coin] = signal_data
            print("\n" + "="*60 + "\n")
        except Exception as e:
            print(f"❌ {coin} hatası: {e}")
            results[coin] = None
    
    # Özet
    print(f"📊 SİNYAL ÖZETİ:")
    print("-" * 50)
    print(f"{'Coin':<12} {'Sinyal':<8} {'Güç':<8} {'Fiyat':<12}")
    print("-" * 50)
    
    for coin, data in results.items():
        if data:
            print(f"{coin:<12} {data['signal']:<8} {data['strength']:>6.2f}% ${data['price']:>10.4f}")
        else:
            print(f"{coin:<12} {'ERROR':<8} {'N/A':<8} {'N/A':<12}")
    
    return results

def main():
    """Ana fonksiyon"""
    print("🎯 SİNYAL YAPISI KONTROL SİSTEMİ")
    print("=" * 80)
    
    # Tek coin test
    print("1️⃣ TEK COİN TEST:")
    sol_signal = check_signal_quality('SOL/USDT', '1h')
    
    print("\n" + "="*80 + "\n")
    
    # Çoklu coin test
    print("2️⃣ ÇOKLU COİN TEST:")
    multi_results = test_multiple_coins()
    
    print("\n🎯 SİNYAL YAPISI HAZIR MI?")
    print("=" * 50)
    
    ready_count = sum(1 for data in multi_results.values() if data and data['signal'] != 'ERROR')
    total_count = len(multi_results)
    
    if ready_count == total_count:
        print("✅ EVET! Tüm coinler için sinyal yapısı hazır")
        print("🚀 Otomatik trading sistemine geçebiliriz")
    else:
        print("⚠️ HAYIR! Bazı coinlerde sorun var")
        print("🔧 Önce sorunları çözelim")
    
    print(f"\n📊 Hazırlık Durumu: {ready_count}/{total_count}")

if __name__ == "__main__":
    main()
