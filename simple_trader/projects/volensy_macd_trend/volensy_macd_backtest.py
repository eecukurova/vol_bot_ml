#!/usr/bin/env python3
"""
Volensy MACD Backtest - SUI/USDT için timeframe optimizasyonu
"""

import ccxt
import pandas as pd
import numpy as np
import json
import sys
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add common path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../common')))

class VolensyMacdBacktest:
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
        self.atr_period = 14
        
        # Test edilecek timeframes
        self.timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d']
        
        # Backtest parametreleri
        self.trade_amount_usd = 100
        self.leverage = 10
        self.sl_percent = 0.01  # 1%
        self.tp_percent = 0.004  # 0.4%
        
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
    
    def generate_signals(self, df):
        """Volensy MACD sinyalleri üret"""
        try:
            if len(df) < max(self.ema_trend_period, self.macd_slow, self.rsi_period):
                return pd.Series(['HOLD'] * len(df), index=df.index)
            
            indicators = self.calculate_volensy_macd(df)
            if indicators is None:
                return pd.Series(['HOLD'] * len(df), index=df.index)
            
            close = df['close']
            ema_trend = indicators['ema_trend']
            macd = indicators['macd']
            macd_signal = indicators['macd_signal']
            rsi = indicators['rsi']
            
            signals = pd.Series(['HOLD'] * len(df), index=df.index)
            
            for i in range(max(self.ema_trend_period, self.macd_slow, self.rsi_period), len(df)):
                # Pine Script koşulları
                is_bull_trend = close.iloc[i] > ema_trend.iloc[i]
                is_bear_trend = close.iloc[i] < ema_trend.iloc[i]
                
                is_bull_momentum = rsi.iloc[i] > 50
                is_bear_momentum = rsi.iloc[i] < 50
                
                is_bull_power = macd.iloc[i] > macd_signal.iloc[i]
                is_bear_power = macd.iloc[i] < macd_signal.iloc[i]
                
                not_overbought = rsi.iloc[i] < self.rsi_overbought
                not_oversold = rsi.iloc[i] > self.rsi_oversold
                
                # Skor hesapla
                bull_score = (1 if is_bull_trend else 0) + (1 if is_bull_momentum else 0) + (1 if is_bull_power else 0)
                bear_score = (1 if is_bear_trend else 0) + (1 if is_bear_momentum else 0) + (1 if is_bear_power else 0)
                
                # Sinyaller
                if bull_score == 3 and not_overbought:
                    signals.iloc[i] = 'BUY'
                elif bear_score == 3 and not_oversold:
                    signals.iloc[i] = 'SELL'
            
            return signals
            
        except Exception as e:
            print(f"❌ Sinyal üretme hatası: {e}")
            return pd.Series(['HOLD'] * len(df), index=df.index)
    
    def backtest_timeframe(self, timeframe, days=30):
        """Belirli timeframe için backtest yap"""
        try:
            print(f"\n🔄 {timeframe} timeframe backtest başlatılıyor...")
            
            # Veri al
            limit = min(1000, days * 24 * 60 // self.get_timeframe_minutes(timeframe))
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            
            if not ohlcv:
                print(f"❌ {timeframe} için veri alınamadı")
                return None
            
            # DataFrame oluştur
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            print(f"📊 {len(df)} bar verisi alındı ({df.index[0]} - {df.index[-1]})")
            
            # Sinyalleri üret
            signals = self.generate_signals(df)
            
            # Backtest simülasyonu
            trades = []
            position = None
            
            for i in range(len(df)):
                current_price = df['close'].iloc[i]
                signal = signals.iloc[i]
                
                if signal == 'BUY' and position is None:
                    # LONG pozisyon aç
                    position = {
                        'type': 'LONG',
                        'entry_price': current_price,
                        'entry_time': df.index[i],
                        'size': self.trade_amount_usd / current_price,
                        'sl': current_price * (1 - self.sl_percent),
                        'tp': current_price * (1 + self.tp_percent)
                    }
                    
                elif signal == 'SELL' and position is None:
                    # SHORT pozisyon aç
                    position = {
                        'type': 'SHORT',
                        'entry_price': current_price,
                        'entry_time': df.index[i],
                        'size': self.trade_amount_usd / current_price,
                        'sl': current_price * (1 + self.sl_percent),
                        'tp': current_price * (1 - self.tp_percent)
                    }
                
                elif position is not None:
                    # Pozisyon kontrolü
                    exit_reason = None
                    exit_price = current_price
                    
                    if position['type'] == 'LONG':
                        if current_price <= position['sl']:
                            exit_reason = 'SL'
                        elif current_price >= position['tp']:
                            exit_reason = 'TP'
                    else:  # SHORT
                        if current_price >= position['sl']:
                            exit_reason = 'SL'
                        elif current_price <= position['tp']:
                            exit_reason = 'TP'
                    
                    if exit_reason:
                        # Pozisyon kapat
                        pnl = self.calculate_pnl(position, exit_price)
                        
                        trade = {
                            'entry_time': position['entry_time'],
                            'exit_time': df.index[i],
                            'type': position['type'],
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'exit_reason': exit_reason,
                            'pnl': pnl,
                            'pnl_percent': (pnl / self.trade_amount_usd) * 100
                        }
                        
                        trades.append(trade)
                        position = None
            
            # Son pozisyon varsa kapat
            if position is not None:
                pnl = self.calculate_pnl(position, df['close'].iloc[-1])
                trade = {
                    'entry_time': position['entry_time'],
                    'exit_time': df.index[-1],
                    'type': position['type'],
                    'entry_price': position['entry_price'],
                    'exit_price': df['close'].iloc[-1],
                    'exit_reason': 'END',
                    'pnl': pnl,
                    'pnl_percent': (pnl / self.trade_amount_usd) * 100
                }
                trades.append(trade)
            
            return self.analyze_results(trades, timeframe)
            
        except Exception as e:
            print(f"❌ {timeframe} backtest hatası: {e}")
            return None
    
    def calculate_pnl(self, position, exit_price):
        """PnL hesapla"""
        if position['type'] == 'LONG':
            return (exit_price - position['entry_price']) * position['size']
        else:  # SHORT
            return (position['entry_price'] - exit_price) * position['size']
    
    def analyze_results(self, trades, timeframe):
        """Backtest sonuçlarını analiz et"""
        if not trades:
            return {
                'timeframe': timeframe,
                'total_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'max_drawdown': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0
            }
        
        df_trades = pd.DataFrame(trades)
        
        # Temel istatistikler
        total_trades = len(trades)
        winning_trades = len(df_trades[df_trades['pnl'] > 0])
        losing_trades = len(df_trades[df_trades['pnl'] < 0])
        
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        avg_pnl = df_trades['pnl'].mean()
        
        # Profit Factor
        gross_profit = df_trades[df_trades['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(df_trades[df_trades['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Drawdown
        cumulative_pnl = df_trades['pnl'].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = (cumulative_pnl - running_max) / running_max * 100
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
        
        # Sharpe Ratio (basit)
        returns = df_trades['pnl_percent']
        sharpe_ratio = returns.mean() / returns.std() if returns.std() > 0 else 0
        
        return {
            'timeframe': timeframe,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss
        }
    
    def get_timeframe_minutes(self, timeframe):
        """Timeframe'i dakikaya çevir"""
        timeframe_map = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '12h': 720, '1d': 1440
        }
        return timeframe_map.get(timeframe, 60)
    
    def run_backtest(self, days=30):
        """Tüm timeframes için backtest çalıştır"""
        print(f"🚀 Volensy MACD Backtest - {self.symbol}")
        print(f"📅 {days} günlük veri")
        print(f"💰 Trade Amount: ${self.trade_amount_usd}")
        print(f"🛡️ SL: {self.sl_percent*100}% | TP: {self.tp_percent*100}%")
        print("="*80)
        
        results = []
        
        for timeframe in self.timeframes:
            try:
                result = self.backtest_timeframe(timeframe, days)
                if result:
                    results.append(result)
                    self.print_timeframe_result(result)
            except Exception as e:
                print(f"❌ {timeframe} hatası: {e}")
        
        # En iyi timeframes'i bul
        if results:
            print("\n" + "="*80)
            print("🏆 EN İYİ TIMEFRAME'LER:")
            print("="*80)
            
            # Total PnL'e göre sırala
            results_sorted = sorted(results, key=lambda x: x['total_pnl'], reverse=True)
            
            for i, result in enumerate(results_sorted[:5]):
                print(f"\n{i+1}. {result['timeframe']} - PnL: ${result['total_pnl']:.2f}")
                print(f"   📊 Trades: {result['total_trades']} | Win Rate: {result['win_rate']:.1f}%")
                print(f"   💰 Avg PnL: ${result['avg_pnl']:.2f} | Profit Factor: {result['profit_factor']:.2f}")
                print(f"   📉 Max DD: {result['max_drawdown']:.1f}% | Sharpe: {result['sharpe_ratio']:.2f}")
            
            # En iyi timeframe'i öner
            best = results_sorted[0]
            print(f"\n🎯 ÖNERİLEN TIMEFRAME: {best['timeframe']}")
            print(f"   💰 Toplam PnL: ${best['total_pnl']:.2f}")
            print(f"   📊 Win Rate: {best['win_rate']:.1f}%")
            print(f"   🛡️ Profit Factor: {best['profit_factor']:.2f}")
            
            return best
        
        return None
    
    def print_timeframe_result(self, result):
        """Timeframe sonucunu yazdır"""
        print(f"\n📊 {result['timeframe']} Sonuçları:")
        print(f"   💰 Total PnL: ${result['total_pnl']:.2f}")
        print(f"   📈 Trades: {result['total_trades']} (W:{result['winning_trades']} L:{result['losing_trades']})")
        print(f"   🎯 Win Rate: {result['win_rate']:.1f}%")
        print(f"   📊 Avg PnL: ${result['avg_pnl']:.2f}")
        print(f"   🛡️ Profit Factor: {result['profit_factor']:.2f}")
        print(f"   📉 Max Drawdown: {result['max_drawdown']:.1f}%")

if __name__ == "__main__":
    backtest = VolensyMacdBacktest("SUI/USDT")
    best_timeframe = backtest.run_backtest(days=30)
