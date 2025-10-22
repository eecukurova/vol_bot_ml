#!/usr/bin/env python3
"""
SOL MACD Trend Strategy Test
"""

import sys
import os
import pandas as pd
import numpy as np
import json

# Path'leri ayarla
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sol_macd_trader import VolensyMacdStrategy, HeikinAshiCalculator

def create_sample_data(n=1000):
    """Örnek OHLCV verisi oluştur"""
    np.random.seed(42)
    
    # Başlangıç fiyatı
    price = 100.0
    
    data = []
    for i in range(n):
        # Random walk ile fiyat hareketi
        change = np.random.normal(0, 0.02)
        price *= (1 + change)
        
        # OHLCV oluştur
        high = price * (1 + abs(np.random.normal(0, 0.01)))
        low = price * (1 - abs(np.random.normal(0, 0.01)))
        open_price = price * (1 + np.random.normal(0, 0.005))
        close_price = price
        
        volume = np.random.uniform(1000, 10000)
        
        data.append({
            'timestamp': pd.Timestamp.now() - pd.Timedelta(minutes=(n-i)*4),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df

def test_heikin_ashi():
    """Heikin Ashi test"""
    print("Testing Heikin Ashi Calculator...")
    
    df = create_sample_data(100)
    ha_data = HeikinAshiCalculator.calculate_heikin_ashi(df)
    
    # Kontroller
    assert 'ha_close' in ha_data.columns
    assert 'ha_open' in ha_data.columns
    assert 'ha_high' in ha_data.columns
    assert 'ha_low' in ha_data.columns
    
    print("✅ Heikin Ashi test passed")

def test_strategy():
    """Strategy test"""
    print("Testing Volensy MACD Strategy...")
    
    # Config
    config = {
        'ema_len': 20,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_len': 14,
        'rsi_ob': 70,
        'rsi_os': 30,
        'atr_len': 14
    }
    
    strategy = VolensyMacdStrategy(config)
    
    # Test verisi
    df = create_sample_data(200)
    
    # Indicators hesapla
    df_with_indicators = strategy.calculate_indicators(df)
    
    # Kontroller
    assert 'ema_trend' in df_with_indicators.columns
    assert 'macd' in df_with_indicators.columns
    assert 'macd_signal' in df_with_indicators.columns
    assert 'rsi' in df_with_indicators.columns
    assert 'atr' in df_with_indicators.columns
    
    # Sinyaller üret
    df_with_signals = strategy.generate_signals(df_with_indicators)
    
    # Kontroller
    assert 'buy_signal' in df_with_signals.columns
    assert 'sell_signal' in df_with_signals.columns
    assert 'bull_score' in df_with_signals.columns
    assert 'bear_score' in df_with_signals.columns
    
    print("✅ Strategy test passed")

def test_signal_generation():
    """Sinyal üretimi test"""
    print("Testing Signal Generation...")
    
    config = {
        'ema_len': 20,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'rsi_len': 14,
        'rsi_ob': 70,
        'rsi_os': 30,
        'atr_len': 14
    }
    
    strategy = VolensyMacdStrategy(config)
    df = create_sample_data(200)
    
    # Indicators ve sinyaller
    df_with_indicators = strategy.calculate_indicators(df)
    df_with_signals = strategy.generate_signals(df_with_indicators)
    
    # Sinyal sayıları
    buy_signals = df_with_signals['buy_signal'].sum()
    sell_signals = df_with_signals['sell_signal'].sum()
    
    print(f"Buy signals: {buy_signals}")
    print(f"Sell signals: {sell_signals}")
    
    # En az bir sinyal olmalı
    assert buy_signals > 0 or sell_signals > 0
    
    print("✅ Signal generation test passed")

def test_config_loading():
    """Config yükleme test"""
    print("Testing Config Loading...")
    
    config_file = os.path.join(current_dir, "sol_macd_config.json")
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Kontroller
        assert 'symbol' in config
        assert 'volensy_macd' in config
        assert 'multi_timeframe' in config
        
        print("✅ Config loading test passed")
    else:
        print("⚠️ Config file not found, skipping test")

if __name__ == "__main__":
    print("=" * 50)
    print("SOL MACD Trend Strategy Test")
    print("=" * 50)
    
    try:
        test_heikin_ashi()
        test_strategy()
        test_signal_generation()
        test_config_loading()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
