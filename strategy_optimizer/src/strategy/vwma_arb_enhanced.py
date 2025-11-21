"""
Enhanced VWMA Strategy for ARB - Multiple Indicators
MACD, Bollinger Bands, ATR, Volume Analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class VWMAARBEnhancedStrategy:
    """Enhanced VWMA Strategy with Multiple Indicators"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        Initialize Enhanced VWMA Strategy
        
        Args:
            params: Strategy parameters
        """
        # Entry parameters
        self.vwma_length = params.get('vwma_length', 25)
        self.rsi_length = params.get('rsi_length', 14)
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_overbought = params.get('rsi_overbought', 70)
        self.ema_fast = params.get('ema_fast', 12)
        self.ema_slow = params.get('ema_slow', 26)
        self.volume_ma_length = params.get('volume_ma_length', 20)
        self.volume_threshold = params.get('volume_threshold', 1.2)
        
        # New indicators
        self.macd_fast = params.get('macd_fast', 12)
        self.macd_slow = params.get('macd_slow', 26)
        self.macd_signal = params.get('macd_signal', 9)
        self.bb_length = params.get('bb_length', 20)
        self.bb_std = params.get('bb_std', 2.0)
        self.atr_length = params.get('atr_length', 14)
        self.atr_multiplier = params.get('atr_multiplier', 1.5)
        
        # Filters
        self.use_macd = params.get('use_macd', True)
        self.use_bollinger = params.get('use_bollinger', True)
        self.use_atr = params.get('use_atr', True)
        self.use_volume = params.get('use_volume', True)
        self.min_indicators = params.get('min_indicators', 3)  # Minimum kaç indikatör onaylamalı
        
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
    
    def calculate_macd(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        ema_fast = df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        sma = df['close'].rolling(window=self.bb_length, min_periods=self.bb_length).mean()
        std = df['close'].rolling(window=self.bb_length, min_periods=self.bb_length).std()
        upper = sma + (std * self.bb_std)
        lower = sma - (std * self.bb_std)
        return upper, sma, lower
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=self.atr_length, min_periods=self.atr_length).mean()
        return atr
    
    def calculate_volume_ma(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Volume Moving Average"""
        return df['volume'].rolling(window=self.volume_ma_length, min_periods=self.volume_ma_length).mean()
    
    def check_entry_long(self, df: pd.DataFrame, i: int) -> bool:
        """Check if LONG entry conditions are met - Multiple indicators"""
        if i < max(self.vwma_length, self.rsi_length, self.ema_slow, self.volume_ma_length, 
                  self.bb_length, self.atr_length, self.macd_slow):
            return False
        
        indicators_ok = 0
        
        # VWMA
        vwma_cond = df['close'].iloc[i] > df['vwma'].iloc[i]
        if vwma_cond:
            indicators_ok += 1
        
        # RSI
        rsi_cond = df['rsi'].iloc[i] < self.rsi_overbought and df['rsi'].iloc[i] > self.rsi_oversold
        if rsi_cond:
            indicators_ok += 1
        
        # EMA
        ema_cond = df['ema_fast'].iloc[i] > df['ema_slow'].iloc[i]
        if ema_cond:
            indicators_ok += 1
        
        # MACD
        if self.use_macd:
            macd_cond = df['macd'].iloc[i] > df['macd_signal'].iloc[i] and df['macd_hist'].iloc[i] > 0
            if macd_cond:
                indicators_ok += 1
        
        # Bollinger Bands
        if self.use_bollinger:
            bb_cond = df['close'].iloc[i] > df['bb_middle'].iloc[i] and df['close'].iloc[i] < df['bb_upper'].iloc[i]
            if bb_cond:
                indicators_ok += 1
        
        # ATR (volatility filter)
        if self.use_atr:
            atr_cond = (df['high'].iloc[i] - df['low'].iloc[i]) < (df['atr'].iloc[i] * self.atr_multiplier)
            if atr_cond:
                indicators_ok += 1
        
        # Volume
        if self.use_volume:
            volume_cond = df['volume'].iloc[i] > df['volume_ma'].iloc[i] * self.volume_threshold
            if volume_cond:
                indicators_ok += 1
        
        return indicators_ok >= self.min_indicators
    
    def check_entry_short(self, df: pd.DataFrame, i: int) -> bool:
        """Check if SHORT entry conditions are met - Multiple indicators"""
        if i < max(self.vwma_length, self.rsi_length, self.ema_slow, self.volume_ma_length,
                  self.bb_length, self.atr_length, self.macd_slow):
            return False
        
        indicators_ok = 0
        
        # VWMA
        vwma_cond = df['close'].iloc[i] < df['vwma'].iloc[i]
        if vwma_cond:
            indicators_ok += 1
        
        # RSI
        rsi_cond = df['rsi'].iloc[i] > self.rsi_oversold and df['rsi'].iloc[i] < self.rsi_overbought
        if rsi_cond:
            indicators_ok += 1
        
        # EMA
        ema_cond = df['ema_fast'].iloc[i] < df['ema_slow'].iloc[i]
        if ema_cond:
            indicators_ok += 1
        
        # MACD
        if self.use_macd:
            macd_cond = df['macd'].iloc[i] < df['macd_signal'].iloc[i] and df['macd_hist'].iloc[i] < 0
            if macd_cond:
                indicators_ok += 1
        
        # Bollinger Bands
        if self.use_bollinger:
            bb_cond = df['close'].iloc[i] < df['bb_middle'].iloc[i] and df['close'].iloc[i] > df['bb_lower'].iloc[i]
            if bb_cond:
                indicators_ok += 1
        
        # ATR
        if self.use_atr:
            atr_cond = (df['high'].iloc[i] - df['low'].iloc[i]) < (df['atr'].iloc[i] * self.atr_multiplier)
            if atr_cond:
                indicators_ok += 1
        
        # Volume
        if self.use_volume:
            volume_cond = df['volume'].iloc[i] > df['volume_ma'].iloc[i] * self.volume_threshold
            if volume_cond:
                indicators_ok += 1
        
        return indicators_ok >= self.min_indicators
    
    def run_backtest(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run backtest with enhanced indicators"""
        df = df.copy()
        df.columns = df.columns.str.lower()
        
        # Calculate indicators
        df['vwma'] = self.calculate_vwma(df)
        df['rsi'] = self.calculate_rsi(df, self.rsi_length)
        df['ema_fast'] = self.calculate_ema(df, self.ema_fast)
        df['ema_slow'] = self.calculate_ema(df, self.ema_slow)
        df['volume_ma'] = self.calculate_volume_ma(df)
        
        # New indicators
        if self.use_macd:
            macd, signal, hist = self.calculate_macd(df)
            df['macd'] = macd
            df['macd_signal'] = signal
            df['macd_hist'] = hist
        
        if self.use_bollinger:
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df)
            df['bb_upper'] = bb_upper
            df['bb_middle'] = bb_middle
            df['bb_lower'] = bb_lower
        
        if self.use_atr:
            df['atr'] = self.calculate_atr(df)
        
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
        if self.use_bollinger:
            min_bars = max(min_bars, self.bb_length)
        if self.use_atr:
            min_bars = max(min_bars, self.atr_length)
        if self.use_macd:
            min_bars = max(min_bars, self.macd_slow)
        
        # Main loop
        for i in range(min_bars, len(df)):
            current_price = df['close'].iloc[i]
            current_high = df['high'].iloc[i]
            current_low = df['low'].iloc[i]
            
            # Skip if NaN
            required_cols = ['vwma', 'rsi', 'ema_fast', 'ema_slow', 'volume_ma']
            if self.use_macd:
                required_cols.extend(['macd', 'macd_signal', 'macd_hist'])
            if self.use_bollinger:
                required_cols.extend(['bb_upper', 'bb_middle', 'bb_lower'])
            if self.use_atr:
                required_cols.append('atr')
            
            if any(pd.isna(df[col].iloc[i]) for col in required_cols):
                continue
            
            # Exit conditions (same as before)
            exit_signal = False
            exit_reason = None
            exit_price = None
            
            if position == 'LONG':
                current_profit_pct = ((current_price - entry_price) / entry_price) * 100
                
                if not trailing_activated and current_profit_pct >= self.trailing_activation_pct:
                    trailing_activated = True
                    trailing_stop_price = entry_price * (1 + trailing_activation_mult - trailing_distance_mult)
                
                if trailing_activated:
                    new_trailing = current_price * (1 - trailing_distance_mult)
                    if new_trailing > trailing_stop_price:
                        trailing_stop_price = new_trailing
                
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
                
                if not trailing_activated and current_profit_pct >= self.trailing_activation_pct:
                    trailing_activated = True
                    trailing_stop_price = entry_price * (1 - trailing_activation_mult + trailing_distance_mult)
                
                if trailing_activated:
                    new_trailing = current_price * (1 + trailing_distance_mult)
                    if new_trailing < trailing_stop_price:
                        trailing_stop_price = new_trailing
                
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

