#!/usr/bin/env python3
"""
Gerçek Backtest - Tüm Sinyalleri Kullanarak
"""

from src.strategy.nasdaq_atr_supertrend import create_strategy
from src.data.nasdaq_provider import NASDAQDataProvider
import pandas as pd

def main():
    print('🔬 GERÇEK BACKTEST - TÜM SİNYALLERİ KULLANARAK')
    print('='*60)

    # MSFT verisi al
    provider = NASDAQDataProvider()
    data = provider.fetch_data('MSFT', period='1y', interval='1d')

    # Fix data format
    data = data.reset_index()
    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
        data.set_index('date', inplace=True)

    # TradingView parametreleri
    tv_params = {
        'a': 0.5,
        'c': 2, 
        'st_factor': 0.4,
        'use_ema_confirmation': False,
        'volume_filter': False,
        'stop_loss_pct': 0.5,
        'take_profit_pct': 1.0
    }

    strategy = create_strategy(tv_params)
    data_with_indicators = strategy.calculate_indicators(data)

    # TÜM sinyalleri manuel olarak bul
    all_signals = []
    for i in range(1, len(data_with_indicators)):
        current = data_with_indicators.iloc[i]
        previous = data_with_indicators.iloc[i-1]
        
        # BUY sinyali
        if current['close'] > current['super_trend'] and previous['close'] <= previous['super_trend']:
            all_signals.append({
                'timestamp': current.name,
                'signal_type': 'BUY',
                'price': current['close'],
                'confidence': 1.0
            })
        
        # SELL sinyali
        if current['close'] < current['super_trend'] and previous['close'] >= previous['super_trend']:
            all_signals.append({
                'timestamp': current.name,
                'signal_type': 'SELL',
                'price': current['close'],
                'confidence': 1.0
            })

    print(f'📊 TÜM SİNYALLER: {len(all_signals)}')
    for signal in all_signals:
        print(f'   {signal["timestamp"].strftime("%Y-%m-%d")} - {signal["signal_type"]} @ ${signal["price"]:.2f}')

    # Basit backtest simülasyonu
    print(f'\n🎯 BASIT BACKTEST SIMÜLASYONU:')
    capital = 100000  # $100K
    position = None
    trades = []

    for signal in all_signals:
        if signal['signal_type'] == 'BUY' and position is None:
            # BUY pozisyonu aç
            position = {
                'side': 'BUY',
                'entry_price': signal['price'],
                'entry_time': signal['timestamp'],
                'stop_loss': signal['price'] * 0.995,  # %0.5 stop loss
                'take_profit': signal['price'] * 1.01   # %1.0 take profit
            }
            print(f'   BUY @ ${signal["price"]:.2f} (SL: ${position["stop_loss"]:.2f}, TP: ${position["take_profit"]:.2f})')
        
        elif signal['signal_type'] == 'SELL' and position is not None:
            # Pozisyonu kapat
            exit_price = signal['price']
            if position['side'] == 'BUY':
                pnl = (exit_price - position['entry_price']) / position['entry_price']
            else:
                pnl = (position['entry_price'] - exit_price) / position['entry_price']
            
            trades.append({
                'entry_time': position['entry_time'],
                'exit_time': signal['timestamp'],
                'side': position['side'],
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'pnl': pnl
            })
            
            print(f'   SELL @ ${exit_price:.2f} | P&L: {pnl:.2%}')
            position = None

    print(f'\n📊 BACKTEST SONUÇLARI:')
    print(f'   Toplam işlem: {len(trades)}')
    if trades:
        profitable = sum(1 for t in trades if t['pnl'] > 0)
        win_rate = profitable / len(trades) * 100
        total_return = sum(t['pnl'] for t in trades)
        
        print(f'   Win Rate: {win_rate:.2%}')
        print(f'   Total Return: {total_return:.2%}')
        
        print(f'\n📈 TRADINGVIEW KARŞILAŞTIRMA:')
        print(f'   Python Total Return: {total_return:.2%} vs TradingView: +0.50%')
        print(f'   Python Total Trades: {len(trades)} vs TradingView: 28')
        print(f'   Python Win Rate: {win_rate:.2%} vs TradingView: %39.29')
        
        # Detaylı işlem analizi
        print(f'\n🔍 İŞLEM DETAYLARI:')
        for i, trade in enumerate(trades, 1):
            print(f'   {i}. {trade["entry_time"].strftime("%Y-%m-%d")} - {trade["side"]} @ ${trade["entry_price"]:.2f} -> ${trade["exit_price"]:.2f} | P&L: {trade["pnl"]:.2%}')

if __name__ == "__main__":
    main()
