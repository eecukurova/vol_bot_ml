#!/usr/bin/env python3
"""
MSFT Backtest Comparison with TradingView
"""

from src.strategy.nasdaq_atr_supertrend import create_strategy
from src.data.nasdaq_provider import NASDAQDataProvider
import pandas as pd
import numpy as np

def main():
    print('🔬 GERÇEK BACKTEST - MSFT İLE KARŞILAŞTIRMA')
    print('='*60)

    # MSFT verisi al (TradingView'deki gibi)
    provider = NASDAQDataProvider()
    data = provider.fetch_data('MSFT', period='1y', interval='1d')

    # Fix data format
    data = data.reset_index()
    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
        data.set_index('date', inplace=True)

    print(f'📊 MSFT Veri: {len(data)} gün')
    print(f'📅 Tarih aralığı: {data.index[0].strftime("%Y-%m-%d")} - {data.index[-1].strftime("%Y-%m-%d")}')

    # TradingView'deki parametreler
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
    print(f'   ATR Sensitivity: {tv_params["a"]}')
    print(f'   ATR Period: {tv_params["c"]}')
    print(f'   SuperTrend Factor: {tv_params["st_factor"]}')
    print(f'   Stop Loss: {tv_params["stop_loss_pct"]}%')
    print(f'   Take Profit: {tv_params["take_profit_pct"]}%')

    # Strategy oluştur
    strategy = create_strategy(tv_params)

    # Indicators hesapla
    data_with_indicators = strategy.calculate_indicators(data)

    # Signals üret
    signals = strategy.generate_signals(data_with_indicators)

    print(f'\n📈 Sinyal Analizi:')
    print(f'   Toplam sinyal: {len(signals)}')

    # Backtest çalıştır
    result = strategy.run_strategy(data)

    print(f'\n📊 BACKTEST SONUÇLARI:')
    print(f'   Toplam işlem: {result.metrics["total_trades"]}')
    print(f'   Win Rate: {result.metrics["win_rate"]:.2%}')
    print(f'   Profit Factor: {result.metrics["profit_factor"]:.3f}')
    print(f'   Total Return: {result.metrics["total_return"]:.2%}')
    print(f'   Max Drawdown: {result.metrics["max_drawdown"]:.2%}')
    
    # Available metrics
    print(f'\n🔍 MEVCUT METRİKLER:')
    for key, value in result.metrics.items():
        print(f'   {key}: {value}')

    print(f'\n📈 TRADINGVIEW KARŞILAŞTIRMA:')
    print(f'   Python Win Rate: {result.metrics["win_rate"]:.2%} vs TradingView: %39.29')
    print(f'   Python Profit Factor: {result.metrics["profit_factor"]:.3f} vs TradingView: 1.772')
    print(f'   Python Total Return: {result.metrics["total_return"]:.2%} vs TradingView: +0.50%')

    # Detaylı işlem analizi
    if result.trades:
        print(f'\n🔍 İŞLEM DETAYLARI:')
        for i, trade in enumerate(result.trades[-5:], 1):  # Son 5 işlem
            if isinstance(trade, dict):
                print(f'   {i}. {trade.get("entry_time", "N/A")} - {trade.get("side", "N/A").upper()} @ ${trade.get("entry_price", 0):.2f} -> ${trade.get("exit_price", 0):.2f} | P&L: ${trade.get("pnl", 0):.2f}')
            else:
                print(f'   {i}. {trade.entry_time.strftime("%Y-%m-%d")} - {trade.side.upper()} @ ${trade.entry_price:.2f} -> ${trade.exit_price:.2f} | P&L: ${trade.pnl:.2f}')

    # Sorun tespiti
    if result.metrics['win_rate'] < 0.4:
        print(f'\n❌ SORUN TESPİTİ:')
        print(f'   Win Rate çok düşük! TradingView ile uyumsuz.')
        print(f'   Muhtemelen stop loss/take profit hesaplaması yanlış.')
    elif result.metrics['profit_factor'] < 1.5:
        print(f'\n❌ SORUN TESPİTİ:')
        print(f'   Profit Factor düşük! TradingView ile uyumsuz.')
        print(f'   Muhtemelen risk management yanlış.')
    else:
        print(f'\n✅ SONUÇLAR UYUMLU!')

if __name__ == "__main__":
    main()
