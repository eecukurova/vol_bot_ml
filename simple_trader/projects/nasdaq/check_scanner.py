#!/usr/bin/env python3
"""
NASDAQ Dynamic Scanner Durum Kontrolü
"""

import sys
sys.path.append('/Users/ahmet/ATR/simple_trader/projects/nasdaq')
from nasdaq_dynamic_scanner import NASDAQDynamicScanner
import json

def check_nasdaq_scanner():
    """NASDAQ scanner durumunu kontrol et"""
    
    # Scanner oluştur
    scanner = NASDAQDynamicScanner()
    
    print('🔍 NASDAQ DYNAMIC SCANNER - MEVCUT DURUM')
    print('=' * 60)
    
    print(f'📊 Max Price: ${scanner.max_price}')
    print(f'📈 Min Volume: {scanner.min_volume:,}')
    print(f'💰 Min Market Cap: ${scanner.min_market_cap:,}')
    print(f'💰 Max Market Cap: ${scanner.max_market_cap:,}')
    
    print(f'\n📋 Watchlist Durumu:')
    print(f'  Enabled: {scanner.watchlist_cfg.get("enabled", False)}')
    if scanner.watchlist_cfg.get('enabled'):
        print(f'  File: {scanner.watchlist_cfg.get("file", "N/A")}')
        print(f'  Max Price: ${scanner.watchlist_cfg.get("max_price", 0)}')
        print(f'  Min Volume: {scanner.watchlist_cfg.get("min_volume", 0):,}')
    
    # Watchlist hisselerini göster
    if hasattr(scanner, 'watchlist_stocks'):
        print(f'\n📈 Watchlist Hisse Sayısı: {len(scanner.watchlist_stocks)}')
        print(f'📋 Watchlist Hisse Listesi: {scanner.watchlist_stocks}')
    else:
        print('\n❌ Watchlist stocks yüklenmemiş')
    
    # Scanner'ın nasıl çalıştığını açıkla
    print(f'\n🔧 Scanner Çalışma Mantığı:')
    print(f'  1. ${scanner.max_price} altındaki hisseleri tarar')
    print(f'  2. Min {scanner.min_volume:,} hacim filtresi uygular')
    print(f'  3. Market cap filtresi: ${scanner.min_market_cap:,} - ${scanner.max_market_cap:,}')
    print(f'  4. Watchlist aktifse ek hisseleri de tarar')
    
    print(f'\n❓ IPO Takibi Sorunu:')
    print(f'  - Scanner mevcut hisseleri tarar')
    print(f'  - Yeni IPO\'lar otomatik eklenmez')
    print(f'  - Manuel olarak watchlist\'e eklenmeli')

if __name__ == "__main__":
    check_nasdaq_scanner()
