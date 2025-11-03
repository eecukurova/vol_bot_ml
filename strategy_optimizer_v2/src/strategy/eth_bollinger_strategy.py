"""
ETH Bollinger Bands Strategy Implementation
Optimized for ETH USDT with Heiken Ashi candles and multiple entry scenarios
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

class ETHBollingerStrategy:
    """ETH Bollinger Bands Strategy with Heiken Ashi integration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.parameters = {}
        self.position = None
        self.trades = []
        
    def set_parameters(self, params: Dict):
        """Set strategy parameters"""
        self.parameters = params
        
    def calculate_heiken_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Heiken Ashi candles"""
        ha_df = df.copy()
        
        # Initialize HA values
        ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_df['ha_open'] = 0.0
        ha_df['ha_high'] = 0.0
        ha_df['ha_low'] = 0.0
        
        # Calculate HA Open (smoothed)
        for i in range(len(ha_df)):
            if i == 0:
                ha_df.iloc[i, ha_df.columns.get_loc('ha_open')] = df.iloc[i]['open']
            else:
                ha_df.iloc[i, ha_df.columns.get_loc('ha_open')] = (
                    ha_df.iloc[i-1]['ha_open'] + ha_df.iloc[i-1]['ha_close']
                ) / 2
        
        # Calculate HA High and Low
        ha_df['ha_high'] = np.maximum(
            df['high'],
            np.maximum(ha_df['ha_open'], ha_df['ha_close'])
        )
        ha_df['ha_low'] = np.minimum(
            df['low'],
            np.minimum(ha_df['ha_open'], ha_df['ha_close'])
        )
        
        return ha_df
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int, std_dev: float) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        middle = df['ha_close'].rolling(window=period).mean()
        std = df['ha_close'].rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return upper, middle, lower
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = df['ha_close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        ema_fast = df['ha_close'].ewm(span=fast).mean()
        ema_slow = df['ha_close'].ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate EMA"""
        return df['ha_close'].ewm(span=period).mean()
    
    def check_entry_conditions(self, df: pd.DataFrame, idx: int) -> Dict[str, bool]:
        """Check all entry conditions"""
        if idx < 20:  # Need enough data for indicators
            return {'entry': False, 'scenarios': {}}
        
        # Get current and previous values
        current = df.iloc[idx]
        prev = df.iloc[idx - 1]
        
        # Bollinger Bands
        bb_upper = current['bb_upper']
        bb_middle = current['bb_middle']
        bb_lower = current['bb_lower']
        
        # Price and volume
        ha_close = current['ha_close']
        ha_open = current['ha_open']
        ha_high = current['ha_high']
        ha_low = current['ha_low']
        volume = current['volume']
        
        # Indicators
        rsi = current['rsi']
        macd_line = current['macd_line']
        macd_signal = current['macd_signal']
        ema_20 = current['ema_20']
        ema_50 = current['ema_50']
        
        # Volume analysis
        avg_volume = df['volume'].rolling(window=self.parameters.get('volume_period', 7)).mean().iloc[idx]
        volume_condition = (volume > self.parameters.get('min_volume', 500000) and 
                           volume > avg_volume * self.parameters.get('volume_multiplier', 1.2))
        
        # Price change analysis
        price_change = (ha_close - df.iloc[idx - 1]['ha_close']) / df.iloc[idx - 1]['ha_close']
        price_change_valid = (price_change >= self.parameters.get('min_price_change', 0.015) and 
                             price_change <= self.parameters.get('max_price_change', 0.08))
        
        # Close-High difference
        high_close_diff = abs(1 - (ha_high / ha_close))
        close_near_high = high_close_diff < self.parameters.get('high_close_margin', 0.03)
        
        # Entry scenarios
        scenarios = {}
        
        # Scenario 1: Bollinger Upper Touch
        green_candle = ha_close > ha_open
        bb_upper_touch = ha_close >= bb_upper * 0.98
        rsi_oversold = rsi < 70 and rsi > 30
        
        scenarios['scenario_1'] = (green_candle and close_near_high and 
                                  volume_condition and bb_upper_touch and rsi_oversold)
        
        # Scenario 2: Middle Band Cross
        bb_middle_cross = ha_close > bb_middle and df.iloc[idx - 1]['ha_close'] <= df.iloc[idx - 1]['bb_middle']
        macd_bullish = macd_line > macd_signal and df.iloc[idx - 1]['macd_line'] <= df.iloc[idx - 1]['macd_signal']
        trend_bullish = ema_20 > ema_50 and ha_close > ema_20
        
        scenarios['scenario_2'] = (bb_middle_cross and volume_condition and 
                                  macd_bullish and trend_bullish)
        
        # Scenario 3: Strong Momentum
        strong_momentum = (ha_close - ha_open) / ha_open > 0.002
        bb_expansion = (bb_upper - bb_lower) / bb_middle > 0.02
        
        scenarios['scenario_3'] = (green_candle and strong_momentum and 
                                  volume_condition and bb_expansion and rsi_oversold)
        
        # Overall entry condition
        entry = any(scenarios.values())
        
        return {
            'entry': entry,
            'scenarios': scenarios,
            'price_change_valid': price_change_valid,
            'volume_condition': volume_condition
        }
    
    def calculate_exit_conditions(self, df: pd.DataFrame, idx: int, entry_price: float, entry_idx: int) -> Dict[str, bool]:
        """Calculate exit conditions"""
        current = df.iloc[idx]
        ha_close = current['ha_close']
        
        # Take profit
        target_profit = self.parameters.get('target_profit', 0.018)
        take_profit_price = entry_price * (1 + target_profit)
        take_profit_hit = ha_close >= take_profit_price
        
        # Stop loss
        stop_loss_pct = self.parameters.get('stop_loss_pct', 0.025)
        stop_loss_price = entry_price * (1 - stop_loss_pct)
        stop_loss_hit = ha_close <= stop_loss_price
        
        # Trailing stop (if enabled)
        trailing_active = False
        if self.parameters.get('trailing_stop', True):
            bars_since_entry = idx - entry_idx
            if bars_since_entry > 5:  # Start trailing after 5 bars
                highest_price = df.iloc[entry_idx:idx + 1]['ha_close'].max()
                trailing_percent = self.parameters.get('trailing_percent', 0.01)
                trailing_stop_price = highest_price * (1 - trailing_percent)
                trailing_active = ha_close <= trailing_stop_price
        
        # Time-based exit
        time_exit = (idx - entry_idx) > 100  # Exit after 100 bars
        
        return {
            'take_profit': take_profit_hit,
            'stop_loss': stop_loss_hit,
            'trailing_stop': trailing_active,
            'time_exit': time_exit,
            'exit': take_profit_hit or stop_loss_hit or trailing_active or time_exit
        }
    
    def backtest(self, df: pd.DataFrame) -> List[Dict]:
        """Run backtest on the data"""
        if df.empty:
            return []
        
        # Calculate Heiken Ashi
        df = self.calculate_heiken_ashi(df)
        
        # Calculate indicators
        bb_length = self.parameters.get('bb_length', 14)
        bb_mult = self.parameters.get('bb_mult', 1.8)
        
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = self.calculate_bollinger_bands(df, bb_length, bb_mult)
        df['rsi'] = self.calculate_rsi(df)
        df['macd_line'], df['macd_signal'], df['macd_histogram'] = self.calculate_macd(df)
        df['ema_20'] = self.calculate_ema(df, 20)
        df['ema_50'] = self.calculate_ema(df, 50)
        
        trades = []
        position = None
        
        for i in range(20, len(df)):  # Start after indicators are calculated
            current = df.iloc[i]
            
            if position is None:
                # Check for entry
                entry_conditions = self.check_entry_conditions(df, i)
                
                if entry_conditions['entry']:
                    position = {
                        'entry_price': current['ha_close'],
                        'entry_time': current.name if hasattr(current, 'name') else i,
                        'entry_idx': i,
                        'scenarios': entry_conditions['scenarios']
                    }
                    
            else:
                # Check for exit
                exit_conditions = self.calculate_exit_conditions(
                    df, i, position['entry_price'], position['entry_idx']
                )
                
                if exit_conditions['exit']:
                    # Close position
                    exit_price = current['ha_close']
                    pnl = (exit_price - position['entry_price']) / position['entry_price']
                    
                    trade = {
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'entry_time': position['entry_time'],
                        'exit_time': current.name if hasattr(current, 'name') else i,
                        'pnl': pnl,
                        'duration': i - position['entry_idx'],
                        'exit_reason': self.get_exit_reason(exit_conditions),
                        'scenarios': position['scenarios']
                    }
                    
                    trades.append(trade)
                    position = None
        
        return trades
    
    def get_exit_reason(self, exit_conditions: Dict[str, bool]) -> str:
        """Get exit reason"""
        if exit_conditions['take_profit']:
            return 'take_profit'
        elif exit_conditions['stop_loss']:
            return 'stop_loss'
        elif exit_conditions['trailing_stop']:
            return 'trailing_stop'
        elif exit_conditions['time_exit']:
            return 'time_exit'
        else:
            return 'unknown'
    
    def get_strategy_info(self) -> Dict:
        """Get strategy information"""
        return {
            'name': 'ETH Bollinger Bands Strategy',
            'description': 'Optimized Bollinger Bands strategy for ETH USDT with Heiken Ashi candles',
            'parameters': self.parameters,
            'features': [
                'Heiken Ashi candles',
                'Multiple entry scenarios',
                'Dynamic risk management',
                'Trailing stop',
                'Volume analysis',
                'RSI and MACD confirmation'
            ]
        }
