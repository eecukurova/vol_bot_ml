"""
NASDAQ ATR + SuperTrend Strategy

NASDAQ hisseleri için özelleştirilmiş ATR + SuperTrend stratejisi.
Yahoo Finance verisi ile çalışır ve hisse senetleri için optimize edilmiştir.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class TradeSignal:
    """Trade signal data structure."""
    timestamp: pd.Timestamp
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    price: float
    confidence: float
    reason: str
    indicators: Dict[str, float]

@dataclass
class StrategyResult:
    """Strategy execution result."""
    signals: List[TradeSignal]
    equity_curve: pd.Series
    trades: List[Dict[str, Any]]
    metrics: Dict[str, float]
    parameters: Dict[str, Any]

class BaseNASDAQStrategy(ABC):
    """Base class for NASDAQ strategies."""
    
    def __init__(self, parameters: Dict[str, Any]):
        self.parameters = parameters
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[TradeSignal]:
        """Generate trading signals."""
        pass
    
    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators."""
        pass
    
    def run_strategy(self, data: pd.DataFrame) -> StrategyResult:
        """Run the complete strategy."""
        try:
            # Calculate indicators
            data_with_indicators = self.calculate_indicators(data)
            
            # Generate signals
            signals = self.generate_signals(data_with_indicators)
            
            # Calculate equity curve and trades
            equity_curve, trades = self._calculate_equity_curve(data_with_indicators, signals)
            
            # Calculate metrics
            metrics = self._calculate_metrics(equity_curve, trades)
            
            return StrategyResult(
                signals=signals,
                equity_curve=equity_curve,
                trades=trades,
                metrics=metrics,
                parameters=self.parameters
            )
            
        except Exception as e:
            self.logger.error(f"Strategy execution error: {e}")
            raise

class NASDAQATRSuperTrendStrategy(BaseNASDAQStrategy):
    """
    NASDAQ ATR + SuperTrend Strategy
    
    NASDAQ hisseleri için özelleştirilmiş ATR + SuperTrend stratejisi.
    """
    
    def __init__(self, parameters: Dict[str, Any]):
        super().__init__(parameters)
        
        # ATR parameters
        self.atr_period = parameters.get('c', 10)
        self.atr_multiplier = parameters.get('a', 3)
        
        # SuperTrend parameters
        self.st_factor = parameters.get('st_factor', 1.5)
        
        # EMA confirmation parameters
        self.use_ema_confirmation = parameters.get('use_ema_confirmation', True)
        self.ema_fast_len = parameters.get('ema_fast_len', 12)
        self.ema_slow_len = parameters.get('ema_slow_len', 26)
        
        # Heikin Ashi
        self.use_heikin_ashi = parameters.get('use_heikin_ashi', False)
        
        # Volume filtering
        self.use_volume_filter = parameters.get('volume_filter', True)
        self.min_volume_mult = parameters.get('min_volume_mult', 1.5)
        
        # Risk management
        self.stop_loss_mult = parameters.get('atr_sl_mult', 2.0)
        self.risk_reward_ratio = parameters.get('atr_rr', 2.0)
        
        self.logger.info(f"NASDAQ ATR SuperTrend Strategy initialized with parameters: {parameters}")
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators."""
        df = data.copy()
        
        # Use Heikin Ashi if enabled
        if self.use_heikin_ashi:
            df = self._calculate_heikin_ashi(df)
        
        # Calculate ATR
        df['atr'] = self._calculate_atr(df, self.atr_period)
        
        # Calculate ATR Trailing Stop
        df['atr_trailing_stop'] = self._calculate_atr_trailing_stop(df)
        
        # Calculate SuperTrend
        df['super_trend'] = self._calculate_super_trend(df)
        
        # Calculate EMAs for confirmation
        if self.use_ema_confirmation:
            df['ema_fast'] = df['close'].ewm(span=self.ema_fast_len).mean()
            df['ema_slow'] = df['close'].ewm(span=self.ema_slow_len).mean()
        
        # Calculate volume indicators
        if self.use_volume_filter:
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> List[TradeSignal]:
        """Generate trading signals."""
        signals = []
        
        for i in range(1, len(data)):
            current_data = data.iloc[i]
            prev_data = data.iloc[i-1]
            
            signal = self._check_signal_conditions(current_data, prev_data, i)
            if signal:
                signals.append(signal)
        
        return signals
    
    def _check_signal_conditions(self, current: pd.Series, previous: pd.Series, index: int) -> Optional[TradeSignal]:
        """Check signal conditions for current bar."""
        
        # Volume filter
        if self.use_volume_filter and current['volume_ratio'] < self.min_volume_mult:
            return None
        
        # ATR Trailing Stop signals
        atr_buy = (current['close'] > current['atr_trailing_stop'] and 
                  previous['close'] <= previous['atr_trailing_stop'])
        
        atr_sell = (current['close'] < current['atr_trailing_stop'] and 
                   previous['close'] >= previous['atr_trailing_stop'])
        
        # SuperTrend signals
        st_buy = (current['close'] > current['super_trend'] and 
                 previous['close'] <= previous['super_trend'])
        
        st_sell = (current['close'] < current['super_trend'] and 
                  previous['close'] >= previous['super_trend'])
        
        # EMA confirmation
        ema_confirmation_buy = True
        ema_confirmation_sell = True
        
        if self.use_ema_confirmation:
            ema_confirmation_buy = current['ema_fast'] > current['ema_slow']
            ema_confirmation_sell = current['ema_fast'] < current['ema_slow']
        
        # Combined signals
        buy_signal = atr_buy and st_buy and ema_confirmation_buy
        sell_signal = atr_sell and st_sell and ema_confirmation_sell
        
        if buy_signal:
            confidence = self._calculate_signal_confidence(current, 'BUY')
            return TradeSignal(
                timestamp=current.name,
                signal_type='BUY',
                price=current['close'],
                confidence=confidence,
                reason=f"ATR+ST+EMA BUY: ATR={current['atr_trailing_stop']:.2f}, ST={current['super_trend']:.2f}",
                indicators={
                    'atr': current['atr'],
                    'atr_trailing_stop': current['atr_trailing_stop'],
                    'super_trend': current['super_trend'],
                    'ema_fast': current.get('ema_fast', 0),
                    'ema_slow': current.get('ema_slow', 0),
                    'volume_ratio': current.get('volume_ratio', 1)
                }
            )
        
        elif sell_signal:
            confidence = self._calculate_signal_confidence(current, 'SELL')
            return TradeSignal(
                timestamp=current.name,
                signal_type='SELL',
                price=current['close'],
                confidence=confidence,
                reason=f"ATR+ST+EMA SELL: ATR={current['atr_trailing_stop']:.2f}, ST={current['super_trend']:.2f}",
                indicators={
                    'atr': current['atr'],
                    'atr_trailing_stop': current['atr_trailing_stop'],
                    'super_trend': current['super_trend'],
                    'ema_fast': current.get('ema_fast', 0),
                    'ema_slow': current.get('ema_slow', 0),
                    'volume_ratio': current.get('volume_ratio', 1)
                }
            )
        
        return None
    
    def _calculate_signal_confidence(self, data: pd.Series, signal_type: str) -> float:
        """Calculate signal confidence score."""
        confidence = 0.5  # Base confidence
        
        # Volume confirmation
        if self.use_volume_filter:
            volume_score = min(data['volume_ratio'] / 2.0, 1.0)
            confidence += volume_score * 0.2
        
        # EMA confirmation strength
        if self.use_ema_confirmation:
            ema_diff = abs(data['ema_fast'] - data['ema_slow']) / data['close']
            ema_score = min(ema_diff * 100, 1.0)
            confidence += ema_score * 0.3
        
        return min(confidence, 1.0)
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average True Range."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    def _calculate_atr_trailing_stop(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ATR Trailing Stop."""
        atr = df['atr']
        close = df['close']
        
        # Initialize arrays
        atr_trailing_stop = np.zeros(len(df))
        trend = np.zeros(len(df))
        
        # First value
        atr_trailing_stop[0] = close.iloc[0] - (self.atr_multiplier * atr.iloc[0])
        trend[0] = 1
        
        for i in range(1, len(df)):
            if trend[i-1] == 1:  # Uptrend
                if close.iloc[i] > atr_trailing_stop[i-1]:
                    atr_trailing_stop[i] = max(atr_trailing_stop[i-1], close.iloc[i] - (self.atr_multiplier * atr.iloc[i]))
                    trend[i] = 1
                else:
                    atr_trailing_stop[i] = close.iloc[i] + (self.atr_multiplier * atr.iloc[i])
                    trend[i] = -1
            else:  # Downtrend
                if close.iloc[i] < atr_trailing_stop[i-1]:
                    atr_trailing_stop[i] = min(atr_trailing_stop[i-1], close.iloc[i] + (self.atr_multiplier * atr.iloc[i]))
                    trend[i] = -1
                else:
                    atr_trailing_stop[i] = close.iloc[i] - (self.atr_multiplier * atr.iloc[i])
                    trend[i] = 1
        
        return pd.Series(atr_trailing_stop, index=df.index)
    
    def _calculate_super_trend(self, df: pd.DataFrame) -> pd.Series:
        """Calculate SuperTrend indicator."""
        atr = df['atr']
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Calculate basic upper and lower bands
        hl2 = (high + low) / 2
        upper_band = hl2 + (self.st_factor * atr)
        lower_band = hl2 - (self.st_factor * atr)
        
        # Initialize arrays
        super_trend = np.zeros(len(df))
        trend = np.zeros(len(df))
        
        # First value
        super_trend[0] = lower_band.iloc[0]
        trend[0] = 1
        
        for i in range(1, len(df)):
            if trend[i-1] == 1:  # Uptrend
                if close.iloc[i] <= lower_band.iloc[i]:
                    super_trend[i] = upper_band.iloc[i]
                    trend[i] = -1
                else:
                    super_trend[i] = lower_band.iloc[i]
                    trend[i] = 1
            else:  # Downtrend
                if close.iloc[i] >= upper_band.iloc[i]:
                    super_trend[i] = lower_band.iloc[i]
                    trend[i] = 1
                else:
                    super_trend[i] = upper_band.iloc[i]
                    trend[i] = -1
        
        return pd.Series(super_trend, index=df.index)
    
    def _calculate_heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Heikin Ashi candles."""
        ha_df = df.copy()
        
        # First HA candle
        ha_df.loc[ha_df.index[0], 'ha_close'] = (df['open'].iloc[0] + df['high'].iloc[0] + df['low'].iloc[0] + df['close'].iloc[0]) / 4
        ha_df.loc[ha_df.index[0], 'ha_open'] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
        
        for i in range(1, len(df)):
            # HA Close
            ha_df.loc[ha_df.index[i], 'ha_close'] = (df['open'].iloc[i] + df['high'].iloc[i] + df['low'].iloc[i] + df['close'].iloc[i]) / 4
            
            # HA Open
            ha_df.loc[ha_df.index[i], 'ha_open'] = (ha_df['ha_open'].iloc[i-1] + ha_df['ha_close'].iloc[i-1]) / 2
            
            # HA High
            ha_df.loc[ha_df.index[i], 'ha_high'] = max(df['high'].iloc[i], ha_df['ha_open'].iloc[i], ha_df['ha_close'].iloc[i])
            
            # HA Low
            ha_df.loc[ha_df.index[i], 'ha_low'] = min(df['low'].iloc[i], ha_df['ha_open'].iloc[i], ha_df['ha_close'].iloc[i])
        
        # Replace original OHLC with HA OHLC
        ha_df['open'] = ha_df['ha_open']
        ha_df['high'] = ha_df['ha_high']
        ha_df['low'] = ha_df['ha_low']
        ha_df['close'] = ha_df['ha_close']
        
        # Drop HA columns
        ha_df = ha_df.drop(['ha_open', 'ha_high', 'ha_low', 'ha_close'], axis=1)
        
        return ha_df
    
    def _calculate_equity_curve(self, data: pd.DataFrame, signals: List[TradeSignal]) -> Tuple[pd.Series, List[Dict]]:
        """Calculate equity curve and trades."""
        equity = pd.Series(index=data.index, dtype=float)
        equity.iloc[0] = 10000  # Starting capital
        
        trades = []
        position = None
        
        for i, signal in enumerate(signals):
            if signal.signal_type == 'BUY' and position is None:
                # Open long position
                position = {
                    'entry_time': signal.timestamp,
                    'entry_price': signal.price,
                    'stop_loss': signal.price * (1 - self.stop_loss_mult * data.loc[signal.timestamp, 'atr'] / signal.price),
                    'take_profit': signal.price * (1 + self.risk_reward_ratio * self.stop_loss_mult * data.loc[signal.timestamp, 'atr'] / signal.price),
                    'confidence': signal.confidence
                }
                
            elif signal.signal_type == 'SELL' and position is not None:
                # Close long position
                exit_price = signal.price
                pnl = (exit_price - position['entry_price']) / position['entry_price']
                
                trades.append({
                    'entry_time': position['entry_time'],
                    'exit_time': signal.timestamp,
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'confidence': position['confidence']
                })
                
                position = None
        
        # Calculate equity curve
        current_equity = 10000
        for i in range(len(data)):
            if i == 0:
                equity.iloc[i] = current_equity
            else:
                # Simple equity calculation (can be improved)
                equity.iloc[i] = current_equity
        
        return equity, trades
    
    def _calculate_metrics(self, equity_curve: pd.Series, trades: List[Dict]) -> Dict[str, float]:
        """Calculate performance metrics."""
        if len(trades) == 0:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'total_trades': 0
            }
        
        # Calculate returns
        returns = equity_curve.pct_change().dropna()
        
        # Total return
        total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
        
        # Sharpe ratio
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # Maximum drawdown
        rolling_max = equity_curve.expanding().max()
        drawdown = (equity_curve - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # Win rate
        winning_trades = [t for t in trades if t['pnl'] > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        # Profit factor
        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(trades)
        }


def create_strategy(parameters: Dict[str, Any]) -> NASDAQATRSuperTrendStrategy:
    """Create NASDAQ ATR SuperTrend strategy instance."""
    return NASDAQATRSuperTrendStrategy(parameters)


def create_nasdaq_strategy(strategy_type: str, parameters: Dict[str, Any]) -> BaseNASDAQStrategy:
    """Factory function to create NASDAQ strategies."""
    if strategy_type.lower() == 'atr_supertrend':
        return NASDAQATRSuperTrendStrategy(parameters)
    else:
        raise ValueError(f"Unknown NASDAQ strategy type: {strategy_type}")
