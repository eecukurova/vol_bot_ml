#!/usr/bin/env python3
"""
Stable Breakout Strategy Optimizer for NASDAQ
Optimizes parameters to increase trade frequency while maintaining profitability
"""

import yfinance as yf
import pandas as pd
import numpy as np
from itertools import product
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StableBreakoutStrategy:
    """Stable Breakout Strategy Implementation"""
    
    def __init__(self, params):
        self.lenHigh = params.get('lenHigh', 50)
        self.lenVol = params.get('lenVol', 20)
        self.minRise = params.get('minRise', 1.5)
        self.volKatsay = params.get('volKatsay', 1.2)
        self.useRSI = params.get('useRSI', True)
        self.rsiLen = params.get('rsiLen', 14)
        self.rsiMin = params.get('rsiMin', 45.0)
        self.rsiMax = params.get('rsiMax', 75.0)
        self.useEMA = params.get('useEMA', False)
        self.emaLen = params.get('emaLen', 50)
        self.tpPct = params.get('tpPct', 3.0)
        self.slPct = params.get('slPct', 1.5)
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, df):
        """Generate trading signals"""
        df = df.copy()
        
        # Calculate indicators
        df['highestN'] = df['High'].rolling(window=self.lenHigh).max().shift(1)
        df['smaVol'] = df['Volume'].rolling(window=self.lenVol).mean()
        
        if self.useRSI:
            df['rsi'] = self.calculate_rsi(df['Close'], self.rsiLen)
        
        if self.useEMA:
            df['ema'] = df['Close'].ewm(span=self.emaLen, adjust=False).mean()
        
        # Conditions
        cond1 = df['Close'] > df['highestN']
        cond2 = ((df['Close'] - df['Open']) / df['Open']) * 100 >= self.minRise
        cond3 = df['Volume'] > df['smaVol'] * self.volKatsay
        
        if self.useRSI:
            cond4 = (df['rsi'] >= self.rsiMin) & (df['rsi'] <= self.rsiMax)
        else:
            cond4 = pd.Series([True] * len(df), index=df.index)
        
        if self.useEMA:
            cond5 = df['Close'] > df['ema']
        else:
            cond5 = pd.Series([True] * len(df), index=df.index)
        
        # Signal
        df['signal'] = cond1 & cond2 & cond3 & cond4 & cond5
        
        return df
    
    def backtest(self, df, initial_capital=100000):
        """Backtest strategy"""
        df = self.generate_signals(df)
        
        capital = initial_capital
        position = None
        trades = []
        equity_curve = [capital]
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Exit conditions
            if position is not None:
                entry_price = position['entry_price']
                entry_idx = position['entry_idx']
                
                # TP/SL
                tp_price = entry_price * (1 + self.tpPct / 100.0)
                sl_price = entry_price * (1 - self.slPct / 100.0)
                
                if row['High'] >= tp_price:
                    # TP hit
                    exit_price = tp_price
                    pnl_pct = (exit_price - entry_price) / entry_price
                    pnl = capital * 0.1 * pnl_pct  # 10% position size
                    capital += pnl
                    trades.append({
                        'entry': entry_price,
                        'exit': exit_price,
                        'entry_time': df.index[entry_idx],
                        'exit_time': df.index[i],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct * 100,
                        'type': 'TP'
                    })
                    position = None
                elif row['Low'] <= sl_price:
                    # SL hit
                    exit_price = sl_price
                    pnl_pct = (exit_price - entry_price) / entry_price
                    pnl = capital * 0.1 * pnl_pct
                    capital += pnl
                    trades.append({
                        'entry': entry_price,
                        'exit': exit_price,
                        'entry_time': df.index[entry_idx],
                        'exit_time': df.index[i],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct * 100,
                        'type': 'SL'
                    })
                    position = None
            
            # Entry conditions
            if position is None and row['signal']:
                position = {
                    'entry_price': row['Close'],
                    'entry_idx': i
                }
            
            equity_curve.append(capital)
        
        # Close open position
        if position is not None:
            last_price = df.iloc[-1]['Close']
            entry_price = position['entry_price']
            pnl_pct = (last_price - entry_price) / entry_price
            pnl = capital * 0.1 * pnl_pct
            capital += pnl
            trades.append({
                'entry': entry_price,
                'exit': last_price,
                'entry_time': df.index[position['entry_idx']],
                'exit_time': df.index[-1],
                'pnl': pnl,
                'pnl_pct': pnl_pct * 100,
                'type': 'CLOSE'
            })
        
        # Calculate metrics
        if not trades:
            return {
                'total_return': 0,
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_trade': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0
            }
        
        trades_df = pd.DataFrame(trades)
        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] <= 0]
        
        total_return = (capital - initial_capital) / initial_capital * 100
        win_rate = len(winning_trades) / len(trades) if len(trades) > 0 else 0
        
        total_profit = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
        total_loss = abs(losing_trades['pnl'].sum()) if len(losing_trades) > 0 else 0.0001
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        avg_trade = trades_df['pnl'].mean()
        
        # Max drawdown
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100
        
        # Sharpe ratio (simplified)
        returns = trades_df['pnl_pct'] / 100
        if len(returns) > 1 and returns.std() > 0:
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252)  # Annualized
        else:
            sharpe_ratio = 0
        
        return {
            'total_return': total_return,
            'total_trades': len(trades),
            'win_rate': win_rate * 100,
            'profit_factor': profit_factor,
            'avg_trade': avg_trade,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'trades': trades
        }


def optimize_stable_breakout(symbols=None, period='2y', interval='1d'):
    """Optimize Stable Breakout Strategy for NASDAQ"""
    
    if symbols is None:
        symbols = ['AAPL', 'AMD', 'NVDA', 'MSFT', 'TSLA', 'GOOGL', 'META', 'AMZN']
    
    logger.info(f"🚀 Starting Stable Breakout Optimization")
    logger.info(f"📊 Symbols: {symbols}")
    logger.info(f"⏰ Period: {period}, Interval: {interval}")
    
    # Parameter ranges (optimized for more trades)
    param_space = {
        'lenHigh': [30, 40, 50, 60, 80, 100],  # Reduced from 200
        'lenVol': [15, 20, 25, 30],  # Reduced from 30
        'minRise': [1.0, 1.5, 2.0, 2.5, 3.0],  # Reduced from 4.0
        'volKatsay': [1.0, 1.2, 1.5],  # Reduced from 1.5
        'useRSI': [True, False],
        'rsiMin': [40.0, 45.0, 50.0],
        'rsiMax': [70.0, 75.0, 80.0],
        'useEMA': [False],  # Keep simple for now
        'tpPct': [2.5, 3.0, 3.5, 4.0],
        'slPct': [1.0, 1.5, 2.0]
    }
    
    all_results = []
    
    for symbol in symbols:
        logger.info(f"\n{'='*80}")
        logger.info(f"📈 Optimizing {symbol}")
        logger.info(f"{'='*80}")
        
        try:
            # Fetch data
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty or len(df) < 200:
                logger.warning(f"⚠️ Insufficient data for {symbol}")
                continue
            
            # Rename columns to match strategy
            df.columns = [col.replace(' ', '') for col in df.columns]
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            
            logger.info(f"✅ Data loaded: {len(df)} bars")
            
            # Generate parameter combinations
            param_names = list(param_space.keys())
            param_values = list(param_space.values())
            
            total_combinations = 1
            for vals in param_values:
                total_combinations *= len(vals)
            
            logger.info(f"🔧 Testing {total_combinations} parameter combinations...")
            
            best_result = None
            best_score = -float('inf')
            symbol_results = []
            
            for i, params_tuple in enumerate(product(*param_values)):
                params = dict(zip(param_names, params_tuple))
                
                try:
                    strategy = StableBreakoutStrategy(params)
                    result = strategy.backtest(df)
                    
                    # Calculate optimization score (balance between trades and profitability)
                    # More weight on trade count to increase frequency
                    trade_score = min(result['total_trades'] / 50.0, 1.0) * 0.4  # Normalize to 50 trades max
                    return_score = min(result['total_return'] / 50.0, 1.0) * 0.3  # Normalize to 50% max
                    win_rate_score = result['win_rate'] / 100.0 * 0.2
                    profit_factor_score = min(result['profit_factor'] / 3.0, 1.0) * 0.1
                    
                    score = trade_score + return_score + win_rate_score + profit_factor_score
                    
                    result['symbol'] = symbol
                    result['params'] = params
                    result['score'] = score
                    
                    symbol_results.append(result)
                    
                    if score > best_score:
                        best_score = score
                        best_result = result
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"  Progress: {i+1}/{total_combinations} (Best: {best_result['total_trades']} trades, {best_result['total_return']:.2f}% return)")
                
                except Exception as e:
                    logger.debug(f"  Error with params {params}: {e}")
                    continue
            
            # Sort by score
            symbol_results.sort(key=lambda x: x['score'], reverse=True)
            
            logger.info(f"\n✅ {symbol} optimization completed")
            logger.info(f"📊 Best result:")
            logger.info(f"   Trades: {best_result['total_trades']}")
            logger.info(f"   Return: {best_result['total_return']:.2f}%")
            logger.info(f"   Win Rate: {best_result['win_rate']:.2f}%")
            logger.info(f"   Profit Factor: {best_result['profit_factor']:.2f}")
            logger.info(f"   Max DD: {best_result['max_drawdown']:.2f}%")
            logger.info(f"   Params: {best_result['params']}")
            
            all_results.append({
                'symbol': symbol,
                'best_result': best_result,
                'top_10': symbol_results[:10]
            })
        
        except Exception as e:
            logger.error(f"❌ Error optimizing {symbol}: {e}")
            continue
    
    # Save results
    results_file = Path('stable_breakout_optimization_results.json')
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"✅ Optimization completed!")
    logger.info(f"📁 Results saved to: {results_file}")
    logger.info(f"{'='*80}\n")
    
    # Print summary
    print("\n" + "="*80)
    print("📊 OPTIMIZATION SUMMARY")
    print("="*80)
    for result in all_results:
        best = result['best_result']
        print(f"\n{symbol}:")
        print(f"  Trades: {best['total_trades']}")
        print(f"  Return: {best['total_return']:.2f}%")
        print(f"  Win Rate: {best['win_rate']:.2f}%")
        print(f"  Profit Factor: {best['profit_factor']:.2f}")
        print(f"  Params: {best['params']}")
    
    return all_results


if __name__ == '__main__':
    import sys
    
    symbols = None
    if len(sys.argv) > 1:
        symbols = sys.argv[1].split(',')
    
    optimize_stable_breakout(symbols=symbols)

