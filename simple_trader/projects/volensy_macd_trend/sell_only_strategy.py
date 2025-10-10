#!/usr/bin/env python3
"""
Volensy MACD Sadece SELL Stratejisi + Optimizasyon
- Sadece SELL sinyalleri
- SELL zararlarını minimize et
- RSI, MACD, EMA trend filtreleri
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

class VolensyMacdSellOnlyStrategy:
    def __init__(self, symbol="SUI/USDT", initial_balance=1000):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = None
        self.trades = []
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
        self.position_size_percent = 0.1  # %10 of balance per trade
        
        # SELL Optimizasyon Filtreleri
        self.sell_only = True  # Sadece SELL
        self.min_rsi_for_sell = 25  # RSI minimum threshold
        self.max_rsi_for_sell = 50  # RSI maximum threshold
        self.min_macd_divergence = -0.01  # MACD minimum divergence
        self.strong_bear_trend = True  # Güçlü bear trend gerekli
        
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
    
    def generate_sell_signal(self, df, current_time):
        """Sadece SELL sinyali üret - Optimize edilmiş"""
        try:
            if len(df) < self.min_bars:
                return None
            
            # Volensy MACD hesapla
            indicators = self.calculate_volensy_macd(df)
            if indicators is None:
                return None
            
            close = df['close'].iloc[-1]
            ema_trend = indicators['ema_trend'].iloc[-1]
            macd = indicators['macd'].iloc[-1]
            macd_signal = indicators['macd_signal'].iloc[-1]
            rsi = indicators['rsi'].iloc[-1]
            
            # Pine Script koşulları
            is_bear_trend = close < ema_trend
            is_bear_momentum = rsi < 50
            is_bear_power = macd < macd_signal
            not_oversold = rsi > self.rsi_oversold
            
            # Skor hesapla
            bear_score = (1 if is_bear_trend else 0) + (1 if is_bear_momentum else 0) + (1 if is_bear_power else 0)
            
            # Temel SELL koşulu
            basic_sell = bear_score == 3 and not_oversold
            
            if not basic_sell:
                return None
            
            # SELL Optimizasyon Filtreleri
            filters_passed = 0
            total_filters = 0
            
            # 1. RSI Filtresi - Çok aşırı satım olmamalı
            total_filters += 1
            if self.min_rsi_for_sell <= rsi <= self.max_rsi_for_sell:
                filters_passed += 1
                rsi_filter = True
            else:
                rsi_filter = False
            
            # 2. MACD Divergence Filtresi - Güçlü bearish momentum
            total_filters += 1
            if macd <= self.min_macd_divergence:
                filters_passed += 1
                macd_filter = True
            else:
                macd_filter = False
            
            # 3. Güçlü Bear Trend Filtresi - Price EMA'dan uzak olmalı
            total_filters += 1
            price_ema_distance = abs(close - ema_trend) / ema_trend * 100
            if self.strong_bear_trend and price_ema_distance >= 1.0:  # En az %1 uzaklık
                filters_passed += 1
                trend_filter = True
            else:
                trend_filter = False
            
            # 4. MACD Signal Divergence - MACD signal'dan uzak olmalı
            total_filters += 1
            macd_signal_distance = abs(macd - macd_signal)
            if macd_signal_distance >= 0.005:  # En az 0.005 divergence
                filters_passed += 1
                signal_filter = True
            else:
                signal_filter = False
            
            # En az 3/4 filtre geçmeli
            if filters_passed >= 3:
                signal_strength = abs(close - ema_trend) / close * 100
                return {
                    'signal': 'SELL',
                    'price': close,
                    'strength': signal_strength,
                    'rsi': rsi,
                    'macd': macd,
                    'macd_signal': macd_signal,
                    'ema_trend': ema_trend,
                    'bear_score': bear_score,
                    'filters_passed': filters_passed,
                    'total_filters': total_filters,
                    'rsi_filter': rsi_filter,
                    'macd_filter': macd_filter,
                    'trend_filter': trend_filter,
                    'signal_filter': signal_filter,
                    'price_ema_distance': price_ema_distance,
                    'macd_signal_distance': macd_signal_distance
                }
            
            return None
            
        except Exception as e:
            print(f"❌ SELL sinyal üretme hatası: {e}")
            return None
    
    def open_position(self, signal_data, current_time):
        """Pozisyon aç"""
        try:
            if self.position:
                return False  # Zaten pozisyon var
            
            signal = signal_data['signal']
            price = signal_data['price']
            
            # Pozisyon boyutu hesapla
            position_value = self.balance * self.position_size_percent
            size = position_value / price
            
            # SL/TP fiyatları hesapla (SELL için)
            sl_price = price * (1 + self.sl_percent)
            tp_price = price * (1 - self.tp_percent)
            
            # Pozisyon aç
            self.position = {
                'side': 'short',
                'entry_price': price,
                'entry_time': current_time,
                'size': size,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'signal_data': signal_data
            }
            
            turkey_time = current_time + timedelta(hours=3)
            print(f"🚀 {signal} Pozisyon Açıldı @ ${price:.4f} ({turkey_time.strftime('%m/%d %H:%M TRT')})")
            print(f"   📊 Size: {size:.2f}")
            print(f"   🛡️ SL: ${sl_price:.4f}")
            print(f"   🎯 TP: ${tp_price:.4f}")
            print(f"   💰 Balance: ${self.balance:.2f}")
            print(f"   🎯 RSI: {signal_data['rsi']:.1f}")
            print(f"   📊 MACD: {signal_data['macd']:.6f}")
            print(f"   📊 Filters: {signal_data['filters_passed']}/{signal_data['total_filters']}")
            print(f"   📊 RSI Filter: {'✅' if signal_data['rsi_filter'] else '❌'}")
            print(f"   📊 MACD Filter: {'✅' if signal_data['macd_filter'] else '❌'}")
            print(f"   📊 Trend Filter: {'✅' if signal_data['trend_filter'] else '❌'}")
            print(f"   📊 Signal Filter: {'✅' if signal_data['signal_filter'] else '❌'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Pozisyon açma hatası: {e}")
            return False
    
    def check_position_exit(self, current_price, current_time):
        """Pozisyon çıkış kontrolü"""
        try:
            if not self.position:
                return None
            
            side = self.position['side']
            entry_price = self.position['entry_price']
            sl_price = self.position['sl_price']
            tp_price = self.position['tp_price']
            
            exit_reason = None
            exit_price = None
            
            # SELL pozisyonu için
            if current_price >= sl_price:
                exit_reason = 'SL'
                exit_price = sl_price
            elif current_price <= tp_price:
                exit_reason = 'TP'
                exit_price = tp_price
            
            if exit_reason:
                # Pozisyonu kapat
                pnl = self.calculate_pnl(entry_price, exit_price, side)
                self.balance += pnl
                
                trade = {
                    'entry_time': self.position['entry_time'],
                    'exit_time': current_time,
                    'side': side,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'pnl': pnl,
                    'balance_after': self.balance,
                    'signal_data': self.position['signal_data']
                }
                
                self.trades.append(trade)
                
                turkey_time = current_time + timedelta(hours=3)
                print(f"🔄 Pozisyon Kapandı: {exit_reason} ({turkey_time.strftime('%m/%d %H:%M TRT')})")
                print(f"   📈 Side: {side.upper()}")
                print(f"   💰 Entry: ${entry_price:.4f} -> Exit: ${exit_price:.4f}")
                print(f"   💸 PnL: ${pnl:.2f}")
                print(f"   💰 Balance: ${self.balance:.2f}")
                
                self.position = None
                return trade
            
            return None
            
        except Exception as e:
            print(f"❌ Pozisyon çıkış kontrolü hatası: {e}")
            return None
    
    def calculate_pnl(self, entry_price, exit_price, side):
        """PnL hesapla"""
        try:
            # SELL pozisyonu için
            pnl_percent = (entry_price - exit_price) / entry_price
            
            position_value = self.balance * self.position_size_percent
            pnl = position_value * pnl_percent
            
            return pnl
            
        except Exception as e:
            print(f"❌ PnL hesaplama hatası: {e}")
            return 0
    
    def run_backtest(self, days=30):
        """Backtest çalıştır"""
        try:
            print(f"🚀 Volensy MACD Sadece SELL Stratejisi - {self.symbol}")
            print(f"📅 Son {days} günlük veri")
            print(f"💰 Başlangıç Balance: ${self.initial_balance}")
            print(f"📊 Pozisyon Boyutu: %{self.position_size_percent * 100}")
            print(f"🛡️ Stop Loss: %{self.sl_percent * 100}")
            print(f"🎯 Take Profit: %{self.tp_percent * 100}")
            print(f"📊 SELL Filtreleri:")
            print(f"   🎯 RSI Range: {self.min_rsi_for_sell}-{self.max_rsi_for_sell}")
            print(f"   📊 MACD Min: {self.min_macd_divergence}")
            print(f"   📊 Trend Distance: ≥1.0%")
            print(f"   📊 Signal Distance: ≥0.005")
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
            print()
            
            # Backtest döngüsü
            start_idx = self.min_bars
            
            for i in range(start_idx, len(df)):
                current_time = df.index[i]
                current_price = df['close'].iloc[i]
                
                # Mevcut pozisyonu kontrol et
                if self.position:
                    exit_trade = self.check_position_exit(current_price, current_time)
                    if exit_trade:
                        continue  # Pozisyon kapandı, yeni sinyal bekle
                
                # Yeni sinyal kontrolü (sadece pozisyon yoksa)
                if not self.position:
                    # Tüm veriyi al (baştan itibaren)
                    signal_df = df.iloc[:i+1]
                    signal_data = self.generate_sell_signal(signal_df, current_time)
                    
                    if signal_data:
                        self.open_position(signal_data, current_time)
            
            # Son pozisyonu kapat (eğer varsa)
            if self.position:
                final_price = df['close'].iloc[-1]
                final_time = df.index[-1]
                exit_trade = self.check_position_exit(final_price, final_time)
                if exit_trade:
                    print(f"🔄 Son pozisyon kapatıldı (backtest sonu)")
            
            # Sonuçları analiz et
            self.analyze_results()
            
            return self.trades
            
        except Exception as e:
            print(f"❌ Backtest hatası: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None
    
    def analyze_results(self):
        """Sonuçları analiz et"""
        try:
            print(f"\n📊 SELL STRATEJİSİ SONUÇLARI:")
            print("="*80)
            
            if not self.trades:
                print("❌ Hiç işlem yapılmadı")
                return
            
            # Temel istatistikler
            total_trades = len(self.trades)
            winning_trades = [t for t in self.trades if t['pnl'] > 0]
            losing_trades = [t for t in self.trades if t['pnl'] < 0]
            
            win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
            
            total_pnl = sum(t['pnl'] for t in self.trades)
            total_return = (total_pnl / self.initial_balance) * 100
            
            avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
            
            profit_factor = abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades else float('inf')
            
            # Maksimum drawdown
            balance_history = [self.initial_balance]
            for trade in self.trades:
                balance_history.append(trade['balance_after'])
            
            peak = balance_history[0]
            max_drawdown = 0
            for balance in balance_history:
                if balance > peak:
                    peak = balance
                drawdown = (peak - balance) / peak * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            print(f"📈 Toplam İşlem: {total_trades}")
            print(f"✅ Kazanan İşlem: {len(winning_trades)}")
            print(f"❌ Kaybeden İşlem: {len(losing_trades)}")
            print(f"🎯 Win Rate: {win_rate:.1f}%")
            print(f"💰 Toplam PnL: ${total_pnl:.2f}")
            print(f"📊 Toplam Return: {total_return:.2f}%")
            print(f"📈 Ortalama Kazanç: ${avg_win:.2f}")
            print(f"📉 Ortalama Kayıp: ${avg_loss:.2f}")
            print(f"⚖️ Profit Factor: {profit_factor:.2f}")
            print(f"📉 Max Drawdown: {max_drawdown:.2f}%")
            print(f"💰 Final Balance: ${self.balance:.2f}")
            
            # İşlem detayları
            print(f"\n📋 İŞLEM DETAYLARI:")
            print("="*80)
            
            for i, trade in enumerate(self.trades, 1):
                entry_time_tr = trade['entry_time'] + timedelta(hours=3)
                exit_time_tr = trade['exit_time'] + timedelta(hours=3)
                
                print(f"{i}. {entry_time_tr.strftime('%m/%d %H:%M')} - {exit_time_tr.strftime('%m/%d %H:%M')} TRT")
                print(f"   📈 {trade['side'].upper()} @ ${trade['entry_price']:.4f} -> ${trade['exit_price']:.4f}")
                print(f"   🎯 {trade['exit_reason']} | PnL: ${trade['pnl']:.2f}")
                print(f"   💰 Balance: ${trade['balance_after']:.2f}")
                print(f"   🎯 RSI: {trade['signal_data']['rsi']:.1f}")
                print(f"   📊 MACD: {trade['signal_data']['macd']:.6f}")
                print(f"   📊 Filters: {trade['signal_data']['filters_passed']}/{trade['signal_data']['total_filters']}")
                print()
            
        except Exception as e:
            print(f"❌ Sonuç analizi hatası: {e}")

if __name__ == "__main__":
    backtest = VolensyMacdSellOnlyStrategy("SUI/USDT", initial_balance=1000)
    trades = backtest.run_backtest(days=30)
