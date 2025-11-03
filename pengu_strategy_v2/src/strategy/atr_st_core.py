"""
ATR + SuperTrend Strategy Core Implementation

This module implements the Pine Script v6 strategy logic for ATR trailing stop
with SuperTrend filter and cooldown functionality.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from numba import jit
import logging

logger = logging.getLogger(__name__)


@jit(nopython=True)
def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """
    Calculate ATR (Average True Range) using Numba for performance.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period
        
    Returns:
        ATR values
    """
    n = len(close)
    atr = np.zeros(n)
    
    if n < period:
        return atr
    
    # Calculate True Range
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    # Calculate ATR using Wilder's smoothing
    atr[period-1] = np.mean(tr[:period])
    
    for i in range(period, n):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    return atr


@jit(nopython=True)
def calculate_ema(values: np.ndarray, period: int) -> np.ndarray:
    """
    Calculate EMA (Exponential Moving Average) using Numba.
    
    Args:
        values: Input values
        period: EMA period
        
    Returns:
        EMA values
    """
    n = len(values)
    ema = np.zeros(n)
    
    if n == 0:
        return ema
    
    # Initialize first value
    ema[0] = values[0]
    
    # Calculate smoothing factor
    alpha = 2.0 / (period + 1)
    
    # Calculate EMA
    for i in range(1, n):
        ema[i] = alpha * values[i] + (1 - alpha) * ema[i-1]
    
    return ema


@jit(nopython=True)
def calculate_atr_trailing_stop(close: np.ndarray, atr: np.ndarray, a: float) -> np.ndarray:
    """
    Calculate ATR trailing stop following Pine Script v6 logic.
    
    Args:
        close: Close prices
        atr: ATR values
        a: ATR sensitivity multiplier
        
    Returns:
        ATR trailing stop values
    """
    n = len(close)
    trailing_stop = np.zeros(n)
    nloss = atr * a
    
    # Initialize first value
    trailing_stop[0] = close[0] - nloss[0]
    
    for i in range(1, n):
        prev_trailing = trailing_stop[i-1]
        current_close = close[i]
        prev_close = close[i-1]
        current_nloss = nloss[i]
        
        # Pine Script v6 logic for trailing stop update
        if current_close > prev_trailing and prev_close > prev_trailing:
            # Both current and previous close above trailing stop
            trailing_stop[i] = max(prev_trailing, current_close - current_nloss)
        elif current_close < prev_trailing and prev_close < prev_trailing:
            # Both current and previous close below trailing stop
            trailing_stop[i] = min(prev_trailing, current_close + current_nloss)
        elif current_close > prev_trailing:
            # Current close above trailing stop
            trailing_stop[i] = current_close - current_nloss
        else:
            # Current close below trailing stop
            trailing_stop[i] = current_close + current_nloss
    
    return trailing_stop


@jit(nopython=True)
def calculate_supertrend(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
                         atr: np.ndarray, factor: float) -> np.ndarray:
    """
    Calculate SuperTrend line following Pine Script v6 logic.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        atr: ATR values
        factor: SuperTrend multiplier
        
    Returns:
        SuperTrend line values
    """
    n = len(close)
    supertrend = np.zeros(n)
    
    if n == 0:
        return supertrend
    
    # Calculate basic bands
    hl2 = (high + low) / 2
    upper_band = hl2 + (atr * factor)
    lower_band = hl2 - (atr * factor)
    
    # Initialize first value
    supertrend[0] = lower_band[0]
    
    for i in range(1, n):
        prev_supertrend = supertrend[i-1]
        current_close = close[i]
        current_upper = upper_band[i]
        current_lower = lower_band[i]
        
        # Pine Script v6 SuperTrend logic
        if current_close > prev_supertrend:
            supertrend[i] = max(current_lower, prev_supertrend)
        else:
            supertrend[i] = min(current_upper, prev_supertrend)
    
    return supertrend


@jit(nopython=True)
def detect_crossovers(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
    """
    Detect crossovers between two series.
    
    Args:
        series1: First series
        series2: Second series
        
    Returns:
        Array with 1 for upward crossover, -1 for downward crossover, 0 otherwise
    """
    n = len(series1)
    crossovers = np.zeros(n)
    
    for i in range(1, n):
        if series1[i] > series2[i] and series1[i-1] <= series2[i-1]:
            crossovers[i] = 1  # Upward crossover
        elif series1[i] < series2[i] and series1[i-1] >= series2[i-1]:
            crossovers[i] = -1  # Downward crossover
    
    return crossovers


class ATRSuperTrendStrategy:
    """
    ATR + SuperTrend Strategy implementation following Pine Script v6 logic.
    """
    
    def __init__(self, params: Dict[str, Any]):
        """
        Initialize strategy with parameters.
        
        Args:
            params: Strategy parameters
        """
        self.params = params
        self.a = params.get('a', 2.0)  # ATR sensitivity
        self.c = params.get('c', 10)   # ATR period
        self.st_factor = params.get('st_factor', 1.5)  # SuperTrend multiplier
        self.min_delay_m = params.get('min_delay_m', 60)  # Minimum delay in minutes
        self.atr_sl_mult = params.get('atr_sl_mult', 2.0)  # ATR SL multiplier
        self.atr_rr = params.get('atr_rr', 2.0)  # Risk-reward ratio
        self.use_trailing_stop = params.get('use_trailing_stop', True)  # Use trailing stop
        self.trailing_stop_mult = params.get('trailing_stop_mult', 1.0)  # Trailing stop multiplier
        self.trailing_tp_mult = params.get('trailing_tp_mult', 1.5)  # YENİ: TP taşıma çarpanı
        
        # EMA Confirmation parameters (NEW)
        self.ema_fast_len = params.get('ema_fast_len', 12)  # EMA Fast length
        self.ema_slow_len = params.get('ema_slow_len', 26)  # EMA Slow length
        self.pre_lookback_bars = params.get('pre_lookback_bars', 5)  # Pre-confirm window
        self.post_confirm_bars = params.get('post_confirm_bars', 5)  # Post-confirm window
        self.use_ema_confirmation = params.get('use_ema_confirmation', True)  # Use EMA confirmation
        
        # State variables
        self.last_trade_time = None
        self.current_position = 0  # 0: no position, 1: long, -1: short
        self.last_signal_direction = 0  # Last signal direction for flip logic
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators for the strategy.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            DataFrame with calculated indicators
        """
        if data.empty:
            return data
        
        df = data.copy()
        
        # Convert to numpy arrays for Numba functions
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # Calculate ATR
        atr = calculate_atr(high, low, close, self.c)
        df['atr'] = atr
        
        # Calculate ATR trailing stop
        trailing_stop = calculate_atr_trailing_stop(close, atr, self.a)
        df['trailing_stop'] = trailing_stop
        
        # Calculate EMA(1) for crossover detection
        ema1 = calculate_ema(close, 1)
        df['ema1'] = ema1
        
        # Calculate SuperTrend
        supertrend = calculate_supertrend(high, low, close, atr, self.st_factor)
        df['supertrend'] = supertrend
        
        # Calculate position based on trailing stop
        df['position'] = 0
        for i in range(1, len(df)):
            if close[i-1] < trailing_stop[i-1] and close[i] > trailing_stop[i]:
                df.iloc[i, df.columns.get_loc('position')] = 1
            elif close[i-1] > trailing_stop[i-1] and close[i] < trailing_stop[i]:
                df.iloc[i, df.columns.get_loc('position')] = -1
            else:
                df.iloc[i, df.columns.get_loc('position')] = df.iloc[i-1, df.columns.get_loc('position')]
        
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on Pine Script v6 logic.
        
        Args:
            data: DataFrame with calculated indicators
            
        Returns:
            DataFrame with signals
        """
        if data.empty:
            return data
        
        df = data.copy()
        
        # Initialize signal columns
        df['buy_signal'] = False
        df['sell_signal'] = False
        df['buy_filtered'] = False
        df['sell_filtered'] = False
        
        # Calculate crossovers
        ema_crossovers = detect_crossovers(df['ema1'].values, df['trailing_stop'].values)
        df['ema_crossover'] = ema_crossovers
        
        # Generate basic signals
        df['buy_signal'] = (df['close'] > df['trailing_stop']) & (ema_crossovers == 1)
        df['sell_signal'] = (df['close'] < df['trailing_stop']) & (ema_crossovers == -1)
        
        # Apply SuperTrend filter
        df['buy_signal'] = df['buy_signal'] & (df['close'] > df['supertrend'])
        df['sell_signal'] = df['sell_signal'] & (df['close'] < df['supertrend'])
        
        # Apply flip logic (one-directional)
        df['buy_filtered'] = False
        df['sell_filtered'] = False
        
        for i in range(len(df)):
            if df.iloc[i]['buy_signal'] and self.last_signal_direction != 1:
                df.iloc[i, df.columns.get_loc('buy_filtered')] = True
                self.last_signal_direction = 1
            elif df.iloc[i]['sell_signal'] and self.last_signal_direction != -1:
                df.iloc[i, df.columns.get_loc('sell_filtered')] = True
                self.last_signal_direction = -1
        
        # Apply cooldown filter
        df['buy_final'] = False
        df['sell_final'] = False
        
        for i in range(len(df)):
            current_time = df.index[i]
            
            # Check cooldown
            if self.last_trade_time is not None:
                time_diff = (current_time - self.last_trade_time).total_seconds() / 60
                if time_diff < self.min_delay_m:
                    continue
            
            # Apply signals
            if df.iloc[i]['buy_filtered']:
                df.iloc[i, df.columns.get_loc('buy_final')] = True
                self.last_trade_time = current_time
            elif df.iloc[i]['sell_filtered']:
                df.iloc[i, df.columns.get_loc('sell_final')] = True
                self.last_trade_time = current_time
        
        return df
    
    def calculate_stop_loss_take_profit(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate stop loss and take profit levels based on ATR.
        
        Args:
            data: DataFrame with signals
            
        Returns:
            DataFrame with SL/TP levels
        """
        if data.empty:
            return data
        
        df = data.copy()
        
        # Initialize SL/TP columns
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        
        # Calculate SL/TP for each signal
        for i in range(len(df)):
            if df.iloc[i]['buy_final']:
                # Long position
                entry_price = df.iloc[i]['close']
                atr_value = df.iloc[i]['atr']
                
                sl_price = entry_price - (atr_value * self.atr_sl_mult)
                tp_price = entry_price + (atr_value * self.atr_sl_mult * self.atr_rr)
                
                df.iloc[i, df.columns.get_loc('stop_loss')] = sl_price
                df.iloc[i, df.columns.get_loc('take_profit')] = tp_price
                
            elif df.iloc[i]['sell_final']:
                # Short position
                entry_price = df.iloc[i]['close']
                atr_value = df.iloc[i]['atr']
                
                sl_price = entry_price + (atr_value * self.atr_sl_mult)
                tp_price = entry_price - (atr_value * self.atr_sl_mult * self.atr_rr)
                
                df.iloc[i, df.columns.get_loc('stop_loss')] = sl_price
                df.iloc[i, df.columns.get_loc('take_profit')] = tp_price
        
        return df
    
    def apply_ema_confirmation(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply EMA confirmation logic to classify signals as strong/weak.
        
        Args:
            data: DataFrame with basic signals
            
        Returns:
            DataFrame with EMA confirmation signals
        """
        if data.empty or not self.use_ema_confirmation:
            return data
        
        df = data.copy()
        
        # Calculate EMA Fast and Slow
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast_len).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow_len).mean()
        
        # EMA crossovers
        df['ema_cross_up'] = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
        df['ema_cross_down'] = (df['ema_fast'] < df['ema_slow']) & (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
        
        # Bars since last EMA crossover
        df['bars_since_bull'] = 0
        df['bars_since_bear'] = 0
        
        bull_cross_idx = -1
        bear_cross_idx = -1
        
        for i in range(len(df)):
            if df.iloc[i]['ema_cross_up']:
                bull_cross_idx = i
            if df.iloc[i]['ema_cross_down']:
                bear_cross_idx = i
            
            if bull_cross_idx >= 0:
                df.iloc[i, df.columns.get_loc('bars_since_bull')] = i - bull_cross_idx
            else:
                df.iloc[i, df.columns.get_loc('bars_since_bull')] = 999  # Large number
            
            if bear_cross_idx >= 0:
                df.iloc[i, df.columns.get_loc('bars_since_bear')] = i - bear_cross_idx
            else:
                df.iloc[i, df.columns.get_loc('bars_since_bear')] = 999  # Large number
        
        # Initialize signal strength columns
        df['long_strong_pre'] = False
        df['long_strong_post'] = False
        df['long_weak'] = False
        df['short_strong_pre'] = False
        df['short_strong_post'] = False
        df['short_weak'] = False
        
        # Track pending signals
        pending_long_bar = -1
        pending_short_bar = -1
        
        for i in range(len(df)):
            # LONG signal classification
            if df.iloc[i]['buy_final']:
                bars_since_bull = df.iloc[i]['bars_since_bull']
                
                if bars_since_bull <= self.pre_lookback_bars:
                    # Strong pre-confirm
                    df.iloc[i, df.columns.get_loc('long_strong_pre')] = True
                else:
                    # Weak signal, start pending
                    pending_long_bar = i
                    df.iloc[i, df.columns.get_loc('long_weak')] = True
            
            # Check for post-confirm long signals
            if pending_long_bar >= 0 and df.iloc[i]['ema_cross_up']:
                bars_since_pending = i - pending_long_bar
                if bars_since_pending <= self.post_confirm_bars:
                    # Strong post-confirm
                    df.iloc[i, df.columns.get_loc('long_strong_post')] = True
                pending_long_bar = -1  # Reset
            
            # Expire pending long signals
            if pending_long_bar >= 0:
                bars_since_pending = i - pending_long_bar
                if bars_since_pending > self.post_confirm_bars:
                    pending_long_bar = -1  # Reset
            
            # SHORT signal classification
            if df.iloc[i]['sell_final']:
                bars_since_bear = df.iloc[i]['bars_since_bear']
                
                if bars_since_bear <= self.pre_lookback_bars:
                    # Strong pre-confirm
                    df.iloc[i, df.columns.get_loc('short_strong_pre')] = True
                else:
                    # Weak signal, start pending
                    pending_short_bar = i
                    df.iloc[i, df.columns.get_loc('short_weak')] = True
            
            # Check for post-confirm short signals
            if pending_short_bar >= 0 and df.iloc[i]['ema_cross_down']:
                bars_since_pending = i - pending_short_bar
                if bars_since_pending <= self.post_confirm_bars:
                    # Strong post-confirm
                    df.iloc[i, df.columns.get_loc('short_strong_post')] = True
                pending_short_bar = -1  # Reset
            
            # Expire pending short signals
            if pending_short_bar >= 0:
                bars_since_pending = i - pending_short_bar
                if bars_since_pending > self.post_confirm_bars:
                    pending_short_bar = -1  # Reset
        
        return df
    
    def apply_advanced_trailing_stop(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply advanced trailing stop logic to capture large moves (%30+).
        
        Args:
            data: DataFrame with signals and SL/TP levels
            
        Returns:
            DataFrame with updated SL/TP levels
        """
        if data.empty or not self.use_trailing_stop:
            return data
        
        df = data.copy()
        
        # Initialize trailing stop columns
        df['trailing_sl'] = df['stop_loss'].copy()
        df['trailing_tp'] = df['take_profit'].copy()
        df['position_profit_pct'] = 0.0  # Track position profit percentage
        df['trailing_active'] = False     # Track if trailing is active
        
        # Find all signal positions
        buy_signals = df[df['buy_final'] == True]
        sell_signals = df[df['sell_final'] == True]
        
        # Process each position separately
        for signal_type, signals in [('buy', buy_signals), ('sell', sell_signals)]:
            for signal_idx in signals.index:
                signal_pos = df.index.get_loc(signal_idx)
                
                # Get entry data
                entry_price = df.loc[signal_idx, 'close']
                entry_atr = df.loc[signal_idx, 'atr']
                
                if signal_type == 'buy':
                    # Long position advanced trailing
                    best_price = entry_price
                    trailing_started = False
                    
                    for i in range(signal_pos, len(df)):
                        current_price = df.iloc[i]['close']
                        current_atr = df.iloc[i]['atr']
                        
                        # Calculate position profit percentage
                        profit_pct = ((current_price - entry_price) / entry_price) * 100
                        df.iloc[i, df.columns.get_loc('position_profit_pct')] = profit_pct
                        
                        # Update best price
                        if current_price > best_price:
                            best_price = current_price
                        
                        # Start trailing immediately (no profit threshold)
                        if not trailing_started:
                            trailing_started = True
                            df.iloc[i, df.columns.get_loc('trailing_active')] = True
                        
                        # Always trailing (no profit threshold)
                        # Very loose trailing to capture big moves
                        trailing_mult = 8.0  # Very loose trailing
                        
                        # Calculate new trailing stop
                        new_sl = best_price - (current_atr * self.atr_sl_mult * trailing_mult)
                        
                        # Only update if new SL is better (higher)
                        if new_sl > df.iloc[i]['trailing_sl']:
                            df.iloc[i, df.columns.get_loc('trailing_sl')] = new_sl
                        
                        # Dynamic take profit based on profit level
                        if profit_pct < 10.0:
                            # Small profit: 1:1 risk/reward
                            tp_mult = 1.0
                        elif profit_pct < 20.0:
                            # Medium profit: 1:2 risk/reward
                            tp_mult = 2.0
                        else:
                            # Large profit: 1:3 risk/reward to capture big moves
                            tp_mult = 3.0
                        
                        # Update take profit with dynamic trailing
                        sl_distance = best_price - df.iloc[i]['trailing_sl']
                        new_tp = best_price + (sl_distance * tp_mult)
                        df.iloc[i, df.columns.get_loc('trailing_tp')] = new_tp
                
                else:  # sell
                    # Short position advanced trailing
                    best_price = entry_price
                    trailing_started = False
                    
                    for i in range(signal_pos, len(df)):
                        current_price = df.iloc[i]['close']
                        current_atr = df.iloc[i]['atr']
                        
                        # Calculate position profit percentage
                        profit_pct = ((entry_price - current_price) / entry_price) * 100
                        df.iloc[i, df.columns.get_loc('position_profit_pct')] = profit_pct
                        
                        # Update best price
                        if current_price < best_price:
                            best_price = current_price
                        
                        # Start trailing immediately (no profit threshold)
                        if not trailing_started:
                            trailing_started = True
                            df.iloc[i, df.columns.get_loc('trailing_active')] = True
                        
                        # Always trailing (no profit threshold)
                        # Very loose trailing to capture big moves
                        trailing_mult = 8.0  # Very loose trailing
                        
                        # Calculate new trailing stop
                        new_sl = best_price + (current_atr * self.atr_sl_mult * trailing_mult)
                        
                        # Only update if new SL is better (lower)
                        if new_sl < df.iloc[i]['trailing_sl']:
                            df.iloc[i, df.columns.get_loc('trailing_sl')] = new_sl
                        
                        # Dynamic take profit based on profit level
                        if profit_pct < 10.0:
                            # Small profit: 1:1 risk/reward
                            tp_mult = 1.0
                        elif profit_pct < 20.0:
                            # Medium profit: 1:2 risk/reward
                            tp_mult = 2.0
                        else:
                            # Large profit: 1:3 risk/reward to capture big moves
                            tp_mult = 3.0
                        
                        # Update take profit with dynamic trailing
                        sl_distance = df.iloc[i]['trailing_sl'] - best_price
                        new_tp = best_price - (sl_distance * tp_mult)
                        df.iloc[i, df.columns.get_loc('trailing_tp')] = new_tp
        
        return df
    
    def run_strategy(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Run the complete strategy on the data.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            DataFrame with all indicators and signals
        """
        logger.info(f"Running ATR + SuperTrend strategy with params: {self.params}")
        
        # Calculate indicators
        df = self.calculate_indicators(data)
        
        # Generate signals
        df = self.generate_signals(df)
        
        # Apply EMA confirmation if enabled
        if self.use_ema_confirmation:
            df = self.apply_ema_confirmation(df)
        
        # Calculate SL/TP
        df = self.calculate_stop_loss_take_profit(df)
        
        # Apply advanced trailing stop if enabled
        if self.use_trailing_stop:
            df = self.apply_advanced_trailing_stop(df)
        
        # Add strategy parameters to DataFrame for backtester
        df['atr_sl_mult'] = self.atr_sl_mult
        df['atr_rr'] = self.atr_rr
        
        logger.info(f"Strategy completed. Generated {df['buy_final'].sum()} buy signals and {df['sell_final'].sum()} sell signals")
        
        return df
    
    def get_signal_summary(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Get summary of generated signals.
        
        Args:
            data: DataFrame with signals
            
        Returns:
            Dictionary with signal summary
        """
        if data.empty:
            return {}
        
        buy_signals = data['buy_final'].sum()
        sell_signals = data['sell_final'].sum()
        total_signals = buy_signals + sell_signals
        
        return {
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'signal_frequency': total_signals / len(data) if len(data) > 0 else 0,
            'parameters': self.params,
        }


def create_strategy(params: Dict[str, Any]) -> ATRSuperTrendStrategy:
    """
    Create a strategy instance with given parameters.
    
    Args:
        params: Strategy parameters
        
    Returns:
        ATRSuperTrendStrategy instance
    """
    return ATRSuperTrendStrategy(params)


def validate_strategy_params(params: Dict[str, Any]) -> bool:
    """
    Validate strategy parameters.
    
    Args:
        params: Strategy parameters
        
    Returns:
        True if parameters are valid
    """
    required_params = ['a', 'c', 'st_factor', 'min_delay_m', 'atr_sl_mult', 'atr_rr']
    
    # Check required parameters
    for param in required_params:
        if param not in params:
            logger.error(f"Missing required parameter: {param}")
            return False
    
    # Validate parameter ranges
    if not (0.1 <= params['a'] <= 10.0):
        logger.error(f"Parameter 'a' must be between 0.1 and 10.0, got {params['a']}")
        return False
    
    if not (1 <= params['c'] <= 100):
        logger.error(f"Parameter 'c' must be between 1 and 100, got {params['c']}")
        return False
    
    if not (0.1 <= params['st_factor'] <= 10.0):
        logger.error(f"Parameter 'st_factor' must be between 0.1 and 10.0, got {params['st_factor']}")
        return False
    
    if not (0 <= params['min_delay_m'] <= 1440):
        logger.error(f"Parameter 'min_delay_m' must be between 0 and 1440, got {params['min_delay_m']}")
        return False
    
    if not (0.1 <= params['atr_sl_mult'] <= 10.0):
        logger.error(f"Parameter 'atr_sl_mult' must be between 0.1 and 10.0, got {params['atr_sl_mult']}")
        return False
    
    if not (0.1 <= params['atr_rr'] <= 10.0):
        logger.error(f"Parameter 'atr_rr' must be between 0.1 and 10.0, got {params['atr_rr']}")
        return False
    
    return True
