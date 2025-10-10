#!/usr/bin/env python3
"""
Volensy MACD Son 10 Sinyal Analizi - Türkiye Saati
SL/TP durumları ile birlikte
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

class VolensyMacdLast10Signals:
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
    
    def analyze_last_10_signals(self, days=30):
        """Son 10 sinyali analiz et"""
        try:
            print(f"🚀 Volensy MACD Son 10 Sinyal Analizi - {self.symbol}")
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
            
            # Tüm sinyalleri bul
            signals_found = []
            start_idx = max(self.ema_trend_period, self.macd_slow, self.rsi_period)
            
            for i in range(start_idx, len(df)):
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
                
                if signal != 'HOLD':
                    # SL/TP hesapla
                    if signal == 'BUY':
                        sl_price = current_price * (1 - self.sl_percent)
                        tp_price = current_price * (1 + self.tp_percent)
                    else:  # SELL
                        sl_price = current_price * (1 + self.sl_percent)
                        tp_price = current_price * (1 - self.tp_percent)
                    
                    signals_found.append({
                        'time': current_time,
                        'signal': signal,
                        'price': current_price,
                        'strength': signal_strength,
                        'sl_price': sl_price,
                        'tp_price': tp_price,
                        'rsi': current_rsi,
                        'macd': current_macd,
                        'macd_signal': current_macd_signal,
                        'ema_trend': current_ema
                    })
            
            # Son 10 sinyali al
            last_10_signals = signals_found[-10:] if len(signals_found) >= 10 else signals_found
            
            print(f"\n📊 ÖZET:")
            print("="*80)
            print(f"🔍 Toplam sinyal sayısı: {len(signals_found)}")
            print(f"📈 Son 10 sinyal:")
            
            # Mevcut fiyatı al
            current_price = close.iloc[-1]
            
            for i, sig in enumerate(last_10_signals, 1):
                # Türkiye saati (UTC+3)
                turkey_time = sig['time'] + timedelta(hours=3)
                time_str = turkey_time.strftime('%Y-%m-%d %H:%M TRT')
                
                print(f"\n{i}. {time_str}")
                print(f"   🚨 Signal: {sig['signal']}")
                print(f"   💰 Price: ${sig['price']:.4f}")
                print(f"   💪 Strength: {sig['strength']:.2f}%")
                print(f"   🎯 RSI: {sig['rsi']:.1f}")
                print(f"   📈 MACD: {sig['macd']:.6f}")
                print(f"   📉 MACD Signal: {sig['macd_signal']:.6f}")
                print(f"   🛡️ SL: ${sig['sl_price']:.4f}")
                print(f"   🎯 TP: ${sig['tp_price']:.4f}")
                
                # SL/TP durumu analiz et
                if sig['signal'] == 'BUY':
                    if current_price <= sig['sl_price']:
                        print(f"   ❌ STOP LOSS HİT! (Zarar)")
                        loss_pct = (sig['price'] - sig['sl_price']) / sig['price'] * 100
                        print(f"   💸 Zarar: {loss_pct:.2f}%")
                    elif current_price >= sig['tp_price']:
                        print(f"   ✅ TAKE PROFIT HİT! (Kar)")
                        profit_pct = (sig['tp_price'] - sig['price']) / sig['price'] * 100
                        print(f"   💰 Kar: {profit_pct:.2f}%")
                    else:
                        print(f"   ⏳ HENÜZ AÇIK")
                        if current_price > sig['price']:
                            unrealized_pnl = (current_price - sig['price']) / sig['price'] * 100
                            print(f"   📈 Unrealized PnL: +{unrealized_pnl:.2f}%")
                        else:
                            unrealized_pnl = (sig['price'] - current_price) / sig['price'] * 100
                            print(f"   📉 Unrealized PnL: -{unrealized_pnl:.2f}%")
                
                else:  # SELL
                    if current_price >= sig['sl_price']:
                        print(f"   ❌ STOP LOSS HİT! (Zarar)")
                        loss_pct = (sig['sl_price'] - sig['price']) / sig['price'] * 100
                        print(f"   💸 Zarar: {loss_pct:.2f}%")
                    elif current_price <= sig['tp_price']:
                        print(f"   ✅ TAKE PROFIT HİT! (Kar)")
                        profit_pct = (sig['price'] - sig['tp_price']) / sig['price'] * 100
                        print(f"   💰 Kar: {profit_pct:.2f}%")
                    else:
                        print(f"   ⏳ HENÜZ AÇIK")
                        if current_price < sig['price']:
                            unrealized_pnl = (sig['price'] - current_price) / sig['price'] * 100
                            print(f"   📈 Unrealized PnL: +{unrealized_pnl:.2f}%")
                        else:
                            unrealized_pnl = (current_price - sig['price']) / sig['price'] * 100
                            print(f"   📉 Unrealized PnL: -{unrealized_pnl:.2f}%")
            
            # İstatistikler
            print(f"\n📊 İSTATİSTİKLER:")
            print("="*80)
            
            sl_hits = 0
            tp_hits = 0
            still_open = 0
            
            for sig in last_10_signals:
                if sig['signal'] == 'BUY':
                    if current_price <= sig['sl_price']:
                        sl_hits += 1
                    elif current_price >= sig['tp_price']:
                        tp_hits += 1
                    else:
                        still_open += 1
                else:  # SELL
                    if current_price >= sig['sl_price']:
                        sl_hits += 1
                    elif current_price <= sig['tp_price']:
                        tp_hits += 1
                    else:
                        still_open += 1
            
            print(f"❌ Stop Loss Hit: {sl_hits}")
            print(f"✅ Take Profit Hit: {tp_hits}")
            print(f"⏳ Henüz Açık: {still_open}")
            
            if sl_hits + tp_hits > 0:
                win_rate = (tp_hits / (sl_hits + tp_hits)) * 100
                print(f"🎯 Win Rate: {win_rate:.1f}%")
            
            return last_10_signals
            
        except Exception as e:
            print(f"❌ Analiz hatası: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None

if __name__ == "__main__":
    analyzer = VolensyMacdLast10Signals("SUI/USDT")
    signals = analyzer.analyze_last_10_signals(days=30)
