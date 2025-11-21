"""
TWMA (Time Weighted Moving Average) Trend Strategy - Python Implementation
4H Zaman Ağırlıklı Trend Stratejisi
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class TWMATrendStrategy:
    """TWMA Trend Strategy - 4H Zaman Ağırlıklı Trend Stratejisi"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        Initialize TWMA Trend Strategy
        
        Args:
            params: Strategy parameters
                - twma_len: TWMA period (default: 20)
                - atr_len: ATR period (default: 14)
                - sl_atr_mult: Stop Loss ATR multiplier (default: 0.5)
                - tp_atr_mult: Take Profit ATR multiplier (default: 1.0)
                - pivot_len: Pivot left/right bar count (default: 5)
                - leverage: Leverage multiplier (default: 5.0)
                - commission: Commission rate (default: 0.0005)
                - slippage: Slippage percentage (default: 0.0002)
        """
        # TWMA Parameters
        self.twma_len = params.get('twma_len', 20)
        self.atr_len = params.get('atr_len', 14)
        self.sl_atr_mult = params.get('sl_atr_mult', 0.5)
        self.tp_atr_mult = params.get('tp_atr_mult', 1.0)
        self.pivot_len = params.get('pivot_len', 5)
        
        # Trading Parameters
        self.leverage = params.get('leverage', 5.0)
        self.commission = params.get('commission', 0.0005)
        self.slippage = params.get('slippage', 0.0002)
    
    def calculate_twma(self, src: pd.Series, length: int) -> pd.Series:
        """
        Calculate Time Weighted Moving Average (TWMA)
        
        TWMA formula: weighted average where recent values have higher weight
        weight = (length - i) for i in range(length)
        """
        twma = pd.Series(index=src.index, dtype=float)
        
        for i in range(len(src)):
            if i < length - 1:
                twma.iloc[i] = np.nan
                continue
            
            num = 0.0
            den = 0.0
            
            for j in range(length):
                w = length - j
                num += src.iloc[i - j] * w
                den += w
            
            twma.iloc[i] = num / den if den > 0 else np.nan
        
        return twma
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_len).mean()
        return atr
    
    def calculate_pivot_high_low(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate pivot high and pivot low
        
        Pivot High: high is higher than 'pivot_len' bars on left and right
        Pivot Low: low is lower than 'pivot_len' bars on left and right
        """
        pivot_high = pd.Series(index=df.index, dtype=float)
        pivot_low = pd.Series(index=df.index, dtype=float)
        
        for i in range(self.pivot_len, len(df) - self.pivot_len):
            # Check pivot high
            high_val = df['high'].iloc[i]
            is_pivot_high = True
            for j in range(1, self.pivot_len + 1):
                if df['high'].iloc[i - j] >= high_val or df['high'].iloc[i + j] >= high_val:
                    is_pivot_high = False
                    break
            if is_pivot_high:
                pivot_high.iloc[i] = high_val
            
            # Check pivot low
            low_val = df['low'].iloc[i]
            is_pivot_low = True
            for j in range(1, self.pivot_len + 1):
                if df['low'].iloc[i - j] <= low_val or df['low'].iloc[i + j] <= low_val:
                    is_pivot_low = False
                    break
            if is_pivot_low:
                pivot_low.iloc[i] = low_val
        
        return pivot_high, pivot_low
    
    def run_backtest(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Run backtest on the given dataframe
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary with backtest results
        """
        # Calculate indicators
        twma = self.calculate_twma(df['close'], self.twma_len)
        atr = self.calculate_atr(df)
        pivot_high, pivot_low = self.calculate_pivot_high_low(df)
        
        # Track last swing high/low
        last_swing_high = None
        last_swing_low = None
        
        # Track position
        position = None  # 'long', 'short', or None
        entry_price = None
        stop_loss = None
        take_profit = None
        
        # Track trades
        trades = []
        equity = 100000.0  # Initial capital
        equity_curve = [equity]
        
        # Track state
        long_sl = None
        long_tp = None
        short_sl = None
        short_tp = None
        
        for i in range(1, len(df)):
            if pd.isna(twma.iloc[i]) or pd.isna(twma.iloc[i-1]) or pd.isna(atr.iloc[i]):
                equity_curve.append(equity)
                continue
            
            # Update last swing high/low
            if not pd.isna(pivot_high.iloc[i]):
                last_swing_high = pivot_high.iloc[i]
            if not pd.isna(pivot_low.iloc[i]):
                last_swing_low = pivot_low.iloc[i]
            
            # TWMA direction
            twma_up = twma.iloc[i] > twma.iloc[i-1]
            twma_down = twma.iloc[i] < twma.iloc[i-1]
            
            # Current bar values
            curr_close = df['close'].iloc[i]
            curr_high = df['high'].iloc[i]
            curr_low = df['low'].iloc[i]
            curr_twma = twma.iloc[i]
            curr_atr = atr.iloc[i]
            
            # Previous bar values
            prev_close = df['close'].iloc[i-1]
            prev_low = df['low'].iloc[i-1]
            prev_high = df['high'].iloc[i-1]
            prev_twma = twma.iloc[i-1]
            
            # Entry conditions - Pine: longEntryCond = setupLongBar[1] and touchLongNow[1] and noPos
            # This means: setup bar was 2 bars ago, touch was 1 bar ago, entry is now
            no_pos = position is None
            
            # Check if setup was 2 bars ago and touch was 1 bar ago
            if i >= 3:
                # Setup bar (2 bars ago): close > twma and twmaUp
                setup_bar_close = df['close'].iloc[i-2]
                setup_bar_twma = twma.iloc[i-2]
                setup_bar_twma_prev = twma.iloc[i-3]
                setup_twma_up = setup_bar_twma > setup_bar_twma_prev
                
                prev_setup_long = setup_bar_close > setup_bar_twma and setup_twma_up
                prev_setup_short = setup_bar_close < setup_bar_twma and (setup_bar_twma < setup_bar_twma_prev)
                
                # Touch bar (1 bar ago): low <= twma and close >= twma (for long)
                prev_touch_long = prev_low <= prev_twma and prev_close >= prev_twma
                prev_touch_short = prev_high >= prev_twma and prev_close <= prev_twma
                
                long_entry_cond = prev_setup_long and prev_touch_long and no_pos
                short_entry_cond = prev_setup_short and prev_touch_short and no_pos
            else:
                long_entry_cond = False
                short_entry_cond = False
            
            # LONG ENTRY
            if long_entry_cond:
                base_twma = prev_twma
                prev_atr_val = atr.iloc[i-1] if not pd.isna(atr.iloc[i-1]) else atr.iloc[i]
                sl_price = base_twma - self.sl_atr_mult * prev_atr_val if not pd.isna(prev_atr_val) else base_twma * 0.98
                tp_base = last_swing_high if last_swing_high is not None else base_twma
                tp_price = tp_base + self.tp_atr_mult * prev_atr_val if not pd.isna(prev_atr_val) else base_twma * 1.02
                
                long_sl = sl_price
                long_tp = tp_price
                
                # Enter long position
                position = 'long'
                entry_price = curr_close * (1 + self.slippage)  # Apply slippage
                stop_loss = long_sl
                take_profit = long_tp
                
                # Calculate position size (10% of equity with leverage)
                position_value = equity * 0.10 * self.leverage
                quantity = position_value / entry_price
                
                # Apply commission
                commission_cost = position_value * self.commission
                equity -= commission_cost
            
            # SHORT ENTRY
            elif short_entry_cond:
                base_twma_s = prev_twma
                prev_atr_val_s = atr.iloc[i-1] if not pd.isna(atr.iloc[i-1]) else atr.iloc[i]
                sl_price_s = base_twma_s + self.sl_atr_mult * prev_atr_val_s if not pd.isna(prev_atr_val_s) else base_twma_s * 1.02
                tp_base_s = last_swing_low if last_swing_low is not None else base_twma_s
                tp_price_s = tp_base_s - self.tp_atr_mult * prev_atr_val_s if not pd.isna(prev_atr_val_s) else base_twma_s * 0.98
                
                short_sl = sl_price_s
                short_tp = tp_price_s
                
                # Enter short position
                position = 'short'
                entry_price = curr_close * (1 - self.slippage)  # Apply slippage
                stop_loss = short_sl
                take_profit = short_tp
                
                # Calculate position size (10% of equity with leverage)
                position_value = equity * 0.10 * self.leverage
                quantity = position_value / entry_price
                
                # Apply commission
                commission_cost = position_value * self.commission
                equity -= commission_cost
            
            # Check exit conditions
            if position == 'long' and entry_price is not None:
                # Check stop loss
                if curr_low <= stop_loss:
                    exit_price = stop_loss * (1 - self.slippage)
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * self.leverage
                    pnl = equity * 0.10 * (pnl_pct / 100)
                    equity += pnl
                    
                    # Apply commission
                    commission_cost = equity * 0.10 * self.commission
                    equity -= commission_cost
                    
                    trades.append({
                        'entry_time': df.index[i-1] if i > 0 else df.index[i],
                        'exit_time': df.index[i],
                        'side': 'long',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'sl'
                    })
                    
                    position = None
                    entry_price = None
                    stop_loss = None
                    take_profit = None
                
                # Check take profit
                elif curr_high >= take_profit:
                    exit_price = take_profit * (1 + self.slippage)
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * self.leverage
                    pnl = equity * 0.10 * (pnl_pct / 100)
                    equity += pnl
                    
                    # Apply commission
                    commission_cost = equity * 0.10 * self.commission
                    equity -= commission_cost
                    
                    trades.append({
                        'entry_time': df.index[i-1] if i > 0 else df.index[i],
                        'exit_time': df.index[i],
                        'side': 'long',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'tp'
                    })
                    
                    position = None
                    entry_price = None
                    stop_loss = None
                    take_profit = None
            
            elif position == 'short' and entry_price is not None:
                # Check stop loss
                if curr_high >= stop_loss:
                    exit_price = stop_loss * (1 + self.slippage)
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * self.leverage
                    pnl = equity * 0.10 * (pnl_pct / 100)
                    equity += pnl
                    
                    # Apply commission
                    commission_cost = equity * 0.10 * self.commission
                    equity -= commission_cost
                    
                    trades.append({
                        'entry_time': df.index[i-1] if i > 0 else df.index[i],
                        'exit_time': df.index[i],
                        'side': 'short',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'sl'
                    })
                    
                    position = None
                    entry_price = None
                    stop_loss = None
                    take_profit = None
                
                # Check take profit
                elif curr_low <= take_profit:
                    exit_price = take_profit * (1 - self.slippage)
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * self.leverage
                    pnl = equity * 0.10 * (pnl_pct / 100)
                    equity += pnl
                    
                    # Apply commission
                    commission_cost = equity * 0.10 * self.commission
                    equity -= commission_cost
                    
                    trades.append({
                        'entry_time': df.index[i-1] if i > 0 else df.index[i],
                        'exit_time': df.index[i],
                        'side': 'short',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'tp'
                    })
                    
                    position = None
                    entry_price = None
                    stop_loss = None
                    take_profit = None
            
            equity_curve.append(equity)
        
        # Close any open position at the end
        if position is not None and entry_price is not None:
            exit_price = df['close'].iloc[-1]
            if position == 'long':
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * self.leverage
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * self.leverage
            
            pnl = equity * 0.10 * (pnl_pct / 100)
            equity += pnl
            commission_cost = equity * 0.10 * self.commission
            equity -= commission_cost
            
            trades.append({
                'entry_time': df.index[-2] if len(df) > 1 else df.index[-1],
                'exit_time': df.index[-1],
                'side': position,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_pct': pnl_pct,
                'exit_reason': 'end'
            })
        
        # Calculate metrics
        if len(trades) == 0:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'total_return_pct': 0.0,
                'max_drawdown_pct': 0.0,
                'avg_win_pct': 0.0,
                'avg_loss_pct': 0.0,
                'gross_profit': 0.0,
                'gross_loss': 0.0,
                'final_equity': equity,
                'trades': []
            }
        
        winning_trades = [t for t in trades if t['pnl_pct'] > 0]
        losing_trades = [t for t in trades if t['pnl_pct'] < 0]
        
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0.0
        
        gross_profit = sum(t['pnl_pct'] for t in winning_trades) if winning_trades else 0.0
        gross_loss = abs(sum(t['pnl_pct'] for t in losing_trades)) if losing_trades else 0.0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        avg_win = np.mean([t['pnl_pct'] for t in winning_trades]) if winning_trades else 0.0
        avg_loss = np.mean([t['pnl_pct'] for t in losing_trades]) if losing_trades else 0.0
        
        total_return_pct = ((equity - 100000.0) / 100000.0) * 100
        
        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown_pct = abs(drawdown.min()) if len(drawdown) > 0 else 0.0
        
        return {
            'total_trades': len(trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return_pct': total_return_pct,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'final_equity': equity,
            'trades': trades
        }

