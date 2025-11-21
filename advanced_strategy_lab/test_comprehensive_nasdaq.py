#!/usr/bin/env python3
"""
Comprehensive NASDAQ Stock Testing - Find High Signal, High Performance Stocks
"""

import pandas as pd
import numpy as np
from src.data.nasdaq_provider import NASDAQDataProvider
from typing import Dict, List, Any
import time

class RSIBollingerStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.rsi_period = params.get('rsi_period', 7)
        self.rsi_oversold = params.get('rsi_oversold', 20)
        self.rsi_overbought = params.get('rsi_overbought', 80)
        self.bb_period = params.get('bb_period', 15)
        self.bb_std_dev = params.get('bb_std_dev', 1.5)
        self.stop_loss = params.get('stop_loss', 0.01)
        self.take_profit = params.get('take_profit', 0.02)
        self.require_both_signals = params.get('require_both_signals', False)
    
    def calculate_rsi(self, src: pd.Series, period: int) -> pd.Series:
        delta = src.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Calculate RSI
        df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)
        
        # Calculate Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=self.bb_period).mean()
        bb_std = df['close'].rolling(window=self.bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * self.bb_std_dev)
        df['bb_lower'] = df['bb_middle'] - (bb_std * self.bb_std_dev)
        
        # Calculate BB position
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # RSI signals
            rsi_buy = (previous['rsi'] <= self.rsi_oversold and 
                      current['rsi'] > self.rsi_oversold)
            rsi_sell = (previous['rsi'] >= self.rsi_overbought and 
                       current['rsi'] < self.rsi_overbought)
            
            # Bollinger Bands signals
            bb_buy = (previous['close'] <= previous['bb_lower'] and 
                     current['close'] > current['bb_lower'] and
                     current['bb_position'] > 0.1)
            bb_sell = (previous['close'] >= previous['bb_upper'] and 
                      current['close'] < current['bb_upper'] and
                      current['bb_position'] < 0.9)
            
            # Combined signals
            if self.require_both_signals:
                buy_signal = rsi_buy and bb_buy
                sell_signal = rsi_sell and bb_sell
            else:
                buy_signal = rsi_buy or bb_buy
                sell_signal = rsi_sell or bb_sell
            
            if buy_signal:
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'BUY',
                    'price': current['close'],
                    'rsi': current['rsi'],
                    'bb_position': current['bb_position'],
                    'confidence': 0.8 if (rsi_buy and bb_buy) else 0.6
                })
            elif sell_signal:
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'SELL',
                    'price': current['close'],
                    'rsi': current['rsi'],
                    'bb_position': current['bb_position'],
                    'confidence': 0.8 if (rsi_sell and bb_sell) else 0.6
                })
        
        return signals

def backtest_strategy(signals: List[Dict[str, Any]], stop_loss: float = 0.01, take_profit: float = 0.02) -> List[Dict[str, Any]]:
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

def test_comprehensive_nasdaq_stocks():
    """Test comprehensive list of NASDAQ stocks"""
    print('🚀 KAPSAMLI NASDAQ HİSSE TESTİ - YÜKSEK SİNYAL VE PERFORMANS')
    print('='*80)
    
    # Comprehensive NASDAQ stock list
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
    print()
    
    # Strategy parameters (best performing)
    strategy_params = {
        'rsi_period': 7,
        'rsi_oversold': 20,
        'rsi_overbought': 80,
        'bb_period': 15,
        'bb_std_dev': 1.5,
        'stop_loss': 0.01,
        'take_profit': 0.02,
        'require_both_signals': False
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
            strategy = RSIBollingerStrategy(strategy_params)
            
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
        print(f'\n🏆 EN İYİ PERFORMANS GÖSTEREN HİSSELER')
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
            if (result['signals_count'] >= 20 and  # At least 20 signals
                result['total_trades'] >= 5 and     # At least 5 trades
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
        
        print(f'\n📊 GENEL İSTATİSTİKLER:')
        print(f'   Ortalama Return: {avg_return:.2%}')
        print(f'   Ortalama İşlem Sayısı: {avg_trades:.1f}')
        print(f'   Ortalama Sinyal Sayısı: {avg_signals:.1f}')
        print(f'   Ortalama Win Rate: {avg_winrate:.1f}%')
        
        # Top recommendations
        print(f'\n🎯 ÖNERİLER:')
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
    test_comprehensive_nasdaq_stocks()
