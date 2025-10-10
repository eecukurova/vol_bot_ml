#!/usr/bin/env python3
"""
Volensy MACD Son Sinyaller Analizi
TradingView ile karşılaştırma için
"""

import ccxt
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add common path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../common')))

class VolensyMacdSignalAnalyzer:
    def __init__(self, symbol="SUI/USDT"):
        self.symbol = symbol
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # Volensy MACD parametreleri
        self.ema_trend_period = 55
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
        # Test parametreleri
        self.timeframe = '1h'
        self.sl_percent = 0.02  # 2%
        self.tp_percent = 0.04  # 4%
        
    def calculate_volensy_macd(self, df):
        """Volensy MACD hesapla"""
        try:
            close = df['close']
            
            # EMA Trend (55 periyot)
            ema_trend = close.ewm(span=self.ema_trend_period).mean()
            
            # MACD hesapla
            ema_fast = close.ewm(span=self.macd_fast).mean()
            ema_slow = close.ewm(span=self.macd_slow).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=self.macd_signal).mean()
            
            # RSI hesapla
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return {
                'ema_trend': ema_trend,
                'macd': macd,
                'macd_signal': macd_signal,
                'rsi': rsi
            }
            
        except Exception as e:
            print(f"❌ Volensy MACD hesaplama hatası: {e}")
            return None
    
    def analyze_recent_signals(self, days=7):
        """Son sinyalleri analiz et"""
        try:
            print(f"🚀 Volensy MACD Son Sinyaller Analizi - {self.symbol}")
            print(f"📅 Son {days} günlük veri")
            print("="*80)
            
            # Veri al
            limit = min(1000, days * 24)
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            
            if not ohlcv:
                print(f"❌ Veri alınamadı")
                return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            print(f"📊 {len(df)} bar verisi alındı")
            print(f"📅 Tarih aralığı: {df.index[0]} - {df.index[-1]}")
            
            # Volensy MACD hesapla
            indicators = self.calculate_volensy_macd(df)
            if indicators is None:
                return None
            
            close = df['close']
            ema_trend = indicators['ema_trend']
            macd = indicators['macd']
            macd_signal = indicators['macd_signal']
            rsi = indicators['rsi']
            
            # Son 20 bar'ı analiz et
            recent_bars = 20
            start_idx = max(self.ema_trend_period, self.macd_slow, self.rsi_period)
            
            print(f"\n🔍 Son {recent_bars} Bar Analizi:")
            print("="*80)
            
            signals_found = []
            
            for i in range(len(df) - recent_bars, len(df)):
                if i < start_idx:
                    continue
                    
                current_time = df.index[i]
                current_price = close.iloc[i]
                current_ema = ema_trend.iloc[i]
                current_macd = macd.iloc[i]
                current_macd_signal = macd_signal.iloc[i]
                current_rsi = rsi.iloc[i]
                
                # Pine Script koşulları
                is_bull_trend = current_price > current_ema
                is_bear_trend = current_price < current_ema
                
                is_bull_momentum = current_rsi > 50
                is_bear_momentum = current_rsi < 50
                
                is_bull_power = current_macd > current_macd_signal
                is_bear_power = current_macd < current_macd_signal
                
                not_overbought = current_rsi < self.rsi_overbought
                not_oversold = current_rsi > self.rsi_oversold
                
                # Skor hesapla
                bull_score = (1 if is_bull_trend else 0) + (1 if is_bull_momentum else 0) + (1 if is_bull_power else 0)
                bear_score = (1 if is_bear_trend else 0) + (1 if is_bear_momentum else 0) + (1 if is_bear_power else 0)
                
                # Sinyaller
                signal = 'HOLD'
                signal_strength = 0
                
                if bull_score == 3 and not_overbought:
                    signal = 'BUY'
                    signal_strength = abs(current_price - current_ema) / current_price * 100
                elif bear_score == 3 and not_oversold:
                    signal = 'SELL'
                    signal_strength = abs(current_price - current_ema) / current_price * 100
                
                # Bar bilgilerini yazdır
                time_str = current_time.strftime('%Y-%m-%d %H:%M UTC')
                print(f"\n📅 {time_str}")
                print(f"   💰 Price: ${current_price:.4f}")
                print(f"   📊 EMA Trend: ${current_ema:.4f}")
                print(f"   📈 MACD: {current_macd:.6f}")
                print(f"   📉 MACD Signal: {current_macd_signal:.6f}")
                print(f"   🎯 RSI: {current_rsi:.1f}")
                print(f"   📊 Bull Score: {bull_score}/3 | Bear Score: {bear_score}/3")
                print(f"   🚨 Signal: {signal}")
                
                if signal != 'HOLD':
                    print(f"   💪 Strength: {signal_strength:.2f}%")
                    
                    # SL/TP hesapla
                    if signal == 'BUY':
                        sl_price = current_price * (1 - self.sl_percent)
                        tp_price = current_price * (1 + self.tp_percent)
                        print(f"   🛡️ SL: ${sl_price:.4f} | 🎯 TP: ${tp_price:.4f}")
                    else:  # SELL
                        sl_price = current_price * (1 + self.sl_percent)
                        tp_price = current_price * (1 - self.tp_percent)
                        print(f"   🛡️ SL: ${sl_price:.4f} | 🎯 TP: ${tp_price:.4f}")
                    
                    signals_found.append({
                        'time': current_time,
                        'signal': signal,
                        'price': current_price,
                        'strength': signal_strength,
                        'sl_price': sl_price if signal == 'BUY' else sl_price,
                        'tp_price': tp_price if signal == 'BUY' else tp_price,
                        'rsi': current_rsi,
                        'macd': current_macd,
                        'macd_signal': current_macd_signal
                    })
            
            # Sonuçları özetle
            print(f"\n📊 ÖZET:")
            print("="*80)
            print(f"🔍 Analiz edilen bar sayısı: {recent_bars}")
            print(f"🚨 Bulunan sinyal sayısı: {len(signals_found)}")
            
            if signals_found:
                print(f"\n🎯 SON SİNYALLER:")
                for i, sig in enumerate(signals_found[-3:], 1):  # Son 3 sinyal
                    time_str = sig['time'].strftime('%Y-%m-%d %H:%M UTC')
                    print(f"\n{i}. {time_str}")
                    print(f"   🚨 Signal: {sig['signal']}")
                    print(f"   💰 Price: ${sig['price']:.4f}")
                    print(f"   💪 Strength: {sig['strength']:.2f}%")
                    print(f"   🎯 RSI: {sig['rsi']:.1f}")
                    print(f"   📈 MACD: {sig['macd']:.6f}")
                    print(f"   📉 MACD Signal: {sig['macd_signal']:.6f}")
                    print(f"   🛡️ SL: ${sig['sl_price']:.4f}")
                    print(f"   🎯 TP: ${sig['tp_price']:.4f}")
                
                # En son sinyal
                last_signal = signals_found[-1]
                print(f"\n🔥 EN SON SİNYAL:")
                print(f"   📅 Zaman: {last_signal['time'].strftime('%Y-%m-%d %H:%M UTC')}")
                print(f"   🚨 Signal: {last_signal['signal']}")
                print(f"   💰 Price: ${last_signal['price']:.4f}")
                print(f"   🛡️ SL: ${last_signal['sl_price']:.4f}")
                print(f"   🎯 TP: ${last_signal['tp_price']:.4f}")
                
                # TradingView için bilgiler
                print(f"\n📊 TRADINGVIEW İÇİN:")
                print(f"   📅 Son sinyal zamanı: {last_signal['time'].strftime('%Y-%m-%d %H:%M')}")
                print(f"   💰 Sinyal fiyatı: ${last_signal['price']:.4f}")
                print(f"   🚨 Sinyal türü: {last_signal['signal']}")
                print(f"   🎯 RSI: {last_signal['rsi']:.1f}")
                print(f"   📈 MACD: {last_signal['macd']:.6f}")
                print(f"   📉 MACD Signal: {last_signal['macd_signal']:.6f}")
            else:
                print(f"\n❌ Son {recent_bars} bar'da sinyal bulunamadı")
                print(f"   📊 Mevcut RSI: {rsi.iloc[-1]:.1f}")
                print(f"   📈 Mevcut MACD: {macd.iloc[-1]:.6f}")
                print(f"   📉 Mevcut MACD Signal: {macd_signal.iloc[-1]:.6f}")
            
            return signals_found
            
        except Exception as e:
            print(f"❌ Analiz hatası: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None

if __name__ == "__main__":
    analyzer = VolensyMacdSignalAnalyzer("SUI/USDT")
    signals = analyzer.analyze_recent_signals(days=7)
