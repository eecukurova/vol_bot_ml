"""
Volensy MACD Trend Strategy Implementation

This module implements the Pine Script v6 strategy logic for Volensy MACD Trend
with EMA trend filter, MACD momentum, and RSI confirmation.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from numba import jit
import logging

logger = logging.getLogger(__name__)


@jit(nopython=True)
def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Calculate EMA using Numba for performance."""
    n = len(prices)
    ema = np.zeros(n)
    
    if n < period:
        return ema
    
    # Calculate initial SMA
    sma = np.mean(prices[:period])
    ema[period-1] = sma
    
    # Calculate EMA
    multiplier = 2.0 / (period + 1)
    for i in range(period, n):
        ema[i] = (prices[i] * multiplier) + (ema[i-1] * (1 - multiplier))
    
    return ema


@jit(nopython=True)
def calculate_rsi(prices: np.ndarray, period: int) -> np.ndarray:
    """Calculate RSI using Numba for performance."""
    n = len(prices)
    rsi = np.zeros(n)
    
    if n < period + 1:
        return rsi
    
    # Calculate price changes
    deltas = np.zeros(n)
    for i in range(1, n):
        deltas[i] = prices[i] - prices[i-1]
    
    # Separate gains and losses
    gains = np.zeros(n)
    losses = np.zeros(n)
    
    for i in range(1, n):
        if deltas[i] > 0:
            gains[i] = deltas[i]
        else:
            losses[i] = -deltas[i]
    
    # Calculate initial average gain and loss
    avg_gain = np.mean(gains[1:period+1])
    avg_loss = np.mean(losses[1:period+1])
    
    # Calculate RSI
    for i in range(period, n):
        if i == period:
            avg_gain = avg_gain
            avg_loss = avg_loss
        else:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    
    return rsi


class VolensyMacdTrendStrategy:
    """
    Volensy MACD Trend Strategy Implementation
    
    This strategy combines:
    - EMA trend filter
    - MACD momentum
    - RSI confirmation
    - Score-based signal generation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the strategy with configuration parameters.
        
        Args:
            config: Strategy configuration dictionary
        """
        self.config = config
        
        # Trend/EMA parameters
        self.ema_len = config.get('ema_len', 55)
        
        # MACD parameters
        self.macd_fast = config.get('macd_fast', 12)
        self.macd_slow = config.get('macd_slow', 26)
        self.macd_signal = config.get('macd_signal', 9)
        
        # RSI parameters
        self.rsi_len = config.get('rsi_len', 14)
        self.rsi_ob = config.get('rsi_ob', 70.0)
        self.rsi_os = config.get('rsi_os', 30.0)
        
        # ATR parameters (for information)
        self.atr_len = config.get('atr_len', 14)
        
        # Signal settings
        self.only_on_close = config.get('only_on_close', True)
        
        # State variables
        self.last_direction = 0  # 1 = last signal BUY, -1 = last signal SELL, 0 = none
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all required indicators for the strategy.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with calculated indicators
        """
        df = df.copy()
        
        # Calculate EMA trend
        df['ema_trend'] = calculate_ema(df['close'].values, self.ema_len)
        
        # Calculate MACD
        ema_fast = calculate_ema(df['close'].values, self.macd_fast)
        ema_slow = calculate_ema(df['close'].values, self.macd_slow)
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = calculate_ema(df['macd'].values, self.macd_signal)
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Calculate RSI
        df['rsi'] = calculate_rsi(df['close'].values, self.rsi_len)
        
        # Calculate ATR (for information)
        df['atr'] = self._calculate_atr(df)
        
        return df
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ATR using pandas."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_len).mean()
        
        return atr
    
    def run_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run the complete strategy on the given data.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with signals
        """
        # Calculate indicators
        df_with_indicators = self.calculate_indicators(df)
        
        # Generate signals
        df_with_signals = self.generate_signals(df_with_indicators)
        
        return df_with_signals
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on the strategy logic.
        
        Args:
            df: DataFrame with OHLCV data and indicators
            
        Returns:
            DataFrame with signals
        """
        df = df.copy()
        
        # Component conditions
        df['is_bull_trend'] = df['close'] > df['ema_trend']
        df['is_bear_trend'] = df['close'] < df['ema_trend']
        df['is_bull_momentum'] = df['rsi'] > 50
        df['is_bear_momentum'] = df['rsi'] < 50
        df['is_bull_power'] = df['macd'] > df['macd_signal']
        df['is_bear_power'] = df['macd'] < df['macd_signal']
        
        # RSI overbought/oversold conditions
        df['not_overbought'] = df['rsi'] < self.rsi_ob
        df['not_oversold'] = df['rsi'] > self.rsi_os
        
        # Calculate scores
        df['bull_score'] = (
            df['is_bull_trend'].astype(int) + 
            df['is_bull_momentum'].astype(int) + 
            df['is_bull_power'].astype(int)
        )
        
        df['bear_score'] = (
            df['is_bear_trend'].astype(int) + 
            df['is_bear_momentum'].astype(int) + 
            df['is_bear_power'].astype(int)
        )
        
        # Raw signals
        df['raw_buy'] = (df['bull_score'] == 3) & df['not_overbought']
        df['raw_sell'] = (df['bear_score'] == 3) & df['not_oversold']
        
        # Signal confirmation (only on close if enabled)
        if self.only_on_close:
            df['can_signal'] = True  # In backtesting, we assume all bars are confirmed
        else:
            df['can_signal'] = True
        
        # Prevent duplicate signals
        df['buy_signal'] = False
        df['sell_signal'] = False
        
        # Track last direction to prevent duplicates
        last_dir = 0
        
        for i in range(len(df)):
            if df.iloc[i]['can_signal'] and df.iloc[i]['raw_buy'] and last_dir != 1:
                df.iloc[i, df.columns.get_loc('buy_signal')] = True
                last_dir = 1
            elif df.iloc[i]['can_signal'] and df.iloc[i]['raw_sell'] and last_dir != -1:
                df.iloc[i, df.columns.get_loc('sell_signal')] = True
                last_dir = -1
        
        # Convert signals to backtester format
        df['buy_final'] = df['buy_signal']
        df['sell_final'] = df['sell_signal']
        
        return df
    
    def get_strategy_name(self) -> str:
        """Get the strategy name."""
        return "VolensyMacdTrend"
    
    def get_parameter_ranges(self) -> Dict[str, List]:
        """
        Get parameter ranges for optimization.
        
        Returns:
            Dictionary with parameter ranges
        """
        return {
            'ema_len': list(range(20, 100, 5)),
            'macd_fast': list(range(8, 20, 2)),
            'macd_slow': list(range(20, 35, 3)),
            'macd_signal': list(range(6, 15, 2)),
            'rsi_len': list(range(10, 20, 2)),
            'rsi_ob': [65.0, 70.0, 75.0, 80.0],
            'rsi_os': [20.0, 25.0, 30.0, 35.0],
            'atr_len': list(range(10, 20, 2)),
        }
    
    def get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration parameters.
        
        Returns:
            Dictionary with default parameters
        """
        return {
            'ema_len': 55,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'rsi_len': 14,
            'rsi_ob': 70.0,
            'rsi_os': 30.0,
            'atr_len': 14,
            'only_on_close': True,
        }


def validate_strategy_params(params: Dict[str, Any]) -> bool:
    """
    Validate strategy parameters.
    
    Args:
        params: Parameter dictionary
        
    Returns:
        True if parameters are valid
    """
    required_params = ['ema_len', 'macd_fast', 'macd_slow', 'macd_signal', 'rsi_len', 'rsi_ob', 'rsi_os', 'atr_len']
    
    for param in required_params:
        if param not in params:
            logger.error(f"Missing required parameter: {param}")
            return False
    
    # Validate ranges
    if not (1 <= params['ema_len'] <= 200):
        logger.error(f"Invalid ema_len: {params['ema_len']}")
        return False
    
    if not (1 <= params['macd_fast'] <= 50):
        logger.error(f"Invalid macd_fast: {params['macd_fast']}")
        return False
    
    if not (1 <= params['macd_slow'] <= 100):
        logger.error(f"Invalid macd_slow: {params['macd_slow']}")
        return False
    
    if not (1 <= params['macd_signal'] <= 50):
        logger.error(f"Invalid macd_signal: {params['macd_signal']}")
        return False
    
    if not (1 <= params['rsi_len'] <= 100):
        logger.error(f"Invalid rsi_len: {params['rsi_len']}")
        return False
    
    if not (50 <= params['rsi_ob'] <= 100):
        logger.error(f"Invalid rsi_ob: {params['rsi_ob']}")
        return False
    
    if not (0 <= params['rsi_os'] <= 50):
        logger.error(f"Invalid rsi_os: {params['rsi_os']}")
        return False
    
    if not (1 <= params['atr_len'] <= 100):
        logger.error(f"Invalid atr_len: {params['atr_len']}")
        return False
    
    return True


def create_strategy(config: Dict[str, Any]) -> VolensyMacdTrendStrategy:
    """
    Factory function to create a strategy instance.
    
    Args:
        config: Strategy configuration
        
    Returns:
        Strategy instance
    """
    return VolensyMacdTrendStrategy(config)
