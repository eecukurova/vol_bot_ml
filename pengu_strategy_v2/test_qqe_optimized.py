#!/usr/bin/env python3
"""
QQE MT4 Glaz Strategy - Optimized Parameters Test
"""

import pandas as pd
import numpy as np
from src.data.nasdaq_provider import NASDAQDataProvider
from typing import Dict, List, Any

class QQEMT4GlazStrategy:
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.rsi_period = params.get('rsi_period', 14)
        self.sf = params.get('sf', 5)  # RSI Smoothing
        self.qqe = params.get('qqe', 4.238)  # Fast QQE Factor
        self.threshold = params.get('threshold', 10)  # Threshold
        
        # Calculate Wilders Period
        self.wilders_period = self.rsi_period * 2 - 1
    
    def calculate_rsi(self, src: pd.Series, period: int) -> pd.Series:
        """Calculate RSI"""
        delta = src.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_ema(self, src: pd.Series, period: int) -> pd.Series:
        """Calculate EMA"""
        return src.ewm(span=period).mean()
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators for QQE MT4 Glaz strategy"""
        df = df.copy()
        
        # Calculate RSI
        df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)
        
        # Calculate RSI MA (smoothed RSI)
        df['rsi_ma'] = self.calculate_ema(df['rsi'], self.sf)
        
        # Calculate ATR RSI
        df['atr_rsi'] = abs(df['rsi_ma'].shift(1) - df['rsi_ma'])
        
        # Calculate MA ATR RSI
        df['ma_atr_rsi'] = self.calculate_ema(df['atr_rsi'], self.wilders_period)
        
        # Calculate DAR (Dynamic Adaptive Range)
        df['dar'] = self.calculate_ema(df['ma_atr_rsi'], self.wilders_period) * self.qqe
        
        # Initialize bands and trend
        df['longband'] = 0.0
        df['shortband'] = 0.0
        df['trend'] = 0
        
        # Calculate QQE bands and trend
        for i in range(1, len(df)):
            delta_fast_atr_rsi = df['dar'].iloc[i]
            rsi_index = df['rsi_ma'].iloc[i]
            
            new_shortband = rsi_index + delta_fast_atr_rsi
            new_longband = rsi_index - delta_fast_atr_rsi
            
            # Update longband
            if (df['rsi_ma'].iloc[i-1] > df['longband'].iloc[i-1] and 
                rsi_index > df['longband'].iloc[i-1]):
                df['longband'].iloc[i] = max(df['longband'].iloc[i-1], new_longband)
            else:
                df['longband'].iloc[i] = new_longband
            
            # Update shortband
            if (df['rsi_ma'].iloc[i-1] < df['shortband'].iloc[i-1] and 
                rsi_index < df['shortband'].iloc[i-1]):
                df['shortband'].iloc[i] = min(df['shortband'].iloc[i-1], new_shortband)
            else:
                df['shortband'].iloc[i] = new_shortband
            
            # Update trend
            prev_trend = df['trend'].iloc[i-1] if i > 0 else 1
            
            if (rsi_index > df['shortband'].iloc[i-1] and 
                df['rsi_ma'].iloc[i-1] <= df['shortband'].iloc[i-1]):
                df['trend'].iloc[i] = 1
            elif (df['longband'].iloc[i-1] > rsi_index and 
                  df['longband'].iloc[i-1] >= df['rsi_ma'].iloc[i-1]):
                df['trend'].iloc[i] = -1
            else:
                df['trend'].iloc[i] = prev_trend
        
        # Calculate Fast ATR RSI Trend Line
        df['fast_atr_rsi_tl'] = np.where(df['trend'] == 1, df['longband'], df['shortband'])
        
        # Calculate signals
        df['qqe_signal'] = np.where(df['rsi_ma'] > df['fast_atr_rsi_tl'], 1, -1)
        
        # Threshold channel signals
        df['qqe_long_signal'] = df['rsi_ma'] > (50 + self.threshold)
        df['qqe_short_signal'] = df['rsi_ma'] < (50 - self.threshold)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate trading signals based on QQE MT4 Glaz strategy"""
        signals = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # QQE Cross signals
            if (current['qqe_signal'] == 1 and previous['qqe_signal'] == -1):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'BUY',
                    'price': current['close'],
                    'rsi_ma': current['rsi_ma'],
                    'fast_tl': current['fast_atr_rsi_tl'],
                    'confidence': 1.0
                })
            elif (current['qqe_signal'] == -1 and previous['qqe_signal'] == 1):
                signals.append({
                    'timestamp': current.name,
                    'signal_type': 'SELL',
                    'price': current['close'],
                    'rsi_ma': current['rsi_ma'],
                    'fast_tl': current['fast_atr_rsi_tl'],
                    'confidence': 1.0
                })
        
        return signals

def test_qqe_optimized():
    """Test QQE MT4 Glaz strategy with optimized parameters"""
    print('🚀 QQE MT4 GLAZ STRATEJİSİ - OPTİMİZE EDİLMİŞ PARAMETRELER')
    print('='*70)
    
    # Test stocks
    symbols = ['MSFT', 'AAPL', 'NVDA', 'TSLA', 'AMZN']
    
    # Test different parameter sets
    param_sets = [
        {
            'name': 'Orijinal',
            'params': {'rsi_period': 14, 'sf': 5, 'qqe': 4.238, 'threshold': 10}
        },
        {
            'name': 'Agresif',
            'params': {'rsi_period': 10, 'sf': 3, 'qqe': 2.5, 'threshold': 5}
        },
        {
            'name': 'Çok Agresif',
            'params': {'rsi_period': 7, 'sf': 2, 'qqe': 1.8, 'threshold': 3}
        },
        {
            'name': 'Ultra Agresif',
            'params': {'rsi_period': 5, 'sf': 1, 'qqe': 1.2, 'threshold': 2}
        }
    ]
    
    provider = NASDAQDataProvider()
    all_results = []
    
    for param_set in param_sets:
        print(f'\n📊 {param_set["name"]} Parametreler Test Ediliyor...')
        print(f'   RSI Period: {param_set["params"]["rsi_period"]}')
        print(f'   SF: {param_set["params"]["sf"]}')
        print(f'   QQE: {param_set["params"]["qqe"]}')
        print(f'   Threshold: {param_set["params"]["threshold"]}')
        
        param_results = []
        
        for symbol in symbols:
            try:
                # Get data
                data = provider.fetch_data(symbol, period='1y', interval='1d')
                data = data.reset_index()
                if 'date' in data.columns:
                    data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
                    data.set_index('date', inplace=True)
                
                # Create strategy
                strategy = QQEMT4GlazStrategy(param_set['params'])
                
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
                        'param_set': param_set['name'],
                        'total_trades': len(trades),
                        'win_rate': win_rate,
                        'total_return': total_return,
                        'signals_count': len(signals)
                    }
                    param_results.append(result)
                    
                    print(f'   {symbol}: {len(trades)} işlem, {win_rate:.1f}% WR, {total_return:.2%} return')
                else:
                    print(f'   {symbol}: İşlem yok, {len(signals)} sinyal')
                    
            except Exception as e:
                print(f'   {symbol}: Hata - {e}')
        
        # Calculate averages for this parameter set
        if param_results:
            avg_trades = sum(r['total_trades'] for r in param_results) / len(param_results)
            avg_win_rate = sum(r['win_rate'] for r in param_results) / len(param_results)
            avg_return = sum(r['total_return'] for r in param_results) / len(param_results)
            avg_signals = sum(r['signals_count'] for r in param_results) / len(param_results)
            
            print(f'\n📈 {param_set["name"]} Ortalama:')
            print(f'   İşlem sayısı: {avg_trades:.1f}')
            print(f'   Win Rate: {avg_win_rate:.1f}%')
            print(f'   Total Return: {avg_return:.2%}')
            print(f'   Sinyal sayısı: {avg_signals:.1f}')
            
            all_results.extend(param_results)
    
    # Find best parameter set
    if all_results:
        print(f'\n🏆 EN İYİ PARAMETRE SETİ')
        print('='*70)
        
        # Group by parameter set
        param_groups = {}
        for result in all_results:
            param_set = result['param_set']
            if param_set not in param_groups:
                param_groups[param_set] = []
            param_groups[param_set].append(result)
        
        # Calculate averages for each parameter set
        param_averages = {}
        for param_set, results in param_groups.items():
            avg_trades = sum(r['total_trades'] for r in results) / len(results)
            avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
            avg_return = sum(r['total_return'] for r in results) / len(results)
            avg_signals = sum(r['signals_count'] for r in results) / len(results)
            
            param_averages[param_set] = {
                'avg_trades': avg_trades,
                'avg_win_rate': avg_win_rate,
                'avg_return': avg_return,
                'avg_signals': avg_signals
            }
        
        # Sort by total return
        sorted_params = sorted(param_averages.items(), key=lambda x: x[1]['avg_return'], reverse=True)
        
        for i, (param_set, metrics) in enumerate(sorted_params, 1):
            print(f'{i}. {param_set}:')
            print(f'   İşlem sayısı: {metrics["avg_trades"]:.1f}')
            print(f'   Win Rate: {metrics["avg_win_rate"]:.1f}%')
            print(f'   Total Return: {metrics["avg_return"]:.2%}')
            print(f'   Sinyal sayısı: {metrics["avg_signals"]:.1f}')
            print()
        
        # Best performing stock
        best_stock = max(all_results, key=lambda x: x['total_return'])
        print(f'🥇 En İyi Hisse: {best_stock["symbol"]} ({best_stock["param_set"]})')
        print(f'   Win Rate: {best_stock["win_rate"]:.1f}%')
        print(f'   Total Return: {best_stock["total_return"]:.2%}')
        print(f'   Total Trades: {best_stock["total_trades"]}')
        
        return all_results
    else:
        print(f'\n❌ Hiçbir parametre setinde işlem yapılamadı!')
        return []

if __name__ == "__main__":
    test_qqe_optimized()
