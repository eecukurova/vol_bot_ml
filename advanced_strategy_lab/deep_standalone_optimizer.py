#!/usr/bin/env python3
"""
DEEP Supertrend RSI Strategy - Standalone Optimizer Test
"""

import pandas as pd
import numpy as np
import pandas_ta as pta
from itertools import product
import json

class DeepSupertrendRSIStrategy:
    def __init__(self, params):
        self.rsi_length = params.get('rsi_length', 14)
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_overbought = params.get('rsi_overbought', 70)
        self.rsi_long_exit = params.get('rsi_long_exit', 65)
        self.rsi_short_exit = params.get('rsi_short_exit', 35)
        self.supertrend_length = params.get('supertrend_length', 1)
        self.supertrend_multiplier = params.get('supertrend_multiplier', 3.0)
        self.support_resistance_period = params.get('support_resistance_period', 22)
    
    def calculate_indicators(self, df):
        """Teknik indikatörleri hesapla"""
        result_df = df.copy()
        
        # RSI hesaplama
        result_df['rsi'] = pta.rsi(df['Close'], length=self.rsi_length)
        
        # Supertrend hesaplama
        supertrend_data = pta.supertrend(
            df['High'], 
            df['Low'], 
            df['Close'], 
            length=self.supertrend_length,
            multiplier=self.supertrend_multiplier
        )
        result_df['supertrend'] = supertrend_data[f'SUPERT_{self.supertrend_length}_{self.supertrend_multiplier}']
        
        # Support/Resistance seviyeleri
        result_df['max_level'] = df['High'].rolling(window=self.support_resistance_period).max()
        result_df['min_level'] = df['Low'].rolling(window=self.support_resistance_period).min()
        
        return result_df
    
    def generate_signals(self, df):
        """Trading sinyalleri üret"""
        result_df = df.copy()
        
        # State variables
        long_status = 0
        short_status = 0
        long_position = 0
        short_position = 0
        dip_level = 0.0
        tepe_level = 0.0
        long_boyun = 0.0
        short_boyun = 0.0
        
        # Signal arrays
        buy_signals = []
        sell_signals = []
        close_long_signals = []
        close_short_signals = []
        
        for i in range(len(result_df)):
            current_price = result_df.iloc[i]['Close']
            current_high = result_df.iloc[i]['High']
            current_low = result_df.iloc[i]['Low']
            rsi = result_df.iloc[i]['rsi']
            supertrend = result_df.iloc[i]['supertrend']
            min_level = result_df.iloc[i]['min_level']
            max_level = result_df.iloc[i]['max_level']
            
            # Skip if indicators are NaN
            if pd.isna(rsi) or pd.isna(supertrend) or pd.isna(min_level) or pd.isna(max_level):
                buy_signals.append(False)
                sell_signals.append(False)
                close_long_signals.append(False)
                close_short_signals.append(False)
                continue
            
            # LONG Signal Logic (5 stages)
            if long_status == 0 and rsi < self.rsi_oversold:
                if long_position == 0 and short_position == 0:
                    long_status = 1
                    dip_level = min_level
            
            elif long_status == 1 and supertrend < current_price:
                long_status = 2
                long_boyun = current_high
            
            elif long_status == 2:
                if current_high > long_boyun:
                    long_boyun = current_high
                
                if supertrend > current_price and current_price < long_boyun:
                    long_status = 3
            
            elif long_status == 3 and supertrend < current_price and current_price > long_boyun:
                long_status = 4
            
            elif long_status == 4 and supertrend > current_price and current_price < long_boyun:
                long_status = 5
            
            # SHORT Signal Logic (5 stages)
            if short_status == 0 and rsi > self.rsi_overbought:
                if long_position == 0 and short_position == 0:
                    short_status = 1
                    tepe_level = max_level
            
            elif short_status == 1 and supertrend > current_price:
                short_status = 2
                short_boyun = current_low
            
            elif short_status == 2:
                if current_low < short_boyun:
                    short_boyun = current_low
                
                if supertrend < current_price and current_price > short_boyun:
                    short_status = 3
            
            elif short_status == 3 and supertrend > current_price and current_price < short_boyun:
                short_status = 4
            
            elif short_status == 4 and supertrend < current_price and current_price > short_boyun:
                short_status = 5
            
            # Reset conditions
            if long_status in [2, 4] and rsi > self.rsi_long_exit:
                long_status = 0
            
            if long_status in [2, 3, 4, 5] and rsi < self.rsi_oversold:
                long_status = 1
                dip_level = min_level
            
            if short_status in [2, 4] and rsi < self.rsi_short_exit:
                short_status = 0
            
            if short_status in [2, 3, 4, 5] and rsi > self.rsi_overbought:
                short_status = 1
                tepe_level = max_level
            
            # Position management
            buy_signal = False
            sell_signal = False
            close_long_signal = False
            close_short_signal = False
            
            if long_position == 0 and short_position == 0:
                if long_status == 5 and current_price > long_boyun:
                    long_position = 1
                    buy_signal = True
                elif short_status == 5 and current_price < short_boyun:
                    short_position = 1
                    sell_signal = True
            
            if long_position == 1 and current_price < min_level:
                long_position = 0
                long_status = 0
                short_status = 0
                close_long_signal = True
            
            if short_position == 1 and current_price > max_level:
                short_position = 0
                long_status = 0
                short_status = 0
                close_short_signal = True
            
            buy_signals.append(buy_signal)
            sell_signals.append(sell_signal)
            close_long_signals.append(close_long_signal)
            close_short_signals.append(close_short_signal)
        
        result_df['buy_signal'] = buy_signals
        result_df['sell_signal'] = sell_signals
        result_df['close_long'] = close_long_signals
        result_df['close_short'] = close_short_signals
        
        return result_df
    
    def get_signals(self, df):
        """Ana sinyal üretme fonksiyonu"""
        df_with_indicators = self.calculate_indicators(df)
        df_with_signals = self.generate_signals(df_with_indicators)
        return df_with_signals

def create_test_data():
    """Test verisi oluştur"""
    print("📊 Test verisi oluşturuluyor...")
    
    dates = pd.date_range('2024-10-01', periods=2000, freq='1min')
    np.random.seed(42)
    
    # Simulated DEEP/USDT price data
    base_price = 0.08
    returns = np.random.normal(0, 0.01, 2000)
    prices = [base_price]
    
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    test_df = pd.DataFrame({
        'Open': prices,
        'High': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'Low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'Close': prices,
        'Volume': np.random.randint(1000, 10000, 2000)
    }, index=dates)
    
    print(f"✅ Test verisi hazır: {len(test_df)} bar")
    return test_df

def test_strategy():
    """Stratejiyi test et"""
    print("\n🧪 DEEP Supertrend RSI Strategy Test")
    print("=" * 50)
    
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
    
    # Test verisi
    test_df = create_test_data()
    
    # Strateji oluştur
    strategy = DeepSupertrendRSIStrategy(test_params)
    print(f"✅ Strateji oluşturuldu")
    
    # Sinyalleri üret
    signals_df = strategy.get_signals(test_df)
    print(f"✅ Sinyaller üretildi")
    
    # İstatistikler
    buy_signals = signals_df['buy_signal'].sum()
    sell_signals = signals_df['sell_signal'].sum()
    close_long = signals_df['close_long'].sum()
    close_short = signals_df['close_short'].sum()
    
    print(f"\n📊 Sinyal İstatistikleri:")
    print(f"   🟢 BUY Sinyalleri: {buy_signals}")
    print(f"   🔴 SELL Sinyalleri: {sell_signals}")
    print(f"   🔒 LONG Kapatma: {close_long}")
    print(f"   🔒 SHORT Kapatma: {close_short}")
    
    # Son durum
    last_row = signals_df.iloc[-1]
    print(f"\n📈 Son Durum:")
    print(f"   💰 Fiyat: ${last_row['Close']:.4f}")
    print(f"   📊 RSI: {last_row['rsi']:.2f}")
    print(f"   📈 Supertrend: ${last_row['supertrend']:.4f}")
    
    return signals_df

def optimize_strategy():
    """Stratejiyi optimize et"""
    print("\n🔧 DEEP Supertrend RSI Strategy Optimizasyonu")
    print("=" * 50)
    
    # Optimizasyon parametreleri
    param_grid = {
        'rsi_length': [10, 14, 18],
        'rsi_oversold': [25, 30, 35],
        'rsi_overbought': [65, 70, 75],
        'supertrend_multiplier': [2.0, 3.0, 4.0],
        'support_resistance_period': [15, 20, 25]
    }
    
    print(f"📊 Optimizasyon Grid:")
    total_combinations = 1
    for param, values in param_grid.items():
        total_combinations *= len(values)
        print(f"   {param}: {values}")
    
    print(f"\n🎯 Toplam Kombinasyon: {total_combinations}")
    
    # Test verisi
    test_df = create_test_data()
    
    # Optimizasyon
    best_params = None
    best_score = -np.inf
    results = []
    
    print(f"\n🔄 Optimizasyon başlıyor...")
    
    for i, params in enumerate(product(*param_grid.values())):
        param_dict = dict(zip(param_grid.keys(), params))
        
        try:
            strategy = DeepSupertrendRSIStrategy(param_dict)
            signals_df = strategy.get_signals(test_df)
            
            # Skor hesaplama
            buy_signals = signals_df['buy_signal'].sum()
            sell_signals = signals_df['sell_signal'].sum()
            total_signals = buy_signals + sell_signals
            
            # Basit skor: sinyal sıklığı + dengeli sinyal dağılımı
            if total_signals > 0:
                signal_frequency = total_signals / len(signals_df) * 100
                signal_balance = min(buy_signals, sell_signals) / max(buy_signals, sell_signals) if max(buy_signals, sell_signals) > 0 else 0
                score = signal_frequency * signal_balance
            else:
                score = 0
            
            results.append({
                'params': param_dict,
                'score': score,
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'total_signals': total_signals,
                'signal_frequency': signal_frequency if total_signals > 0 else 0
            })
            
            if score > best_score:
                best_score = score
                best_params = param_dict
            
            if (i + 1) % 20 == 0:
                print(f"   🔄 {i + 1}/{total_combinations} kombinasyon test edildi...")
                
        except Exception as e:
            print(f"   ❌ Parametre hatası: {param_dict} - {e}")
            continue
    
    # Sonuçları sırala
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n🏆 Optimizasyon Sonuçları:")
    print(f"   🎯 En İyi Skor: {best_score:.2f}")
    print(f"   📊 En İyi Parametreler:")
    for key, value in best_params.items():
        print(f"      {key}: {value}")
    
    print(f"\n📈 Top 5 Sonuçlar:")
    for i, result in enumerate(results[:5]):
        print(f"   {i+1}. Skor: {result['score']:.2f}")
        print(f"      Sinyaller: {result['total_signals']} (BUY: {result['buy_signals']}, SELL: {result['sell_signals']})")
        print(f"      Sıklık: {result['signal_frequency']:.2f}%")
        print(f"      Parametreler: {result['params']}")
        print()
    
    return best_params, results

if __name__ == "__main__":
    print("🎯 DEEP Supertrend RSI Strategy Optimizer")
    print("=" * 60)
    
    # Test strateji
    signals_df = test_strategy()
    
    # Optimizasyon yap
    best_params, results = optimize_strategy()
    
    print(f"\n🎉 Optimizasyon tamamlandı!")
    print(f"🏆 En iyi parametreler kaydediliyor...")
    
    # Sonuçları kaydet
    with open('deep_optimization_results.json', 'w') as f:
        json.dump({
            'best_params': best_params,
            'best_score': best_score,
            'top_results': results[:10]
        }, f, indent=2)
    
    print(f"✅ Sonuçlar 'deep_optimization_results.json' dosyasına kaydedildi")
