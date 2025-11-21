"""
Simple VWMA Strategy for ARB - Optimized
Basit ama etkili, gerçek veri ile test edilmiş
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class VWMAARBSimpleStrategy:
    """Simple VWMA Strategy for ARB - Clean Implementation"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        Initialize Simple VWMA Strategy for ARB
        
        Args:
            params: Strategy parameters
                - vwma_length: VWMA period
                - rsi_length: RSI period
                - rsi_oversold: RSI oversold level
                - rsi_overbought: RSI overbought level
                - ema_fast: Fast EMA period
                - ema_slow: Slow EMA period
                - tp_pct: Take profit percentage
                - sl_pct: Stop loss percentage
                - trailing_activation_pct: Trailing stop activation profit
                - trailing_distance_pct: Trailing stop distance
                - leverage: Leverage multiplier
                - commission: Commission rate
                - slippage: Slippage percentage
        """
        # Entry parameters
        self.vwma_length = params.get('vwma_length', 30)
        self.rsi_length = params.get('rsi_length', 14)
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_overbought = params.get('rsi_overbought', 70)
        self.ema_fast = params.get('ema_fast', 12)
        self.ema_slow = params.get('ema_slow', 26)
        self.volume_ma_length = params.get('volume_ma_length', 20)
        self.volume_threshold = params.get('volume_threshold', 1.2)
        
        # Exit parameters
        self.tp_pct = params.get('tp_pct', 0.8)
        self.sl_pct = params.get('sl_pct', 0.6)
        self.trailing_activation_pct = params.get('trailing_activation_pct', 0.5)
        self.trailing_distance_pct = params.get('trailing_distance_pct', 0.5)
        
        # Trading parameters
        self.leverage = params.get('leverage', 5.0)
        self.commission = params.get('commission', 0.0004)
        self.slippage = params.get('slippage', 0.0002)
        
    def calculate_vwma(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Volume Weighted Moving Average"""
        price_volume = df['close'] * df['volume']
        sum_price_volume = price_volume.rolling(window=self.vwma_length, min_periods=self.vwma_length).sum()
        sum_volume = df['volume'].rolling(window=self.vwma_length, min_periods=self.vwma_length).sum()
        vwma = sum_price_volume / sum_volume.replace(0, np.nan)
        return vwma
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return df['close'].ewm(span=period, adjust=False).mean()
    
    def calculate_volume_ma(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Volume Moving Average"""
        return df['volume'].rolling(window=self.volume_ma_length, min_periods=self.volume_ma_length).mean()
    
    def check_entry_long(self, df: pd.DataFrame, i: int) -> bool:
        """Check if LONG entry conditions are met"""
        if i < max(self.vwma_length, self.rsi_length, self.ema_slow, self.volume_ma_length):
            return False
        
        vwma_cond = df['close'].iloc[i] > df['vwma'].iloc[i]
        rsi_cond = df['rsi'].iloc[i] < self.rsi_overbought and df['rsi'].iloc[i] > self.rsi_oversold
        ema_cond = df['ema_fast'].iloc[i] > df['ema_slow'].iloc[i]
        volume_cond = df['volume'].iloc[i] > df['volume_ma'].iloc[i] * self.volume_threshold
        
        return vwma_cond and rsi_cond and ema_cond and volume_cond
    
    def check_entry_short(self, df: pd.DataFrame, i: int) -> bool:
        """Check if SHORT entry conditions are met"""
        if i < max(self.vwma_length, self.rsi_length, self.ema_slow, self.volume_ma_length):
            return False
        
        vwma_cond = df['close'].iloc[i] < df['vwma'].iloc[i]
        rsi_cond = df['rsi'].iloc[i] > self.rsi_oversold and df['rsi'].iloc[i] < self.rsi_overbought
        ema_cond = df['ema_fast'].iloc[i] < df['ema_slow'].iloc[i]
        volume_cond = df['volume'].iloc[i] > df['volume_ma'].iloc[i] * self.volume_threshold
        
        return vwma_cond and rsi_cond and ema_cond and volume_cond
    
    def run_backtest(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Run backtest - Simple and clean implementation
        """
        df = df.copy()
        df.columns = df.columns.str.lower()
        
        # Calculate indicators
        df['vwma'] = self.calculate_vwma(df)
        df['rsi'] = self.calculate_rsi(df, self.rsi_length)
        df['ema_fast'] = self.calculate_ema(df, self.ema_fast)
        df['ema_slow'] = self.calculate_ema(df, self.ema_slow)
        df['volume_ma'] = self.calculate_volume_ma(df)
        
        # Initialize
        position = None
        entry_price = None
        entry_index = None
        trailing_stop_price = None
        trailing_activated = False
        
        trades = []
        equity = 10000
        initial_equity = equity
        equity_curve = [equity]
        
        # Multipliers
        tp_mult = self.tp_pct / 100.0
        sl_mult = self.sl_pct / 100.0
        trailing_activation_mult = self.trailing_activation_pct / 100.0
        trailing_distance_mult = self.trailing_distance_pct / 100.0
        
        min_bars = max(self.vwma_length, self.rsi_length, self.ema_slow, self.volume_ma_length)
        
        # Main loop
        for i in range(min_bars, len(df)):
            current_price = df['close'].iloc[i]
            current_high = df['high'].iloc[i]
            current_low = df['low'].iloc[i]
            
            # Skip if NaN
            if (pd.isna(df['vwma'].iloc[i]) or pd.isna(df['rsi'].iloc[i]) or 
                pd.isna(df['ema_fast'].iloc[i]) or pd.isna(df['ema_slow'].iloc[i]) or
                pd.isna(df['volume_ma'].iloc[i])):
                continue
            
            # Exit conditions
            exit_signal = False
            exit_reason = None
            exit_price = None
            
            if position == 'LONG':
                current_profit_pct = ((current_price - entry_price) / entry_price) * 100
                
                # Activate trailing stop
                if not trailing_activated and current_profit_pct >= self.trailing_activation_pct:
                    trailing_activated = True
                    trailing_stop_price = entry_price * (1 + trailing_activation_mult - trailing_distance_mult)
                
                # Update trailing stop
                if trailing_activated:
                    new_trailing = current_price * (1 - trailing_distance_mult)
                    if new_trailing > trailing_stop_price:
                        trailing_stop_price = new_trailing
                
                # Check exits
                if trailing_activated and current_low <= trailing_stop_price:
                    exit_signal = True
                    exit_reason = 'TRAILING_STOP'
                    exit_price = trailing_stop_price
                elif current_high >= entry_price * (1 + tp_mult):
                    exit_signal = True
                    exit_reason = 'TP'
                    exit_price = entry_price * (1 + tp_mult)
                elif current_low <= entry_price * (1 - sl_mult):
                    exit_signal = True
                    exit_reason = 'SL'
                    exit_price = entry_price * (1 - sl_mult)
            
            elif position == 'SHORT':
                current_profit_pct = ((entry_price - current_price) / entry_price) * 100
                
                # Activate trailing stop
                if not trailing_activated and current_profit_pct >= self.trailing_activation_pct:
                    trailing_activated = True
                    trailing_stop_price = entry_price * (1 - trailing_activation_mult + trailing_distance_mult)
                
                # Update trailing stop
                if trailing_activated:
                    new_trailing = current_price * (1 + trailing_distance_mult)
                    if new_trailing < trailing_stop_price:
                        trailing_stop_price = new_trailing
                
                # Check exits
                if trailing_activated and current_high >= trailing_stop_price:
                    exit_signal = True
                    exit_reason = 'TRAILING_STOP'
                    exit_price = trailing_stop_price
                elif current_low <= entry_price * (1 - tp_mult):
                    exit_signal = True
                    exit_reason = 'TP'
                    exit_price = entry_price * (1 - tp_mult)
                elif current_high >= entry_price * (1 + sl_mult):
                    exit_signal = True
                    exit_reason = 'SL'
                    exit_price = entry_price * (1 + sl_mult)
            
            # Execute exit
            if exit_signal:
                if position == 'LONG':
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                
                pnl_pct -= (self.commission * 100 * 2)
                pnl_pct -= (self.slippage * 100 * 2)
                pnl_pct *= self.leverage
                
                equity *= (1 + pnl_pct / 100)
                equity_curve.append(equity)
                
                trades.append({
                    'entry_time': str(df.index[entry_index]),
                    'exit_time': str(df.index[i]),
                    'side': position,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'pnl_pct': pnl_pct,
                    'bars_held': i - entry_index
                })
                
                position = None
                entry_price = None
                entry_index = None
                trailing_stop_price = None
                trailing_activated = False
            
            # Entry conditions
            if position is None:
                if self.check_entry_long(df, i):
                    position = 'LONG'
                    entry_price = current_price * (1 + self.slippage)
                    entry_index = i
                    trailing_activated = False
                elif self.check_entry_short(df, i):
                    position = 'SHORT'
                    entry_price = current_price * (1 - self.slippage)
                    entry_index = i
                    trailing_activated = False
        
        # Close open position
        if position is not None:
            exit_price = df['close'].iloc[-1]
            if position == 'LONG':
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
            
            pnl_pct -= (self.commission * 100 * 2)
            pnl_pct -= (self.slippage * 100 * 2)
            pnl_pct *= self.leverage
            
            equity *= (1 + pnl_pct / 100)
            equity_curve.append(equity)
            
            trades.append({
                'entry_time': str(df.index[entry_index]),
                'exit_time': str(df.index[-1]),
                'side': position,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'exit_reason': 'END',
                'pnl_pct': pnl_pct,
                'bars_held': len(df) - entry_index
            })
        
        # Calculate metrics
        if len(trades) == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_return_pct': 0,
                'max_drawdown_pct': 0,
                'sharpe_ratio': 0,
                'avg_win_pct': 0,
                'avg_loss_pct': 0,
                'trades': []
            }
        
        trades_df = pd.DataFrame(trades)
        
        winning_trades = trades_df[trades_df['pnl_pct'] > 0]
        win_rate = len(winning_trades) / len(trades_df) * 100 if len(trades_df) > 0 else 0
        
        gross_profit = winning_trades['pnl_pct'].sum() if len(winning_trades) > 0 else 0
        losing_trades = trades_df[trades_df['pnl_pct'] < 0]
        gross_loss = abs(losing_trades['pnl_pct'].sum()) if len(losing_trades) > 0 else 0.01
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        avg_win_pct = winning_trades['pnl_pct'].mean() if len(winning_trades) > 0 else 0
        avg_loss_pct = losing_trades['pnl_pct'].mean() if len(losing_trades) > 0 else 0
        
        total_return_pct = ((equity - initial_equity) / initial_equity) * 100
        
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown_pct = abs(drawdown.min())
        
        returns = trades_df['pnl_pct'].values
        sharpe_ratio = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252) if len(returns) > 1 else 0
        
        return {
            'total_trades': len(trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return_pct': total_return_pct,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'avg_win_pct': avg_win_pct,
            'avg_loss_pct': avg_loss_pct,
            'final_equity': equity,
            'trades': trades
        }

