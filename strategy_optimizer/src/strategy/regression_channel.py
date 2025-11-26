"""
Regression Channel Strategy with Volatility Oscillator
Volensy - Regresyon Kanalları ve Volatilite Stratejisi
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class RegressionChannelStrategy:
    """Regression Channel Strategy with Volatility Oscillator"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        Initialize Regression Channel Strategy
        
        Args:
            params: Strategy parameters
                - reg_len: Regression period (default: 100)
                - inner_mult: Inner band StdDev multiplier (default: 1.0)
                - outer_mult: Outer band StdDev multiplier (default: 1.2 for crypto)
                - sma_len: SMA length for trend filter (default: 14)
                - use_trend_filter: Use trend filter (default: False for crypto)
                - stoch_len: Stochastic length (default: 14)
                - smooth_k: K smoothing (default: 3)
                - smooth_d: D smoothing (default: 3)
                - ob_level: Overbought level (default: 75 for crypto)
                - os_level: Oversold level (default: 25 for crypto)
                - tp_pct: Take profit percentage (default: 0.01 = 1%)
                - sl_pct: Stop loss percentage (default: 0.01 = 1%)
        """
        self.reg_len = params.get('reg_len', 100)
        self.inner_mult = params.get('inner_mult', 1.0)
        self.outer_mult = params.get('outer_mult', 1.2)
        self.sma_len = params.get('sma_len', 14)
        self.use_trend_filter = params.get('use_trend_filter', False)
        self.stoch_len = params.get('stoch_len', 14)
        self.smooth_k = params.get('smooth_k', 3)
        self.smooth_d = params.get('smooth_d', 3)
        self.ob_level = params.get('ob_level', 75.0)
        self.os_level = params.get('os_level', 25.0)
        self.tp_pct = params.get('tp_pct', 0.01)
        self.sl_pct = params.get('sl_pct', 0.01)
        
    def calculate_regression_channel(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate regression channel indicators"""
        result = df.copy()
        
        # Regression line (linear regression) - Pine Script ta.linreg equivalent
        # ta.linreg(src, length, offset) calculates linear regression at offset
        # For offset=0, it's the value at the current bar
        def calc_regression(series):
            if len(series) < self.reg_len:
                return np.nan
            x = np.arange(len(series))
            y = series.values
            # Linear regression: y = ax + b
            coeffs = np.polyfit(x, y, 1)
            # Value at the last point (offset=0 in Pine Script)
            return coeffs[0] * (len(series) - 1) + coeffs[1]
        
        # Use rolling apply for regression
        result['regression_line'] = result['close'].rolling(
            window=self.reg_len, min_periods=self.reg_len
        ).apply(calc_regression, raw=False)
        
        # StdDev
        result['reg_dev'] = result['close'].rolling(
            window=self.reg_len, min_periods=self.reg_len
        ).std()
        
        # Inner bands
        result['upper_inner'] = result['regression_line'] + result['reg_dev'] * self.inner_mult
        result['lower_inner'] = result['regression_line'] - result['reg_dev'] * self.inner_mult
        
        # Outer bands
        result['upper_outer'] = result['regression_line'] + result['reg_dev'] * self.outer_mult
        result['lower_outer'] = result['regression_line'] - result['reg_dev'] * self.outer_mult
        
        # SMA for trend filter
        result['sma'] = result['close'].rolling(
            window=self.sma_len, min_periods=self.sma_len
        ).mean()
        
        return result
    
    def calculate_volatility_oscillator(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volatility oscillator (Stochastic-like)"""
        result = df.copy()
        
        # Calculate Stochastic %K
        low_min = result['low'].rolling(window=self.stoch_len, min_periods=self.stoch_len).min()
        high_max = result['high'].rolling(window=self.stoch_len, min_periods=self.stoch_len).max()
        
        k_raw = 100 * (result['close'] - low_min) / (high_max - low_min)
        k_raw = k_raw.replace([np.inf, -np.inf], np.nan)
        
        # Smooth K
        result['k'] = k_raw.rolling(window=self.smooth_k, min_periods=self.smooth_k).mean()
        
        # Smooth D (smooth of K)
        result['d'] = result['k'].rolling(window=self.smooth_d, min_periods=self.smooth_d).mean()
        
        return result
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals"""
        result = df.copy()
        
        # Calculate indicators
        result = self.calculate_regression_channel(result)
        result = self.calculate_volatility_oscillator(result)
        
        # Initialize signal columns
        result['signal'] = 0  # 0: no signal, 1: long, -1: short
        result['buy_cond'] = False
        result['sell_cond'] = False
        
        # Check if we have enough data
        min_periods = max(self.reg_len, self.stoch_len, self.sma_len)
        
        for i in range(min_periods, len(result)):
            # Current values
            close = result['close'].iloc[i]
            upper_outer = result['upper_outer'].iloc[i]
            lower_outer = result['lower_outer'].iloc[i]
            k = result['k'].iloc[i]
            d = result['d'].iloc[i]
            k_prev = result['k'].iloc[i-1] if i > 0 else k
            d_prev = result['d'].iloc[i-1] if i > 0 else d
            sma = result['sma'].iloc[i]
            
            # Previous values for crossover detection
            close_prev = result['close'].iloc[i-1] if i > 0 else close
            
            # 1) Check if price is in extreme zone
            in_extreme_low = close <= lower_outer
            in_extreme_high = close >= upper_outer
            
            # 2) Trend filter (for crypto, usually disabled)
            bull_trend = not self.use_trend_filter or close > sma
            bear_trend = not self.use_trend_filter or close < sma
            
            # 3) Volatility oscillator signals (crypto mode: K and D crossover)
            # Crypto: K crosses D, with level filter
            vol_buy = k < self.os_level and k_prev <= d_prev and k > d  # K crosses above D from oversold
            vol_sell = k > self.ob_level and k_prev >= d_prev and k < d  # K crosses below D from overbought
            
            # 4) Final buy/sell conditions
            buy_cond = in_extreme_low and bull_trend and vol_buy
            sell_cond = in_extreme_high and bear_trend and vol_sell
            
            result.loc[result.index[i], 'buy_cond'] = buy_cond
            result.loc[result.index[i], 'sell_cond'] = sell_cond
            
            if buy_cond:
                result.loc[result.index[i], 'signal'] = 1
            elif sell_cond:
                result.loc[result.index[i], 'signal'] = -1
        
        return result
    
    def run_backtest(self, df: pd.DataFrame, 
                    commission: float = 0.0005,
                    slippage: float = 0.0002) -> Dict[str, Any]:
        """
        Run backtest on data
        
        Args:
            df: OHLCV DataFrame
            commission: Commission per trade (default: 0.05%)
            slippage: Slippage per trade (default: 0.02%)
            
        Returns:
            Dictionary with backtest results
        """
        # Generate signals
        df_signals = self.generate_signals(df)
        
        # Initialize backtest state
        capital = 100000.0
        initial_capital = capital
        position = None  # None, 'long', or 'short'
        entry_price = 0.0
        entry_time = None
        stop_loss = 0.0
        take_profit = 0.0
        
        trades = []
        equity_curve = []
        max_equity = initial_capital
        max_drawdown = 0.0
        
        winning_trades = 0
        losing_trades = 0
        total_pnl = 0.0
        
        # Process each bar
        for i, (timestamp, row) in enumerate(df_signals.iterrows()):
            current_price = row['close']
            high = row['high']
            low = row['low']
            signal = row['signal']
            
            # Check stop loss / take profit first
            if position == 'long':
                # Check SL
                if low <= stop_loss:
                    exit_price = stop_loss
                    pnl = (exit_price - entry_price) / entry_price
                    pnl_amount = capital * pnl
                    capital += pnl_amount
                    total_pnl += pnl_amount
                    
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'side': 'long',
                        'pnl_pct': pnl * 100,
                        'pnl_amount': pnl_amount,
                        'exit_reason': 'sl'
                    })
                    
                    if pnl > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1
                    
                    position = None
                # Check TP
                elif high >= take_profit:
                    exit_price = take_profit
                    pnl = (exit_price - entry_price) / entry_price
                    pnl_amount = capital * pnl
                    capital += pnl_amount
                    total_pnl += pnl_amount
                    
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'side': 'long',
                        'pnl_pct': pnl * 100,
                        'pnl_amount': pnl_amount,
                        'exit_reason': 'tp'
                    })
                    
                    winning_trades += 1
                    position = None
                    
            elif position == 'short':
                # Check SL
                if high >= stop_loss:
                    exit_price = stop_loss
                    pnl = (entry_price - exit_price) / entry_price
                    pnl_amount = capital * pnl
                    capital += pnl_amount
                    total_pnl += pnl_amount
                    
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'side': 'short',
                        'pnl_pct': pnl * 100,
                        'pnl_amount': pnl_amount,
                        'exit_reason': 'sl'
                    })
                    
                    if pnl > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1
                    
                    position = None
                # Check TP
                elif low <= take_profit:
                    exit_price = take_profit
                    pnl = (entry_price - exit_price) / entry_price
                    pnl_amount = capital * pnl
                    capital += pnl_amount
                    total_pnl += pnl_amount
                    
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'side': 'short',
                        'pnl_pct': pnl * 100,
                        'pnl_amount': pnl_amount,
                        'exit_reason': 'tp'
                    })
                    
                    winning_trades += 1
                    position = None
            
            # Process new signals
            if position is None and signal != 0:
                if signal == 1:  # Buy signal
                    # Close short if exists
                    if position == 'short':
                        exit_price = current_price * (1 - slippage)
                        pnl = (entry_price - exit_price) / entry_price
                        pnl_amount = capital * pnl
                        capital += pnl_amount
                        total_pnl += pnl_amount
                        
                        trades.append({
                            'entry_time': entry_time,
                            'exit_time': timestamp,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'side': 'short',
                            'pnl_pct': pnl * 100,
                            'pnl_amount': pnl_amount,
                            'exit_reason': 'signal'
                        })
                    
                    # Open long
                    entry_price = current_price * (1 + slippage)
                    entry_time = timestamp
                    stop_loss = entry_price * (1 - self.sl_pct)
                    take_profit = entry_price * (1 + self.tp_pct)
                    position = 'long'
                    
                elif signal == -1:  # Sell signal
                    # Close long if exists
                    if position == 'long':
                        exit_price = current_price * (1 - slippage)
                        pnl = (exit_price - entry_price) / entry_price
                        pnl_amount = capital * pnl
                        capital += pnl_amount
                        total_pnl += pnl_amount
                        
                        trades.append({
                            'entry_time': entry_time,
                            'exit_time': timestamp,
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'side': 'long',
                            'pnl_pct': pnl * 100,
                            'pnl_amount': pnl_amount,
                            'exit_reason': 'signal'
                        })
                    
                    # Open short
                    entry_price = current_price * (1 - slippage)
                    entry_time = timestamp
                    stop_loss = entry_price * (1 + self.sl_pct)
                    take_profit = entry_price * (1 - self.tp_pct)
                    position = 'short'
            
            # Update equity curve
            if position == 'long':
                unrealized_pnl = (current_price - entry_price) / entry_price
                equity = capital * (1 + unrealized_pnl)
            elif position == 'short':
                unrealized_pnl = (entry_price - current_price) / entry_price
                equity = capital * (1 + unrealized_pnl)
            else:
                equity = capital
            
            equity_curve.append(equity)
            
            # Update max drawdown
            if equity > max_equity:
                max_equity = equity
            drawdown = (max_equity - equity) / max_equity * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Close any open position at the end
        if position is not None:
            final_price = df_signals['close'].iloc[-1]
            if position == 'long':
                exit_price = final_price * (1 - slippage)
                pnl = (exit_price - entry_price) / entry_price
            else:
                exit_price = final_price * (1 + slippage)
                pnl = (entry_price - exit_price) / entry_price
            
            pnl_amount = capital * pnl
            capital += pnl_amount
            total_pnl += pnl_amount
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': df_signals.index[-1],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'side': position,
                'pnl_pct': pnl * 100,
                'pnl_amount': pnl_amount,
                'exit_reason': 'end'
            })
            
            if pnl > 0:
                winning_trades += 1
            else:
                losing_trades += 1
        
        # Calculate metrics
        total_trades = len(trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_return_pct = ((capital - initial_capital) / initial_capital) * 100
        
        # Profit factor
        gross_profit = sum([t['pnl_amount'] for t in trades if t['pnl_amount'] > 0])
        gross_loss = abs(sum([t['pnl_amount'] for t in trades if t['pnl_amount'] < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Average win/loss
        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_return_pct': total_return_pct,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown,
            'avg_win_pct': avg_win / initial_capital * 100 if winning_trades > 0 else 0,
            'avg_loss_pct': avg_loss / initial_capital * 100 if losing_trades > 0 else 0,
            'final_capital': capital,
            'trades': trades,
            'equity_curve': equity_curve
        }

