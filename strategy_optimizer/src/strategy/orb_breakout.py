"""
ORB Breakout Strategy - Python Implementation
Opening Range Breakout with Multi-Stage Detection
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ORBBreakoutStrategy:
    """ORB Breakout Strategy - Clean Implementation"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        Initialize ORB Breakout Strategy
        
        Args:
            params: Strategy parameters
                - orb_minutes: ORB period in minutes (5, 15, 30, 60)
                - breakout_buffer_pct: Breakout buffer percentage
                - min_bars_outside: Minimum bars outside ORB
                - enable_volume_filter: Enable volume filter
                - volume_ma_length: Volume MA length
                - volume_multiplier: Volume multiplier threshold
                - enable_trend_filter: Enable trend filter
                - trend_mode: Trend mode (VWAP, EMA, SuperTrend)
                - tp1_pct: Take profit 1 percentage
                - tp2_pct: Take profit 2 percentage
                - tp3_pct: Take profit 3 percentage
                - stop_mode: Stop loss mode (ATR, ORB %, % Based, Smart Adaptive)
                - atr_length: ATR length
                - atr_multiplier: ATR multiplier
                - max_stop_loss_pct: Maximum stop loss percentage (default 2.5%)
                - leverage: Leverage multiplier
                - commission: Commission rate
                - slippage: Slippage percentage
        """
        # ORB Parameters
        self.orb_minutes = params.get('orb_minutes', 15)
        self.breakout_buffer_pct = params.get('breakout_buffer_pct', 0.2)
        self.min_bars_outside = params.get('min_bars_outside', 2)
        
        # Filters
        self.enable_volume_filter = params.get('enable_volume_filter', False)
        self.volume_ma_length = params.get('volume_ma_length', 20)
        self.volume_multiplier = params.get('volume_multiplier', 1.5)
        
        self.enable_trend_filter = params.get('enable_trend_filter', False)
        self.trend_mode = params.get('trend_mode', 'VWAP')
        self.trend_ema_length = params.get('trend_ema_length', 12)
        
        # Exit Parameters
        self.tp1_pct = params.get('tp1_pct', 1.0)
        self.tp2_pct = params.get('tp2_pct', 2.0)
        self.tp3_pct = params.get('tp3_pct', 3.0)
        self.stop_mode = params.get('stop_mode', 'Smart Adaptive')
        self.atr_length = params.get('atr_length', 14)
        self.atr_multiplier = params.get('atr_multiplier', 1.5)
        self.max_stop_loss_pct = params.get('max_stop_loss_pct', 2.5)  # Maksimum %2.5
        
        # Trading Parameters
        self.leverage = params.get('leverage', 5.0)
        self.commission = params.get('commission', 0.0004)
        self.slippage = params.get('slippage', 0.0002)
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_length).mean()
        return atr
    
    def calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Volume Weighted Average Price"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return df['close'].ewm(span=period, adjust=False).mean()
    
    def calculate_supertrend(self, df: pd.DataFrame, atr: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Calculate SuperTrend"""
        hl2 = (df['high'] + df['low']) / 2
        upper_band = hl2 + (self.atr_multiplier * atr)
        lower_band = hl2 - (self.atr_multiplier * atr)
        
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        final_upper = None
        final_lower = None
        
        for i in range(len(df)):
            if pd.isna(upper_band.iloc[i]) or pd.isna(lower_band.iloc[i]):
                continue
            
            # Upper band
            if final_upper is None:
                final_upper = upper_band.iloc[i]
            else:
                if df['close'].iloc[i-1] <= final_upper:
                    final_upper = min(upper_band.iloc[i], final_upper)
                else:
                    final_upper = upper_band.iloc[i]
            
            # Lower band
            if final_lower is None:
                final_lower = lower_band.iloc[i]
            else:
                if df['close'].iloc[i-1] >= final_lower:
                    final_lower = max(lower_band.iloc[i], final_lower)
                else:
                    final_lower = lower_band.iloc[i]
            
            # Direction
            if i == 0:
                direction.iloc[i] = 1
            else:
                if df['close'].iloc[i] > final_upper:
                    direction.iloc[i] = 1
                elif df['close'].iloc[i] < final_lower:
                    direction.iloc[i] = -1
                else:
                    direction.iloc[i] = direction.iloc[i-1]
            
            # SuperTrend value
            if direction.iloc[i] == 1:
                supertrend.iloc[i] = final_lower
            else:
                supertrend.iloc[i] = final_upper
        
        return supertrend, direction
    
    def calculate_orb_levels(self, df: pd.DataFrame, session_start_idx: int, timeframe_minutes: int = 240) -> Tuple[float, float, float]:
        """Calculate ORB levels for the session"""
        # For 4h timeframe, use first 1-2 bars of the day as ORB
        # This gives us a 4-8 hour opening range
        
        if session_start_idx >= len(df):
            return None, None, None
        
        # For 4h timeframe, use first 1-2 bars (4-8 hours) as ORB
        # This simulates daily opening range
        orb_bars = min(2, len(df) - session_start_idx)  # Use first 2 bars max
        orb_data = df.iloc[session_start_idx:session_start_idx + orb_bars]
        
        if len(orb_data) == 0:
            return None, None, None
        
        orb_high = orb_data['high'].max()
        orb_low = orb_data['low'].min()
        orb_mid = (orb_high + orb_low) / 2
        
        return orb_high, orb_low, orb_mid
    
    def calculate_stop_loss(self, entry: float, orb_high: float, orb_low: float, 
                           orb_range: float, atr: float, is_long: bool) -> float:
        """Calculate stop loss with maximum %2.5 limit"""
        max_sl_long = entry * (1 - self.max_stop_loss_pct / 100)
        max_sl_short = entry * (1 + self.max_stop_loss_pct / 100)
        
        if self.stop_mode == "ATR":
            if is_long:
                sl = entry - (atr * self.atr_multiplier)
            else:
                sl = entry + (atr * self.atr_multiplier)
        elif self.stop_mode == "ORB %":
            if is_long:
                sl = orb_low - (orb_range * 0.2)
            else:
                sl = orb_high + (orb_range * 0.2)
        elif self.stop_mode == "% Based":
            if is_long:
                sl = entry * (1 - self.max_stop_loss_pct / 100)
            else:
                sl = entry * (1 + self.max_stop_loss_pct / 100)
        elif self.stop_mode == "Smart Adaptive":
            atr_pct = (atr / entry) * 100 if entry > 0 else 0
            if atr_pct > 3:
                multiplier = 1.5
            elif atr_pct > 1.5:
                multiplier = 1.0
            else:
                multiplier = 0.7
            
            if is_long:
                sl = entry - (atr * multiplier)
            else:
                sl = entry + (atr * multiplier)
        else:
            # Default to % Based
            if is_long:
                sl = entry * (1 - self.max_stop_loss_pct / 100)
            else:
                sl = entry * (1 + self.max_stop_loss_pct / 100)
        
        # Apply maximum stop loss limit
        if is_long:
            sl = max(sl, max_sl_long)  # Stop loss can't be lower than max_sl_long
        else:
            sl = min(sl, max_sl_short)  # Stop loss can't be higher than max_sl_short
        
        return sl
    
    def check_volume_filter(self, df: pd.DataFrame, i: int) -> bool:
        """Check volume filter"""
        if not self.enable_volume_filter:
            return True
        
        if i < self.volume_ma_length:
            return False
        
        volume_ma = df['volume'].iloc[i - self.volume_ma_length:i].mean()
        current_volume = df['volume'].iloc[i]
        
        return current_volume >= volume_ma * self.volume_multiplier
    
    def check_trend_filter(self, df: pd.DataFrame, i: int, is_long: bool) -> bool:
        """Check trend filter"""
        if not self.enable_trend_filter:
            return True
        
        if self.trend_mode == "VWAP":
            vwap = self.calculate_vwap(df)
            if pd.isna(vwap.iloc[i]):
                return True
            if is_long:
                return df['close'].iloc[i] > vwap.iloc[i]
            else:
                return df['close'].iloc[i] < vwap.iloc[i]
        elif self.trend_mode == "EMA":
            ema = self.calculate_ema(df, self.trend_ema_length)
            if pd.isna(ema.iloc[i]):
                return True
            if is_long:
                return df['close'].iloc[i] > ema.iloc[i]
            else:
                return df['close'].iloc[i] < ema.iloc[i]
        elif self.trend_mode == "SuperTrend":
            atr = self.calculate_atr(df)
            supertrend, direction = self.calculate_supertrend(df, atr)
            if pd.isna(direction.iloc[i]):
                return True
            if is_long:
                return direction.iloc[i] == 1
            else:
                return direction.iloc[i] == -1
        
        return True
    
    def run_backtest(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run backtest with ORB strategy"""
        df = df.copy()
        df.columns = df.columns.str.lower()
        
        # Calculate indicators
        atr = self.calculate_atr(df)
        
        # Initialize
        position = None
        entry_price = None
        entry_index = None
        stop_loss = None
        tp1 = None
        tp2 = None
        tp3 = None
        orb_high = None
        orb_low = None
        orb_mid = None
        session_start_idx = 0
        bars_outside = 0
        
        trades = []
        equity = 10000
        initial_equity = equity
        equity_curve = [equity]
        max_equity = equity
        
        # Session detection (simplified - assume new session every day)
        session_starts = []
        current_date = None
        for i, idx in enumerate(df.index):
            if current_date is None or idx.date() != current_date:
                session_starts.append(i)
                current_date = idx.date()
        
        # Main loop
        for i in range(max(self.atr_length, self.volume_ma_length if self.enable_volume_filter else 0) + self.orb_minutes, len(df)):
            # Check for new session
            if i in session_starts:
                # Calculate ORB for new session
                session_start_idx = i
                orb_high, orb_low, orb_mid = self.calculate_orb_levels(df, session_start_idx)
                bars_outside = 0
                if position is not None:
                    # Close position at session end (optional)
                    pass
            
            # Skip if ORB not calculated
            if orb_high is None or orb_low is None:
                continue
            
            current_price = df['close'].iloc[i]
            current_high = df['high'].iloc[i]
            current_low = df['low'].iloc[i]
            
            # Track bars outside ORB (for entry condition)
            # Reset when new session starts
            if i > session_start_idx:
                # Check if price is outside ORB range
                if current_price > orb_high:
                    bars_outside += 1
                elif current_price < orb_low:
                    bars_outside += 1
                else:
                    # Price back inside ORB - reset counter
                    bars_outside = 0
            
            # LONG Entry: Breakout above ORB High
            if position is None and orb_high is not None and i > session_start_idx:
                breakout_buffer = orb_high * (self.breakout_buffer_pct / 100)
                breakout_level = orb_high + breakout_buffer
                
                # Check if price crossed breakout level (close above breakout level)
                prev_price = df['close'].iloc[i-1] if i > 0 else current_price
                crossed_above = current_price > breakout_level
                
                # Also check if we've been outside ORB for minimum bars
                if (crossed_above and 
                    bars_outside >= self.min_bars_outside and
                    self.check_volume_filter(df, i) and
                    self.check_trend_filter(df, i, True)):
                    
                    entry_price = current_price * (1 + self.slippage)
                    entry_index = i
                    
                    # Calculate stop loss and targets
                    orb_range = orb_high - orb_low
                    current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else orb_range * 0.5
                    stop_loss = self.calculate_stop_loss(entry_price, orb_high, orb_low, orb_range, current_atr, True)
                    tp1 = entry_price * (1 + self.tp1_pct / 100)
                    tp2 = entry_price * (1 + self.tp2_pct / 100)
                    tp3 = entry_price * (1 + self.tp3_pct / 100)
                    
                    position = 'LONG'
                    bars_outside = 0
            
            # SHORT Entry: Breakout below ORB Low
            elif position is None and orb_low is not None and i > session_start_idx:
                breakout_buffer = orb_low * (self.breakout_buffer_pct / 100)
                breakout_level = orb_low - breakout_buffer
                
                # Check if price crossed breakout level (close below breakout level)
                prev_price = df['close'].iloc[i-1] if i > 0 else current_price
                crossed_below = current_price < breakout_level
                
                # Also check if we've been outside ORB for minimum bars
                if (crossed_below and 
                    bars_outside >= self.min_bars_outside and
                    self.check_volume_filter(df, i) and
                    self.check_trend_filter(df, i, False)):
                    
                    entry_price = current_price * (1 - self.slippage)
                    entry_index = i
                    
                    # Calculate stop loss and targets
                    orb_range = orb_high - orb_low
                    current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else orb_range * 0.5
                    stop_loss = self.calculate_stop_loss(entry_price, orb_high, orb_low, orb_range, current_atr, False)
                    tp1 = entry_price * (1 - self.tp1_pct / 100)
                    tp2 = entry_price * (1 - self.tp2_pct / 100)
                    tp3 = entry_price * (1 - self.tp3_pct / 100)
                    
                    position = 'SHORT'
                    bars_outside = 0
            
            # Exit Logic - Check in priority order: SL first, then TP1, TP2, TP3
            # Note: In real trading, we'd close position partially, but for backtest we close fully at first TP/SL
            if position == 'LONG' and entry_price is not None:
                exit_price = None
                exit_reason = None
                
                # Check Stop Loss first (highest priority)
                if current_low <= stop_loss:
                    exit_price = stop_loss * (1 + self.slippage)
                    exit_reason = 'SL'
                # Check TP1 first (closest target)
                elif current_high >= tp1:
                    exit_price = tp1 * (1 - self.slippage)
                    exit_reason = 'TP1'
                # Check TP2 (if TP1 not hit)
                elif current_high >= tp2:
                    exit_price = tp2 * (1 - self.slippage)
                    exit_reason = 'TP2'
                # Check TP3 (if TP1 and TP2 not hit)
                elif current_high >= tp3:
                    exit_price = tp3 * (1 - self.slippage)
                    exit_reason = 'TP3'
                
                if exit_price is not None:
                    # Calculate P&L
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                    pnl = equity * (pnl_pct / 100) * self.leverage
                    commission_cost = equity * self.commission * 2  # Entry + Exit
                    net_pnl = pnl - commission_cost
                    equity += net_pnl
                    
                    trades.append({
                        'entry_time': df.index[entry_index],
                        'exit_time': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'position': position,
                        'pnl_pct': pnl_pct,
                        'pnl': net_pnl,
                        'exit_reason': exit_reason
                    })
                    
                    position = None
                    entry_price = None
                    entry_index = None
                    stop_loss = None
                    tp1 = None
                    tp2 = None
                    tp3 = None
            
            elif position == 'SHORT' and entry_price is not None:
                exit_price = None
                exit_reason = None
                
                # Check Stop Loss first (highest priority)
                if current_high >= stop_loss:
                    exit_price = stop_loss * (1 - self.slippage)
                    exit_reason = 'SL'
                # Check TP1 first (closest target)
                elif current_low <= tp1:
                    exit_price = tp1 * (1 + self.slippage)
                    exit_reason = 'TP1'
                # Check TP2 (if TP1 not hit)
                elif current_low <= tp2:
                    exit_price = tp2 * (1 + self.slippage)
                    exit_reason = 'TP2'
                # Check TP3 (if TP1 and TP2 not hit)
                elif current_low <= tp3:
                    exit_price = tp3 * (1 + self.slippage)
                    exit_reason = 'TP3'
                
                if exit_price is not None:
                    # Calculate P&L
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                    pnl = equity * (pnl_pct / 100) * self.leverage
                    commission_cost = equity * self.commission * 2  # Entry + Exit
                    net_pnl = pnl - commission_cost
                    equity += net_pnl
                    
                    trades.append({
                        'entry_time': df.index[entry_index],
                        'exit_time': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'position': position,
                        'pnl_pct': pnl_pct,
                        'pnl': net_pnl,
                        'exit_reason': exit_reason
                    })
                    
                    position = None
                    entry_price = None
                    entry_index = None
                    stop_loss = None
                    tp1 = None
                    tp2 = None
                    tp3 = None
            
            equity_curve.append(equity)
            max_equity = max(max_equity, equity)
        
        # Calculate metrics
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_return_pct': 0,
                'max_drawdown_pct': 0,
                'avg_win_pct': 0,
                'avg_loss_pct': 0,
                'trades': []
            }
        
        trades_df = pd.DataFrame(trades)
        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] < 0]
        
        total_return_pct = ((equity - initial_equity) / initial_equity) * 100
        
        win_rate = (len(winning_trades) / len(trades_df)) * 100 if len(trades_df) > 0 else 0
        
        gross_profit = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
        gross_loss = abs(losing_trades['pnl'].sum()) if len(losing_trades) > 0 else 0.01
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        avg_win_pct = winning_trades['pnl_pct'].mean() if len(winning_trades) > 0 else 0
        avg_loss_pct = losing_trades['pnl_pct'].mean() if len(losing_trades) > 0 else 0
        
        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown_pct = abs(drawdown.min()) if len(drawdown) > 0 else 0
        
        return {
            'total_trades': len(trades_df),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return_pct': total_return_pct,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_win_pct': avg_win_pct,
            'avg_loss_pct': avg_loss_pct,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'final_equity': equity,
            'trades': trades
        }

