#!/usr/bin/env python3
"""
ONDO Simple Optimizer - Working version
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import logging
from itertools import product

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_ondo_data(timeframe='1h'):
    """Get ONDO data"""
    try:
        ticker = yf.Ticker("ONDO-USD")
        
        if timeframe == '15m':
            period = '1mo'
        else:
            period = '3mo'
            
        data = ticker.history(period=period, interval=timeframe)
        
        if data.empty:
            return None
            
        # Clean data
        data.columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
        data = data.drop(['Dividends', 'Stock Splits'], axis=1)
        
        logger.info(f"✅ Data loaded: {len(data)} candles for {timeframe}")
        return data
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return None

def simple_moving_average_strategy(data, fast_period=10, slow_period=20):
    """Simple MA crossover strategy"""
    data = data.copy()
    
    # Calculate moving averages
    data['ma_fast'] = data['Close'].rolling(window=fast_period).mean()
    data['ma_slow'] = data['Close'].rolling(window=slow_period).mean()
    
    # Generate signals
    data['signal'] = 0
    data.loc[data['ma_fast'] > data['ma_slow'], 'signal'] = 1
    data.loc[data['ma_fast'] < data['ma_slow'], 'signal'] = -1
    
    # Calculate position changes
    data['position'] = data['signal'].diff()
    
    return data

def backtest_strategy(data, initial_capital=10000):
    """Simple backtest"""
    capital = initial_capital
    position = 0
    trades = []
    
    for i in range(len(data)):
        if data['position'].iloc[i] == 1 and position == 0:  # Buy
            position = capital * 0.2 / data['Close'].iloc[i]
            capital -= capital * 0.2
            trades.append({'type': 'buy', 'price': data['Close'].iloc[i], 'time': data.index[i]})
            
        elif data['position'].iloc[i] == -1 and position > 0:  # Sell
            pnl = position * data['Close'].iloc[i] - capital * 0.2
            capital += position * data['Close'].iloc[i]
            trades.append({'type': 'sell', 'price': data['Close'].iloc[i], 'pnl': pnl, 'time': data.index[i]})
            position = 0
    
    # Calculate metrics
    if trades:
        total_pnl = sum([t.get('pnl', 0) for t in trades])
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
        
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        profit_factor = abs(sum([t['pnl'] for t in winning_trades]) / sum([t['pnl'] for t in losing_trades])) if losing_trades else float('inf')
        
        return {
            'total_pnl': total_pnl,
            'total_return': (total_pnl / initial_capital) * 100,
            'num_trades': len(trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'final_capital': capital
        }
    else:
        return {
            'total_pnl': 0,
            'total_return': 0,
            'num_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'final_capital': capital
        }

def optimize_ondo():
    """Optimize ONDO strategy"""
    logger.info("🚀 Starting ONDO Simple Optimization")
    
    timeframes = ['15m', '1h']
    results = {}
    
    for timeframe in timeframes:
        logger.info(f"🎯 Optimizing {timeframe}")
        
        # Get data
        data = get_ondo_data(timeframe)
        if data is None:
            continue
        
        # Parameter ranges
        fast_periods = [5, 10, 15, 20]
        slow_periods = [20, 30, 40, 50]
        
        best_result = None
        best_score = -float('inf')
        all_results = []
        
        # Test all combinations
        for fast, slow in product(fast_periods, slow_periods):
            if fast >= slow:
                continue
                
            try:
                # Run strategy
                strategy_data = simple_moving_average_strategy(data, fast, slow)
                result = backtest_strategy(strategy_data)
                
                # Calculate score
                score = result['total_return'] * 0.4 + result['profit_factor'] * 0.3 + result['win_rate'] * 0.3
                
                result['score'] = score
                result['fast_period'] = fast
                result['slow_period'] = slow
                result['timeframe'] = timeframe
                
                all_results.append(result)
                
                if score > best_score:
                    best_score = score
                    best_result = result
                    
            except Exception as e:
                logger.error(f"❌ Error with {fast}/{slow}: {e}")
                continue
        
        # Sort results
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        results[timeframe] = {
            'best_result': best_result,
            'top_results': all_results[:5],
            'all_results': all_results
        }
        
        logger.info(f"✅ {timeframe} completed: {len(all_results)} valid results")
    
    # Print results
    print("\n" + "="*80)
    print("🎯 ONDO Simple Optimization Results")
    print("="*80)
    
    for timeframe, result in results.items():
        if result['best_result']:
            best = result['best_result']
            print(f"\n📊 {timeframe.upper()} TIMEFRAME:")
            print(f"   🏆 Best Score: {best['score']:.2f}")
            print(f"   💰 Total Return: {best['total_return']:.2f}%")
            print(f"   📈 Profit Factor: {best['profit_factor']:.2f}")
            print(f"   🎯 Win Rate: {best['win_rate']:.2f}%")
            print(f"   📊 Total Trades: {best['num_trades']}")
            print(f"   ⚙️ Parameters: MA({best['fast_period']}, {best['slow_period']})")
        else:
            print(f"\n❌ {timeframe.upper()}: No valid results")
    
    print("\n" + "="*80)
    
    return results

if __name__ == "__main__":
    optimize_ondo()
