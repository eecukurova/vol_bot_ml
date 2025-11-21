#!/usr/bin/env python3
"""
TOTT (Twin Optimized Trend Tracker) Strategy Implementation and Testing
"""

import pandas as pd
import numpy as np
from src.data.nasdaq_provider import NASDAQDataProvider
from typing import Dict, List, Any, Tuple

class TOTTStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.length = params.get('length', 40)
        self.percent = params.get('percent', 1.0)
        self.coeff = params.get('coeff', 0.001)
        self.mav = params.get('mav', 'VAR')
    
    def calculate_var(self, src: pd.Series, length: int) -> pd.Series:
        """Calculate VAR (Variable Adaptive Rate) moving average"""
        valpha = 2 / (length + 1)
        
        vud1 = np.where(src > src.shift(1), src - src.shift(1), 0)
        vdd1 = np.where(src < src.shift(1), src.shift(1) - src, 0)
        
        vUD = pd.Series(vud1).rolling(window=9).sum()
        vDD = pd.Series(vdd1).rolling(window=9).sum()
        
        vCMO = (vUD - vDD) / (vUD + vDD)
        vCMO = vCMO.fillna(0)
        
        VAR = pd.Series(index=src.index, dtype=float)
        VAR.iloc[0] = src.iloc[0]
        
        for i in range(1, len(src)):
            VAR.iloc[i] = valpha * abs(vCMO.iloc[i]) * src.iloc[i] + (1 - valpha * abs(vCMO.iloc[i])) * VAR.iloc[i-1]
        
        return VAR
    
    def calculate_ma(self, src: pd.Series, length: int) -> pd.Series:
        """Calculate moving average based on type"""
        if self.mav == "SMA":
            return src.rolling(window=length).mean()
        elif self.mav == "EMA":
            return src.ewm(span=length).mean()
        elif self.mav == "WMA":
            weights = np.arange(1, length + 1)
            return src.rolling(window=length).apply(lambda x: np.average(x, weights=weights), raw=True)
        elif self.mav == "VAR":
            return self.calculate_var(src, length)
        else:
            return src.rolling(window=length).mean()  # Default to SMA
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators for TOTT strategy"""
        df = df.copy()
        
        # Calculate moving average
        df['MAvg'] = self.calculate_ma(df['close'], self.length)
        
        # Calculate fark (difference)
        df['fark'] = df['MAvg'] * self.percent * 0.01
        
        # Calculate long and short stops
        df['longStop'] = df['MAvg'] - df['fark']
        df['shortStop'] = df['MAvg'] + df['fark']
        
        # Calculate trailing stops
        df['longStopPrev'] = df['longStop'].shift(1)
        df['shortStopPrev'] = df['shortStop'].shift(1)
        
        # Update stops based on trend
        for i in range(1, len(df)):
            if df['MAvg'].iloc[i] > df['longStopPrev'].iloc[i]:
                df['longStop'].iloc[i] = max(df['longStop'].iloc[i], df['longStopPrev'].iloc[i])
            if df['MAvg'].iloc[i] < df['shortStopPrev'].iloc[i]:
                df['shortStop'].iloc[i] = min(df['shortStop'].iloc[i], df['shortStopPrev'].iloc[i])
        
        # Calculate direction
        df['dir'] = 1
        for i in range(1, len(df)):
            prev_dir = df['dir'].iloc[i-1]
            if prev_dir == -1 and df['MAvg'].iloc[i] > df['shortStopPrev'].iloc[i]:
                df['dir'].iloc[i] = 1
            elif prev_dir == 1 and df['MAvg'].iloc[i] < df['longStopPrev'].iloc[i]:
                df['dir'].iloc[i] = -1
            else:
                df['dir'].iloc[i] = prev_dir
        
        # Calculate MT (Moving Trend)
        df['MT'] = np.where(df['dir'] == 1, df['longStop'], df['shortStop'])
        
        # Calculate OTT (Optimized Trend Tracker)
        df['OTT'] = np.where(
            df['MAvg'] > df['MT'],
            df['MT'] * (200 + self.percent) / 200,
            df['MT'] * (200 - self.percent) / 200
        )
        
        # Calculate OTT up and down
        df['OTTup'] = df['OTT'] * (1 + self.coeff)
        df['OTTdn'] = df['OTT'] * (1 - self.coeff)
        
        # Shift OTT for signal calculation
        df['OTTup_shifted'] = df['OTTup'].shift(2)
        df['OTTdn_shifted'] = df['OTTdn'].shift(2)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate trading signals based on TOTT strategy"""
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # Buy signal: MAvg crosses above OTTup
            if (current['MAvg'] > current['OTTup_shifted'] and 
                previous['MAvg'] <= previous['OTTup_shifted']):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'BUY',
                    'price': current['close'],
                    'confidence': 1.0
                })
            
            # Sell signal: MAvg crosses below OTTdn
            elif (current['MAvg'] < current['OTTdn_shifted'] and 
                  previous['MAvg'] >= previous['OTTdn_shifted']):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'SELL',
                    'price': current['close'],
                    'confidence': 1.0
                })
        
        return signals

def test_tott_strategy():
    """Test TOTT strategy on NASDAQ stocks"""
    print('🚀 TOTT (Twin Optimized Trend Tracker) STRATEJİSİ TEST EDİLİYOR')
    print('='*70)
    
    # Test stocks
    symbols = ['MSFT', 'AAPL', 'NVDA', 'TSLA', 'AMZN']
    
    # Default parameters from Pine Script
    default_params = {
        'length': 40,
        'percent': 1.0,
        'coeff': 0.001,
        'mav': 'VAR'
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
            strategy = TOTTStrategy(default_params)
            
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
                        'entry_time': signal['timestamp']
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
        print(f'\n🏆 TOTT STRATEJİSİ ÖZETİ')
        print('='*70)
        
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
    test_tott_strategy()
