#!/usr/bin/env python3
"""
BIST Signal Generator Test Script
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bist_signal_generator import BISTSignalGenerator

def test_single_symbol():
    """Tek hisse test et"""
    generator = BISTSignalGenerator()
    
    # Test için tek hisse
    test_symbol = "THYAO.IS"
    print(f"🔍 {test_symbol} test ediliyor...")
    
    signal_data = generator.generate_signals(test_symbol)
    if signal_data:
        print(f"✅ Sinyal verisi alındı:")
        print(f"   Fiyat: ₺{signal_data['price']:.2f}")
        print(f"   Trailing Stop: ₺{signal_data['trailing_stop']:.2f}")
        print(f"   EMA(1): ₺{signal_data['ema1']:.2f}")
        print(f"   ATR: ₺{signal_data['atr']:.2f}")
        print(f"   Buy Signal: {signal_data['buy_signal']}")
        print(f"   Sell Signal: {signal_data['sell_signal']}")
    else:
        print("❌ Sinyal verisi alınamadı")

def test_telegram():
    """Telegram test et"""
    generator = BISTSignalGenerator()
    
    test_msg = """
🧪 <b>BIST TEST MESAJI</b>

📊 <b>Test:</b> Telegram bağlantısı
⏰ <b>Zaman:</b> Test zamanı

✅ <b>Başarılı!</b>
"""
    
    generator.send_telegram_message(test_msg)
    print("📱 Test mesajı gönderildi")

if __name__ == "__main__":
    print("🚀 BIST Signal Generator Test")
    print("1. Tek hisse testi")
    test_single_symbol()
    print("\n2. Telegram testi")
    test_telegram()
    print("\n✅ Test tamamlandı")
