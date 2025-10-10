#!/usr/bin/env python3
"""
API Anahtarı Test Script
Binance API izinlerini kontrol et
"""

import ccxt
import json

def test_api_permissions():
    """API izinlerini test et"""
    print("🔑 BİNANCE API İZİN TESTİ")
    print("=" * 60)
    
    # Config yükle
    try:
        with open('auto_config.json', 'r') as f:
            config = json.load(f)
        print("✅ Config dosyası yüklendi")
    except Exception as e:
        print(f"❌ Config hatası: {e}")
        return
    
    # Exchange oluştur
    try:
        exchange = ccxt.binance({
            'apiKey': config['api_key'],
            'secret': config['secret'],
            'sandbox': False,
            'options': {
                'defaultType': 'future'  # Futures trading için
            }
        })
        print("✅ Exchange oluşturuldu (Futures mode)")
    except Exception as e:
        print(f"❌ Exchange hatası: {e}")
        return
    
    # API anahtarı kontrolü
    print(f"\n🔍 API ANAHTARI KONTROLÜ:")
    print(f"   • API Key: {config['api_key'][:10]}...")
    print(f"   • Secret: {config['secret'][:10]}...")
    
    # Spot API testi
    try:
        print(f"\n📊 SPOT API TESTİ:")
        spot_exchange = ccxt.binance({
            'apiKey': config['api_key'],
            'secret': config['secret'],
            'sandbox': False
        })
        
        # Spot balance
        balance = spot_exchange.fetch_balance()
        print(f"✅ Spot API çalışıyor")
        print(f"💰 USDT Bakiyesi: {balance.get('USDT', {}).get('free', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Spot API hatası: {e}")
    
    # Futures API testi
    try:
        print(f"\n📈 FUTURES API TESTİ:")
        
        # Futures balance
        balance = exchange.fetch_balance()
        print(f"✅ Futures API çalışıyor")
        print(f"💰 USDT Bakiyesi: {balance.get('USDT', {}).get('free', 'N/A')}")
        
        # Futures pozisyonları
        positions = exchange.fetch_positions()
        print(f"📊 Aktif pozisyonlar: {len([p for p in positions if p['contracts'] > 0])}")
        
    except Exception as e:
        print(f"❌ Futures API hatası: {e}")
        print(f"   Hata detayı: {str(e)}")
    
    # API izinleri kontrolü
    print(f"\n🔐 GEREKLİ API İZİNLERİ:")
    print("   ✅ Spot Trading")
    print("   ✅ Futures Trading")
    print("   ✅ Read Info")
    print("   ✅ Enable Withdrawals (opsiyonel)")
    
    print(f"\n🌐 IP KISITLAMASI:")
    print("   • Binance'de API anahtarı ayarlarını kontrol edin")
    print("   • IP kısıtlaması varsa kaldırın veya IP'nizi ekleyin")
    print("   • Veya 'Restrict access to trusted IPs only' seçeneğini kapatın")

def main():
    """Ana fonksiyon"""
    test_api_permissions()
    
    print(f"\n💡 ÇÖZÜM ÖNERİLERİ:")
    print("=" * 50)
    print("1. Binance hesabınıza giriş yapın")
    print("2. API Management > API Keys")
    print("3. Mevcut API anahtarını düzenleyin")
    print("4. 'Restrict access to trusted IPs only' seçeneğini KAPATIN")
    print("5. 'Enable Futures' seçeneğini AÇIN")
    print("6. 'Enable Spot & Margin Trading' seçeneğini AÇIN")
    print("7. Değişiklikleri kaydedin")
    print("8. Testi tekrar çalıştırın")

if __name__ == "__main__":
    main()
