"""
Backtesting engine for ATR + SuperTrend strategy.

This module implements a comprehensive backtesting engine with position management,
stop loss/take profit execution, commission handling, and slippage simulation.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Trade record."""
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    side: str  # 'long' or 'short'
    quantity: float
    stop_loss: float
    take_profit: float
    pnl: Optional[float] = None
    commission: Optional[float] = None
    slippage: Optional[float] = None
    exit_reason: Optional[str] = None  # 'sl', 'tp', 'signal', 'end'


@dataclass
class BacktestResult:
    """Backtest result container."""
    trades: List[Trade]
    equity_curve: pd.Series
    metrics: Dict[str, float]
    parameters: Dict[str, Any]
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime


class Backtester:
    """
    Backtesting engine for ATR + SuperTrend strategy.
    """
    
    def __init__(self, initial_capital: float = 10000.0, fee_bps: float = 5.0, 
                 slippage_bps: float = 5.0, position_size: float = 200.0, 
                 leverage: float = 10.0):
        """
        Initialize backtester with risk management.
        
        Args:
            initial_capital: Initial capital amount
            fee_bps: Fee in basis points (0.05% = 5 bps)
            slippage_bps: Slippage in basis points
            position_size: Fixed position size in USD ($200)
            leverage: Leverage multiplier (10x)
        """
        self.initial_capital = initial_capital
        self.fee_bps = fee_bps / 10000.0  # Convert to decimal
        self.slippage_bps = slippage_bps / 10000.0  # Convert to decimal
        
        # Risk management parameters
        self.position_size = position_size  # $200 fixed position size
        self.leverage = leverage  # 10x leverage
        
        # State variables
        self.current_capital = initial_capital
        self.current_position = None
        self.trades = []
        self.equity_curve = []
        
    def calculate_position_size(self, price: float, stop_loss: float) -> float:
        """
        Calculate position size based on fixed $200 position size with 10x leverage.
        
        Args:
            price: Entry price
            stop_loss: Stop loss price
            
        Returns:
            Position size in units
        """
        # Fixed position size: $200 with 10x leverage
        # This means we control $2000 worth of assets with $200 margin
        position_value = self.position_size * self.leverage  # $200 * 10 = $2000
        
        # Calculate quantity based on position value
        quantity = position_value / price
        
        return quantity
    
    def apply_slippage(self, price: float, side: str) -> float:
        """
        Apply slippage to price.
        
        Args:
            price: Original price
            side: 'buy' or 'sell'
            
        Returns:
            Price with slippage applied
        """
        slippage_amount = price * self.slippage_bps
        
        if side == 'buy':
            return price + slippage_amount
        else:
            return price - slippage_amount
    
    def calculate_commission(self, price: float, quantity: float) -> float:
        """
        Calculate commission for trade.
        
        Args:
            price: Trade price
            quantity: Trade quantity
            
        Returns:
            Commission amount
        """
        trade_value = price * quantity
        return trade_value * self.fee_bps
    
    def open_position(self, timestamp: datetime, price: float, side: str, 
                     stop_loss: float, take_profit: float, trailing_tp: Optional[float] = None) -> Optional[Trade]:
        """
        Open a new position with fixed stop loss and trailing take profit.
        
        Args:
            timestamp: Entry timestamp
            price: Entry price
            side: 'long' or 'short'
            stop_loss: Fixed stop loss price (never changes)
            take_profit: Initial take profit price
            trailing_tp: Trailing take profit price (can be updated)
            
        Returns:
            Trade object or None if position couldn't be opened
        """
        if self.current_position is not None:
            logger.warning("Attempting to open position while one is already open")
            return None
        
        # Apply slippage
        entry_price = self.apply_slippage(price, 'buy' if side == 'long' else 'sell')
        
        # Calculate position size based on fixed $200 with 10x leverage
        quantity = self.calculate_position_size(entry_price, stop_loss)
        
        if quantity <= 0:
            logger.warning("Position size is zero or negative")
            return None
        
        # Calculate commission
        commission = self.calculate_commission(entry_price, quantity)
        
        # Check if we have enough capital for margin
        margin_required = self.position_size  # $200 margin for $2000 position
        if margin_required > self.current_capital:
            logger.warning(f"Insufficient capital for position. Required: ${margin_required:.2f}, Available: ${self.current_capital:.2f}")
            return None
        
        # Create trade
        trade = Trade(
            entry_time=timestamp,
            exit_time=None,
            entry_price=entry_price,
            exit_price=None,
            side=side,
            quantity=quantity,
            stop_loss=stop_loss,  # Fixed stop loss
            take_profit=trailing_tp if trailing_tp is not None else take_profit,  # Use trailing TP if available
            commission=commission,
            slippage=abs(entry_price - price)
        )
        
        # Update capital (deduct margin)
        self.current_capital -= margin_required
        self.current_position = trade
        
        logger.info(f"Opened {side} position: {quantity:.6f} units at ${entry_price:.4f}, "
                   f"SL: ${stop_loss:.4f}, TP: ${trade.take_profit:.4f}, Margin: ${margin_required:.2f}")
        
        return trade
    
    def close_position(self, timestamp: datetime, price: float, reason: str) -> Optional[Trade]:
        """
        Close current position.
        
        Args:
            timestamp: Exit timestamp
            price: Exit price
            reason: Exit reason
            
        Returns:
            Updated trade object or None if no position to close
        """
        if self.current_position is None:
            logger.warning("Attempting to close position when none is open")
            return None
        
        trade = self.current_position
        
        # Apply slippage
        exit_price = self.apply_slippage(price, 'sell' if trade.side == 'long' else 'buy')
        
        # Calculate PnL with leverage
        if trade.side == 'long':
            pnl = (exit_price - trade.entry_price) * trade.quantity
        else:
            pnl = (trade.entry_price - exit_price) * trade.quantity
        
        # Calculate exit commission
        exit_commission = self.calculate_commission(exit_price, trade.quantity)
        
        # Update trade
        trade.exit_time = timestamp
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.commission = (trade.commission or 0) + exit_commission
        trade.exit_reason = reason
        
        # Update capital: return margin + PnL - commissions
        margin_return = self.position_size  # Return $200 margin
        self.current_capital += margin_return + pnl - exit_commission
        
        # Add to trades list
        self.trades.append(trade)
        self.current_position = None
        
        logger.info(f"Closed {trade.side} position: PnL: ${pnl:.2f}, Commission: ${exit_commission:.2f}, "
                   f"Margin Return: ${margin_return:.2f}, New Capital: ${self.current_capital:.2f}")
        
        return trade
    
    def check_stop_loss_take_profit(self, timestamp: datetime, high: float, 
                                   low: float, close: float) -> Optional[str]:
        """
        Check if stop loss or take profit should be triggered.
        
        Args:
            timestamp: Current timestamp
            high: High price
            low: Low price
            close: Close price
            
        Returns:
            Exit reason if triggered, None otherwise
        """
        if self.current_position is None:
            return None
        
        trade = self.current_position
        
        if trade.side == 'long':
            # Check take profit
            if high >= trade.take_profit:
                self.close_position(timestamp, trade.take_profit, 'tp')
                return 'tp'
            
            # Check stop loss
            if low <= trade.stop_loss:
                self.close_position(timestamp, trade.stop_loss, 'sl')
                return 'sl'
        
        else:  # short position
            # Check take profit
            if low <= trade.take_profit:
                self.close_position(timestamp, trade.take_profit, 'tp')
                return 'tp'
            
            # Check stop loss
            if high >= trade.stop_loss:
                self.close_position(timestamp, trade.stop_loss, 'sl')
                return 'sl'
        
        return None
    
    def run_backtest(self, data: pd.DataFrame, signals: pd.DataFrame) -> BacktestResult:
        """
        Run backtest on data with signals.
        
        Args:
            data: OHLCV data
            signals: DataFrame with trading signals
            
        Returns:
            BacktestResult object
        """
        logger.info(f"Starting backtest with {len(data)} candles")
        
        # Reset state
        self.current_capital = self.initial_capital
        self.current_position = None
        self.trades = []
        self.equity_curve = []
        
        # Process each candle
        for i, (timestamp, row) in enumerate(data.iterrows()):
            # Check SL/TP first
            sl_tp_triggered = self.check_stop_loss_take_profit(
                timestamp, row['high'], row['low'], row['close']
            )
            
            # Process signals if no SL/TP triggered
            if not sl_tp_triggered:
                # Check for buy signal
                if signals.iloc[i]['buy_final'] and self.current_position is None:
                    entry_price = row['close']
                    
                    # Calculate SL/TP from entry price (TradingView style)
                    atr_sl_mult = signals.iloc[i].get('atr_sl_mult', 0.02)  # Default 2%
                    atr_rr = signals.iloc[i].get('atr_rr', 0.01)  # Default 1%
                    
                    # Convert percentage to price
                    if atr_sl_mult < 1.0:  # If it's a percentage (0.004 = 0.4%)
                        sl = entry_price * (1 - atr_sl_mult)  # Long: entry - 0.4%
                        tp = entry_price * (1 + atr_rr)       # Long: entry + 0.4%
                    else:  # If it's ATR multiplier (2.0 = 2x ATR)
                        atr = signals.iloc[i].get('atr', 0.01)
                        sl = entry_price - (atr * atr_sl_mult)  # ATR based
                        tp = entry_price + (atr * atr_rr)       # ATR based
                    
                    # Get trailing TP if available
                    trailing_tp = signals.iloc[i].get('trailing_tp')
                    
                    self.open_position(
                        timestamp=timestamp,
                        price=entry_price,
                        side='long',
                        stop_loss=sl,
                        take_profit=tp,
                        trailing_tp=trailing_tp
                    )
                
                # Check for sell signal
                elif signals.iloc[i]['sell_final'] and self.current_position is None:
                    entry_price = row['close']
                    
                    # Calculate SL/TP from entry price (TradingView style)
                    atr_sl_mult = signals.iloc[i].get('atr_sl_mult', 0.02)  # Default 2%
                    atr_rr = signals.iloc[i].get('atr_rr', 0.01)  # Default 1%
                    
                    # Convert percentage to price
                    if atr_sl_mult < 1.0:  # If it's a percentage (0.004 = 0.4%)
                        sl = entry_price * (1 + atr_sl_mult)  # Short: entry + 0.4%
                        tp = entry_price * (1 - atr_rr)       # Short: entry - 0.4%
                    else:  # If it's ATR multiplier (2.0 = 2x ATR)
                        atr = signals.iloc[i].get('atr', 0.01)
                        sl = entry_price + (atr * atr_sl_mult)  # ATR based
                        tp = entry_price - (atr * atr_rr)       # ATR based
                    
                    # Get trailing TP if available
                    trailing_tp = signals.iloc[i].get('trailing_tp')
                    
                    self.open_position(
                        timestamp=timestamp,
                        price=entry_price,
                        side='short',
                        stop_loss=sl,
                        take_profit=tp,
                        trailing_tp=trailing_tp
                    )
                
                # Update TP for existing position (trailing TP only, SL stays fixed)
                elif self.current_position is not None:
                    # Update trailing TP if available (SL stays fixed)
                    trailing_tp = signals.iloc[i].get('trailing_tp')
                    
                    if trailing_tp is not None:
                        self.current_position.take_profit = trailing_tp
            
            # Calculate current equity
            current_equity = self.current_capital
            
            if self.current_position is not None:
                # Add unrealized PnL
                trade = self.current_position
                if trade.side == 'long':
                    unrealized_pnl = (row['close'] - trade.entry_price) * trade.quantity
                else:
                    unrealized_pnl = (trade.entry_price - row['close']) * trade.quantity
                
                current_equity += unrealized_pnl
            
            self.equity_curve.append(current_equity)
        
        # Close any remaining position at the end
        if self.current_position is not None:
            last_timestamp = data.index[-1]
            last_close = data.iloc[-1]['close']
            self.close_position(last_timestamp, last_close, 'end')
        
        # Create equity curve series
        equity_series = pd.Series(self.equity_curve, index=data.index)
        
        # Calculate metrics
        metrics = self.calculate_metrics(equity_series)
        
        logger.info(f"Backtest completed. {len(self.trades)} trades executed.")
        
        return BacktestResult(
            trades=self.trades,
            equity_curve=equity_series,
            metrics=metrics,
            parameters={},  # Will be filled by caller
            symbol="",  # Will be filled by caller
            timeframe="",  # Will be filled by caller
            start_date=data.index[0],
            end_date=data.index[-1]
        )
    
    def calculate_metrics(self, equity_curve: pd.Series) -> Dict[str, float]:
        """
        Calculate backtest metrics.
        
        Args:
            equity_curve: Equity curve series
            
        Returns:
            Dictionary of metrics
        """
        if len(equity_curve) == 0:
            return {}
        
        # Basic metrics
        total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0] * 100
        
        # Drawdown calculation
        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak * 100
        max_drawdown = drawdown.min()
        
        # Trade metrics
        if self.trades:
            winning_trades = [t for t in self.trades if t.pnl > 0]
            losing_trades = [t for t in self.trades if t.pnl < 0]
            
            win_rate = len(winning_trades) / len(self.trades) * 100 if self.trades else 0
            
            total_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
            total_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0
            
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
            
            avg_win = total_profit / len(winning_trades) if winning_trades else 0
            avg_loss = total_loss / len(losing_trades) if losing_trades else 0
            
            expectancy = (avg_win * len(winning_trades) - avg_loss * len(losing_trades)) / len(self.trades) if self.trades else 0
            
            # Sharpe ratio (simplified)
            returns = equity_curve.pct_change().dropna()
            sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
            
            # MAR ratio
            mar = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # Exposure
            total_days = (equity_curve.index[-1] - equity_curve.index[0]).days
            exposure_days = sum((t.exit_time - t.entry_time).days for t in self.trades if t.exit_time)
            exposure = exposure_days / total_days * 100 if total_days > 0 else 0
            
        else:
            win_rate = 0
            profit_factor = 0
            expectancy = 0
            sharpe = 0
            mar = 0
            exposure = 0
        
        return {
            'total_return_pct': total_return,
            'max_drawdown_pct': max_drawdown,
            'profit_factor': profit_factor,
            'win_rate_pct': win_rate,
            'num_trades': len(self.trades),
            'expectancy': expectancy,
            'sharpe_ratio': sharpe,
            'mar_ratio': mar,
            'exposure_pct': exposure,
            'final_capital': equity_curve.iloc[-1],
        }


def run_backtest(data: pd.DataFrame, signals: pd.DataFrame, 
                initial_capital: float = 10000.0, fee_bps: float = 5.0,
                slippage_bps: float = 5.0) -> BacktestResult:
    """
    Convenience function to run backtest.
    
    Args:
        data: OHLCV data
        signals: DataFrame with signals
        initial_capital: Initial capital
        fee_bps: Fee in basis points
        slippage_bps: Slippage in basis points
        
    Returns:
        BacktestResult object
    """
    backtester = Backtester(initial_capital, fee_bps, slippage_bps)
    return backtester.run_backtest(data, signals)
