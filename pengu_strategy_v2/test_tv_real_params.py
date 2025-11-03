#!/usr/bin/env python3
"""
TradingView Gerçek Parametreleri ile Backtest
"""

from src.strategy.nasdaq_atr_supertrend import create_strategy
from src.data.nasdaq_provider import NASDAQDataProvider
import pandas as pd
import numpy as np

def main():
    print('🔬 TRADINGVIEW GERÇEK PARAMETRELERİ İLE BACKTEST')
    print('='*60)

    # MSFT verisi al - TradingView'deki gibi 1 yıl
    provider = NASDAQDataProvider()
    data = provider.fetch_data('MSFT', period='1y', interval='1d')

    # Fix data format
    data = data.reset_index()
    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
        data.set_index('date', inplace=True)

    print(f'📊 MSFT Veri: {len(data)} gün')
    print(f'📅 Tarih: {data.index[0].strftime("%Y-%m-%d")} - {data.index[-1].strftime("%Y-%m-%d")}')

    # TradingView'deki GERÇEK parametreler
    tv_params = {
        'a': 0.5,
        'c': 2, 
        'st_factor': 0.4,
        'use_ema_confirmation': False,
        'volume_filter': False,
        'stop_loss_pct': 0.5,
        'take_profit_pct': 1.0
    }

    print(f'\n🔧 TradingView Parametreleri:')
    for key, value in tv_params.items():
        print(f'   {key}: {value}')

    # Strategy oluştur
    strategy = create_strategy(tv_params)

    # Indicators hesapla
    data_with_indicators = strategy.calculate_indicators(data)

    # Signals üret
    signals = strategy.generate_signals(data_with_indicators)

    print(f'\n📈 Sinyal Analizi:')
    print(f'   Toplam sinyal: {len(signals)}')

    # Her sinyal için detay
    for i, signal in enumerate(signals):
        print(f'   {i+1}. {signal.timestamp.strftime("%Y-%m-%d")} - {signal.signal_type} @ ${signal.price:.2f}')

    # Backtest çalıştır
    result = strategy.run_strategy(data)

    print(f'\n📊 BACKTEST SONUÇLARI:')
    print(f'   Toplam işlem: {result.metrics["total_trades"]}')
    print(f'   Win Rate: {result.metrics["win_rate"]:.2%}')
    print(f'   Profit Factor: {result.metrics["profit_factor"]:.3f}')
    print(f'   Total Return: {result.metrics["total_return"]:.2%}')
    print(f'   Max Drawdown: {result.metrics["max_drawdown"]:.2%}')

    print(f'\n📈 TRADINGVIEW KARŞILAŞTIRMA:')
    print(f'   Python Total Return: {result.metrics["total_return"]:.2%} vs TradingView: +0.50%')
    print(f'   Python Total Trades: {result.metrics["total_trades"]} vs TradingView: 28')
    print(f'   Python Win Rate: {result.metrics["win_rate"]:.2%} vs TradingView: %39.29')
    print(f'   Python Profit Factor: {result.metrics["profit_factor"]:.3f} vs TradingView: 1.772')

    # Sorun analizi
    if result.metrics['total_trades'] < 20:
        print(f'\n❌ SORUN: Çok az işlem!')
        print(f'   Python: {result.metrics["total_trades"]} vs TradingView: 28')
        print(f'   Muhtemelen sinyal üretimi yanlış.')
    elif result.metrics['total_return'] == 0:
        print(f'\n❌ SORUN: Total return 0!')
        print(f'   Python: {result.metrics["total_return"]:.2%} vs TradingView: +0.50%')
        print(f'   Muhtemelen P&L hesaplaması yanlış.')
    else:
        print(f'\n✅ SONUÇLAR UYUMLU!')

    # Detaylı analiz
    print(f'\n🔍 DETAYLI ANALİZ:')
    print(f'   Sinyal sayısı: {len(signals)}')
    print(f'   İşlem sayısı: {result.metrics["total_trades"]}')
    print(f'   Sinyal/İşlem oranı: {len(signals)/result.metrics["total_trades"]:.2f}' if result.metrics["total_trades"] > 0 else '   Sinyal/İşlem oranı: N/A')
    
    # TradingView'deki gerçek sonuçları kabul et
    print(f'\n🎯 SONUÇ:')
    print(f'   TradingView\'deki sonuçlar GERÇEK:')
    print(f'   - Total Return: +0.50%')
    print(f'   - Total Trades: 28')
    print(f'   - Win Rate: %39.29')
    print(f'   - Profit Factor: 1.772')
    print(f'   Python kodu bu sonuçları üretemiyor!')

if __name__ == "__main__":
    main()
