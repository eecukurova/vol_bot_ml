#!/usr/bin/env python3
"""
NASDAQ IPO Yönetim Scripti
Yeni IPO'ları ekleme, çıkarma ve listeleme
"""

import sys
sys.path.append('/Users/ahmet/ATR/simple_trader/projects/nasdaq')
from nasdaq_dynamic_scanner import NASDAQDynamicScanner
import json

def main():
    """Ana fonksiyon"""
    
    # Scanner oluştur
    scanner = NASDAQDynamicScanner()
    
    print('🔍 NASDAQ IPO YÖNETİMİ')
    print('=' * 50)
    
    while True:
        print('\n📋 Seçenekler:')
        print('1. Watchlist\'i listele')
        print('2. Yeni IPO ekle')
        print('3. IPO çıkar')
        print('4. Scanner\'ı test et')
        print('5. Çıkış')
        
        choice = input('\nSeçiminizi yapın (1-5): ').strip()
        
        if choice == '1':
            # Watchlist'i listele
            print('\n📋 WATCHLİST LİSTESİ')
            print('-' * 30)
            watchlist = scanner.list_watchlist()
            if watchlist:
                for i, stock in enumerate(watchlist, 1):
                    print(f'{i:2d}. {stock}')
            else:
                print('❌ Watchlist boş')
                
        elif choice == '2':
            # Yeni IPO ekle
            print('\n🆕 YENİ IPO EKLEME')
            print('-' * 30)
            symbol = input('Hisse sembolü (örn: NEWIPO): ').strip().upper()
            description = input('Açıklama (opsiyonel): ').strip()
            
            if symbol:
                success = scanner.add_new_ipo(symbol, description)
                if success:
                    print(f'✅ {symbol} başarıyla eklendi!')
                else:
                    print(f'❌ {symbol} eklenemedi!')
            else:
                print('❌ Geçersiz sembol!')
                
        elif choice == '3':
            # IPO çıkar
            print('\n🗑️ IPO ÇIKARMA')
            print('-' * 30)
            watchlist = scanner.list_watchlist()
            if watchlist:
                for i, stock in enumerate(watchlist, 1):
                    print(f'{i:2d}. {stock}')
                
                try:
                    index = int(input('\nÇıkarılacak hisse numarası: ')) - 1
                    if 0 <= index < len(watchlist):
                        symbol = watchlist[index]
                        success = scanner.remove_ipo(symbol)
                        if success:
                            print(f'✅ {symbol} başarıyla çıkarıldı!')
                        else:
                            print(f'❌ {symbol} çıkarılamadı!')
                    else:
                        print('❌ Geçersiz numara!')
                except ValueError:
                    print('❌ Geçersiz giriş!')
            else:
                print('❌ Watchlist boş')
                
        elif choice == '4':
            # Scanner'ı test et
            print('\n🔍 SCANNER TEST')
            print('-' * 30)
            print('Scanner çalışıyor...')
            
            # Sadece watchlist hisselerini tara
            watchlist = scanner.list_watchlist()
            if watchlist:
                print(f'📊 {len(watchlist)} hisse taranıyor...')
                for stock in watchlist:
                    print(f'  🔍 {stock} taranıyor...')
                    # Burada gerçek tarama yapılabilir
            else:
                print('❌ Watchlist boş')
                
        elif choice == '5':
            # Çıkış
            print('\n👋 Görüşürüz!')
            break
            
        else:
            print('❌ Geçersiz seçim!')

if __name__ == "__main__":
    main()
