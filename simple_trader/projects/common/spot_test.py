#!/usr/bin/env python3
"""
Spot Trading Test Script
Leverage olmadan spot trading testi
"""

import ccxt
import json

def test_spot_trading():
    """Spot trading testi"""
    print("💰 SPOT TRADİNG TESTİ")
    print("=" * 60)
    
    # Config yükle
    try:
        with open('auto_config.json', 'r') as f:
            config = json.load(f)
        print("✅ Config dosyası yüklendi")
    except Exception as e:
        print(f"❌ Config hatası: {e}")
        return False
    
    # Spot exchange oluştur
    try:
        exchange = ccxt.binance({
            'apiKey': config['api_key'],
            'secret': config['secret'],
            'sandbox': False
        })
        print("✅ Spot Exchange oluşturuldu")
    except Exception as e:
        print(f"❌ Spot Exchange hatası: {e}")
        return False
    
    # Spot balance testi
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        print(f"✅ Spot API çalışıyor")
        print(f"💰 USDT Bakiyesi: {usdt_balance}")
        
        if usdt_balance < 10:
            print("⚠️ USDT bakiyesi düşük (min $10 gerekli)")
        
    except Exception as e:
        print(f"❌ Spot balance hatası: {e}")
        return False
    
    # Fiyat testi
    try:
        symbol = config['symbol']
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        print(f"✅ {symbol} fiyat: ${price:.4f}")
        
        # Spot pozisyon hesaplama
        position_value = config['position_size']
        quantity = position_value / price
        
        print(f"\n💰 SPOT POZİSYON HESAPLAMASI:")
        print(f"   • Pozisyon Değeri: ${position_value}")
        print(f"   • Miktar: {quantity:.6f} {symbol.split('/')[0]}")
        print(f"   • Leverage: 1x (Spot)")
        
    except Exception as e:
        print(f"❌ Fiyat alma hatası: {e}")
        return False
    
    return True

def main():
    """Ana fonksiyon"""
    print("🎯 SPOT TRADİNG ALTERNATİFİ")
    print("=" * 80)
    
    success = test_spot_trading()
    
    if success:
        print(f"\n✅ SPOT TRADİNG HAZIR!")
        print("=" * 50)
        print("💰 Leverage olmadan spot trading yapabiliriz")
        print("📊 Risk daha düşük, kar daha az")
        print("🚀 Spot trading sistemini başlatmak için:")
        print("python3 spot_trader.py")
    else:
        print(f"\n❌ SPOT TRADİNG DE ÇALIŞMIYOR")
        print("🔧 API anahtarı ayarlarını kontrol edin")

if __name__ == "__main__":
    main()
