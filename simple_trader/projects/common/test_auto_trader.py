#!/usr/bin/env python3
"""
Otomatik Trading Test Script
Sandbox modunda test
"""

import json
import time
from datetime import datetime

def test_auto_trader():
    """Otomatik trading sistemini test et"""
    print("🚀 OTOMATİK TRADİNG SİSTEMİ TEST")
    print("=" * 60)
    
    # Config kontrolü
    try:
        with open('auto_config.json', 'r') as f:
            config = json.load(f)
        print("✅ Config dosyası yüklendi")
    except Exception as e:
        print(f"❌ Config hatası: {e}")
        return
    
    # Sandbox modu kontrolü
    if config.get('sandbox', True):
        print("🔒 SANDBOX MODU AKTİF - Gerçek işlem yapılmayacak")
    else:
        print("⚠️ CANLI MODU AKTİF - Gerçek işlem yapılacak!")
    
    # Parametreler
    print(f"\n📊 TRADİNG PARAMETRELERİ:")
    print(f"   • Symbol: {config['symbol']}")
    print(f"   • Pozisyon Büyüklüğü: ${config['position_size']}")
    print(f"   • Leverage: {config['leverage']}x")
    print(f"   • Stop Loss: {config['sl']*100:.1f}%")
    print(f"   • Take Profit: {config['tp']*100:.1f}%")
    print(f"   • Kontrol Aralığı: {config['interval']} saniye")
    
    # API anahtarı kontrolü
    if config['api_key'] and config['api_key'] != "your_binance_api_key":
        print("✅ API anahtarı ayarlanmış")
    else:
        print("❌ API anahtarı ayarlanmamış")
        print("   auto_config.json dosyasını düzenleyin")
        return
    
    print(f"\n🎯 SİSTEM HAZIR!")
    print("=" * 60)
    print("Otomatik trading sistemini başlatmak için:")
    print("python3 auto_trader.py")
    print("\n⚠️ DİKKAT: İlk çalıştırmada sandbox modunda test edin!")

if __name__ == "__main__":
    test_auto_trader()
