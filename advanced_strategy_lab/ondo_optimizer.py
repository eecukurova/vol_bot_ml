#!/usr/bin/env python3
"""
ONDO ATR SuperTrend Strategy Optimizer

Bu script ONDO USDT için ATR SuperTrend stratejisini optimize eder.
15m ve 1h timeframe'lerde backtest yapar ve en iyi parametreleri bulur.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Any
import json
import os
from itertools import product
import warnings
warnings.filterwarnings('ignore')

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ONDOATRSuperTrendStrategy:
    """ONDO ATR SuperTrend Strategy Implementation"""
    
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.atr_period = params.get('atr_period', 10)
        self.atr_multiplier = params.get('atr_multiplier', 3.0)
        self.supertrend_multiplier = params.get('supertrend_multiplier', 1.5)
        self.use_heikin_ashi = params.get('use_heikin_ashi', True)
        self.stop_loss_pct = params.get('stop_loss_pct', 0.02)
        self.take_profit_pct = params.get('take_profit_pct', 0.035)
        self.use_volume_filter = params.get('use_volume_filter', True)
        self.volume_multiplier = params.get('volume_multiplier', 1.4)
        self.use_rsi_filter = params.get('use_rsi_filter', True)
        self.rsi_period = params.get('rsi_period', 14)
        self.rsi_oversold = params.get('rsi_oversold', 35)
        self.rsi_overbought = params.get('rsi_overbought', 65)
        
    def calculate_heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Heikin Ashi candles"""
        ha_df = df.copy()
        
        # Initialize first candle
        ha_df.loc[0, 'ha_close'] = (df.loc[0, 'Open'] + df.loc[0, 'High'] + df.loc[0, 'Low'] + df.loc[0, 'Close']) / 4
        ha_df.loc[0, 'ha_open'] = df.loc[0, 'Open']
        
        for i in range(1, len(df)):
            # Heikin Ashi Close
            ha_df.loc[i, 'ha_close'] = (df.loc[i, 'Open'] + df.loc[i, 'High'] + df.loc[i, 'Low'] + df.loc[i, 'Close']) / 4
            
            # Heikin Ashi Open
            ha_df.loc[i, 'ha_open'] = (ha_df.loc[i-1, 'ha_open'] + ha_df.loc[i-1, 'ha_close']) / 2
            
            # Heikin Ashi High
            ha_df.loc[i, 'ha_high'] = max(df.loc[i, 'High'], ha_df.loc[i, 'ha_open'], ha_df.loc[i, 'ha_close'])
            
            # Heikin Ashi Low
            ha_df.loc[i, 'ha_low'] = min(df.loc[i, 'Low'], ha_df.loc[i, 'ha_open'], ha_df.loc[i, 'ha_close'])
        
        return ha_df
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        return atr
    
    def calculate_supertrend(self, df: pd.DataFrame, atr: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Calculate SuperTrend indicator"""
        hl2 = (df['High'] + df['Low']) / 2
        supertrend = atr * self.supertrend_multiplier
        
        trend_up = hl2 - supertrend
        trend_down = hl2 + supertrend
        
        supertrend_line = pd.Series(index=df.index, dtype=float)
        
        for i in range(len(df)):
            if i == 0:
                supertrend_line.iloc[i] = trend_down.iloc[i]
            else:
                if df['Close'].iloc[i] > supertrend_line.iloc[i-1]:
                    supertrend_line.iloc[i] = max(trend_up.iloc[i], supertrend_line.iloc[i-1])
                else:
                    supertrend_line.iloc[i] = min(trend_down.iloc[i], supertrend_line.iloc[i-1])
        
        return supertrend_line, trend_up, trend_down
    
    def calculate_atr_trailing_stop(self, df: pd.DataFrame, atr: pd.Series) -> pd.Series:
        """Calculate ATR Trailing Stop"""
        src = df['ha_close'] if self.use_heikin_ashi else df['Close']
        n_loss = self.atr_multiplier * atr
        
        trailing_stop = pd.Series(index=df.index, dtype=float)
        
        for i in range(len(df)):
            if i == 0:
                trailing_stop.iloc[i] = src.iloc[i] - n_loss.iloc[i]
            else:
                if (src.iloc[i] > trailing_stop.iloc[i-1] and 
                    src.iloc[i-1] > trailing_stop.iloc[i-1]):
                    trailing_stop.iloc[i] = max(trailing_stop.iloc[i-1], src.iloc[i] - n_loss.iloc[i])
                elif (src.iloc[i] < trailing_stop.iloc[i-1] and 
                      src.iloc[i-1] < trailing_stop.iloc[i-1]):
                    trailing_stop.iloc[i] = min(trailing_stop.iloc[i-1], src.iloc[i] + n_loss.iloc[i])
                elif src.iloc[i] > trailing_stop.iloc[i-1]:
                    trailing_stop.iloc[i] = src.iloc[i] - n_loss.iloc[i]
                else:
                    trailing_stop.iloc[i] = src.iloc[i] + n_loss.iloc[i]
        
        return trailing_stop
    
    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """Calculate RSI"""
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals"""
        signals_df = df.copy()
        
        # Calculate Heikin Ashi if needed
        if self.use_heikin_ashi:
            signals_df = self.calculate_heikin_ashi(signals_df)
            src = signals_df['ha_close']
        else:
            src = signals_df['Close']
        
        # Calculate indicators
        atr = self.calculate_atr(signals_df)
        supertrend_line, trend_up, trend_down = self.calculate_supertrend(signals_df, atr)
        trailing_stop = self.calculate_atr_trailing_stop(signals_df, atr)
        rsi = self.calculate_rsi(signals_df)
        
        # Volume filter
        volume_sma = signals_df['Volume'].rolling(window=20).mean()
        volume_condition = signals_df['Volume'] > volume_sma * self.volume_multiplier
        
        # RSI filter
        rsi_condition_long = rsi < self.rsi_overbought
        rsi_condition_short = rsi > self.rsi_oversold
        
        # ATR SuperTrend signals
        ema_fast = src.ewm(span=1).mean()
        above_crossover = (ema_fast > trailing_stop) & (ema_fast.shift(1) <= trailing_stop.shift(1))
        below_crossover = (trailing_stop > ema_fast) & (trailing_stop.shift(1) <= ema_fast.shift(1))
        
        buy_atr = (src > trailing_stop) & above_crossover
        sell_atr = (src < trailing_stop) & below_crossover
        
        # SuperTrend signals
        buy_supertrend = (signals_df['Close'] > supertrend_line) & (signals_df['Close'].shift(1) <= supertrend_line.shift(1))
        sell_supertrend = (signals_df['Close'] < supertrend_line) & (signals_df['Close'].shift(1) >= supertrend_line.shift(1))
        
        # Combined filters
        filters_ok_long = volume_condition & rsi_condition_long
        filters_ok_short = volume_condition & rsi_condition_short
        
        # Final signals
        long_condition = (buy_atr | buy_supertrend) & filters_ok_long
        short_condition = (sell_atr | sell_supertrend) & filters_ok_short
        
        signals_df['long_signal'] = long_condition
        signals_df['short_signal'] = short_condition
        signals_df['atr'] = atr
        signals_df['supertrend_line'] = supertrend_line
        signals_df['trailing_stop'] = trailing_stop
        signals_df['rsi'] = rsi
        
        return signals_df

class ONDOBacktester:
    """ONDO Backtester"""
    
    def __init__(self, initial_capital: float = 10000.0, fee_bps: float = 10.0):
        self.initial_capital = initial_capital
        self.fee_bps = fee_bps / 10000.0  # Convert to decimal
        
    def run_backtest(self, df: pd.DataFrame, strategy: ONDOATRSuperTrendStrategy) -> Dict[str, Any]:
        """Run backtest"""
        signals_df = strategy.generate_signals(df)
        
        capital = self.initial_capital
        position = 0
        position_size = 0
        entry_price = 0
        trades = []
        
        for i in range(len(signals_df)):
            current_price = signals_df['Close'].iloc[i]
            
            # Long signal
            if signals_df['long_signal'].iloc[i] and position == 0:
                position = 1
                position_size = capital * 0.2  # 20% position size
                entry_price = current_price
                capital -= position_size
                
            # Short signal
            elif signals_df['short_signal'].iloc[i] and position == 0:
                position = -1
                position_size = capital * 0.2  # 20% position size
                entry_price = current_price
                capital -= position_size
                
            # Exit conditions
            elif position != 0:
                exit_price = current_price
                pnl = 0
                
                if position == 1:  # Long position
                    # Stop loss
                    if current_price <= entry_price * (1 - strategy.stop_loss_pct):
                        pnl = position_size * (current_price / entry_price - 1)
                        exit_reason = "Stop Loss"
                    # Take profit
                    elif current_price >= entry_price * (1 + strategy.take_profit_pct):
                        pnl = position_size * (current_price / entry_price - 1)
                        exit_reason = "Take Profit"
                    # Trailing stop
                    elif current_price <= signals_df['trailing_stop'].iloc[i]:
                        pnl = position_size * (current_price / entry_price - 1)
                        exit_reason = "Trailing Stop"
                    else:
                        continue
                        
                elif position == -1:  # Short position
                    # Stop loss
                    if current_price >= entry_price * (1 + strategy.stop_loss_pct):
                        pnl = position_size * (entry_price / current_price - 1)
                        exit_reason = "Stop Loss"
                    # Take profit
                    elif current_price <= entry_price * (1 - strategy.take_profit_pct):
                        pnl = position_size * (entry_price / current_price - 1)
                        exit_reason = "Take Profit"
                    # Trailing stop
                    elif current_price >= signals_df['trailing_stop'].iloc[i]:
                        pnl = position_size * (entry_price / current_price - 1)
                        exit_reason = "Trailing Stop"
                    else:
                        continue
                
                # Apply fees
                fee = position_size * self.fee_bps
                pnl -= fee
                
                # Update capital
                capital += position_size + pnl
                
                # Record trade
                trades.append({
                    'entry_time': signals_df.index[i-1],
                    'exit_time': signals_df.index[i],
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'position': position,
                    'pnl': pnl,
                    'exit_reason': exit_reason
                })
                
                # Reset position
                position = 0
                position_size = 0
                entry_price = 0
        
        # Calculate metrics
        if trades:
            trades_df = pd.DataFrame(trades)
            total_pnl = trades_df['pnl'].sum()
            winning_trades = trades_df[trades_df['pnl'] > 0]
            losing_trades = trades_df[trades_df['pnl'] < 0]
            
            win_rate = len(winning_trades) / len(trades) * 100
            profit_factor = abs(winning_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 else float('inf')
            avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
            avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
            
            # Calculate drawdown
            cumulative_pnl = trades_df['pnl'].cumsum()
            running_max = cumulative_pnl.expanding().max()
            drawdown = (cumulative_pnl - running_max) / running_max * 100
            max_drawdown = drawdown.min()
            
        else:
            total_pnl = 0
            win_rate = 0
            profit_factor = 0
            avg_win = 0
            avg_loss = 0
            max_drawdown = 0
        
        return {
            'total_pnl': total_pnl,
            'total_return': total_pnl / self.initial_capital * 100,
            'num_trades': len(trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'final_capital': capital,
            'trades': trades
        }

class ONDOOptimizer:
    """ONDO Strategy Optimizer"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def get_ondo_data(self, timeframe: str = '1h', period: str = '6mo') -> pd.DataFrame:
        """Get ONDO data from Yahoo Finance"""
        try:
            ticker = yf.Ticker("ONDO-USD")
            
            # Map timeframe to interval - Use shorter periods for 15m
            if timeframe == '15m':
                period = '1mo'  # 15m data only available for 1 month
            elif timeframe == '1h':
                period = '3mo'  # 1h data available for 3 months
            
            interval_map = {
                '15m': '15m',
                '1h': '1h',
                '4h': '1h',  # Use 1h for 4h
                '1d': '1d'
            }
            
            interval = interval_map.get(timeframe, '1h')
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                self.logger.error(f"❌ No data found for ONDO-USD {timeframe}")
                return None
                
            # Rename columns to standard format
            data.columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
            data = data.drop(['Dividends', 'Stock Splits'], axis=1)
            
            self.logger.info(f"✅ ONDO data loaded: {len(data)} candles for {timeframe} ({period})")
            return data
            
        except Exception as e:
            self.logger.error(f"❌ Error loading ONDO data: {e}")
            return None
    
    def optimize_timeframe(self, timeframe: str) -> Dict[str, Any]:
        """Optimize strategy for specific timeframe"""
        self.logger.info(f"🎯 Optimizing ONDO ATR SuperTrend for {timeframe}")
        
        # Get data
        data = self.get_ondo_data(timeframe)
        if data is None:
            return None
        
        # Parameter ranges - Simplified for faster optimization
        param_ranges = {
            'atr_period': [10, 12, 14],
            'atr_multiplier': [2.5, 3.0, 3.5],
            'supertrend_multiplier': [1.2, 1.5, 1.8],
            'stop_loss_pct': [0.02, 0.025],
            'take_profit_pct': [0.035, 0.045],
            'volume_multiplier': [1.4, 1.6],
            'rsi_period': [14, 18],
            'rsi_oversold': [35, 40],
            'rsi_overbought': [60, 65]
        }
        
        # Generate combinations
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        combinations = list(product(*param_values))
        
        self.logger.info(f"📊 Testing {len(combinations)} parameter combinations...")
        
        results = []
        best_result = None
        best_score = -float('inf')
        
        backtester = ONDOBacktester()
        
        for i, params in enumerate(combinations):
            try:
                param_dict = dict(zip(param_names, params))
                param_dict.update({
                    'use_heikin_ashi': True,
                    'use_volume_filter': True,
                    'use_rsi_filter': True
                })
                
                strategy = ONDOATRSuperTrendStrategy(param_dict)
                result = backtester.run_backtest(data, strategy)
                
                # Calculate optimization score
                score = self.calculate_optimization_score(result)
                result['optimization_score'] = score
                result['timeframe'] = timeframe
                result['parameters'] = param_dict
                
                results.append(result)
                
                if score > best_score:
                    best_score = score
                    best_result = result
                
                if (i + 1) % 100 == 0:
                    self.logger.info(f"📈 Processed {i + 1}/{len(combinations)} combinations")
                    
            except Exception as e:
                self.logger.error(f"❌ Error in optimization {i}: {e}")
                continue
        
        # Sort results by score
        results.sort(key=lambda x: x['optimization_score'], reverse=True)
        
        self.logger.info(f"✅ {timeframe} optimization completed: {len(results)} valid results")
        return {
            'timeframe': timeframe,
            'best_result': best_result,
            'top_results': results[:10],
            'all_results': results
        }
    
    def calculate_optimization_score(self, result: Dict[str, Any]) -> float:
        """Calculate optimization score"""
        if result['num_trades'] < 5:  # Minimum trades
            return 0
        
        # Weighted score
        score = (
            result['total_return'] * 0.3 +  # Total return
            result['profit_factor'] * 0.25 +  # Profit factor
            result['win_rate'] * 0.2 +  # Win rate
            result['num_trades'] * 0.1 +  # Number of trades
            (100 + result['max_drawdown']) * 0.15  # Drawdown (lower is better)
        )
        
        return score
    
    def run_optimization(self):
        """Run full optimization"""
        self.logger.info("🚀 Starting ONDO ATR SuperTrend Optimization")
        
        timeframes = ['15m', '1h']
        all_results = {}
        
        for timeframe in timeframes:
            result = self.optimize_timeframe(timeframe)
            if result:
                all_results[timeframe] = result
        
        # Save results
        self.save_results(all_results)
        
        # Print summary
        self.print_summary(all_results)
        
        return all_results
    
    def save_results(self, results: Dict[str, Any]):
        """Save optimization results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ondo_optimization_results_{timestamp}.json"
        
        # Convert numpy types to Python types for JSON serialization
        def convert_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj
        
        # Clean results for JSON
        clean_results = {}
        for timeframe, result in results.items():
            if result and result.get('best_result'):
                clean_results[timeframe] = {
                    'timeframe': result['timeframe'],
                    'best_result': {k: convert_types(v) for k, v in result['best_result'].items() if k != 'trades'},
                    'top_results': [{k: convert_types(v) for k, v in r.items() if k != 'trades'} for r in result['top_results']]
                }
            else:
                clean_results[timeframe] = {
                    'timeframe': timeframe,
                    'best_result': None,
                    'top_results': [],
                    'error': 'No valid results found'
                }
        
        with open(filename, 'w') as f:
            json.dump(clean_results, f, indent=2)
        
        self.logger.info(f"💾 Results saved to {filename}")
    
    def print_summary(self, results: Dict[str, Any]):
        """Print optimization summary"""
        print("\n" + "="*80)
        print("🎯 ONDO ATR SuperTrend Optimization Results")
        print("="*80)
        
        for timeframe, result in results.items():
            if result and result.get('best_result'):
                best = result['best_result']
                print(f"\n📊 {timeframe.upper()} TIMEFRAME:")
                print(f"   🏆 Best Score: {best['optimization_score']:.2f}")
                print(f"   💰 Total Return: {best['total_return']:.2f}%")
                print(f"   📈 Profit Factor: {best['profit_factor']:.2f}")
                print(f"   🎯 Win Rate: {best['win_rate']:.2f}%")
                print(f"   📊 Total Trades: {best['num_trades']}")
                print(f"   📉 Max Drawdown: {best['max_drawdown']:.2f}%")
                
                print(f"\n   ⚙️ Best Parameters:")
                for param, value in best['parameters'].items():
                    print(f"      {param}: {value}")
            else:
                print(f"\n❌ {timeframe.upper()} TIMEFRAME: No valid results found")
        
        print("\n" + "="*80)

def main():
    """Main function"""
    optimizer = ONDOOptimizer()
    results = optimizer.run_optimization()
    
    if results:
        print("\n🎉 Optimization completed successfully!")
        print("📁 Check the generated JSON file for detailed results.")
    else:
        print("\n❌ Optimization failed!")

if __name__ == "__main__":
    main()
