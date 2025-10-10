#!/usr/bin/env python3
"""
EMA Crossover Test - Pine Script stratejisine göre
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Path'leri düzelt
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
common_dir = os.path.join(parent_dir, "common")

sys.path.append(common_dir)
sys.path.append(current_dir)

from eigen_ema_multi_trader import HeikinAshiCalculator, TechnicalIndicators
import logging

def create_ema_crossover_data():
    """EMA crossover oluşturacak mock data - daha net crossover"""
    
    periods = 60
    start_time = datetime.now() - timedelta(minutes=15 * periods)
    
    data = []
    
    for i in range(periods):
        timestamp = start_time + timedelta(minutes=15 * i)
        
        # İlk 40 mumda: Slow EMA > Fast EMA (düşüş trendi)
        # 40-45 mum arası: Crossover bölgesi
        # Son 15 mumda: Fast EMA > Slow EMA (yükseliş trendi)
        
        if i < 40:
            # Düşüş trendi - Slow EMA > Fast EMA
            base_price = 0.05 - (i * 0.0002)
            trend_factor = -0.002
        elif i < 45:
            # Crossover bölgesi - EMA'lar yaklaşır
            base_price = 0.042 + ((i - 40) * 0.0005)
            trend_factor = 0.001
        else:
            # Yükseliş trendi - Fast EMA > Slow EMA
            base_price = 0.0445 + ((i - 45) * 0.0008)
            trend_factor = 0.003
        
        # OHLCV hesapla
        open_price = base_price + np.random.normal(0, 0.0003)
        close_price = base_price + trend_factor + np.random.normal(0, 0.0003)
        high_price = max(open_price, close_price) + abs(np.random.normal(0, 0.0008))
        low_price = min(open_price, close_price) - abs(np.random.normal(0, 0.0008))
        volume = np.random.uniform(1000000, 5000000)
        
        data.append({
            'timestamp': timestamp,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df

def test_ema_crossover():
    """EMA crossover'ı test et"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    log = logging.getLogger(__name__)
    
    try:
        log.info("🎯 EMA Crossover test başlatılıyor...")
        
        # Mock data oluştur
        df = create_ema_crossover_data()
        log.info(f"📊 Mock data oluşturuldu: {len(df)} mum")
        
        # Heikin Ashi hesapla
        ha_df = HeikinAshiCalculator.calculate_heikin_ashi(df)
        close_data = ha_df['ha_close']
        
        # EMA hesapla
        ema_fast = TechnicalIndicators.calculate_ema(close_data, 12)
        ema_slow = TechnicalIndicators.calculate_ema(close_data, 26)
        
        # Son 5 mumun EMA değerlerini göster
        log.info("📈 Son 5 mumun EMA değerleri:")
        for i in range(-5, 0):
            log.info(f"  Mum {i}: Fast=${ema_fast.iloc[i]:.6f}, Slow=${ema_slow.iloc[i]:.6f}")
        
        # EMA crossover tespit et
        crossover = TechnicalIndicators.detect_ema_crossover(ema_fast, ema_slow)
        log.info(f"🎯 EMA Crossover Sonucu: {crossover}")
        
        # Pine Script stratejisine göre sinyal kontrolü
        current_close = close_data.iloc[-1]
        current_ema_fast = ema_fast.iloc[-1]
        current_ema_slow = ema_slow.iloc[-1]
        
        # Heikin Ashi yön
        ha_up = current_close > ha_df['ha_open'].iloc[-1]
        
        # Pine Script'teki EMA crossover kontrolü
        ema_cross_long = crossover == 'long'
        ema_cross_short = crossover == 'short'
        
        log.info("🎯 Pine Script EMA Crossover Test:")
        log.info(f"• EMA Cross Long: {ema_cross_long}")
        log.info(f"• EMA Cross Short: {ema_cross_short}")
        log.info(f"• Current Price: ${current_close:.6f}")
        log.info(f"• EMA Fast: ${current_ema_fast:.6f}")
        log.info(f"• EMA Slow: ${current_ema_slow:.6f}")
        log.info(f"• Heikin Ashi: {'UP' if ha_up else 'DOWN'}")
        
        # Ana sinyal belirleme (Pine Script stratejisine göre)
        if ema_cross_long:
            signal = 'EMA_CROSS_LONG'
            log.info("🚀 EMA LONG sinyali tespit edildi!")
        elif ema_cross_short:
            signal = 'EMA_CROSS_SHORT'
            log.info("📉 EMA SHORT sinyali tespit edildi!")
        else:
            signal = 'NONE'
            log.info("📊 EMA crossover sinyali yok")
        
        log.info(f"🎯 Final Signal: {signal}")
        
        # EMA trend analizi
        if current_ema_fast > current_ema_slow:
            log.info("📈 EMA Trend: Fast > Slow (Bullish)")
        elif current_ema_fast < current_ema_slow:
            log.info("📉 EMA Trend: Fast < Slow (Bearish)")
        else:
            log.info("📊 EMA Trend: Fast = Slow (Neutral)")
        
        log.info("✅ EMA Crossover testi tamamlandı")
        
    except Exception as e:
        log.error(f"❌ Test hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ema_crossover()
