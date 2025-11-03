#!/usr/bin/env python3
"""
Real Backtest Engine Test
"""

from src.strategy.backtester import Backtester
from src.data.nasdaq_provider import NASDAQDataProvider
from src.strategy.nasdaq_atr_supertrend import create_strategy
import pandas as pd

def main():
    print('🔬 GERÇEK BACKTEST ENGINE İLE TEST')
    print('='*50)

    # MSFT verisi al
    provider = NASDAQDataProvider()
    data = provider.fetch_data('MSFT', period='1y', interval='1d')

    # Fix data format
    data = data.reset_index()
    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
        data.set_index('date', inplace=True)

    print(f'📊 MSFT Veri: {len(data)} gün')

    # Gerçek backtest engine kullan
    backtester = Backtester(
        initial_capital=100000,  # $100K
        fee_bps=1.0,  # 0.01% fee
        slippage_bps=2.0,  # 0.02% slippage
        position_size_pct=0.1,  # 10% position size
        leverage=1.0  # No leverage
    )

    # TradingView parametreleri ile strategy oluştur
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

    # Strategy ile signals üret
    data_with_indicators = strategy.calculate_indicators(data)
    signals = strategy.generate_signals(data_with_indicators)
    
    # Signals'i DataFrame'e çevir
    signals_df = pd.DataFrame([
        {
            'timestamp': signal.timestamp,
            'signal_type': signal.signal_type,
            'price': signal.price,
            'confidence': signal.confidence,
            'buy_final': signal.signal_type == 'BUY',
            'sell_final': signal.signal_type == 'SELL'
        }
        for signal in signals
    ])
    
    if not signals_df.empty:
        signals_df.set_index('timestamp', inplace=True)
    
    print(f'📈 Üretilen sinyal sayısı: {len(signals)}')

    # Gerçek backtest çalıştır
    result = backtester.run_backtest(data, signals_df)

    print(f'\n📊 GERÇEK BACKTEST SONUÇLARI:')
    print(f'   Toplam işlem: {result.metrics["total_trades"]}')
    print(f'   Win Rate: {result.metrics["win_rate"]:.2%}')
    print(f'   Profit Factor: {result.metrics["profit_factor"]:.3f}')
    print(f'   Total Return: {result.metrics["total_return_pct"]:.2%}')
    print(f'   Max Drawdown: {result.metrics["max_drawdown_pct"]:.2%}')

    print(f'\n📈 TRADINGVIEW KARŞILAŞTIRMA:')
    print(f'   Python Total Return: {result.metrics["total_return_pct"]:.2%} vs TradingView: +0.50%')
    print(f'   Python Total Trades: {result.metrics["total_trades"]} vs TradingView: 28')

    # İşlem detayları
    if result.trades:
        print(f'\n🔍 İŞLEM DETAYLARI (Son 5):')
        for i, trade in enumerate(result.trades[-5:], 1):
            print(f'   {i}. {trade.entry_time.strftime("%Y-%m-%d")} - {trade.side.upper()} @ ${trade.entry_price:.2f} -> ${trade.exit_price:.2f} | P&L: ${trade.pnl:.2f}')

if __name__ == "__main__":
    main()
