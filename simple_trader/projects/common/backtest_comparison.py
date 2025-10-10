#!/usr/bin/env python3
"""
ATR SuperTrend Strategy Backtest
C3 kuralı ile ve olmadan karşılaştırma
"""

import ccxt
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

class SuperTrendBacktest:
    def __init__(self, symbol='EIGEN/USDT', timeframe='1h', days=30):
        self.symbol = symbol
        self.timeframe = timeframe
        self.days = days
        
        # Exchange
        self.exchange = ccxt.binance()
        
        # Sonuçlar
        self.results = {
            'with_c3': {'trades': [], 'stats': {}},
            'without_c3': {'trades': [], 'stats': {}}
        }
    
    def get_historical_data(self):
        """Geçmiş veriyi al"""
        since = self.exchange.milliseconds() - (self.days * 24 * 60 * 60 * 1000)
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=since)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def calculate_atr(self, df, period=14):
        """ATR hesapla"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        return tr.rolling(period).mean()
    
    def calculate_supertrend(self, df, period=14, multiplier=1.5):
        """SuperTrend hesapla"""
        atr_val = self.calculate_atr(df, period)
        hl2 = (df['high'] + df['low']) / 2
        upper = hl2 + (atr_val * multiplier)
        lower = hl2 - (atr_val * multiplier)
        
        st = pd.Series(index=df.index, dtype=float)
        for i in range(len(df)):
            if i == 0:
                st.iloc[i] = lower.iloc[i]
            else:
                if df['close'].iloc[i] > st.iloc[i-1]:
                    st.iloc[i] = max(lower.iloc[i], st.iloc[i-1])
                else:
                    st.iloc[i] = min(upper.iloc[i], st.iloc[i-1])
        return st
    
    def generate_signals(self, df, use_c3=True):
        """Sinyal üret"""
        st = self.calculate_supertrend(df)
        ema1 = df['close'].ewm(span=1).mean()
        
        signals = pd.Series(index=df.index, dtype=str)
        signals[:] = 'HOLD'
        
        for i in range(1, len(df)):
            close = df['close'].iloc[i]
            st_val = st.iloc[i]
            ema1_val = ema1.iloc[i]
            prev_ema1 = ema1.iloc[i-1]
            prev_st = st.iloc[i-1]
            
            # LONG koşulları
            long_cond1 = close > st_val
            long_cond2 = ema1_val > st_val
            long_cond3 = prev_ema1 <= prev_st
            
            # SHORT koşulları
            short_cond1 = close < st_val
            short_cond2 = ema1_val < st_val
            short_cond3 = prev_ema1 >= prev_st
            
            if use_c3:
                # C3 kuralı ile
                if long_cond1 and long_cond2 and long_cond3:
                    signals.iloc[i] = 'BUY'
                elif short_cond1 and short_cond2 and short_cond3:
                    signals.iloc[i] = 'SELL'
            else:
                # C3 kuralı olmadan
                if long_cond1 and long_cond2:
                    signals.iloc[i] = 'BUY'
                elif short_cond1 and short_cond2:
                    signals.iloc[i] = 'SELL'
        
        return signals
    
    def backtest_strategy(self, df, signals, strategy_name):
        """Stratejiyi backtest et"""
        trades = []
        position = None
        initial_balance = 10000  # $10,000 başlangıç
        balance = initial_balance
        position_size = 0.1  # %10 pozisyon
        
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            signal = signals.iloc[i]
            
            if signal == 'BUY' and position is None:
                # LONG pozisyon aç
                position = {
                    'type': 'LONG',
                    'entry_price': current_price,
                    'entry_time': df.index[i],
                    'size': balance * position_size / current_price
                }
                
            elif signal == 'SELL' and position is None:
                # SHORT pozisyon aç
                position = {
                    'type': 'SHORT',
                    'entry_price': current_price,
                    'entry_time': df.index[i],
                    'size': balance * position_size / current_price
                }
                
            elif position is not None:
                # Pozisyon kapatma koşulları
                should_close = False
                exit_reason = ''
                
                if position['type'] == 'LONG':
                    if signal == 'SELL':
                        should_close = True
                        exit_reason = 'Signal'
                    elif current_price <= position['entry_price'] * 0.994:  # %0.6 SL
                        should_close = True
                        exit_reason = 'Stop Loss'
                    elif current_price >= position['entry_price'] * 1.006:  # %0.6 TP
                        should_close = True
                        exit_reason = 'Take Profit'
                        
                elif position['type'] == 'SHORT':
                    if signal == 'BUY':
                        should_close = True
                        exit_reason = 'Signal'
                    elif current_price >= position['entry_price'] * 1.006:  # %0.6 SL
                        should_close = True
                        exit_reason = 'Stop Loss'
                    elif current_price <= position['entry_price'] * 0.994:  # %0.6 TP
                        should_close = True
                        exit_reason = 'Take Profit'
                
                if should_close:
                    # Pozisyon kapat
                    if position['type'] == 'LONG':
                        pnl = (current_price - position['entry_price']) * position['size']
                    else:
                        pnl = (position['entry_price'] - current_price) * position['size']
                    
                    trade = {
                        'entry_time': position['entry_time'],
                        'exit_time': df.index[i],
                        'type': position['type'],
                        'entry_price': position['entry_price'],
                        'exit_price': current_price,
                        'pnl': pnl,
                        'exit_reason': exit_reason,
                        'duration_hours': (df.index[i] - position['entry_time']).total_seconds() / 3600
                    }
                    
                    trades.append(trade)
                    balance += pnl
                    position = None
        
        # İstatistikleri hesapla
        if trades:
            total_pnl = sum(t['pnl'] for t in trades)
            wins = sum(1 for t in trades if t['pnl'] > 0)
            losses = len(trades) - wins
            win_rate = (wins / len(trades)) * 100
            avg_win = sum(t['pnl'] for t in trades if t['pnl'] > 0) / wins if wins > 0 else 0
            avg_loss = sum(t['pnl'] for t in trades if t['pnl'] < 0) / losses if losses > 0 else 0
            profit_factor = abs(sum(t['pnl'] for t in trades if t['pnl'] > 0) / sum(t['pnl'] for t in trades if t['pnl'] < 0)) if losses > 0 else float('inf')
            
            stats = {
                'total_trades': len(trades),
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'final_balance': balance,
                'return_pct': ((balance - initial_balance) / initial_balance) * 100,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'max_drawdown': self.calculate_max_drawdown(trades)
            }
        else:
            stats = {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'final_balance': balance,
                'return_pct': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'max_drawdown': 0
            }
        
        return trades, stats
    
    def calculate_max_drawdown(self, trades):
        """Maksimum düşüş hesapla"""
        if not trades:
            return 0
        
        balance = 10000
        peak = balance
        max_dd = 0
        
        for trade in trades:
            balance += trade['pnl']
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak * 100
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def run_backtest(self):
        """Backtest çalıştır"""
        print(f"🔄 {self.symbol} için {self.days} günlük backtest başlatılıyor...")
        
        # Veri al
        df = self.get_historical_data()
        print(f"📊 {len(df)} bar veri alındı")
        
        # C3 ile sinyaller
        signals_with_c3 = self.generate_signals(df, use_c3=True)
        trades_with_c3, stats_with_c3 = self.backtest_strategy(df, signals_with_c3, "With C3")
        
        # C3 olmadan sinyaller
        signals_without_c3 = self.generate_signals(df, use_c3=False)
        trades_without_c3, stats_without_c3 = self.backtest_strategy(df, signals_without_c3, "Without C3")
        
        # Sonuçları kaydet
        self.results['with_c3']['trades'] = trades_with_c3
        self.results['with_c3']['stats'] = stats_with_c3
        self.results['without_c3']['trades'] = trades_without_c3
        self.results['without_c3']['stats'] = stats_without_c3
        
        return self.results
    
    def print_results(self):
        """Sonuçları yazdır"""
        print("\n" + "="*80)
        print("📊 BACKTEST SONUÇLARI")
        print("="*80)
        
        for strategy_name, data in self.results.items():
            stats = data['stats']
            print(f"\n🎯 {strategy_name.upper().replace('_', ' ')} STRATEJİSİ:")
            print("-" * 50)
            print(f"📈 Toplam İşlem: {stats['total_trades']}")
            print(f"✅ Kazanan: {stats['wins']}")
            print(f"❌ Kaybeden: {stats['losses']}")
            print(f"🎯 Win Rate: {stats['win_rate']:.1f}%")
            print(f"💰 Toplam PnL: ${stats['total_pnl']:.2f}")
            print(f"💵 Final Bakiye: ${stats['final_balance']:.2f}")
            print(f"📊 Getiri: {stats['return_pct']:.1f}%")
            print(f"📈 Ortalama Kazanç: ${stats['avg_win']:.2f}")
            print(f"📉 Ortalama Kayıp: ${stats['avg_loss']:.2f}")
            print(f"⚖️ Profit Factor: {stats['profit_factor']:.2f}")
            print(f"📉 Max Drawdown: {stats['max_drawdown']:.1f}%")
        
        # Karşılaştırma
        print(f"\n🏆 KARŞILAŞTIRMA:")
        print("-" * 50)
        
        c3_stats = self.results['with_c3']['stats']
        no_c3_stats = self.results['without_c3']['stats']
        
        print(f"📈 İşlem Sayısı: {c3_stats['total_trades']} → {no_c3_stats['total_trades']} ({no_c3_stats['total_trades'] - c3_stats['total_trades']:+d})")
        print(f"💰 Getiri: {c3_stats['return_pct']:.1f}% → {no_c3_stats['return_pct']:.1f}% ({no_c3_stats['return_pct'] - c3_stats['return_pct']:+.1f}%)")
        print(f"🎯 Win Rate: {c3_stats['win_rate']:.1f}% → {no_c3_stats['win_rate']:.1f}% ({no_c3_stats['win_rate'] - c3_stats['win_rate']:+.1f}%)")
        print(f"⚖️ Profit Factor: {c3_stats['profit_factor']:.2f} → {no_c3_stats['profit_factor']:.2f}")
        print(f"📉 Max Drawdown: {c3_stats['max_drawdown']:.1f}% → {no_c3_stats['max_drawdown']:.1f}%")

if __name__ == "__main__":
    # Backtest çalıştır
    backtest = SuperTrendBacktest(symbol='EIGEN/USDT', timeframe='1h', days=30)
    results = backtest.run_backtest()
    backtest.print_results()
    
    # Sonuçları JSON olarak kaydet
    with open('backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Sonuçlar 'backtest_results.json' dosyasına kaydedildi")
