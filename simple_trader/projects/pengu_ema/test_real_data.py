#!/usr/bin/env python3
"""
EIGEN EMA Gerçek Veri Test Scripti - Sunucuda
Pine Script stratejisine göre gerçek Binance verileriyle sinyal testi
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Path'leri düzelt
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
common_dir = os.path.join(parent_dir, "common")

sys.path.append(common_dir)
sys.path.append(current_dir)

from eigen_ema_multi_trader import MultiTimeframeEMATrader
import ccxt

def test_real_data_signals():
    """Gerçek Binance verileriyle sinyal testi"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    log = logging.getLogger(__name__)
    
    try:
        log.info("🚀 Gerçek Binance verileriyle test başlatılıyor...")
        
        # Trader'ı başlat (sandbox kapalı)
        trader = MultiTimeframeEMATrader()
        
        # Sandbox'ı kapat
        trader.cfg['sandbox'] = False
        trader.exchange.sandbox = False
        
        log.info("📊 Test parametreleri:")
        log.info(f"• Symbol: {trader.symbol}")
        log.info(f"• Sandbox: {trader.cfg['sandbox']}")
        log.info(f"• Timeframes: {list(trader.timeframes.keys())}")
        log.info(f"• EMA Fast: {trader.ema_fast}, Slow: {trader.ema_slow}")
        log.info(f"• Heikin Ashi: {trader.heikin_ashi_enabled}")
        
        # Gerçek veri al
        log.info("\n🔍 Gerçek Binance verileri alınıyor...")
        
        # Her timeframe için veri al
        for tf_name, tf_config in trader.timeframes.items():
            if not tf_config['enabled']:
                continue
                
            log.info(f"📊 {tf_name} timeframe verisi alınıyor...")
            
            try:
                # Market verisi al
                df = trader.get_market_data(tf_name, limit=100)
                if df is None:
                    log.error(f"❌ {tf_name} verisi alınamadı")
                    continue
                
                log.info(f"✅ {tf_name}: {len(df)} mum alındı")
                log.info(f"📅 Son mum zamanı: {df.index[-1]}")
                log.info(f"💰 Son fiyat: ${df['close'].iloc[-1]:.6f}")
                
                # Sinyal hesapla
                signal_info = trader.calculate_signals(df, tf_name)
                if signal_info is None:
                    log.warning(f"⚠️ {tf_name} sinyal hesaplanamadı")
                    continue
                
                # Sinyal detaylarını göster
                log.info(f"🎯 {tf_name} Sinyal: {signal_info['signal_type']}")
                log.info(f"📊 Signal: {signal_info['signal']}")
                log.info(f"💰 Price: ${signal_info['price']:.6f}")
                log.info(f"📈 EMA Fast: ${signal_info['ema_fast']:.6f}")
                log.info(f"📈 EMA Slow: ${signal_info['ema_slow']:.6f}")
                log.info(f"📊 RSI: {signal_info['rsi']:.1f}")
                log.info(f"📊 Volume Ratio: {signal_info['volume_ratio']:.2f}x")
                log.info(f"📊 Momentum: {signal_info['price_momentum']:.2f}%")
                log.info(f"🕯️ HA: {'UP' if signal_info['ha_up'] else 'DOWN'}")
                
                # EMA crossover kontrolü
                if signal_info['signal_type'] == 'EMA_CROSS_LONG':
                    log.info("🚀 EMA LONG CROSSOVER TESPİT EDİLDİ!")
                elif signal_info['signal_type'] == 'EMA_CROSS_SHORT':
                    log.info("📉 EMA SHORT CROSSOVER TESPİT EDİLDİ!")
                
                log.info("")
                
            except Exception as e:
                log.error(f"❌ {tf_name} test hatası: {e}")
                continue
        
        # Tüm timeframe'leri kontrol et
        log.info("\n🔍 Tüm timeframe'ler kontrol ediliyor...")
        signals = trader.check_all_timeframes()
        
        if signals:
            log.info(f"\n📊 {len(signals)} timeframe'den sinyal alındı:")
            for tf_name, signal_info in signals.items():
                log.info(f"• {tf_name}: {signal_info['signal_type']} - {signal_info['signal']}")
        
        # En iyi sinyali seç
        best_signal = trader.select_best_signal(signals)
        if best_signal:
            log.info(f"\n🎯 EN İYİ SİNYAL:")
            log.info(f"• Timeframe: {best_signal['timeframe']}")
            log.info(f"• Signal Type: {best_signal['signal_type']}")
            log.info(f"• Signal: {best_signal['signal']}")
            log.info(f"• Price: ${best_signal['price']:.6f}")
            
            if best_signal['signal'] != 'none':
                log.info("🚀 TRADING SİNYALİ BULUNDU!")
            else:
                log.info("📊 Sinyal yok")
        else:
            log.info("\n📊 En iyi sinyal bulunamadı")
        
        log.info("\n✅ Gerçek veri testi tamamlandı")
        
    except Exception as e:
        log.error(f"❌ Test hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_data_signals()
