#!/usr/bin/env python3
"""
EIGEN EMA Sinyal Test Scripti - Mock Data ile
Pine Script stratejisine göre sinyal üretimini test eder
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

def create_mock_data(timeframe='15m', periods=100):
    """Mock market data oluştur"""
    
    # Timeframe'e göre interval
    intervals = {
        '15m': 15,
        '30m': 30,
        '1h': 60,
        '4h': 240,
        '1d': 1440
    }
    
    interval_minutes = intervals.get(timeframe, 15)
    
    # Başlangıç zamanı
    start_time = datetime.now() - timedelta(minutes=interval_minutes * periods)
    
    # Mock price data (trending up with some volatility)
    base_price = 0.05
    trend = np.linspace(0, 0.02, periods)  # 2% upward trend
    noise = np.random.normal(0, 0.005, periods)  # 0.5% volatility
    
    prices = base_price + trend + noise
    
    # OHLCV data oluştur
    data = []
    for i, price in enumerate(prices):
        timestamp = start_time + timedelta(minutes=interval_minutes * i)
        
        # OHLC hesapla (basit mock)
        open_price = price + np.random.normal(0, 0.001)
        high_price = max(open_price, price) + abs(np.random.normal(0, 0.002))
        low_price = min(open_price, price) - abs(np.random.normal(0, 0.002))
        close_price = price
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

def test_technical_indicators():
    """Teknik indikatörleri test et"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    log = logging.getLogger(__name__)
    
    try:
        log.info("🧪 Teknik indikatörler test ediliyor...")
        
        # Mock data oluştur
        df = create_mock_data('15m', 100)
        log.info(f"📊 Mock data oluşturuldu: {len(df)} mum")
        
        # Heikin Ashi hesapla
        ha_df = HeikinAshiCalculator.calculate_heikin_ashi(df)
        log.info("🕯️ Heikin Ashi hesaplandı")
        
        # Teknik indikatörleri hesapla
        close_data = ha_df['ha_close']
        
        # EMA
        ema_fast = TechnicalIndicators.calculate_ema(close_data, 12)
        ema_slow = TechnicalIndicators.calculate_ema(close_data, 26)
        
        # RSI
        rsi = TechnicalIndicators.calculate_rsi(close_data, 15)
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = TechnicalIndicators.calculate_bollinger_bands(close_data, 20, 2.0)
        
        # Volume ratio
        volume_ratio = TechnicalIndicators.calculate_volume_ratio(df['volume'], 20)
        
        # Price momentum
        price_mom = TechnicalIndicators.calculate_price_momentum(close_data, 4)
        
        # Son değerleri al
        current_close = close_data.iloc[-1]
        current_ema_fast = ema_fast.iloc[-1]
        current_ema_slow = ema_slow.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_bb_upper = bb_upper.iloc[-1]
        current_bb_lower = bb_lower.iloc[-1]
        current_volume_ratio = volume_ratio.iloc[-1]
        current_price_mom = price_mom.iloc[-1]
        
        log.info("📊 Teknik indikatör sonuçları:")
        log.info(f"• Price: ${current_close:.6f}")
        log.info(f"• EMA Fast: ${current_ema_fast:.6f}")
        log.info(f"• EMA Slow: ${current_ema_slow:.6f}")
        log.info(f"• RSI: {current_rsi:.1f}")
        log.info(f"• BB Upper: ${current_bb_upper:.6f}")
        log.info(f"• BB Lower: ${current_bb_lower:.6f}")
        log.info(f"• Volume Ratio: {current_volume_ratio:.2f}x")
        log.info(f"• Price Momentum: {current_price_mom:.2f}%")
        
        # EMA crossover test et
        crossover = TechnicalIndicators.detect_ema_crossover(ema_fast, ema_slow)
        log.info(f"🎯 EMA Crossover: {crossover}")
        
        # Heikin Ashi yön
        ha_up = current_close > ha_df['ha_open'].iloc[-1]
        ha_down = current_close < ha_df['ha_open'].iloc[-1]
        log.info(f"🕯️ Heikin Ashi: {'UP' if ha_up else 'DOWN'}")
        
        # Pine Script sinyal kurallarını test et
        rsi_oversold = 25
        rsi_overbought = 70
        volume_threshold = 1.0
        momentum_threshold = 0.6
        
        # Long sinyalleri
        long_c1 = (current_rsi < rsi_oversold) and (current_close <= current_bb_lower * 1.02) and (current_volume_ratio > volume_threshold) and (current_ema_fast > current_ema_slow) and (current_price_mom > -momentum_threshold) and ha_up
        
        # Short sinyalleri  
        short_c1 = (current_rsi > rsi_overbought) and (current_close >= current_bb_upper * 0.98) and (current_volume_ratio > volume_threshold) and (current_ema_fast < current_ema_slow) and (current_price_mom < momentum_threshold) and ha_down
        
        log.info("🎯 Pine Script sinyal testleri:")
        log.info(f"• Long C1: {long_c1}")
        log.info(f"• Short C1: {short_c1}")
        
        # Ana sinyal belirleme
        if crossover == 'long':
            signal = 'EMA_CROSS_LONG'
        elif crossover == 'short':
            signal = 'EMA_CROSS_SHORT'
        elif long_c1:
            signal = 'COMPLEX_LONG'
        elif short_c1:
            signal = 'COMPLEX_SHORT'
        else:
            signal = 'NONE'
        
        log.info(f"🎯 Final Signal: {signal}")
        
        log.info("✅ Teknik indikatör testi tamamlandı")
        
    except Exception as e:
        log.error(f"❌ Test hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_technical_indicators()
