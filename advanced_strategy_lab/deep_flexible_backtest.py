#!/usr/bin/env python3
"""
DEEP Supertrend RSI Strategy - Flexible Backtest
Daha esnek parametrelerle kar/zarar analizi
"""

import pandas as pd
import numpy as np
import pandas_ta as pta
import json
from datetime import datetime

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
        """Basitleştirilmiş trading sinyalleri"""
        result_df = df.copy()
        
        # Basit RSI + Supertrend stratejisi
        buy_signals = []
        sell_signals = []
        
        for i in range(len(result_df)):
            if i < max(self.rsi_length, self.support_resistance_period):
                buy_signals.append(False)
                sell_signals.append(False)
                continue
            
            rsi = result_df.iloc[i]['rsi']
            supertrend = result_df.iloc[i]['supertrend']
            current_price = result_df.iloc[i]['Close']
            
            # Skip if indicators are NaN
            if pd.isna(rsi) or pd.isna(supertrend):
                buy_signals.append(False)
                sell_signals.append(False)
                continue
            
            # Basit sinyal mantığı
            buy_signal = (rsi < self.rsi_oversold) and (current_price > supertrend)
            sell_signal = (rsi > self.rsi_overbought) and (current_price < supertrend)
            
            buy_signals.append(buy_signal)
            sell_signals.append(sell_signal)
        
        result_df['buy_signal'] = buy_signals
        result_df['sell_signal'] = sell_signals
        
        return result_df
    
    def get_signals(self, df):
        """Ana sinyal üretme fonksiyonu"""
        df_with_indicators = self.calculate_indicators(df)
        df_with_signals = self.generate_signals(df_with_indicators)
        return df_with_signals

def create_realistic_test_data():
    """Gerçekçi DEEP/USDT test verisi oluştur"""
    print("📊 Gerçekçi DEEP/USDT test verisi oluşturuluyor...")
    
    # 7 günlük 1 dakika verisi
    dates = pd.date_range('2024-10-15', periods=10080, freq='1min')  # 7 gün * 24 saat * 60 dakika
    
    # DEEP/USDT gerçekçi fiyat simülasyonu
    np.random.seed(42)
    base_price = 0.08
    
    # Trend + Noise + Volatilite
    trend = np.linspace(0, 0.05, 10080)  # %5 yukarı trend
    noise = np.random.normal(0, 0.008, 10080)  # %0.8 volatilite
    
    # Volatilite patlamaları ekle
    volatility_spikes = np.random.choice([0, 1], 10080, p=[0.95, 0.05])
    spike_noise = np.random.normal(0, 0.02, 10080) * volatility_spikes
    
    returns = trend + noise + spike_noise
    prices = [base_price]
    
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    # OHLCV verisi
    test_df = pd.DataFrame({
        'Open': prices,
        'High': [p * (1 + abs(np.random.normal(0, 0.015))) for p in prices],
        'Low': [p * (1 - abs(np.random.normal(0, 0.015))) for p in prices],
        'Close': prices,
        'Volume': np.random.randint(1000, 50000, 10080)
    }, index=dates)
    
    print(f"✅ Test verisi hazır: {len(test_df)} bar (7 gün)")
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
        
        # Pozisyon kapatma (ters sinyal geldiğinde)
        elif current_position == 'LONG' and row['sell_signal']:
            exit_price = row['Close']
            pnl = (exit_price - entry_price) / entry_price * trade_amount
            trades[-1].update({
                'exit_time': i,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_percent': (exit_price - entry_price) / entry_price * 100
            })
            current_position = None
        
        elif current_position == 'SHORT' and row['buy_signal']:
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
            'sharpe_ratio': 0,
            'trades': []
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

def run_flexible_backtest():
    """Esnek backtest çalıştır"""
    print("🎯 DEEP Supertrend RSI Strategy - Esnek Backtest")
    print("=" * 60)
    
    # Daha esnek parametreler
    flexible_params = {
        'rsi_length': 14,
        'rsi_oversold': 35,  # Daha esnek
        'rsi_overbought': 65,  # Daha esnek
        'rsi_long_exit': 70,
        'rsi_short_exit': 30,
        'supertrend_length': 1,
        'supertrend_multiplier': 2.5,
        'support_resistance_period': 20
    }
    
    print(f"📊 Esnek Parametreler:")
    for key, value in flexible_params.items():
        print(f"   {key}: {value}")
    
    # Test verisi
    test_df = create_realistic_test_data()
    
    # Strateji oluştur
    strategy = DeepSupertrendRSIStrategy(flexible_params)
    print(f"\n✅ Strateji oluşturuldu")
    
    # Sinyalleri üret
    signals_df = strategy.get_signals(test_df)
    print(f"✅ Sinyaller üretildi")
    
    # Sinyal sayılarını kontrol et
    buy_signals = signals_df['buy_signal'].sum()
    sell_signals = signals_df['sell_signal'].sum()
    print(f"📊 Sinyal Sayıları: BUY={buy_signals}, SELL={sell_signals}")
    
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
        'strategy': 'DEEP Supertrend RSI (Flexible)',
        'parameters': flexible_params,
        'backtest_period': '7 days',
        'metrics': metrics,
        'timestamp': datetime.now().isoformat()
    }
    
    with open('deep_flexible_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✅ Sonuçlar 'deep_flexible_backtest_results.json' dosyasına kaydedildi")
    
    return results

if __name__ == "__main__":
    results = run_flexible_backtest()
