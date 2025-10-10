#!/usr/bin/env python3
"""
BIST Sinyal Test Scripti
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bist_signal_generator import BISTSignalGenerator

def test_all_signals():
    """Tüm hisseler için sinyal test et"""
    generator = BISTSignalGenerator()
    
    print("🔍 Tüm hisseler için sinyal kontrolü:")
    print("=" * 50)
    
    signals_found = False
    
    for symbol in generator.symbols:
        signal_data = generator.generate_signals(symbol)
        if signal_data:
            symbol_name = symbol.replace('.IS', '')
            print(f"📊 {symbol_name}:")
            print(f"   Fiyat: ₺{signal_data['price']:.2f}")
            print(f"   Trailing Stop: ₺{signal_data['trailing_stop']:.2f}")
            print(f"   EMA(1): ₺{signal_data['ema1']:.2f}")
            print(f"   ATR: ₺{signal_data['atr']:.2f}")
            print(f"   Buy Signal: {signal_data['buy_signal']}")
            print(f"   Sell Signal: {signal_data['sell_signal']}")
            
            if signal_data['buy_signal'] or signal_data['sell_signal']:
                signals_found = True
                print(f"   🎯 SİNYAL BULUNDU!")
            
            print()
    
    if not signals_found:
        print("❌ Bugün için sinyal bulunamadı")
    else:
        print("✅ Sinyaller bulundu!")

if __name__ == "__main__":
    test_all_signals()
