#!/usr/bin/env python3
"""
ATR SuperTrend Strategy - Comprehensive NASDAQ Stock Testing
Find High Signal, High Performance Stocks with ATR SuperTrend
"""

import pandas as pd
import numpy as np
from src.data.nasdaq_provider import NASDAQDataProvider
from typing import Dict, List, Any
import time

class ATRSuperTrendStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.atr_period = params.get('atr_period', 2)
        self.atr_multiplier = params.get('atr_multiplier', 0.4)
        self.stop_loss = params.get('stop_loss', 0.05)
        self.take_profit = params.get('take_profit', 0.15)
        self.use_ema_confirmation = params.get('use_ema_confirmation', False)
        self.use_heikin_ashi = params.get('use_heikin_ashi', False)
        self.volume_filter = params.get('volume_filter', False)
    
    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def calculate_supertrend(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate SuperTrend indicator"""
        df = df.copy()
        
        # Calculate ATR
        df['atr'] = self.calculate_atr(df, self.atr_period)
        
        # Calculate basic upper and lower bands
        df['hl2'] = (df['high'] + df['low']) / 2
        df['upper_band'] = df['hl2'] + (self.atr_multiplier * df['atr'])
        df['lower_band'] = df['hl2'] - (self.atr_multiplier * df['atr'])
        
        # Calculate final upper and lower bands
        df['final_upper_band'] = df['upper_band']
        df['final_lower_band'] = df['lower_band']
        
        for i in range(1, len(df)):
            # Final Upper Band
            if df.iloc[i]['final_upper_band'] < df.iloc[i-1]['final_upper_band'] or df.iloc[i-1]['close'] > df.iloc[i-1]['final_upper_band']:
                df.iloc[i, df.columns.get_loc('final_upper_band')] = df.iloc[i]['upper_band']
            else:
                df.iloc[i, df.columns.get_loc('final_upper_band')] = df.iloc[i-1]['final_upper_band']
            
            # Final Lower Band
            if df.iloc[i]['final_lower_band'] > df.iloc[i-1]['final_lower_band'] or df.iloc[i-1]['close'] < df.iloc[i-1]['final_lower_band']:
                df.iloc[i, df.columns.get_loc('final_lower_band')] = df.iloc[i]['lower_band']
            else:
                df.iloc[i, df.columns.get_loc('final_lower_band')] = df.iloc[i-1]['final_lower_band']
        
        # Calculate SuperTrend
        df['supertrend'] = 0.0
        df['supertrend_direction'] = 1
        
        for i in range(1, len(df)):
            if df.iloc[i-1]['supertrend_direction'] == 1 and df.iloc[i]['close'] <= df.iloc[i]['final_lower_band']:
                df.iloc[i, df.columns.get_loc('supertrend')] = df.iloc[i]['final_lower_band']
                df.iloc[i, df.columns.get_loc('supertrend_direction')] = -1
            elif df.iloc[i-1]['supertrend_direction'] == -1 and df.iloc[i]['close'] >= df.iloc[i]['final_upper_band']:
                df.iloc[i, df.columns.get_loc('supertrend')] = df.iloc[i]['final_upper_band']
                df.iloc[i, df.columns.get_loc('supertrend_direction')] = 1
            else:
                df.iloc[i, df.columns.get_loc('supertrend')] = df.iloc[i-1]['supertrend']
                df.iloc[i, df.columns.get_loc('supertrend_direction')] = df.iloc[i-1]['supertrend_direction']
        
        return df
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators"""
        df = self.calculate_supertrend(df)
        
        # EMA confirmation (optional)
        if self.use_ema_confirmation:
            df['ema_fast'] = df['close'].ewm(span=9).mean()
            df['ema_slow'] = df['close'].ewm(span=21).mean()
        
        # Volume filter (optional)
        if self.volume_filter:
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate trading signals"""
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # SuperTrend signals
            supertrend_buy = (previous['supertrend_direction'] == -1 and 
                            current['supertrend_direction'] == 1)
            supertrend_sell = (previous['supertrend_direction'] == 1 and 
                             current['supertrend_direction'] == -1)
            
            # Additional filters
            volume_ok = True
            if self.volume_filter:
                volume_ok = current['volume'] > current['volume_sma'] * 1.2
            
            ema_ok = True
            if self.use_ema_confirmation:
                ema_ok = current['ema_fast'] > current['ema_slow']
            
            # Generate signals
            if supertrend_buy and volume_ok and ema_ok:
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'BUY',
                    'price': current['close'],
                    'supertrend': current['supertrend'],
                    'atr': current['atr'],
                    'confidence': 0.8
                })
            elif supertrend_sell and volume_ok:
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'SELL',
                    'price': current['close'],
                    'supertrend': current['supertrend'],
                    'atr': current['atr'],
                    'confidence': 0.8
                })
        
        return signals

def backtest_strategy(signals: List[Dict[str, Any]], stop_loss: float = 0.05, take_profit: float = 0.15) -> List[Dict[str, Any]]:
    """Simple backtest with stop loss and take profit"""
    trades = []
    position = None
    
    for signal in signals:
        if signal['signal_type'] == 'BUY' and position is None:
            position = {
                'side': 'BUY',
                'entry_price': signal['price'],
                'entry_time': signal['timestamp'],
                'stop_loss_price': signal['price'] * (1 - stop_loss),
                'take_profit_price': signal['price'] * (1 + take_profit)
            }
        elif signal['signal_type'] == 'SELL' and position is not None:
            exit_price = signal['price']
            pnl = (exit_price - position['entry_price']) / position['entry_price']
            
            trades.append({
                'entry_time': position['entry_time'],
                'exit_time': signal['timestamp'],
                'side': position['side'],
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'pnl': pnl
            })
            position = None
    
    return trades

def test_atr_supertrend_nasdaq_stocks():
    """Test ATR SuperTrend strategy on comprehensive NASDAQ stocks"""
    print('🚀 ATR SUPERTREND STRATEJİSİ - KAPSAMLI NASDAQ HİSSE TESTİ')
    print('='*80)
    
    # Comprehensive NASDAQ stock list (same as RSI+Bollinger test)
    nasdaq_stocks = [
        # Tech Giants
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'ADBE', 'CRM',
        # Semiconductor
        'AMD', 'INTC', 'QCOM', 'AVGO', 'TXN', 'AMAT', 'LRCX', 'KLAC', 'MCHP', 'ADI',
        # Software
        'ORCL', 'NOW', 'SNOW', 'PLTR', 'CRWD', 'ZS', 'OKTA', 'DOCU', 'TEAM', 'WDAY',
        # E-commerce & Retail
        'EBAY', 'ETSY', 'SHOP', 'SQ', 'PYPL', 'ROKU', 'ZM', 'PTON', 'UBER', 'LYFT',
        # Biotech & Healthcare
        'GILD', 'AMGN', 'BIIB', 'REGN', 'VRTX', 'ILMN', 'MRNA', 'BNTX', 'ABBV', 'JNJ',
        # Financial Tech
        'COIN', 'SOFI', 'HOOD', 'AFRM', 'UPST', 'LC', 'OPEN', 'COMP', 'Z', 'ZG',
        # Cloud & Infrastructure
        'SNOW', 'DDOG', 'NET', 'FSLY', 'ESTC', 'SPLK', 'MDB', 'WDAY', 'NOW', 'CRM',
        # Gaming & Entertainment
        'EA', 'ATVI', 'TTWO', 'ZNGA', 'ROKU', 'DIS', 'CMCSA', 'NFLX', 'SPOT', 'PINS',
        # Electric Vehicles & Clean Energy
        'TSLA', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'FSR', 'WKHS', 'NKLA', 'PLUG',
        # AI & Machine Learning
        'NVDA', 'AMD', 'INTC', 'GOOGL', 'MSFT', 'AMZN', 'META', 'AAPL', 'TSLA', 'PLTR',
        # Cybersecurity
        'CRWD', 'ZS', 'OKTA', 'PANW', 'FTNT', 'CYBR', 'SAIL', 'S', 'TENB', 'QLYS',
        # Fintech
        'SQ', 'PYPL', 'COIN', 'SOFI', 'HOOD', 'AFRM', 'UPST', 'LC', 'OPEN', 'COMP',
        # Streaming & Media
        'NFLX', 'DIS', 'ROKU', 'SPOT', 'PINS', 'SNAP', 'TWTR', 'FB', 'GOOGL', 'AMZN',
        # Cloud Computing
        'AMZN', 'MSFT', 'GOOGL', 'CRM', 'NOW', 'WDAY', 'SNOW', 'DDOG', 'NET', 'MDB',
        # Additional High Volume Stocks
        'BABA', 'JD', 'PDD', 'TME', 'VIPS', 'WB', 'YMM', 'BILI', 'IQ', 'NTES',
        'MU', 'MRVL', 'SWKS', 'QRVO', 'SLAB', 'MXIM', 'IDTI', 'ALTR', 'XLNX', 'CY',
        'CTXS', 'VMW', 'RHT', 'WDC', 'STX', 'NTAP', 'EMC', 'HPQ', 'DELL', 'CSCO'
    ]
    
    # Remove duplicates and limit to reasonable number
    unique_stocks = list(set(nasdaq_stocks))[:100]  # Test first 100 unique stocks
    
    print(f'📊 Test Edilecek Hisse Sayısı: {len(unique_stocks)}')
    print(f'📅 Test Periyodu: 1 yıl')
    print(f'🎯 Strateji: ATR SuperTrend (Ultra Agresif Parametreler)')
    print()
    
    # Strategy parameters (ultra aggressive - best performing from Python tests)
    strategy_params = {
        'atr_period': 2,
        'atr_multiplier': 0.4,
        'stop_loss': 0.05,
        'take_profit': 0.15,
        'use_ema_confirmation': False,
        'use_heikin_ashi': False,
        'volume_filter': False
    }
    
    provider = NASDAQDataProvider()
    results = []
    successful_tests = 0
    
    for i, symbol in enumerate(unique_stocks, 1):
        try:
            print(f'[{i:3d}/{len(unique_stocks)}] {symbol} test ediliyor...', end=' ')
            
            # Get data
            data = provider.fetch_data(symbol, period='1y', interval='1d')
            data = data.reset_index()
            if 'date' in data.columns:
                data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
                data.set_index('date', inplace=True)
            
            # Skip if not enough data
            if len(data) < 50:
                print('Yetersiz veri')
                continue
            
            # Create strategy
            strategy = ATRSuperTrendStrategy(strategy_params)
            
            # Calculate indicators
            data_with_indicators = strategy.calculate_indicators(data)
            
            # Generate signals
            signals = strategy.generate_signals(data_with_indicators)
            
            # Skip if no signals
            if len(signals) == 0:
                print('Sinyal yok')
                continue
            
            # Backtest
            trades = backtest_strategy(signals, strategy_params['stop_loss'], strategy_params['take_profit'])
            
            # Skip if no trades
            if len(trades) == 0:
                print('İşlem yok')
                continue
            
            # Calculate metrics
            profitable = sum(1 for t in trades if t['pnl'] > 0)
            win_rate = profitable / len(trades) * 100
            total_return = sum(t['pnl'] for t in trades)
            
            result = {
                'symbol': symbol,
                'total_trades': len(trades),
                'win_rate': win_rate,
                'total_return': total_return,
                'signals_count': len(signals),
                'avg_trade_return': total_return / len(trades),
                'max_trade_return': max(t['pnl'] for t in trades),
                'min_trade_return': min(t['pnl'] for t in trades)
            }
            results.append(result)
            successful_tests += 1
            
            print(f'{len(trades)} işlem, {win_rate:.1f}% WR, {total_return:.2%} return')
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            print(f'Hata: {str(e)[:30]}...')
            continue
    
    print(f'\n✅ Başarılı test sayısı: {successful_tests}/{len(unique_stocks)}')
    
    if results:
        # Sort by different criteria
        print(f'\n🏆 ATR SUPERTREND - EN İYİ PERFORMANS GÖSTEREN HİSSELER')
        print('='*80)
        
        # Sort by total return
        by_return = sorted(results, key=lambda x: x['total_return'], reverse=True)
        print(f'\n📈 EN YÜKSEK RETURN:')
        for i, result in enumerate(by_return[:10], 1):
            print(f'{i:2d}. {result["symbol"]}: {result["total_return"]:.2%} '
                  f'({result["total_trades"]} işlem, {result["win_rate"]:.1f}% WR)')
        
        # Sort by signal count
        by_signals = sorted(results, key=lambda x: x['signals_count'], reverse=True)
        print(f'\n📊 EN ÇOK SİNYAL:')
        for i, result in enumerate(by_signals[:10], 1):
            print(f'{i:2d}. {result["symbol"]}: {result["signals_count"]} sinyal '
                  f'({result["total_trades"]} işlem, {result["total_return"]:.2%} return)')
        
        # Sort by win rate
        by_winrate = sorted(results, key=lambda x: x['win_rate'], reverse=True)
        print(f'\n🎯 EN YÜKSEK WIN RATE:')
        for i, result in enumerate(by_winrate[:10], 1):
            print(f'{i:2d}. {result["symbol"]}: {result["win_rate"]:.1f}% WR '
                  f'({result["total_trades"]} işlem, {result["total_return"]:.2%} return)')
        
        # Sort by trade count
        by_trades = sorted(results, key=lambda x: x['total_trades'], reverse=True)
        print(f'\n🔄 EN ÇOK İŞLEM:')
        for i, result in enumerate(by_trades[:10], 1):
            print(f'{i:2d}. {result["symbol"]}: {result["total_trades"]} işlem '
                  f'({result["win_rate"]:.1f}% WR, {result["total_return"]:.2%} return)')
        
        # Find best balanced stocks (high signals + good performance)
        balanced_stocks = []
        for result in results:
            if (result['signals_count'] >= 15 and  # At least 15 signals
                result['total_trades'] >= 3 and     # At least 3 trades
                result['total_return'] > 0 and      # Profitable
                result['win_rate'] >= 50):          # At least 50% win rate
                balanced_stocks.append(result)
        
        if balanced_stocks:
            balanced_stocks.sort(key=lambda x: x['total_return'], reverse=True)
            print(f'\n⚖️ DENGE HİSSELERİ (Yüksek Sinyal + İyi Performans):')
            for i, result in enumerate(balanced_stocks[:15], 1):
                print(f'{i:2d}. {result["symbol"]}: {result["signals_count"]} sinyal, '
                      f'{result["total_trades"]} işlem, {result["win_rate"]:.1f}% WR, '
                      f'{result["total_return"]:.2%} return')
        
        # Summary statistics
        avg_return = sum(r['total_return'] for r in results) / len(results)
        avg_trades = sum(r['total_trades'] for r in results) / len(results)
        avg_signals = sum(r['signals_count'] for r in results) / len(results)
        avg_winrate = sum(r['win_rate'] for r in results) / len(results)
        
        print(f'\n📊 ATR SUPERTREND GENEL İSTATİSTİKLER:')
        print(f'   Ortalama Return: {avg_return:.2%}')
        print(f'   Ortalama İşlem Sayısı: {avg_trades:.1f}')
        print(f'   Ortalama Sinyal Sayısı: {avg_signals:.1f}')
        print(f'   Ortalama Win Rate: {avg_winrate:.1f}%')
        
        # Top recommendations
        print(f'\n🎯 ATR SUPERTREND ÖNERİLERİ:')
        print(f'1. En yüksek return: {by_return[0]["symbol"]} ({by_return[0]["total_return"]:.2%})')
        print(f'2. En çok sinyal: {by_signals[0]["symbol"]} ({by_signals[0]["signals_count"]} sinyal)')
        print(f'3. En yüksek win rate: {by_winrate[0]["symbol"]} ({by_winrate[0]["win_rate"]:.1f}%)')
        print(f'4. En çok işlem: {by_trades[0]["symbol"]} ({by_trades[0]["total_trades"]} işlem)')
        
        if balanced_stocks:
            print(f'5. En dengeli: {balanced_stocks[0]["symbol"]} '
                  f'({balanced_stocks[0]["signals_count"]} sinyal, {balanced_stocks[0]["total_return"]:.2%} return)')
        
        return results
    else:
        print(f'\n❌ Hiçbir hissede başarılı test yapılamadı!')
        return []

if __name__ == "__main__":
    test_atr_supertrend_nasdaq_stocks()
