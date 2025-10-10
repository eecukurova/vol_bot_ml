#!/usr/bin/env python3
"""
Volensy MACD Debug Backtest - Sinyal neden çıkmıyor?
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

class VolensyMacdDebugBacktest:
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
        
        # Trading parametreleri
        self.timeframe = '1h'
        self.signal_cooldown_hours = 2  # 2 saat cooldown
        
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
    
    def debug_signals(self, days=30):
        """Sinyalleri debug et"""
        try:
            print(f"🔍 Volensy MACD Sinyal Debug - {self.symbol}")
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
            
            # Tüm sinyalleri bul ve debug et
            signals_found = []
            start_idx = max(self.ema_trend_period, self.macd_slow, self.rsi_period)
            
            print(f"\n🔍 Sinyal Analizi (Son 20 bar):")
            print("="*80)
            
            # Son 20 bar'ı analiz et
            for i in range(max(start_idx, len(df)-20), len(df)):
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
                if bull_score == 3 and not_overbought:
                    signal = 'BUY'
                elif bear_score == 3 and not_oversold:
                    signal = 'SELL'
                
                # Türkiye saati
                turkey_time = current_time + timedelta(hours=3)
                time_str = turkey_time.strftime('%m/%d %H:%M TRT')
                
                print(f"{time_str}")
                print(f"   💰 Price: ${current_price:.4f}")
                print(f"   📈 EMA Trend: ${current_ema:.4f}")
                print(f"   🎯 RSI: {current_rsi:.1f}")
                print(f"   📊 MACD: {current_macd:.6f}")
                print(f"   📉 MACD Signal: {current_macd_signal:.6f}")
                print(f"   🎯 Bull Score: {bull_score}/3 | Bear Score: {bear_score}/3")
                print(f"   🚨 Signal: {signal}")
                print(f"   📊 Trend: {'BULL' if is_bull_trend else 'BEAR'}")
                print(f"   📊 Momentum: {'BULL' if is_bull_momentum else 'BEAR'}")
                print(f"   📊 Power: {'BULL' if is_bull_power else 'BEAR'}")
                print(f"   🚫 Overbought: {not not_overbought} | Oversold: {not not_oversold}")
                print("   " + "-"*60)
                
                if signal != 'HOLD':
                    signals_found.append({
                        'time': current_time,
                        'signal': signal,
                        'price': current_price,
                        'rsi': current_rsi,
                        'macd': current_macd,
                        'macd_signal': current_macd_signal,
                        'ema_trend': current_ema,
                        'bull_score': bull_score,
                        'bear_score': bear_score
                    })
            
            print(f"\n📊 ÖZET:")
            print("="*80)
            print(f"🔍 Son 20 bar'da sinyal sayısı: {len(signals_found)}")
            
            if signals_found:
                print(f"📈 Bulunan sinyaller:")
                for i, sig in enumerate(signals_found, 1):
                    turkey_time = sig['time'] + timedelta(hours=3)
                    print(f"{i}. {turkey_time.strftime('%m/%d %H:%M TRT')} - {sig['signal']} @ ${sig['price']:.4f}")
            else:
                print(f"❌ Son 20 bar'da hiç sinyal bulunamadı!")
                print(f"💡 Muhtemel sebepler:")
                print(f"   - RSI aşırı alım/satım bölgesinde")
                print(f"   - Skor 3/3'e ulaşmıyor")
                print(f"   - MACD ve Signal çok yakın")
            
            return signals_found
            
        except Exception as e:
            print(f"❌ Debug hatası: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None

if __name__ == "__main__":
    debug = VolensyMacdDebugBacktest("SUI/USDT")
    signals = debug.debug_signals(days=30)
