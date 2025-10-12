#!/usr/bin/env python3
"""
EIGEN EMA Sinyal Test Scripti
Pine Script stratejisine göre sinyal üretimini test eder
"""

import sys
import os

# Path'leri düzelt
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
common_dir = os.path.join(parent_dir, "common")

sys.path.append(common_dir)
sys.path.append(current_dir)

from eigen_ema_multi_trader import MultiTimeframeEMATrader
import logging

def test_signal_generation():
    """Sinyal üretimini test et"""
    
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    log = logging.getLogger(__name__)
    
    try:
        # Trader'ı başlat
        log.info("🚀 EIGEN EMA Trader test başlatılıyor...")
        trader = MultiTimeframeEMATrader()
        
        # Test için sandbox modunu etkinleştir
        trader.cfg['sandbox'] = True
        trader.cfg['logging']['detailed_timeframes'] = True
        
        log.info("📊 Test parametreleri:")
        log.info(f"• Symbol: {trader.symbol}")
        log.info(f"• Timeframes: {list(trader.timeframes.keys())}")
        log.info(f"• EMA Fast: {trader.ema_fast}, Slow: {trader.ema_slow}")
        log.info(f"• Heikin Ashi: {trader.heikin_ashi_enabled}")
        
        # Tüm timeframe'leri test et
        log.info("\n🔍 Timeframe'ler test ediliyor...")
        signals = trader.check_all_timeframes()
        
        if signals:
            log.info(f"\n📊 {len(signals)} timeframe'den sinyal alındı:")
            for tf_name, signal_info in signals.items():
                log.info(f"• {tf_name}: {signal_info['signal_type']} - {signal_info['signal']}")
                log.info(f"  Price: ${signal_info['price']:.4f}")
                log.info(f"  EMA: Fast=${signal_info['ema_fast']:.4f}, Slow=${signal_info['ema_slow']:.4f}")
                log.info(f"  RSI: {signal_info['rsi']:.1f}")
                log.info(f"  Volume: {signal_info['volume_ratio']:.2f}x")
                log.info(f"  Momentum: {signal_info['price_momentum']:.2f}%")
                log.info(f"  HA: {'UP' if signal_info['ha_up'] else 'DOWN'}")
                log.info("")
        else:
            log.info("❌ Hiçbir timeframe'den sinyal alınamadı")
        
        # En iyi sinyali seç
        best_signal = trader.select_best_signal(signals)
        if best_signal:
            log.info(f"🎯 En iyi sinyal: {best_signal['timeframe']} - {best_signal['signal_type']}")
        else:
            log.info("📊 En iyi sinyal bulunamadı")
            
        log.info("✅ Test tamamlandı")
        
    except Exception as e:
        log.error(f"❌ Test hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_signal_generation()
