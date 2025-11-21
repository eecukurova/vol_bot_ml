#!/usr/bin/env python3
"""
Sinyal Üretimi Analizi
"""

from src.strategy.nasdaq_atr_supertrend import create_strategy
from src.data.nasdaq_provider import NASDAQDataProvider
import pandas as pd

def main():
    print('🔍 SİNYAL ÜRETİMİ ANALİZİ')
    print('='*40)

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

    # Indicators hesapla
    data_with_indicators = strategy.calculate_indicators(data)

    # SuperTrend değerlerini kontrol et
    print(f'📊 SuperTrend Analizi:')
    print(f'   Toplam veri: {len(data_with_indicators)}')
    print(f'   SuperTrend column var mı: {"super_trend" in data_with_indicators.columns}')

    if 'super_trend' in data_with_indicators.columns:
        # Son 10 SuperTrend değeri
        print(f'\n📈 Son 10 SuperTrend değeri:')
        for i in range(-10, 0):
            row = data_with_indicators.iloc[i]
            print(f'   {row.name.strftime("%Y-%m-%d")}: Close=${row["close"]:.2f}, SuperTrend=${row["super_trend"]:.2f}')
        
        # Sinyal noktalarını bul
        print(f'\n🎯 Sinyal Noktaları:')
        for i in range(1, len(data_with_indicators)):
            current = data_with_indicators.iloc[i]
            previous = data_with_indicators.iloc[i-1]
            
            # BUY sinyali
            if current['close'] > current['super_trend'] and previous['close'] <= previous['super_trend']:
                print(f'   BUY: {current.name.strftime("%Y-%m-%d")} @ ${current["close"]:.2f}')
            
            # SELL sinyali
            if current['close'] < current['super_trend'] and previous['close'] >= previous['super_trend']:
                print(f'   SELL: {current.name.strftime("%Y-%m-%d")} @ ${current["close"]:.2f}')

    # Signals üret
    signals = strategy.generate_signals(data_with_indicators)
    print(f'\n📊 Strategy Signals: {len(signals)}')
    for signal in signals:
        print(f'   {signal.timestamp.strftime("%Y-%m-%d")} - {signal.signal_type} @ ${signal.price:.2f}')

if __name__ == "__main__":
    main()
