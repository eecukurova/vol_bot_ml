#!/usr/bin/env python3
"""
DEEP Supertrend RSI Strategy - Detailed Backtest Analysis
Kar/Zarar oranları ve performans metrikleri
"""

import pandas as pd
import numpy as np
import pandas_ta as pta
from itertools import product
import json
from datetime import datetime, timedelta

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

def create_realistic_test_data():
    """Gerçekçi DEEP/USDT test verisi oluştur"""
    print("📊 Gerçekçi DEEP/USDT test verisi oluşturuluyor...")
    
    # 30 günlük 1 dakika verisi
    dates = pd.date_range('2024-09-22', periods=43200, freq='1min')  # 30 gün * 24 saat * 60 dakika
    
    # DEEP/USDT gerçekçi fiyat simülasyonu
    np.random.seed(42)
    base_price = 0.08
    
    # Trend + Noise
    trend = np.linspace(0, 0.02, 43200)  # %2 yukarı trend
    noise = np.random.normal(0, 0.005, 43200)  # %0.5 volatilite
    
    returns = trend + noise
    prices = [base_price]
    
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    # OHLCV verisi
    test_df = pd.DataFrame({
        'Open': prices,
        'High': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'Low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'Close': prices,
        'Volume': np.random.randint(1000, 50000, 43200)
    }, index=dates)
    
    print(f"✅ Test verisi hazır: {len(test_df)} bar (30 gün)")
    return test_df

def calculate_backtest_metrics(signals_df, initial_capital=1000, trade_amount=10):
    """Backtest metriklerini hesapla"""
    print("📊 Backtest metrikleri hesaplanıyor...")
    
    # Trade log
    trades = []
    current_position = None
    entry_price = 0
    entry_time = None
    
    for i, row in signals_df.iterrows():
        # LONG pozisyon açma
        if row['buy_signal'] and current_position is None:
            current_position = 'LONG'
            entry_price = row['Close']
            entry_time = i
            trades.append({
                'type': 'LONG',
                'entry_time': entry_time,
                'entry_price': entry_price,
                'amount': trade_amount
            })
        
        # SHORT pozisyon açma
        elif row['sell_signal'] and current_position is None:
            current_position = 'SHORT'
            entry_price = row['Close']
            entry_time = i
            trades.append({
                'type': 'SHORT',
                'entry_time': entry_time,
                'entry_price': entry_price,
                'amount': trade_amount
            })
        
        # LONG pozisyon kapatma
        elif row['close_long'] and current_position == 'LONG':
            exit_price = row['Close']
            pnl = (exit_price - entry_price) / entry_price * trade_amount
            trades[-1].update({
                'exit_time': i,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_percent': (exit_price - entry_price) / entry_price * 100
            })
            current_position = None
        
        # SHORT pozisyon kapatma
        elif row['close_short'] and current_position == 'SHORT':
            exit_price = row['Close']
            pnl = (entry_price - exit_price) / entry_price * trade_amount
            trades[-1].update({
                'exit_time': i,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_percent': (entry_price - exit_price) / entry_price * 100
            })
            current_position = None
    
    # Tamamlanmamış pozisyonları kapat
    if current_position:
        last_trade = trades[-1]
        last_price = signals_df.iloc[-1]['Close']
        if current_position == 'LONG':
            pnl = (last_price - last_trade['entry_price']) / last_trade['entry_price'] * trade_amount
            pnl_percent = (last_price - last_trade['entry_price']) / last_trade['entry_price'] * 100
        else:  # SHORT
            pnl = (last_trade['entry_price'] - last_price) / last_trade['entry_price'] * trade_amount
            pnl_percent = (last_trade['entry_price'] - last_price) / last_trade['entry_price'] * 100
        
        trades[-1].update({
            'exit_time': signals_df.index[-1],
            'exit_price': last_price,
            'pnl': pnl,
            'pnl_percent': pnl_percent
        })
    
    # Sadece tamamlanmış trade'leri al
    completed_trades = [t for t in trades if 'pnl' in t]
    
    if not completed_trades:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0
        }
    
    # Metrikleri hesapla
    total_trades = len(completed_trades)
    winning_trades = [t for t in completed_trades if t['pnl'] > 0]
    losing_trades = [t for t in completed_trades if t['pnl'] < 0]
    
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    
    total_pnl = sum(t['pnl'] for t in completed_trades)
    
    avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
    avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
    
    total_wins = sum(t['pnl'] for t in winning_trades)
    total_losses = abs(sum(t['pnl'] for t in losing_trades))
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    # Drawdown hesaplama
    cumulative_pnl = np.cumsum([t['pnl'] for t in completed_trades])
    running_max = np.maximum.accumulate(cumulative_pnl)
    drawdown = running_max - cumulative_pnl
    max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
    
    # Sharpe ratio (basit)
    pnl_returns = [t['pnl'] for t in completed_trades]
    sharpe_ratio = np.mean(pnl_returns) / np.std(pnl_returns) if np.std(pnl_returns) > 0 else 0
    
    return {
        'total_trades': total_trades,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'trades': completed_trades
    }

def run_detailed_backtest():
    """Detaylı backtest çalıştır"""
    print("🎯 DEEP Supertrend RSI Strategy - Detaylı Backtest")
    print("=" * 60)
    
    # En iyi parametreler (optimizasyondan)
    best_params = {
        'rsi_length': 10,
        'rsi_oversold': 25,
        'rsi_overbought': 65,
        'rsi_long_exit': 60,
        'rsi_short_exit': 30,
        'supertrend_length': 1,
        'supertrend_multiplier': 2.0,
        'support_resistance_period': 15
    }
    
    print(f"📊 En İyi Parametreler:")
    for key, value in best_params.items():
        print(f"   {key}: {value}")
    
    # Test verisi
    test_df = create_realistic_test_data()
    
    # Strateji oluştur
    strategy = DeepSupertrendRSIStrategy(best_params)
    print(f"\n✅ Strateji oluşturuldu")
    
    # Sinyalleri üret
    signals_df = strategy.get_signals(test_df)
    print(f"✅ Sinyaller üretildi")
    
    # Backtest metrikleri
    metrics = calculate_backtest_metrics(signals_df, initial_capital=1000, trade_amount=10)
    
    # Sonuçları yazdır
    print(f"\n🏆 BACKTEST SONUÇLARI:")
    print(f"=" * 40)
    
    print(f"📊 Genel İstatistikler:")
    print(f"   Toplam Trade: {metrics['total_trades']}")
    print(f"   Kazanan Trade: {metrics['winning_trades']}")
    print(f"   Kaybeden Trade: {metrics['losing_trades']}")
    print(f"   Kazanma Oranı: {metrics['win_rate']:.1f}%")
    
    print(f"\n💰 Kar/Zarar Analizi:")
    print(f"   Toplam P&L: ${metrics['total_pnl']:.2f}")
    print(f"   Ortalama Kazanç: ${metrics['avg_win']:.2f}")
    print(f"   Ortalama Kayıp: ${metrics['avg_loss']:.2f}")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    
    print(f"\n📈 Risk Metrikleri:")
    print(f"   Max Drawdown: ${metrics['max_drawdown']:.2f}")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    
    # Trade detayları
    if metrics['trades']:
        print(f"\n📋 Son 5 Trade:")
        for i, trade in enumerate(metrics['trades'][-5:]):
            print(f"   {i+1}. {trade['type']} - Entry: ${trade['entry_price']:.4f}, Exit: ${trade['exit_price']:.4f}, P&L: ${trade['pnl']:.2f} ({trade['pnl_percent']:.1f}%)")
    
    # Sonuçları kaydet
    results = {
        'strategy': 'DEEP Supertrend RSI',
        'parameters': best_params,
        'backtest_period': '30 days',
        'metrics': metrics,
        'timestamp': datetime.now().isoformat()
    }
    
    with open('deep_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✅ Sonuçlar 'deep_backtest_results.json' dosyasına kaydedildi")
    
    return results

if __name__ == "__main__":
    results = run_detailed_backtest()
