#!/usr/bin/env python3
"""
Canlı Mod Test Script
Gerçek API ile bağlantı testi
"""

import ccxt
import json
from datetime import datetime

def test_live_connection():
    """Canlı bağlantıyı test et"""
    print("🚀 CANLI MOD BAĞLANTI TESTİ")
    print("=" * 60)
    
    # Config yükle
    try:
        with open('auto_config.json', 'r') as f:
            config = json.load(f)
        print("✅ Config dosyası yüklendi")
    except Exception as e:
        print(f"❌ Config hatası: {e}")
        return False
    
    # Exchange oluştur
    try:
        exchange = ccxt.binance({
            'apiKey': config['api_key'],
            'secret': config['secret'],
            'sandbox': config.get('sandbox', False)
        })
        print("✅ Exchange oluşturuldu")
    except Exception as e:
        print(f"❌ Exchange hatası: {e}")
        return False
    
    # API bağlantısını test et
    try:
        balance = exchange.fetch_balance()
        print("✅ API bağlantısı başarılı")
        print(f"💰 USDT Bakiyesi: {balance.get('USDT', {}).get('free', 'N/A')}")
    except Exception as e:
        print(f"❌ API bağlantı hatası: {e}")
        return False
    
    # Leverage ayarla
    try:
        symbol = config['symbol']
        leverage = config['leverage']
        exchange.set_leverage(leverage, symbol)
        print(f"✅ {symbol} için {leverage}x leverage ayarlandı")
    except Exception as e:
        print(f"⚠️ Leverage ayarlama hatası: {e}")
    
    # Son fiyatı al
    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        print(f"✅ {symbol} son fiyat: ${price:.4f}")
    except Exception as e:
        print(f"❌ Fiyat alma hatası: {e}")
        return False
    
    # Parametreler
    print(f"\n📊 TRADİNG PARAMETRELERİ:")
    print(f"   • Symbol: {config['symbol']}")
    print(f"   • Pozisyon Büyüklüğü: ${config['position_size']}")
    print(f"   • Leverage: {config['leverage']}x")
    print(f"   • Stop Loss: {config['sl']*100:.1f}%")
    print(f"   • Take Profit: {config['tp']*100:.1f}%")
    print(f"   • Kontrol Aralığı: {config['interval']} saniye")
    
    # Pozisyon büyüklüğü hesapla
    position_value = config['position_size'] * config['leverage']
    quantity = position_value / price
    
    print(f"\n💰 POZİSYON HESAPLAMASI:")
    print(f"   • Pozisyon Değeri: ${position_value}")
    print(f"   • Miktar: {quantity:.6f} {symbol.split('/')[0]}")
    print(f"   • Margin Gereksinimi: ${config['position_size']}")
    
    print(f"\n🎯 SİSTEM HAZIR!")
    print("=" * 60)
    print("✅ Tüm testler başarılı")
    print("🚀 Otomatik trading sistemini başlatabilirsiniz:")
    print("python3 auto_trader.py")
    
    return True

def test_sol_connection():
    """SOL için bağlantı testi"""
    print("\n🚀 SOL/USDT BAĞLANTI TESTİ")
    print("=" * 60)
    
    # SOL config yükle
    try:
        with open('sol_config.json', 'r') as f:
            config = json.load(f)
        print("✅ SOL config dosyası yüklendi")
    except Exception as e:
        print(f"❌ SOL config hatası: {e}")
        return False
    
    # Exchange oluştur
    try:
        exchange = ccxt.binance({
            'apiKey': config['api_key'],
            'secret': config['secret'],
            'sandbox': config.get('sandbox', False)
        })
        print("✅ SOL Exchange oluşturuldu")
    except Exception as e:
        print(f"❌ SOL Exchange hatası: {e}")
        return False
    
    # SOL fiyatı
    try:
        symbol = config['symbol']
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        print(f"✅ {symbol} son fiyat: ${price:.4f}")
        
        # Pozisyon hesaplama
        position_value = config['position_size'] * config['leverage']
        quantity = position_value / price
        
        print(f"💰 SOL Pozisyon Değeri: ${position_value}")
        print(f"💰 SOL Miktar: {quantity:.6f} SOL")
        
    except Exception as e:
        print(f"❌ SOL fiyat hatası: {e}")
        return False
    
    return True

def main():
    """Ana fonksiyon"""
    print("🎯 CANLI MOD SİSTEM TESTİ")
    print("=" * 80)
    
    # EIGEN test
    eigen_ok = test_live_connection()
    
    # SOL test
    sol_ok = test_sol_connection()
    
    print(f"\n🏆 TEST SONUÇLARI:")
    print("=" * 50)
    print(f"EIGEN/USDT: {'✅ BAŞARILI' if eigen_ok else '❌ BAŞARISIZ'}")
    print(f"SOL/USDT: {'✅ BAŞARILI' if sol_ok else '❌ BAŞARISIZ'}")
    
    if eigen_ok and sol_ok:
        print(f"\n🎯 TÜM SİSTEMLER HAZIR!")
        print("🚀 Otomatik trading başlatılabilir")
    else:
        print(f"\n⚠️ BAZI SİSTEMLERDE SORUN VAR")
        print("🔧 Önce sorunları çözün")

if __name__ == "__main__":
    main()
