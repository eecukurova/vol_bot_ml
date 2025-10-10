#!/usr/bin/env python3
"""
Volensy MACD Backtest Debug - Neden işlem yapılmıyor?
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

class VolensyMacdBacktestDebug:
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
    
    def debug_backtest_logic(self, days=30):
        """Backtest mantığını debug et"""
        try:
            print(f"🔍 Volensy MACD Backtest Debug - {self.symbol}")
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
            
            # Backtest simülasyonu
            position = None
            trades = []
            start_idx = max(self.ema_trend_period, self.macd_slow, self.rsi_period)
            
            print(f"\n🔍 Backtest Simülasyonu (Son 10 bar):")
            print("="*80)
            
            # Son 10 bar'ı simüle et
            for i in range(max(start_idx, len(df)-10), len(df)):
                current_time = df.index[i]
                current_price = df['close'].iloc[i]
                
                turkey_time = current_time + timedelta(hours=3)
                print(f"\n📅 {turkey_time.strftime('%m/%d %H:%M TRT')} - Price: ${current_price:.4f}")
                
                # Mevcut pozisyonu kontrol et
                if position:
                    side = position['side']
                    entry_price = position['entry_price']
                    sl_price = position['sl_price']
                    tp_price = position['tp_price']
                    
                    exit_reason = None
                    exit_price = None
                    
                    if side == 'long':
                        if current_price <= sl_price:
                            exit_reason = 'SL'
                            exit_price = sl_price
                        elif current_price >= tp_price:
                            exit_reason = 'TP'
                            exit_price = tp_price
                    else:  # short
                        if current_price >= sl_price:
                            exit_reason = 'SL'
                            exit_price = sl_price
                        elif current_price <= tp_price:
                            exit_reason = 'TP'
                            exit_price = tp_price
                    
                    if exit_reason:
                        print(f"   🔄 Pozisyon Kapandı: {exit_reason}")
                        print(f"   📈 Side: {side.upper()}")
                        print(f"   💰 Entry: ${entry_price:.4f} -> Exit: ${exit_price:.4f}")
                        position = None
                        continue
                    else:
                        print(f"   ⏳ Pozisyon Açık: {side.upper()} @ ${entry_price:.4f}")
                        print(f"   🛡️ SL: ${sl_price:.4f} | TP: ${tp_price:.4f}")
                        continue
                
                # Yeni sinyal kontrolü (sadece pozisyon yoksa)
                if not position:
                    # Son 50 bar'ı al (sinyal hesaplama için)
                    signal_df = df.iloc[max(0, i-50):i+1]
                    
                    if len(signal_df) < max(self.ema_trend_period, self.macd_slow, self.rsi_period):
                        print(f"   ⚠️ Yetersiz veri: {len(signal_df)} bar")
                        continue
                    
                    # Volensy MACD hesapla
                    indicators = self.calculate_volensy_macd(signal_df)
                    if indicators is None:
                        print(f"   ❌ Indicator hesaplama hatası")
                        continue
                    
                    close = signal_df['close'].iloc[-1]
                    ema_trend = indicators['ema_trend'].iloc[-1]
                    macd = indicators['macd'].iloc[-1]
                    macd_signal = indicators['macd_signal'].iloc[-1]
                    rsi = indicators['rsi'].iloc[-1]
                    
                    # Pine Script koşulları
                    is_bull_trend = close > ema_trend
                    is_bear_trend = close < ema_trend
                    
                    is_bull_momentum = rsi > 50
                    is_bear_momentum = rsi < 50
                    
                    is_bull_power = macd > macd_signal
                    is_bear_power = macd < macd_signal
                    
                    not_overbought = rsi < self.rsi_overbought
                    not_oversold = rsi > self.rsi_oversold
                    
                    # Skor hesapla
                    bull_score = (1 if is_bull_trend else 0) + (1 if is_bull_momentum else 0) + (1 if is_bull_power else 0)
                    bear_score = (1 if is_bear_trend else 0) + (1 if is_bear_momentum else 0) + (1 if is_bear_power else 0)
                    
                    # Sinyaller
                    signal = None
                    
                    if bull_score == 3 and not_overbought:
                        signal = 'BUY'
                    elif bear_score == 3 and not_oversold:
                        signal = 'SELL'
                    
                    print(f"   📊 RSI: {rsi:.1f} | MACD: {macd:.6f} | Signal: {macd_signal:.6f}")
                    print(f"   🎯 Bull Score: {bull_score}/3 | Bear Score: {bear_score}/3")
                    print(f"   🚫 Overbought: {not not_overbought} | Oversold: {not not_oversold}")
                    print(f"   🚨 Signal: {signal}")
                    
                    if signal:
                        # Pozisyon aç
                        sl_percent = 0.02  # 2%
                        tp_percent = 0.04  # 4%
                        
                        if signal == 'BUY':
                            sl_price = close * (1 - sl_percent)
                            tp_price = close * (1 + tp_percent)
                        else:  # SELL
                            sl_price = close * (1 + sl_percent)
                            tp_price = close * (1 - tp_percent)
                        
                        position = {
                            'side': 'long' if signal == 'BUY' else 'short',
                            'entry_price': close,
                            'entry_time': current_time,
                            'sl_price': sl_price,
                            'tp_price': tp_price
                        }
                        
                        print(f"   🚀 {signal} Pozisyon Açıldı @ ${close:.4f}")
                        print(f"   🛡️ SL: ${sl_price:.4f} | TP: ${tp_price:.4f}")
                    else:
                        print(f"   ⏸️ Sinyal yok")
            
            print(f"\n📊 ÖZET:")
            print("="*80)
            print(f"🔍 Son 10 bar'da işlem sayısı: {len(trades)}")
            
            return trades
            
        except Exception as e:
            print(f"❌ Debug hatası: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None

if __name__ == "__main__":
    debug = VolensyMacdBacktestDebug("SUI/USDT")
    trades = debug.debug_backtest_logic(days=30)
