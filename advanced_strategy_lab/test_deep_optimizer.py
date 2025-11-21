#!/usr/bin/env python3
"""
DEEP Supertrend RSI Strategy Optimizer Test
"""

import sys
import os
sys.path.append('/Users/ahmet/ATR/strategy_optimizer/src')

import pandas as pd
import numpy as np
from strategy.deep_supertrend_rsi import DeepSupertrendRSIStrategy
from data.ccxt_client import CCXTDataClient
from optimize.grid_search import GridSearchOptimizer
from reporting.reporter import StrategyReporter
import json

def test_deep_strategy():
    """DEEP stratejisini test et"""
    print("🚀 DEEP Supertrend RSI Strategy Test Başlıyor...")
    
    # Test parametreleri
    test_params = {
        'rsi_length': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'rsi_long_exit': 65,
        'rsi_short_exit': 35,
        'supertrend_length': 1,
        'supertrend_multiplier': 3.0,
        'support_resistance_period': 22
    }
    
    # Strateji oluştur
    strategy = DeepSupertrendRSIStrategy(test_params)
    print(f"✅ Strateji oluşturuldu: {strategy}")
    
    # Test verisi oluştur
    dates = pd.date_range('2024-10-01', periods=1000, freq='1min')
    np.random.seed(42)
    
    # Simulated price data
    base_price = 0.08
    returns = np.random.normal(0, 0.01, 1000)
    prices = [base_price]
    
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    test_df = pd.DataFrame({
        'Open': prices,
        'High': [p * 1.02 for p in prices],
        'Low': [p * 0.98 for p in prices],
        'Close': prices,
        'Volume': np.random.randint(1000, 10000, 1000)
    }, index=dates)
    
    print(f"✅ Test verisi oluşturuldu: {len(test_df)} bar")
    
    # Sinyalleri üret
    try:
        signals_df = strategy.get_signals(test_df)
        print(f"✅ Sinyaller üretildi: {len(signals_df)} bar")
        
        # Sinyal sayılarını kontrol et
        buy_signals = signals_df['buy_signal'].sum()
        sell_signals = signals_df['sell_signal'].sum()
        close_long = signals_df['close_long'].sum()
        close_short = signals_df['close_short'].sum()
        
        print(f"📊 Sinyal İstatistikleri:")
        print(f"   🟢 BUY Sinyalleri: {buy_signals}")
        print(f"   🔴 SELL Sinyalleri: {sell_signals}")
        print(f"   🔒 LONG Kapatma: {close_long}")
        print(f"   🔒 SHORT Kapatma: {close_short}")
        
        # Son durumu kontrol et
        last_row = signals_df.iloc[-1]
        print(f"📈 Son Durum:")
        print(f"   💰 Fiyat: ${last_row['Close']:.4f}")
        print(f"   📊 RSI: {last_row['rsi']:.2f}")
        print(f"   📈 Supertrend: ${last_row['supertrend']:.4f}")
        print(f"   🟢 LONG Status: {last_row['long_status']}")
        print(f"   🔴 SHORT Status: {last_row['short_status']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        return False

def optimize_deep_strategy():
    """DEEP stratejisini optimize et"""
    print("\n🔧 DEEP Supertrend RSI Strategy Optimizasyonu Başlıyor...")
    
    # Optimizasyon parametreleri
    param_grid = {
        'rsi_length': [10, 14, 18],
        'rsi_oversold': [25, 30, 35],
        'rsi_overbought': [65, 70, 75],
        'supertrend_multiplier': [2.0, 3.0, 4.0],
        'support_resistance_period': [15, 20, 25]
    }
    
    print(f"📊 Optimizasyon Grid: {len(param_grid)} parametre")
    total_combinations = 1
    for param, values in param_grid.items():
        total_combinations *= len(values)
        print(f"   {param}: {values}")
    
    print(f"🎯 Toplam Kombinasyon: {total_combinations}")
    
    # Test verisi oluştur
    dates = pd.date_range('2024-10-01', periods=2000, freq='1min')
    np.random.seed(42)
    
    base_price = 0.08
    returns = np.random.normal(0, 0.01, 2000)
    prices = [base_price]
    
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    test_df = pd.DataFrame({
        'Open': prices,
        'High': [p * 1.02 for p in prices],
        'Low': [p * 0.98 for p in prices],
        'Close': prices,
        'Volume': np.random.randint(1000, 10000, 2000)
    }, index=dates)
    
    print(f"✅ Optimizasyon verisi hazır: {len(test_df)} bar")
    
    # Basit optimizasyon
    best_params = None
    best_score = -np.inf
    results = []
    
    from itertools import product
    
    for i, params in enumerate(product(*param_grid.values())):
        param_dict = dict(zip(param_grid.keys(), params))
        
        try:
            strategy = DeepSupertrendRSIStrategy(param_dict)
            signals_df = strategy.get_signals(test_df)
            
            # Basit skor hesaplama
            buy_signals = signals_df['buy_signal'].sum()
            sell_signals = signals_df['sell_signal'].sum()
            total_signals = buy_signals + sell_signals
            
            if total_signals > 0:
                score = total_signals / len(signals_df) * 100  # Signal frequency
            else:
                score = 0
            
            results.append({
                'params': param_dict,
                'score': score,
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'total_signals': total_signals
            })
            
            if score > best_score:
                best_score = score
                best_params = param_dict
            
            if (i + 1) % 10 == 0:
                print(f"   🔄 {i + 1}/{total_combinations} kombinasyon test edildi...")
                
        except Exception as e:
            print(f"   ❌ Parametre hatası: {param_dict} - {e}")
            continue
    
    # Sonuçları sırala
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n🏆 Optimizasyon Sonuçları:")
    print(f"   🎯 En İyi Skor: {best_score:.2f}")
    print(f"   📊 En İyi Parametreler: {best_params}")
    
    print(f"\n📈 Top 5 Sonuçlar:")
    for i, result in enumerate(results[:5]):
        print(f"   {i+1}. Skor: {result['score']:.2f} - Sinyaller: {result['total_signals']}")
        print(f"      Parametreler: {result['params']}")
    
    return best_params, results

if __name__ == "__main__":
    print("🎯 DEEP Supertrend RSI Strategy Optimizer")
    print("=" * 50)
    
    # Test strateji
    if test_deep_strategy():
        print("\n✅ Strateji testi başarılı!")
        
        # Optimizasyon yap
        best_params, results = optimize_deep_strategy()
        
        print(f"\n🎉 Optimizasyon tamamlandı!")
        print(f"🏆 En iyi parametreler: {best_params}")
        
    else:
        print("\n❌ Strateji testi başarısız!")
