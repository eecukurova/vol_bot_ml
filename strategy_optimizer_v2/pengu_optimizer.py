#!/usr/bin/env python3
"""
PENGU ATR SuperTrend Optimizer
Find best parameters for PENGU/USDT
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
from itertools import product

class PenguOptimizer:
    def __init__(self):
        self.exchange = ccxt.binance()
        self.symbol = "PENGU/USDT"
        
    def fetch_data(self, timeframe='1h', limit=1000):
        """Fetch OHLCV data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"❌ Data fetch error: {e}")
            return None
    
    def calculate_heikin_ashi(self, df):
        """Calculate Heikin Ashi candles"""
        ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_open = ha_close.copy()
        
        for i in range(1, len(ha_open)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        
        ha_high = df[['high', 'ha_open', 'ha_close']].max(axis=1)
        ha_low = df[['low', 'ha_open', 'ha_close']].min(axis=1)
        
        df['ha_open'] = ha_open
        df['ha_high'] = ha_high
        df['ha_low'] = ha_low
        df['ha_close'] = ha_close
        
        return df
    
    def calculate_atr(self, df, period):
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def calculate_supertrend(self, df, atr_period, atr_multiplier, supertrend_multiplier):
        """Calculate SuperTrend"""
        # Calculate ATR
        atr = self.calculate_atr(df, atr_period)
        
        # Use Heikin Ashi or regular close
        src = df['ha_close'] if 'ha_close' in df else df['close']
        
        # Calculate nLoss
        n_loss = atr_multiplier * atr
        
        # Initialize trailing stop
        xATRTrailingStop = np.nan
        pos = np.zeros(len(df))
        
        for i in range(len(df)):
            if pd.isna(xATRTrailingStop):
                xATRTrailingStop = src.iloc[i] - n_loss.iloc[i]
            else:
                if src.iloc[i] > xATRTrailingStop and src.iloc[i-1] > xATRTrailingStop:
                    xATRTrailingStop = max(xATRTrailingStop, src.iloc[i] - n_loss.iloc[i])
                elif src.iloc[i] < xATRTrailingStop and src.iloc[i-1] < xATRTrailingStop:
                    xATRTrailingStop = min(xATRTrailingStop, src.iloc[i] + n_loss.iloc[i])
                elif src.iloc[i] > xATRTrailingStop:
                    xATRTrailingStop = src.iloc[i] - n_loss.iloc[i]
                else:
                    xATRTrailingStop = src.iloc[i] + n_loss.iloc[i]
            
            # Position
            if i > 0:
                if src.iloc[i-1] < prev_xATRTrailingStop and src.iloc[i] > xATRTrailingStop:
                    pos[i] = 1
                elif src.iloc[i-1] > prev_xATRTrailingStop and src.iloc[i] < xATRTrailingStop:
                    pos[i] = -1
                else:
                    pos[i] = pos[i-1]
            
            prev_xATRTrailingStop = xATRTrailingStop
        
        # SuperTrend
        supertrend = atr * supertrend_multiplier
        trend_up = ((df['high'] + df['low']) / 2) - supertrend
        trend_down = ((df['high'] + df['low']) / 2) + supertrend
        
        supertrend_line = np.zeros(len(df))
        for i in range(len(df)):
            if i == 0:
                supertrend_line[i] = trend_down.iloc[i]
            else:
                if df['close'].iloc[i] > supertrend_line[i-1]:
                    supertrend_line[i] = max(trend_up.iloc[i], supertrend_line[i-1])
                else:
                    supertrend_line[i] = min(trend_down.iloc[i], supertrend_line[i-1])
        
        df['atr_trailing_stop'] = xATRTrailingStop
        df['supertrend_line'] = supertrend_line
        df['position'] = pos
        
        return df
    
    def calculate_rsi(self, df, period):
        """Calculate RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def backtest(self, df, params):
        """Backtest strategy"""
        # Apply Heikin Ashi if enabled
        if params['use_heikin_ashi']:
            df = self.calculate_heikin_ashi(df)
            src = df['ha_close']
        else:
            src = df['close']
        
        # Calculate indicators
        df = self.calculate_supertrend(df, params['atr_period'], 
                                       params['atr_multiplier'], 
                                       params['supertrend_multiplier'])
        
        rsi = self.calculate_rsi(df, params['rsi_period']) if params['use_rsi_filter'] else None
        
        # Volume filter
        volume_sma = df['volume'].rolling(window=20).mean()
        
        # Signals
        buy_signals = []
        sell_signals = []
        
        for i in range(1, len(df)):
            # Check filters
            volume_ok = not params['use_volume_filter'] or df['volume'].iloc[i] > volume_sma.iloc[i] * params['volume_multiplier']
            rsi_ok = not params['use_rsi_filter'] or (rsi is not None and params['rsi_oversold'] < rsi.iloc[i] < params['rsi_overbought'])
            
            # ATR signals
            buy_atr = df['position'].iloc[i] == 1 and df['position'].iloc[i-1] != 1
            sell_atr = df['position'].iloc[i] == -1 and df['position'].iloc[i-1] != -1
            
            # SuperTrend signals
            buy_supertrend = df['close'].iloc[i] > df['supertrend_line'].iloc[i] and df['close'].iloc[i-1] <= df['supertrend_line'].iloc[i-1]
            sell_supertrend = df['close'].iloc[i] < df['supertrend_line'].iloc[i] and df['close'].iloc[i-1] >= df['supertrend_line'].iloc[i-1]
            
            long_signal = (buy_atr or buy_supertrend) and volume_ok and rsi_ok
            short_signal = (sell_atr or sell_supertrend) and volume_ok and rsi_ok
            
            if long_signal:
                buy_signals.append(i)
            elif short_signal:
                sell_signals.append(i)
        
        # Calculate performance
        trades = []
        position = None
        
        for i in range(1, len(df)):
            if i in buy_signals and position is None:
                position = {
                    'entry': i,
                    'price': df['close'].iloc[i],
                    'side': 'long'
                }
            elif i in sell_signals and position is not None:
                exit_price = df['close'].iloc[i]
                pnl = (exit_price - position['price']) / position['price']
                if position['side'] == 'short':
                    pnl = -pnl
                
                trades.append({
                    'entry': position['entry'],
                    'exit': i,
                    'pnl': pnl,
                    'entry_price': position['price'],
                    'exit_price': exit_price
                })
                position = None
        
        if trades:
            profitable = [t for t in trades if t['pnl'] > 0]
            total_return = sum(t['pnl'] for t in trades)
            win_rate = len(profitable) / len(trades) * 100
            profit_factor = sum(t['pnl'] for t in trades if t['pnl'] > 0) / abs(sum(t['pnl'] for t in trades if t['pnl'] < 0)) if any(t['pnl'] < 0 for t in trades) else float('inf')
            
            return {
                'total_return': total_return,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'num_trades': len(trades),
                'params': params
            }
        else:
            return None
    
    def optimize(self, timeframes=['15m', '30m', '1h', '4h']):
        """Optimize parameters"""
        print("🚀 PENGU ATR SuperTrend Optimizer")
        print("="*80)
        
        # Parameter ranges
        param_ranges = {
            'atr_period': [12, 14, 16, 18, 20],
            'atr_multiplier': [2.0, 2.5, 3.0, 3.5, 4.0],
            'supertrend_multiplier': [1.0, 1.5, 2.0],
            'stop_loss_pct': [0.015, 0.02, 0.025],
            'take_profit_pct': [0.02, 0.025, 0.03, 0.035],
            'volume_multiplier': [1.2, 1.5, 1.8],
            'rsi_period': [10, 14, 18, 21],
            'rsi_oversold': [30, 35, 40],
            'rsi_overbought': [60, 65, 70],
            'use_heikin_ashi': [True, False],
            'use_volume_filter': [True, False],
            'use_rsi_filter': [True, False],
        }
        
        all_results = []
        
        for tf in timeframes:
            print(f"\n📊 Optimizing {tf} timeframe...")
            df = self.fetch_data(tf, limit=500)
            
            if df is None or len(df) < 100:
                print(f"❌ Not enough data for {tf}")
                continue
            
            # Calculate all parameter combinations
            param_names = list(param_ranges.keys())
            param_values = list(param_ranges.values())
            
            total_combinations = 1
            for v in param_values:
                total_combinations *= len(v)
            
            print(f"Total combinations: {total_combinations}")
            print("Testing... (this may take a while)")
            
            count = 0
            for params_dict in product(*param_values):
                params = dict(zip(param_names, params_dict))
                
                try:
                    result = self.backtest(df, params)
                    if result:
                        result['timeframe'] = tf
                        all_results.append(result)
                        count += 1
                        
                        if count % 10 == 0:
                            print(f"Tested {count}/{total_combinations}")
                except Exception as e:
                    continue
            
            print(f"✅ Tested {count} combinations for {tf}")
        
        # Sort results
        all_results.sort(key=lambda x: (x['total_return'], x['win_rate']), reverse=True)
        
        # Save results
        results_file = f"pengu_optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(all_results[:50], f, indent=2)
        
        print(f"\n✅ Top 10 Results:")
        print("="*80)
        for i, result in enumerate(all_results[:10], 1):
            print(f"{i}. {result['timeframe']} - Return: {result['total_return']:.2%}, "
                  f"WR: {result['win_rate']:.1f}%, Trades: {result['num_trades']}")
            print(f"   Params: {result['params']}")
        
        return all_results[:50]

if __name__ == "__main__":
    optimizer = PenguOptimizer()
    results = optimizer.optimize()
