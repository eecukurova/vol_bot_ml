#!/usr/bin/env python3
"""
Multiple Strategy Testing - Bollinger Bands, EMA, Oscillators
"""

import pandas as pd
import numpy as np
from src.data.nasdaq_provider import NASDAQDataProvider
from typing import Dict, List, Any

class BollingerBandsStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.period = params.get('period', 20)
        self.std_dev = params.get('std_dev', 2.0)
        self.stop_loss = params.get('stop_loss', 0.02)
        self.take_profit = params.get('take_profit', 0.04)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Calculate Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=self.period).mean()
        bb_std = df['close'].rolling(window=self.period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * self.std_dev)
        df['bb_lower'] = df['bb_middle'] - (bb_std * self.std_dev)
        
        # Calculate BB position
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # Buy signal: Price touches lower band and bounces
            if (previous['close'] <= previous['bb_lower'] and 
                current['close'] > current['bb_lower'] and
                current['bb_position'] > 0.1):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'BUY',
                    'price': current['close'],
                    'bb_position': current['bb_position'],
                    'confidence': 1.0
                })
            
            # Sell signal: Price touches upper band and falls
            elif (previous['close'] >= previous['bb_upper'] and 
                  current['close'] < current['bb_upper'] and
                  current['bb_position'] < 0.9):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'SELL',
                    'price': current['close'],
                    'bb_position': current['bb_position'],
                    'confidence': 1.0
                })
        
        return signals

class EMAStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.fast_ema = params.get('fast_ema', 12)
        self.slow_ema = params.get('slow_ema', 26)
        self.stop_loss = params.get('stop_loss', 0.02)
        self.take_profit = params.get('take_profit', 0.04)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=self.fast_ema).mean()
        df['ema_slow'] = df['close'].ewm(span=self.slow_ema).mean()
        
        # Calculate EMA difference
        df['ema_diff'] = df['ema_fast'] - df['ema_slow']
        df['ema_diff_pct'] = df['ema_diff'] / df['ema_slow'] * 100
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # Buy signal: Fast EMA crosses above Slow EMA
            if (previous['ema_fast'] <= previous['ema_slow'] and 
                current['ema_fast'] > current['ema_slow']):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'BUY',
                    'price': current['close'],
                    'ema_diff_pct': current['ema_diff_pct'],
                    'confidence': 1.0
                })
            
            # Sell signal: Fast EMA crosses below Slow EMA
            elif (previous['ema_fast'] >= previous['ema_slow'] and 
                  current['ema_fast'] < current['ema_slow']):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'SELL',
                    'price': current['close'],
                    'ema_diff_pct': current['ema_diff_pct'],
                    'confidence': 1.0
                })
        
        return signals

class RSIStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.period = params.get('period', 14)
        self.oversold = params.get('oversold', 30)
        self.overbought = params.get('overbought', 70)
        self.stop_loss = params.get('stop_loss', 0.02)
        self.take_profit = params.get('take_profit', 0.04)
    
    def calculate_rsi(self, src: pd.Series, period: int) -> pd.Series:
        delta = src.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['rsi'] = self.calculate_rsi(df['close'], self.period)
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # Buy signal: RSI crosses above oversold level
            if (previous['rsi'] <= self.oversold and 
                current['rsi'] > self.oversold):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'BUY',
                    'price': current['close'],
                    'rsi': current['rsi'],
                    'confidence': 1.0
                })
            
            # Sell signal: RSI crosses below overbought level
            elif (previous['rsi'] >= self.overbought and 
                  current['rsi'] < self.overbought):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'SELL',
                    'price': current['close'],
                    'rsi': current['rsi'],
                    'confidence': 1.0
                })
        
        return signals

class MACDStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.fast_ema = params.get('fast_ema', 12)
        self.slow_ema = params.get('slow_ema', 26)
        self.signal_ema = params.get('signal_ema', 9)
        self.stop_loss = params.get('stop_loss', 0.02)
        self.take_profit = params.get('take_profit', 0.04)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=self.fast_ema).mean()
        df['ema_slow'] = df['close'].ewm(span=self.slow_ema).mean()
        
        # Calculate MACD
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['macd_signal'] = df['macd'].ewm(span=self.signal_ema).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # Buy signal: MACD crosses above signal line
            if (previous['macd'] <= previous['macd_signal'] and 
                current['macd'] > current['macd_signal']):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'BUY',
                    'price': current['close'],
                    'macd': current['macd'],
                    'macd_signal': current['macd_signal'],
                    'confidence': 1.0
                })
            
            # Sell signal: MACD crosses below signal line
            elif (previous['macd'] >= previous['macd_signal'] and 
                  current['macd'] < current['macd_signal']):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'SELL',
                    'price': current['close'],
                    'macd': current['macd'],
                    'macd_signal': current['macd_signal'],
                    'confidence': 1.0
                })
        
        return signals

def backtest_strategy(signals: List[Dict[str, Any]], stop_loss: float = 0.02, take_profit: float = 0.04) -> List[Dict[str, Any]]:
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

def test_multiple_strategies():
    """Test multiple strategies on NASDAQ stocks"""
    print('🚀 ÇOKLU STRATEJİ TESTİ - BOLLINGER BANDS, EMA, RSI, MACD')
    print('='*70)
    
    # Test stocks
    symbols = ['MSFT', 'AAPL', 'NVDA', 'TSLA', 'AMZN']
    
    # Strategy configurations
    strategies = [
        {
            'name': 'Bollinger Bands',
            'class': BollingerBandsStrategy,
            'params': {'period': 20, 'std_dev': 2.0, 'stop_loss': 0.02, 'take_profit': 0.04}
        },
        {
            'name': 'EMA Crossover',
            'class': EMAStrategy,
            'params': {'fast_ema': 12, 'slow_ema': 26, 'stop_loss': 0.02, 'take_profit': 0.04}
        },
        {
            'name': 'RSI',
            'class': RSIStrategy,
            'params': {'period': 14, 'oversold': 30, 'overbought': 70, 'stop_loss': 0.02, 'take_profit': 0.04}
        },
        {
            'name': 'MACD',
            'class': MACDStrategy,
            'params': {'fast_ema': 12, 'slow_ema': 26, 'signal_ema': 9, 'stop_loss': 0.02, 'take_profit': 0.04}
        }
    ]
    
    provider = NASDAQDataProvider()
    all_results = []
    
    for strategy_config in strategies:
        print(f'\n📊 {strategy_config["name"]} Stratejisi Test Ediliyor...')
        
        strategy_results = []
        
        for symbol in symbols:
            try:
                # Get data
                data = provider.fetch_data(symbol, period='1y', interval='1d')
                data = data.reset_index()
                if 'date' in data.columns:
                    data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
                    data.set_index('date', inplace=True)
                
                # Create strategy
                strategy = strategy_config['class'](strategy_config['params'])
                
                # Calculate indicators
                data_with_indicators = strategy.calculate_indicators(data)
                
                # Generate signals
                signals = strategy.generate_signals(data_with_indicators)
                
                # Backtest
                trades = backtest_strategy(signals, 
                                        strategy_config['params']['stop_loss'],
                                        strategy_config['params']['take_profit'])
                
                # Calculate metrics
                if trades:
                    profitable = sum(1 for t in trades if t['pnl'] > 0)
                    win_rate = profitable / len(trades) * 100
                    total_return = sum(t['pnl'] for t in trades)
                    
                    result = {
                        'symbol': symbol,
                        'strategy': strategy_config['name'],
                        'total_trades': len(trades),
                        'win_rate': win_rate,
                        'total_return': total_return,
                        'signals_count': len(signals)
                    }
                    strategy_results.append(result)
                    
                    print(f'   {symbol}: {len(trades)} işlem, {win_rate:.1f}% WR, {total_return:.2%} return')
                else:
                    print(f'   {symbol}: İşlem yok, {len(signals)} sinyal')
                    
            except Exception as e:
                print(f'   {symbol}: Hata - {e}')
        
        # Calculate averages for this strategy
        if strategy_results:
            avg_trades = sum(r['total_trades'] for r in strategy_results) / len(strategy_results)
            avg_win_rate = sum(r['win_rate'] for r in strategy_results) / len(strategy_results)
            avg_return = sum(r['total_return'] for r in strategy_results) / len(strategy_results)
            avg_signals = sum(r['signals_count'] for r in strategy_results) / len(strategy_results)
            
            print(f'\n📈 {strategy_config["name"]} Ortalama:')
            print(f'   İşlem sayısı: {avg_trades:.1f}')
            print(f'   Win Rate: {avg_win_rate:.1f}%')
            print(f'   Total Return: {avg_return:.2%}')
            print(f'   Sinyal sayısı: {avg_signals:.1f}')
            
            all_results.extend(strategy_results)
    
    # Find best strategy
    if all_results:
        print(f'\n🏆 EN İYİ STRATEJİLER')
        print('='*70)
        
        # Group by strategy
        strategy_groups = {}
        for result in all_results:
            strategy = result['strategy']
            if strategy not in strategy_groups:
                strategy_groups[strategy] = []
            strategy_groups[strategy].append(result)
        
        # Calculate averages for each strategy
        strategy_averages = {}
        for strategy, results in strategy_groups.items():
            avg_trades = sum(r['total_trades'] for r in results) / len(results)
            avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
            avg_return = sum(r['total_return'] for r in results) / len(results)
            avg_signals = sum(r['signals_count'] for r in results) / len(results)
            
            strategy_averages[strategy] = {
                'avg_trades': avg_trades,
                'avg_win_rate': avg_win_rate,
                'avg_return': avg_return,
                'avg_signals': avg_signals
            }
        
        # Sort by total return
        sorted_strategies = sorted(strategy_averages.items(), key=lambda x: x[1]['avg_return'], reverse=True)
        
        for i, (strategy, metrics) in enumerate(sorted_strategies, 1):
            print(f'{i}. {strategy}:')
            print(f'   İşlem sayısı: {metrics["avg_trades"]:.1f}')
            print(f'   Win Rate: {metrics["avg_win_rate"]:.1f}%')
            print(f'   Total Return: {metrics["avg_return"]:.2%}')
            print(f'   Sinyal sayısı: {metrics["avg_signals"]:.1f}')
            print()
        
        # Best performing stock
        best_stock = max(all_results, key=lambda x: x['total_return'])
        print(f'🥇 En İyi Hisse: {best_stock["symbol"]} ({best_stock["strategy"]})')
        print(f'   Win Rate: {best_stock["win_rate"]:.1f}%')
        print(f'   Total Return: {best_stock["total_return"]:.2%}')
        print(f'   Total Trades: {best_stock["total_trades"]}')
        
        return all_results
    else:
        print(f'\n❌ Hiçbir stratejide işlem yapılamadı!')
        return []

if __name__ == "__main__":
    test_multiple_strategies()
