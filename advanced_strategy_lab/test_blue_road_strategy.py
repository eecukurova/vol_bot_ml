#!/usr/bin/env python3
"""
BLUE_ROAD Strategy Implementation and Testing
"""

import pandas as pd
import numpy as np
from src.data.nasdaq_provider import NASDAQDataProvider
from typing import Dict, List, Any, Tuple

class BlueRoadStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.xtl_period = params.get('xtl_period', 25)
        self.threshold = params.get('threshold', 34)
        self.dma_length = params.get('dma_length', 8)
        self.dma_displacement = params.get('dma_displacement', 5)
        self.stop_loss_ratio = params.get('stop_loss_ratio', 0.5)
        self.entry_ratio = params.get('entry_ratio', 1.5)
        self.target1_ratio = params.get('target1_ratio', 3.0)
        self.target2_ratio = params.get('target2_ratio', 4.0)
    
    def calculate_cci(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Commodity Channel Index"""
        hlc3 = (df['high'] + df['low'] + df['close']) / 3
        sma_hlc3 = hlc3.rolling(window=period).mean()
        mad = hlc3.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())))
        cci = (hlc3 - sma_hlc3) / (0.015 * mad)
        return cci
    
    def calculate_dma(self, df: pd.DataFrame, length: int) -> Tuple[pd.Series, pd.Series]:
        """Calculate Displaced Moving Average"""
        dma1 = df['low'].rolling(window=length).mean()
        dma2 = df['high'].rolling(window=length).mean()
        return dma1, dma2
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators for BLUE_ROAD strategy"""
        df = df.copy()
        
        # Calculate CCI (XTL)
        df['cci'] = self.calculate_cci(df, self.xtl_period)
        
        # Calculate DMA
        df['dma1'], df['dma2'] = self.calculate_dma(df, self.dma_length)
        
        # Calculate signals
        df['bull'] = df['cci'] > self.threshold
        df['bear'] = df['cci'] < -self.threshold
        df['neutral'] = (df['cci'] <= self.threshold) & (df['cci'] >= -self.threshold)
        
        # Calculate state
        df['state'] = 0
        for i in range(1, len(df)):
            if df['bear'].iloc[i]:
                df['state'].iloc[i] = 0
            elif df['bull'].iloc[i]:
                df['state'].iloc[i] = 1
            else:
                df['state'].iloc[i] = df['state'].iloc[i-1]
        
        # Calculate breakout levels
        df['range'] = df['high'] - df['low']
        df['prev_state'] = df['state'].shift(1)
        
        # Calculate stop, entry, and target levels
        df['stop'] = np.where(
            df['state'] > df['prev_state'],
            df['low'] - df['range'] * self.stop_loss_ratio,
            np.where(
                df['state'] < df['prev_state'],
                df['high'] + df['range'] * self.stop_loss_ratio,
                np.nan
            )
        )
        
        df['entry'] = np.where(
            df['state'] > df['prev_state'],
            df['low'] + df['range'] * self.entry_ratio,
            np.where(
                df['state'] < df['prev_state'],
                df['high'] - df['range'] * self.entry_ratio,
                np.nan
            )
        )
        
        df['target1'] = np.where(
            df['state'] > df['prev_state'],
            df['low'] + df['range'] * self.target1_ratio,
            np.where(
                df['state'] < df['prev_state'],
                df['high'] - df['range'] * self.target1_ratio,
                np.nan
            )
        )
        
        df['target2'] = np.where(
            df['state'] > df['prev_state'],
            df['low'] + df['range'] * self.target2_ratio,
            np.where(
                df['state'] < df['prev_state'],
                df['high'] - df['range'] * self.target2_ratio,
                np.nan
            )
        )
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate trading signals based on BLUE_ROAD strategy"""
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # State change signals
            if current['state'] != previous['state']:
                if current['state'] == 1 and previous['state'] == 0:  # Bull signal
                    signals.append({
                        'timestamp': current.name,
                        'signal_type': 'BUY',
                        'price': current['entry'],
                        'stop_loss': current['stop'],
                        'take_profit': current['target1'],
                        'confidence': 1.0
                    })
                elif current['state'] == 0 and previous['state'] == 1:  # Bear signal
                    signals.append({
                        'timestamp': current.name,
                        'signal_type': 'SELL',
                        'price': current['entry'],
                        'stop_loss': current['stop'],
                        'take_profit': current['target1'],
                        'confidence': 1.0
                    })
        
        return signals

def test_blue_road_strategy():
    """Test BLUE_ROAD strategy on NASDAQ stocks"""
    print('🚀 BLUE_ROAD STRATEJİSİ TEST EDİLİYOR')
    print('='*60)
    
    # Test stocks
    symbols = ['MSFT', 'AAPL', 'NVDA', 'TSLA', 'AMZN']
    
    # Default parameters from Pine Script
    default_params = {
        'xtl_period': 25,
        'threshold': 34,
        'dma_length': 8,
        'dma_displacement': 5,
        'stop_loss_ratio': 0.5,
        'entry_ratio': 1.5,
        'target1_ratio': 3.0,
        'target2_ratio': 4.0
    }
    
    provider = NASDAQDataProvider()
    results = []
    
    for symbol in symbols:
        print(f'\n📊 {symbol} Test Ediliyor...')
        
        try:
            # Get data
            data = provider.fetch_data(symbol, period='1y', interval='1d')
            data = data.reset_index()
            if 'date' in data.columns:
                data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
                data.set_index('date', inplace=True)
            
            # Create strategy
            strategy = BlueRoadStrategy(default_params)
            
            # Calculate indicators
            data_with_indicators = strategy.calculate_indicators(data)
            
            # Generate signals
            signals = strategy.generate_signals(data_with_indicators)
            
            # Simple backtest
            trades = []
            position = None
            
            for signal in signals:
                if signal['signal_type'] == 'BUY' and position is None:
                    position = {
                        'side': 'BUY',
                        'entry_price': signal['price'],
                        'entry_time': signal['timestamp'],
                        'stop_loss': signal['stop_loss'],
                        'take_profit': signal['take_profit']
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
            
            # Calculate metrics
            if trades:
                profitable = sum(1 for t in trades if t['pnl'] > 0)
                win_rate = profitable / len(trades) * 100
                total_return = sum(t['pnl'] for t in trades)
                
                result = {
                    'symbol': symbol,
                    'total_trades': len(trades),
                    'win_rate': win_rate,
                    'total_return': total_return,
                    'signals_count': len(signals)
                }
                results.append(result)
                
                print(f'   ✅ İşlem sayısı: {len(trades)}')
                print(f'   📈 Win Rate: {win_rate:.1f}%')
                print(f'   💰 Total Return: {total_return:.2%}')
                print(f'   📊 Sinyal sayısı: {len(signals)}')
            else:
                print(f'   ❌ İşlem yapılamadı')
                
        except Exception as e:
            print(f'   ❌ Hata: {e}')
    
    # Summary
    if results:
        print(f'\n🏆 BLUE_ROAD STRATEJİSİ ÖZETİ')
        print('='*60)
        
        avg_trades = sum(r['total_trades'] for r in results) / len(results)
        avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
        avg_return = sum(r['total_return'] for r in results) / len(results)
        avg_signals = sum(r['signals_count'] for r in results) / len(results)
        
        print(f'📊 Ortalama Performans:')
        print(f'   İşlem sayısı: {avg_trades:.1f}')
        print(f'   Win Rate: {avg_win_rate:.1f}%')
        print(f'   Total Return: {avg_return:.2%}')
        print(f'   Sinyal sayısı: {avg_signals:.1f}')
        
        # Best performing stock
        best = max(results, key=lambda x: x['total_return'])
        print(f'\n🥇 En İyi Performans: {best["symbol"]}')
        print(f'   Win Rate: {best["win_rate"]:.1f}%')
        print(f'   Total Return: {best["total_return"]:.2%}')
        print(f'   Total Trades: {best["total_trades"]}')
        
        return results
    else:
        print(f'\n❌ Hiçbir hissede işlem yapılamadı!')
        return []

if __name__ == "__main__":
    test_blue_road_strategy()
