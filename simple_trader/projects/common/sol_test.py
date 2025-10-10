#!/usr/bin/env python3
"""
SOL/USDT Test Script - Canlı veri ile test
"""

import ccxt
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

def get_sol_data():
    """SOL/USDT verilerini çek"""
    exchange = ccxt.binance()
    
    # Son 100 bar veri çek
    ohlcv = exchange.fetch_ohlcv('SOL/USDT', '1h', limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    
    return df

def calculate_atr(df, period=14):
    """ATR hesapla"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = np.maximum(high_low, np.maximum(high_close, low_close))
    return tr.rolling(period).mean()

def calculate_supertrend(df, period=14, multiplier=1.5):
    """SuperTrend hesapla"""
    atr_val = calculate_atr(df, period)
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

def generate_signals(df):
    """Sinyal üret"""
    st = calculate_supertrend(df)
    ema1 = df['close'].ewm(span=1).mean()
    
    signals = []
    
    for i in range(1, len(df)):
        close = df['close'].iloc[i]
        st_val = st.iloc[i]
        ema1_val = ema1.iloc[i]
        prev_ema1 = ema1.iloc[i-1]
        prev_st = st.iloc[i-1]
        
        signal = 'HOLD'
        if close > st_val and ema1_val > st_val and prev_ema1 <= prev_st:
            signal = 'BUY'
        elif close < st_val and ema1_val < st_val and prev_ema1 >= prev_st:
            signal = 'SELL'
        
        signals.append({
            'timestamp': df.index[i],
            'price': close,
            'supertrend': st_val,
            'ema1': ema1_val,
            'signal': signal
        })
    
    return signals

def backtest_sol(signals, initial_capital=10000, position_size=200, leverage=150, sl_pct=0.006, tp_pct=0.006):
    """SOL için backtest"""
    capital = initial_capital
    position = None
    trades = []
    
    for i, sig in enumerate(signals):
        price = sig['price']
        signal = sig['signal']
        
        # Mevcut pozisyonu kontrol et
        if position:
            # SL/TP kontrolü
            if position['side'] == 'BUY':
                if price <= position['sl']:
                    # Stop Loss
                    pnl = (price - position['entry']) * position['size']
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': sig['timestamp'],
                        'side': 'BUY',
                        'entry': position['entry'],
                        'exit': price,
                        'pnl': pnl,
                        'reason': 'STOP_LOSS'
                    })
                    position = None
                elif price >= position['tp']:
                    # Take Profit
                    pnl = (price - position['entry']) * position['size']
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': sig['timestamp'],
                        'side': 'BUY',
                        'entry': position['entry'],
                        'exit': price,
                        'pnl': pnl,
                        'reason': 'TAKE_PROFIT'
                    })
                    position = None
            
            elif position['side'] == 'SELL':
                if price >= position['sl']:
                    # Stop Loss
                    pnl = (position['entry'] - price) * position['size']
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': sig['timestamp'],
                        'side': 'SELL',
                        'entry': position['entry'],
                        'exit': price,
                        'pnl': pnl,
                        'reason': 'STOP_LOSS'
                    })
                    position = None
                elif price <= position['tp']:
                    # Take Profit
                    pnl = (position['entry'] - price) * position['size']
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': sig['timestamp'],
                        'side': 'SELL',
                        'entry': position['entry'],
                        'exit': price,
                        'pnl': pnl,
                        'reason': 'TAKE_PROFIT'
                    })
                    position = None
        
        # Yeni pozisyon aç
        if not position and signal in ['BUY', 'SELL']:
            size = position_size * leverage / price
            
            if signal == 'BUY':
                sl = price * (1 - sl_pct)
                tp = price * (1 + tp_pct)
            else:
                sl = price * (1 + sl_pct)
                tp = price * (1 - tp_pct)
            
            position = {
                'side': signal,
                'entry': price,
                'size': size,
                'sl': sl,
                'tp': tp,
                'entry_time': sig['timestamp']
            }
    
    return trades, capital

def analyze_results(trades, final_capital, initial_capital):
    """Sonuçları analiz et"""
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'total_return': 0,
            'profit_factor': 0,
            'max_drawdown': 0
        }
    
    total_trades = len(trades)
    wins = sum(1 for t in trades if t['pnl'] > 0)
    win_rate = (wins / total_trades) * 100
    
    total_return = ((final_capital - initial_capital) / initial_capital) * 100
    
    profits = [t['pnl'] for t in trades if t['pnl'] > 0]
    losses = [abs(t['pnl']) for t in trades if t['pnl'] < 0]
    
    gross_profit = sum(profits) if profits else 0
    gross_loss = sum(losses) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Basit drawdown hesaplama
    capital_curve = [initial_capital]
    for trade in trades:
        capital_curve.append(capital_curve[-1] + trade['pnl'])
    
    peak = capital_curve[0]
    max_dd = 0
    for capital in capital_curve:
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak * 100
        if dd > max_dd:
            max_dd = dd
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_return': total_return,
        'profit_factor': profit_factor,
        'max_drawdown': max_dd,
        'final_capital': final_capital,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss
    }

def main():
    """Ana fonksiyon"""
    print("🚀 SOL/USDT Canlı Test Başlıyor...")
    print("=" * 50)
    
    # Veri çek
    print("📊 SOL/USDT verileri çekiliyor...")
    df = get_sol_data()
    print(f"✅ {len(df)} bar veri çekildi")
    print(f"📅 Tarih aralığı: {df.index[0]} - {df.index[-1]}")
    print(f"💰 Son fiyat: ${df['close'].iloc[-1]:.4f}")
    
    # Sinyal üret
    print("\n🎯 Sinyaller üretiliyor...")
    signals = generate_signals(df)
    buy_signals = sum(1 for s in signals if s['signal'] == 'BUY')
    sell_signals = sum(1 for s in signals if s['signal'] == 'SELL')
    print(f"✅ {len(signals)} sinyal üretildi")
    print(f"📈 BUY sinyalleri: {buy_signals}")
    print(f"📉 SELL sinyalleri: {sell_signals}")
    
    # Son sinyalleri göster
    print("\n🔍 Son 5 sinyal:")
    for sig in signals[-5:]:
        print(f"  {sig['timestamp']} | ${sig['price']:.4f} | {sig['signal']}")
    
    # Backtest
    print("\n⚡ Backtest çalıştırılıyor...")
    trades, final_capital = backtest_sol(signals)
    
    # Sonuçları analiz et
    results = analyze_results(trades, final_capital, 10000)
    
    print("\n📊 SOL/USDT TEST SONUÇLARI:")
    print("=" * 50)
    print(f"💰 Başlangıç Sermaye: $10,000")
    print(f"💰 Final Sermaye: ${results['final_capital']:.2f}")
    print(f"📈 Toplam Getiri: {results['total_return']:.2f}%")
    print(f"🎯 Toplam İşlem: {results['total_trades']}")
    print(f"✅ Kazanma Oranı: {results['win_rate']:.1f}%")
    print(f"🔥 Profit Factor: {results['profit_factor']:.2f}")
    print(f"📉 Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"💚 Toplam Kar: ${results['gross_profit']:.2f}")
    print(f"💔 Toplam Zarar: ${results['gross_loss']:.2f}")
    
    # Trade detayları
    if trades:
        print(f"\n📋 İşlem Detayları:")
        print("-" * 80)
        for i, trade in enumerate(trades[-10:], 1):  # Son 10 işlem
            print(f"{i:2d}. {trade['entry_time']} | {trade['side']:4s} | "
                  f"${trade['entry']:.4f} → ${trade['exit']:.4f} | "
                  f"${trade['pnl']:+.2f} | {trade['reason']}")
    
    print("\n🎯 SOL/USDT Test Tamamlandı!")

if __name__ == "__main__":
    main()
