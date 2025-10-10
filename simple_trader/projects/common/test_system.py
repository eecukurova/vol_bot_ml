#!/usr/bin/env python3
"""
Sistem Test Scripti
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

def test_data_fetch():
    """Veri çekme testi"""
    print("🔍 Veri çekme testi...")
    
    exchange = ccxt.binance()
    symbol = 'EIGEN/USDT'
    timeframe = '1h'
    limit = 50
    
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        print(f"✅ {len(ohlcv)} bar verisi çekildi")
        
        # DataFrame oluştur
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        
        print(f"📊 Son fiyat: ${df['close'].iloc[-1]:.4f}")
        print(f"⏰ Son zaman: {df.index[-1]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Veri çekme hatası: {e}")
        return False

def test_telegram():
    """Telegram testi"""
    print("📱 Telegram testi...")
    
    import requests
    
    bot_token = '7956697051:AAErScGMFGVxOyt3dGiw0jrFoakBELRdtm4'
    chat_id = '-1002699769366'
    base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    message = f"""
🔍 <b>SİSTEM TEST</b>

⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S UTC')}
📊 <b>Durum:</b> Sistem test ediliyor
✅ <b>Veri:</b> {'OK' if test_data_fetch() else 'HATA'}

🚀 <b>Bot aktif!</b>
"""
    
    try:
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(base_url, data=data, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram mesajı gönderildi")
            return True
        else:
            print(f"❌ Telegram hatası: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram gönderme hatası: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Sistem Test Başlatılıyor...")
    
    # Veri testi
    data_ok = test_data_fetch()
    
    # Telegram testi
    telegram_ok = test_telegram()
    
    print(f"\n📊 Test Sonuçları:")
    print(f"📈 Veri Çekme: {'✅ OK' if data_ok else '❌ HATA'}")
    print(f"📱 Telegram: {'✅ OK' if telegram_ok else '❌ HATA'}")
    
    if data_ok and telegram_ok:
        print("🎉 Sistem hazır!")
    else:
        print("⚠️ Sistem sorunları var!")
