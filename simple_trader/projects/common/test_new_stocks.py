#!/usr/bin/env python3
"""
Yeni BIST Hisseleri Test Scripti
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bist_signal_generator import BISTSignalGenerator

def test_new_stocks():
    """Yeni eklenen hisseleri test et"""
    generator = BISTSignalGenerator()
    
    print("🔍 Yeni eklenen hisseler:")
    print("=" * 40)
    
    # HALKB test
    print("📊 HALKB (Halkbank):")
    halkb_data = generator.generate_signals('HALKB.IS')
    if halkb_data:
        print(f"   Fiyat: ₺{halkb_data['price']:.2f}")
        print(f"   Trailing Stop: ₺{halkb_data['trailing_stop']:.2f}")
        print(f"   EMA(1): ₺{halkb_data['ema1']:.2f}")
        print(f"   ATR: ₺{halkb_data['atr']:.2f}")
        print(f"   Buy Signal: {halkb_data['buy_signal']}")
        print(f"   Sell Signal: {halkb_data['sell_signal']}")
    else:
        print("   ❌ Veri alınamadı")
    
    print()
    
    # YKBNK test
    print("📊 YKBNK (Yapı Kredi):")
    ykbnk_data = generator.generate_signals('YKBNK.IS')
    if ykbnk_data:
        print(f"   Fiyat: ₺{ykbnk_data['price']:.2f}")
        print(f"   Trailing Stop: ₺{ykbnk_data['trailing_stop']:.2f}")
        print(f"   EMA(1): ₺{ykbnk_data['ema1']:.2f}")
        print(f"   ATR: ₺{ykbnk_data['atr']:.2f}")
        print(f"   Buy Signal: {ykbnk_data['buy_signal']}")
        print(f"   Sell Signal: {ykbnk_data['sell_signal']}")
    else:
        print("   ❌ Veri alınamadı")
    
    print()
    print(f"📊 Toplam hisse sayısı: {len(generator.symbols)}")

if __name__ == "__main__":
    test_new_stocks()
