#!/usr/bin/env python3
"""
ATR + SuperTrend Stratejisi
- ATR Trailing Stop ile sinyal üretimi
- EMA(1) crossover ile onay
- SuperTrend ile trend filtresi
- Heikin Ashi opsiyonel
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

class ATRSuperTrendStrategy:
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
        
        # ATR + SuperTrend parametreleri
        self.key_value = 3  # ATR sensitivity
        self.atr_period = 10  # ATR period
        self.use_heikin_ashi = False  # Heikin Ashi kullan
        self.supertrend_factor = 1.5  # SuperTrend multiplier
        self.ema_period = 1  # EMA period for confirmation
        
        # Trading parametreleri
        self.timeframe = '1h'
        self.sl_percent = 0.02  # 2%
        self.tp_percent = 0.04  # 4%
        self.position_size_percent = 0.1  # %10 of balance per trade
        
        # Minimum veri gereksinimi
        self.min_bars = max(self.atr_period, 50)  # ATR için yeterli veri
        
    def calculate_heikin_ashi(self, df):
        """Heikin Ashi hesapla"""
        try:
            ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
            ha_open = pd.Series(index=df.index, dtype=float)
            ha_open.iloc[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
            
            for i in range(1, len(df)):
                ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
            
            ha_high = pd.concat([df['high'], ha_open, ha_close], axis=1).max(axis=1)
            ha_low = pd.concat([df['low'], ha_open, ha_close], axis=1).min(axis=1)
            
            return pd.DataFrame({
                'open': ha_open,
                'high': ha_high,
                'low': ha_low,
                'close': ha_close
            })
            
        except Exception as e:
            print(f"❌ Heikin Ashi hesaplama hatası: {e}")
            return df
    
    def calculate_atr_trailing_stop(self, df):
        """ATR Trailing Stop hesapla"""
        try:
            # ATR hesapla
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=self.atr_period).mean()
            
            # ATR Trailing Stop hesapla
            src = df['close']
            n_loss = self.key_value * atr
            
            atr_trailing_stop = pd.Series(index=df.index, dtype=float)
            atr_trailing_stop.iloc[0] = src.iloc[0] - n_loss.iloc[0]
            
            for i in range(1, len(df)):
                prev_stop = atr_trailing_stop.iloc[i-1]
                current_src = src.iloc[i]
                prev_src = src.iloc[i-1]
                current_n_loss = n_loss.iloc[i]
                
                if current_src > prev_stop and prev_src > prev_stop:
                    atr_trailing_stop.iloc[i] = max(prev_stop, current_src - current_n_loss)
                elif current_src < prev_stop and prev_src < prev_stop:
                    atr_trailing_stop.iloc[i] = min(prev_stop, current_src + current_n_loss)
                elif current_src > prev_stop:
                    atr_trailing_stop.iloc[i] = current_src - current_n_loss
                else:
                    atr_trailing_stop.iloc[i] = current_src + current_n_loss
            
            return atr_trailing_stop, atr
            
        except Exception as e:
            print(f"❌ ATR Trailing Stop hesaplama hatası: {e}")
            return None, None
    
    def calculate_supertrend(self, df, atr):
        """SuperTrend hesapla"""
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            hl2 = (high + low) / 2
            supertrend_value = atr * self.supertrend_factor
            
            trend_up = hl2 - supertrend_value
            trend_down = hl2 + supertrend_value
            
            supertrend_line = pd.Series(index=df.index, dtype=float)
            supertrend_line.iloc[0] = trend_down.iloc[0]
            
            for i in range(1, len(df)):
                prev_line = supertrend_line.iloc[i-1]
                current_close = close.iloc[i]
                prev_close = close.iloc[i-1]
                
                if current_close > prev_line:
                    supertrend_line.iloc[i] = max(trend_up.iloc[i], prev_line)
                else:
                    supertrend_line.iloc[i] = min(trend_down.iloc[i], prev_line)
            
            return supertrend_line
            
        except Exception as e:
            print(f"❌ SuperTrend hesaplama hatası: {e}")
            return None
    
    def calculate_ema(self, df, period):
        """EMA hesapla"""
        try:
            return df['close'].ewm(span=period).mean()
        except Exception as e:
            print(f"❌ EMA hesaplama hatası: {e}")
            return None
    
    def generate_signals(self, df, current_time):
        """Sinyal üret"""
        try:
            if len(df) < self.min_bars:
                return None
            
            # Heikin Ashi kullan
            if self.use_heikin_ashi:
                df = self.calculate_heikin_ashi(df)
            
            # ATR Trailing Stop hesapla
            atr_trailing_stop, atr = self.calculate_atr_trailing_stop(df)
            if atr_trailing_stop is None:
                return None
            
            # SuperTrend hesapla
            supertrend_line = self.calculate_supertrend(df, atr)
            if supertrend_line is None:
                return None
            
            # EMA hesapla
            ema = self.calculate_ema(df, self.ema_period)
            if ema is None:
                return None
            
            # Mevcut değerler
            current_close = df['close'].iloc[-1]
            current_atr_stop = atr_trailing_stop.iloc[-1]
            current_ema = ema.iloc[-1]
            current_supertrend = supertrend_line.iloc[-1]
            current_atr = atr.iloc[-1]
            
            # Önceki değerler (crossover için)
            prev_close = df['close'].iloc[-2]
            prev_atr_stop = atr_trailing_stop.iloc[-2]
            prev_ema = ema.iloc[-2]
            prev_supertrend = supertrend_line.iloc[-2]
            
            # Pine Script koşulları
            # ATR Trailing Stop pozisyonu
            above_atr = current_close > current_atr_stop
            below_atr = current_close < current_atr_stop
            
            # EMA crossover koşulları
            ema_cross_above = current_ema > current_atr_stop and prev_ema <= prev_atr_stop
            ema_cross_below = current_ema < current_atr_stop and prev_ema >= prev_atr_stop
            
            # SuperTrend koşulları
            above_supertrend = current_close > current_supertrend
            below_supertrend = current_close < current_supertrend
            
            # Sinyaller
            buy_signal = above_atr and ema_cross_above and above_supertrend
            sell_signal = below_atr and ema_cross_below and below_supertrend
            
            signal = None
            if buy_signal:
                signal = 'BUY'
            elif sell_signal:
                signal = 'SELL'
            
            if signal:
                return {
                    'signal': signal,
                    'price': current_close,
                    'atr_trailing_stop': current_atr_stop,
                    'ema': current_ema,
                    'supertrend': current_supertrend,
                    'atr': current_atr,
                    'above_atr': above_atr,
                    'below_atr': below_atr,
                    'ema_cross_above': ema_cross_above,
                    'ema_cross_below': ema_cross_below,
                    'above_supertrend': above_supertrend,
                    'below_supertrend': below_supertrend
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Sinyal üretme hatası: {e}")
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
            
            # SL/TP fiyatları hesapla
            if signal == 'BUY':
                sl_price = price * (1 - self.sl_percent)
                tp_price = price * (1 + self.tp_percent)
            else:  # SELL
                sl_price = price * (1 + self.sl_percent)
                tp_price = price * (1 - self.tp_percent)
            
            # Pozisyon aç
            self.position = {
                'side': 'long' if signal == 'BUY' else 'short',
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
            print(f"   📊 ATR Stop: ${signal_data['atr_trailing_stop']:.4f}")
            print(f"   📊 EMA: ${signal_data['ema']:.4f}")
            print(f"   📊 SuperTrend: ${signal_data['supertrend']:.4f}")
            print(f"   📊 ATR: ${signal_data['atr']:.4f}")
            
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
            if side == 'long':
                pnl_percent = (exit_price - entry_price) / entry_price
            else:  # short
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
            print(f"🚀 ATR + SuperTrend Stratejisi - {self.symbol}")
            print(f"📅 Son {days} günlük veri")
            print(f"💰 Başlangıç Balance: ${self.initial_balance}")
            print(f"📊 Pozisyon Boyutu: %{self.position_size_percent * 100}")
            print(f"🛡️ Stop Loss: %{self.sl_percent * 100}")
            print(f"🎯 Take Profit: %{self.tp_percent * 100}")
            print(f"📊 ATR Key Value: {self.key_value}")
            print(f"📊 ATR Period: {self.atr_period}")
            print(f"📊 SuperTrend Factor: {self.supertrend_factor}")
            print(f"📊 EMA Period: {self.ema_period}")
            print(f"📊 Heikin Ashi: {'✅' if self.use_heikin_ashi else '❌'}")
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
                    signal_data = self.generate_signals(signal_df, current_time)
                    
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
            print(f"\n📊 ATR + SuperTrend SONUÇLARI:")
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
                print()
            
        except Exception as e:
            print(f"❌ Sonuç analizi hatası: {e}")

if __name__ == "__main__":
    backtest = ATRSuperTrendStrategy("SUI/USDT", initial_balance=1000)
    trades = backtest.run_backtest(days=30)
