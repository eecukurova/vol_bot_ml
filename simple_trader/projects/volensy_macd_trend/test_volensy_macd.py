#!/usr/bin/env python3
"""
Volensy MACD Test Script
"""

import ccxt
import pandas as pd
import numpy as np
import sys
import os

# Add common path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../common')))

def test_volensy_macd():
    """Volensy MACD hesaplama testi"""
    try:
        print("🚀 Volensy MACD Test Başlatılıyor...")
        
        # Exchange bağlantısı
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # Test verisi al
        symbol = "SUI/USDT"
        timeframe = "1h"
        limit = 100
        
        print(f"📊 {symbol} verisi alınıyor...")
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        if not ohlcv:
            print("❌ Veri alınamadı")
            return False
        
        # DataFrame oluştur
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        print(f"✅ {len(df)} bar verisi alındı")
        
        # Volensy MACD parametreleri
        ema_trend_period = 55
        macd_fast = 12
        macd_slow = 26
        macd_signal = 9
        rsi_period = 14
        
        # Hesaplamalar
        close = df['close']
        
        # EMA Trend
        ema_trend = close.ewm(span=ema_trend_period).mean()
        
        # MACD
        ema_fast = close.ewm(span=macd_fast).mean()
        ema_slow = close.ewm(span=macd_slow).mean()
        macd = ema_fast - ema_slow
        macd_signal_line = macd.ewm(span=macd_signal).mean()
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Son değerler
        last_close = close.iloc[-1]
        last_ema_trend = ema_trend.iloc[-1]
        last_macd = macd.iloc[-1]
        last_macd_signal = macd_signal_line.iloc[-1]
        last_rsi = rsi.iloc[-1]
        
        print(f"\n📊 Son Değerler:")
        print(f"   Close: ${last_close:.4f}")
        print(f"   EMA Trend: ${last_ema_trend:.4f}")
        print(f"   MACD: {last_macd:.6f}")
        print(f"   MACD Signal: {last_macd_signal:.6f}")
        print(f"   RSI: {last_rsi:.1f}")
        
        # Koşulları kontrol et
        is_bull_trend = last_close > last_ema_trend
        is_bear_trend = last_close < last_ema_trend
        
        is_bull_momentum = last_rsi > 50
        is_bear_momentum = last_rsi < 50
        
        is_bull_power = last_macd > last_macd_signal
        is_bear_power = last_macd < last_macd_signal
        
        not_overbought = last_rsi < 70
        not_oversold = last_rsi > 30
        
        # Skor hesapla
        bull_score = (1 if is_bull_trend else 0) + (1 if is_bull_momentum else 0) + (1 if is_bull_power else 0)
        bear_score = (1 if is_bear_trend else 0) + (1 if is_bear_momentum else 0) + (1 if is_bear_power else 0)
        
        print(f"\n🎯 Koşullar:")
        print(f"   Trend: {'BULL' if is_bull_trend else 'BEAR'}")
        print(f"   Momentum: {'BULL' if is_bull_momentum else 'BEAR'}")
        print(f"   Power: {'BULL' if is_bull_power else 'BEAR'}")
        print(f"   RSI OK: {not_overbought and not_oversold}")
        
        print(f"\n📊 Skorlar:")
        print(f"   Bull Score: {bull_score}/3")
        print(f"   Bear Score: {bear_score}/3")
        
        # Sinyaller
        raw_buy = (bull_score == 3) and not_overbought
        raw_sell = (bear_score == 3) and not_oversold
        
        signal = 'HOLD'
        if raw_buy:
            signal = 'BUY'
        elif raw_sell:
            signal = 'SELL'
        
        print(f"\n🚨 Sinyal: {signal}")
        
        if signal != 'HOLD':
            signal_strength = abs(last_close - last_ema_trend) / last_close * 100
            print(f"💪 Sinyal Gücü: {signal_strength:.2f}%")
        
        print("\n✅ Volensy MACD testi başarılı!")
        return True
        
    except Exception as e:
        print(f"❌ Test hatası: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    test_volensy_macd()
