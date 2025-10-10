#!/usr/bin/env python3
"""
Volensy MACD Stop Loss Analizi
- Stop loss olan işlemlerin ortak özelliklerini bul
- Take profit olan işlemlerle karşılaştır
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

class VolensyMacdStopLossAnalyzer:
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
        self.sl_percent = 0.02  # 2%
        self.tp_percent = 0.04  # 4%
        
        # Minimum veri gereksinimi
        self.min_bars = max(self.ema_trend_period, self.macd_slow, self.rsi_period)
        
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
    
    def analyze_stop_loss_patterns(self, days=30):
        """Stop loss olan işlemlerin pattern'lerini analiz et"""
        try:
            print(f"🔍 Volensy MACD Stop Loss Analizi - {self.symbol}")
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
            
            # Tüm işlemleri simüle et
            position = None
            trades = []
            start_idx = self.min_bars
            
            for i in range(start_idx, len(df)):
                current_time = df.index[i]
                current_price = df['close'].iloc[i]
                
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
                        # Pozisyonu kapat
                        trade = {
                            'entry_time': position['entry_time'],
                            'exit_time': current_time,
                            'side': side,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'exit_reason': exit_reason,
                            'signal_data': position['signal_data']
                        }
                        
                        trades.append(trade)
                        position = None
                        continue
                
                # Yeni sinyal kontrolü (sadece pozisyon yoksa)
                if not position:
                    # Tüm veriyi al (baştan itibaren)
                    signal_df = df.iloc[:i+1]
                    
                    if len(signal_df) < self.min_bars:
                        continue
                    
                    # Volensy MACD hesapla
                    indicators = self.calculate_volensy_macd(signal_df)
                    if indicators is None:
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
                    
                    if signal:
                        # SL/TP fiyatları hesapla
                        if signal == 'BUY':
                            sl_price = close * (1 - self.sl_percent)
                            tp_price = close * (1 + self.tp_percent)
                        else:  # SELL
                            sl_price = close * (1 + self.sl_percent)
                            tp_price = close * (1 - self.tp_percent)
                        
                        signal_data = {
                            'signal': signal,
                            'price': close,
                            'rsi': rsi,
                            'macd': macd,
                            'macd_signal': macd_signal,
                            'ema_trend': ema_trend,
                            'bull_score': bull_score,
                            'bear_score': bear_score,
                            'is_bull_trend': is_bull_trend,
                            'is_bear_trend': is_bear_trend,
                            'is_bull_momentum': is_bull_momentum,
                            'is_bear_momentum': is_bear_momentum,
                            'is_bull_power': is_bull_power,
                            'is_bear_power': is_bear_power,
                            'not_overbought': not_overbought,
                            'not_oversold': not_oversold
                        }
                        
                        position = {
                            'side': 'long' if signal == 'BUY' else 'short',
                            'entry_price': close,
                            'entry_time': current_time,
                            'sl_price': sl_price,
                            'tp_price': tp_price,
                            'signal_data': signal_data
                        }
            
            # Son pozisyonu kapat (eğer varsa)
            if position:
                final_price = df['close'].iloc[-1]
                final_time = df.index[-1]
                side = position['side']
                entry_price = position['entry_price']
                sl_price = position['sl_price']
                tp_price = position['tp_price']
                
                exit_reason = None
                exit_price = None
                
                if side == 'long':
                    if final_price <= sl_price:
                        exit_reason = 'SL'
                        exit_price = sl_price
                    elif final_price >= tp_price:
                        exit_reason = 'TP'
                        exit_price = tp_price
                else:  # short
                    if final_price >= sl_price:
                        exit_reason = 'SL'
                        exit_price = sl_price
                    elif final_price <= tp_price:
                        exit_reason = 'TP'
                        exit_price = tp_price
                
                if exit_reason:
                    trade = {
                        'entry_time': position['entry_time'],
                        'exit_time': final_time,
                        'side': side,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'signal_data': position['signal_data']
                    }
                    trades.append(trade)
            
            # Analiz et
            self.analyze_trades(trades)
            
            return trades
            
        except Exception as e:
            print(f"❌ Analiz hatası: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None
    
    def analyze_trades(self, trades):
        """İşlemleri analiz et"""
        try:
            print(f"\n📊 İŞLEM ANALİZİ:")
            print("="*80)
            
            if not trades:
                print("❌ Hiç işlem yapılmadı")
                return
            
            # Stop Loss ve Take Profit işlemlerini ayır
            sl_trades = [t for t in trades if t['exit_reason'] == 'SL']
            tp_trades = [t for t in trades if t['exit_reason'] == 'TP']
            
            print(f"📈 Toplam İşlem: {len(trades)}")
            print(f"❌ Stop Loss: {len(sl_trades)}")
            print(f"✅ Take Profit: {len(tp_trades)}")
            
            # BUY ve SELL'i ayır
            buy_trades = [t for t in trades if t['side'] == 'long']
            sell_trades = [t for t in trades if t['side'] == 'short']
            
            buy_sl = [t for t in buy_trades if t['exit_reason'] == 'SL']
            buy_tp = [t for t in buy_trades if t['exit_reason'] == 'TP']
            sell_sl = [t for t in sell_trades if t['exit_reason'] == 'SL']
            sell_tp = [t for t in sell_trades if t['exit_reason'] == 'TP']
            
            print(f"\n📊 BUY İŞLEMLERİ:")
            print(f"   Toplam: {len(buy_trades)}")
            print(f"   ❌ Stop Loss: {len(buy_sl)}")
            print(f"   ✅ Take Profit: {len(buy_tp)}")
            if len(buy_trades) > 0:
                buy_win_rate = len(buy_tp) / len(buy_trades) * 100
                print(f"   🎯 Win Rate: {buy_win_rate:.1f}%")
            
            print(f"\n📊 SELL İŞLEMLERİ:")
            print(f"   Toplam: {len(sell_trades)}")
            print(f"   ❌ Stop Loss: {len(sell_sl)}")
            print(f"   ✅ Take Profit: {len(sell_tp)}")
            if len(sell_trades) > 0:
                sell_win_rate = len(sell_tp) / len(sell_trades) * 100
                print(f"   🎯 Win Rate: {sell_win_rate:.1f}%")
            
            # Stop Loss olan işlemlerin ortak özelliklerini analiz et
            print(f"\n🔍 STOP LOSS ANALİZİ:")
            print("="*80)
            
            if sl_trades:
                print(f"❌ Stop Loss Olan İşlemler ({len(sl_trades)}):")
                print()
                
                for i, trade in enumerate(sl_trades, 1):
                    entry_time_tr = trade['entry_time'] + timedelta(hours=3)
                    signal_data = trade['signal_data']
                    
                    print(f"{i}. {entry_time_tr.strftime('%m/%d %H:%M TRT')} - {trade['side'].upper()}")
                    print(f"   💰 Entry: ${trade['entry_price']:.4f}")
                    print(f"   🎯 RSI: {signal_data['rsi']:.1f}")
                    print(f"   📊 MACD: {signal_data['macd']:.6f}")
                    print(f"   📉 MACD Signal: {signal_data['macd_signal']:.6f}")
                    print(f"   📈 EMA Trend: ${signal_data['ema_trend']:.4f}")
                    print(f"   🎯 Bull Score: {signal_data['bull_score']}/3")
                    print(f"   🎯 Bear Score: {signal_data['bear_score']}/3")
                    print(f"   📊 Trend: {'BULL' if signal_data['is_bull_trend'] else 'BEAR'}")
                    print(f"   📊 Momentum: {'BULL' if signal_data['is_bull_momentum'] else 'BEAR'}")
                    print(f"   📊 Power: {'BULL' if signal_data['is_bull_power'] else 'BEAR'}")
                    print(f"   🚫 Overbought: {not signal_data['not_overbought']}")
                    print(f"   🚫 Oversold: {not signal_data['not_oversold']}")
                    print("   " + "-"*60)
                
                # Ortak özellikleri bul
                print(f"\n🔍 STOP LOSS ORTAK ÖZELLİKLER:")
                print("="*80)
                
                # RSI analizi
                sl_rsi_values = [t['signal_data']['rsi'] for t in sl_trades]
                avg_sl_rsi = np.mean(sl_rsi_values)
                print(f"📊 Ortalama RSI: {avg_sl_rsi:.1f}")
                
                # MACD analizi
                sl_macd_values = [t['signal_data']['macd'] for t in sl_trades]
                avg_sl_macd = np.mean(sl_macd_values)
                print(f"📊 Ortalama MACD: {avg_sl_macd:.6f}")
                
                # Trend analizi
                sl_bull_trend_count = sum(1 for t in sl_trades if t['signal_data']['is_bull_trend'])
                sl_bear_trend_count = sum(1 for t in sl_trades if t['signal_data']['is_bear_trend'])
                print(f"📊 Bull Trend: {sl_bull_trend_count}/{len(sl_trades)}")
                print(f"📊 Bear Trend: {sl_bear_trend_count}/{len(sl_trades)}")
                
                # Momentum analizi
                sl_bull_momentum_count = sum(1 for t in sl_trades if t['signal_data']['is_bull_momentum'])
                sl_bear_momentum_count = sum(1 for t in sl_trades if t['signal_data']['is_bear_momentum'])
                print(f"📊 Bull Momentum: {sl_bull_momentum_count}/{len(sl_trades)}")
                print(f"📊 Bear Momentum: {sl_bear_momentum_count}/{len(sl_trades)}")
                
                # Power analizi
                sl_bull_power_count = sum(1 for t in sl_trades if t['signal_data']['is_bull_power'])
                sl_bear_power_count = sum(1 for t in sl_trades if t['signal_data']['is_bear_power'])
                print(f"📊 Bull Power: {sl_bull_power_count}/{len(sl_trades)}")
                print(f"📊 Bear Power: {sl_bear_power_count}/{len(sl_trades)}")
            
            # Take Profit olan işlemlerin ortak özelliklerini analiz et
            print(f"\n✅ TAKE PROFIT ANALİZİ:")
            print("="*80)
            
            if tp_trades:
                print(f"✅ Take Profit Olan İşlemler ({len(tp_trades)}):")
                print()
                
                for i, trade in enumerate(tp_trades, 1):
                    entry_time_tr = trade['entry_time'] + timedelta(hours=3)
                    signal_data = trade['signal_data']
                    
                    print(f"{i}. {entry_time_tr.strftime('%m/%d %H:%M TRT')} - {trade['side'].upper()}")
                    print(f"   💰 Entry: ${trade['entry_price']:.4f}")
                    print(f"   🎯 RSI: {signal_data['rsi']:.1f}")
                    print(f"   📊 MACD: {signal_data['macd']:.6f}")
                    print(f"   📉 MACD Signal: {signal_data['macd_signal']:.6f}")
                    print(f"   📈 EMA Trend: ${signal_data['ema_trend']:.4f}")
                    print(f"   🎯 Bull Score: {signal_data['bull_score']}/3")
                    print(f"   🎯 Bear Score: {signal_data['bear_score']}/3")
                    print(f"   📊 Trend: {'BULL' if signal_data['is_bull_trend'] else 'BEAR'}")
                    print(f"   📊 Momentum: {'BULL' if signal_data['is_bull_momentum'] else 'BEAR'}")
                    print(f"   📊 Power: {'BULL' if signal_data['is_bull_power'] else 'BEAR'}")
                    print(f"   🚫 Overbought: {not signal_data['not_overbought']}")
                    print(f"   🚫 Oversold: {not signal_data['not_oversold']}")
                    print("   " + "-"*60)
                
                # Ortak özellikleri bul
                print(f"\n✅ TAKE PROFIT ORTAK ÖZELLİKLER:")
                print("="*80)
                
                # RSI analizi
                tp_rsi_values = [t['signal_data']['rsi'] for t in tp_trades]
                avg_tp_rsi = np.mean(tp_rsi_values)
                print(f"📊 Ortalama RSI: {avg_tp_rsi:.1f}")
                
                # MACD analizi
                tp_macd_values = [t['signal_data']['macd'] for t in tp_trades]
                avg_tp_macd = np.mean(tp_macd_values)
                print(f"📊 Ortalama MACD: {avg_tp_macd:.6f}")
                
                # Trend analizi
                tp_bull_trend_count = sum(1 for t in tp_trades if t['signal_data']['is_bull_trend'])
                tp_bear_trend_count = sum(1 for t in tp_trades if t['signal_data']['is_bear_trend'])
                print(f"📊 Bull Trend: {tp_bull_trend_count}/{len(tp_trades)}")
                print(f"📊 Bear Trend: {tp_bear_trend_count}/{len(tp_trades)}")
                
                # Momentum analizi
                tp_bull_momentum_count = sum(1 for t in tp_trades if t['signal_data']['is_bull_momentum'])
                tp_bear_momentum_count = sum(1 for t in tp_trades if t['signal_data']['is_bear_momentum'])
                print(f"📊 Bull Momentum: {tp_bull_momentum_count}/{len(tp_trades)}")
                print(f"📊 Bear Momentum: {tp_bear_momentum_count}/{len(tp_trades)}")
                
                # Power analizi
                tp_bull_power_count = sum(1 for t in tp_trades if t['signal_data']['is_bull_power'])
                tp_bear_power_count = sum(1 for t in tp_trades if t['signal_data']['is_bear_power'])
                print(f"📊 Bull Power: {tp_bull_power_count}/{len(tp_trades)}")
                print(f"📊 Bear Power: {tp_bear_power_count}/{len(tp_trades)}")
            
            # Öneriler
            print(f"\n💡 ÖNERİLER:")
            print("="*80)
            
            if sl_trades and tp_trades:
                # RSI karşılaştırması
                if avg_sl_rsi > avg_tp_rsi:
                    print(f"🔍 Stop Loss işlemlerinin RSI'si daha yüksek ({avg_sl_rsi:.1f} vs {avg_tp_rsi:.1f})")
                    print(f"   💡 RSI threshold'u düşürülebilir")
                else:
                    print(f"🔍 Take Profit işlemlerinin RSI'si daha yüksek ({avg_tp_rsi:.1f} vs {avg_sl_rsi:.1f})")
                
                # MACD karşılaştırması
                if avg_sl_macd > avg_tp_macd:
                    print(f"🔍 Stop Loss işlemlerinin MACD'si daha yüksek ({avg_sl_macd:.6f} vs {avg_tp_macd:.6f})")
                else:
                    print(f"🔍 Take Profit işlemlerinin MACD'si daha yüksek ({avg_tp_macd:.6f} vs {avg_sl_macd:.6f})")
            
            # BUY vs SELL analizi
            if len(buy_trades) > 0 and len(sell_trades) > 0:
                buy_win_rate = len(buy_tp) / len(buy_trades) * 100
                sell_win_rate = len(sell_tp) / len(sell_trades) * 100
                
                print(f"\n📊 BUY vs SELL Karşılaştırması:")
                print(f"   📈 BUY Win Rate: {buy_win_rate:.1f}%")
                print(f"   📉 SELL Win Rate: {sell_win_rate:.1f}%")
                
                if sell_win_rate > buy_win_rate:
                    print(f"   💡 SELL sinyalleri daha başarılı! Sadece SELL stratejisi düşünülebilir.")
                else:
                    print(f"   💡 BUY sinyalleri daha başarılı! BUY filtreleri iyileştirilebilir.")
            
        except Exception as e:
            print(f"❌ Analiz hatası: {e}")

if __name__ == "__main__":
    analyzer = VolensyMacdStopLossAnalyzer("SUI/USDT")
    trades = analyzer.analyze_stop_loss_patterns(days=30)
