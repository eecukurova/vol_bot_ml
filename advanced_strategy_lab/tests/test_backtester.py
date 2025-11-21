"""
Tests for backtesting engine functionality.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategy_optimizer.strategy.backtester import (
    Backtester,
    run_backtest,
    Trade,
    BacktestResult,
)


class TestBacktester:
    """Test cases for Backtester class."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
        
        # Create realistic price data
        np.random.seed(42)
        base_price = 100
        trend = np.linspace(0, 10, 100)
        noise = np.random.normal(0, 1, 100)
        close_prices = base_price + trend + noise
        
        high_prices = close_prices + np.random.uniform(0, 2, 100)
        low_prices = close_prices - np.random.uniform(0, 2, 100)
        open_prices = np.roll(close_prices, 1)
        open_prices[0] = close_prices[0]
        
        volumes = np.random.uniform(1000, 10000, 100)
        
        data = pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': volumes
        }, index=dates)
        
        return data
    
    @pytest.fixture
    def sample_signals(self, sample_data):
        """Create sample signals for testing."""
        signals = pd.DataFrame(index=sample_data.index)
        signals['buy_final'] = False
        signals['sell_final'] = False
        signals['stop_loss'] = np.nan
        signals['take_profit'] = np.nan
        
        # Add some test signals
        signals.iloc[10, signals.columns.get_loc('buy_final')] = True
        signals.iloc[10, signals.columns.get_loc('stop_loss')] = sample_data.iloc[10]['close'] - 5
        signals.iloc[10, signals.columns.get_loc('take_profit')] = sample_data.iloc[10]['close'] + 10
        
        signals.iloc[30, signals.columns.get_loc('sell_final')] = True
        signals.iloc[30, signals.columns.get_loc('stop_loss')] = sample_data.iloc[30]['close'] + 5
        signals.iloc[30, signals.columns.get_loc('take_profit')] = sample_data.iloc[30]['close'] - 10
        
        return signals
    
    @pytest.fixture
    def backtester(self):
        """Create backtester instance for testing."""
        return Backtester(initial_capital=10000.0, fee_bps=5.0, slippage_bps=5.0)
    
    def test_backtester_initialization(self):
        """Test backtester initialization."""
        backtester = Backtester(initial_capital=10000.0, fee_bps=10.0, slippage_bps=5.0)
        
        assert backtester.initial_capital == 10000.0
        assert backtester.fee_bps == 0.001  # 10 bps = 0.001
        assert backtester.slippage_bps == 0.0005  # 5 bps = 0.0005
        assert backtester.current_capital == 10000.0
        assert backtester.current_position is None
        assert len(backtester.trades) == 0
    
    def test_calculate_position_size(self, backtester):
        """Test position size calculation."""
        price = 100.0
        stop_loss = 95.0
        
        position_size = backtester.calculate_position_size(price, stop_loss)
        
        # Should calculate based on 2% risk
        expected_risk = backtester.current_capital * 0.02
        expected_position_size = expected_risk / (price - stop_loss)
        
        assert position_size > 0
        assert abs(position_size - expected_position_size) < 0.01
    
    def test_apply_slippage(self, backtester):
        """Test slippage application."""
        price = 100.0
        
        buy_price = backtester.apply_slippage(price, 'buy')
        sell_price = backtester.apply_slippage(price, 'sell')
        
        # Buy price should be higher (worse for buyer)
        assert buy_price > price
        
        # Sell price should be lower (worse for seller)
        assert sell_price < price
        
        # Slippage should be symmetric
        slippage_amount = price * backtester.slippage_bps
        assert abs(buy_price - price - slippage_amount) < 0.01
        assert abs(price - sell_price - slippage_amount) < 0.01
    
    def test_calculate_commission(self, backtester):
        """Test commission calculation."""
        price = 100.0
        quantity = 10.0
        
        commission = backtester.calculate_commission(price, quantity)
        
        expected_commission = price * quantity * backtester.fee_bps
        assert commission == expected_commission
        assert commission > 0
    
    def test_open_position(self, backtester):
        """Test position opening."""
        timestamp = datetime.now()
        price = 100.0
        side = 'long'
        stop_loss = 95.0
        take_profit = 110.0
        
        trade = backtester.open_position(timestamp, price, side, stop_loss, take_profit)
        
        assert trade is not None
        assert trade.entry_time == timestamp
        assert trade.side == side
        assert trade.stop_loss == stop_loss
        assert trade.take_profit == take_profit
        assert trade.exit_time is None
        assert trade.exit_price is None
        assert trade.pnl is None
        
        # Check that position is opened
        assert backtester.current_position == trade
        assert backtester.current_capital < backtester.initial_capital
    
    def test_close_position(self, backtester):
        """Test position closing."""
        # First open a position
        timestamp = datetime.now()
        price = 100.0
        side = 'long'
        stop_loss = 95.0
        take_profit = 110.0
        
        trade = backtester.open_position(timestamp, price, side, stop_loss, take_profit)
        
        # Close the position
        exit_timestamp = timestamp + timedelta(hours=1)
        exit_price = 105.0
        reason = 'test'
        
        closed_trade = backtester.close_position(exit_timestamp, exit_price, reason)
        
        assert closed_trade == trade
        assert trade.exit_time == exit_timestamp
        assert trade.exit_price == exit_price
        assert trade.exit_reason == reason
        assert trade.pnl is not None
        
        # Check PnL calculation for long position
        expected_pnl = (exit_price - trade.entry_price) * trade.quantity
        assert abs(trade.pnl - expected_pnl) < 0.01
        
        # Check that position is closed
        assert backtester.current_position is None
        assert trade in backtester.trades
    
    def test_check_stop_loss_take_profit(self, backtester):
        """Test SL/TP checking."""
        # Open a long position
        timestamp = datetime.now()
        price = 100.0
        side = 'long'
        stop_loss = 95.0
        take_profit = 110.0
        
        backtester.open_position(timestamp, price, side, stop_loss, take_profit)
        
        # Test take profit trigger
        exit_reason = backtester.check_stop_loss_take_profit(
            timestamp + timedelta(minutes=30), 115.0, 110.0, 112.0
        )
        assert exit_reason == 'tp'
        assert backtester.current_position is None
        
        # Reopen position for SL test
        backtester.open_position(timestamp, price, side, stop_loss, take_profit)
        
        # Test stop loss trigger
        exit_reason = backtester.check_stop_loss_take_profit(
            timestamp + timedelta(minutes=30), 98.0, 92.0, 94.0
        )
        assert exit_reason == 'sl'
        assert backtester.current_position is None
    
    def test_run_backtest(self, sample_data, sample_signals, backtester):
        """Test complete backtest run."""
        result = backtester.run_backtest(sample_data, sample_signals)
        
        assert isinstance(result, BacktestResult)
        assert len(result.trades) >= 0
        assert len(result.equity_curve) == len(sample_data)
        assert 'total_return_pct' in result.metrics
        assert 'max_drawdown_pct' in result.metrics
        assert 'profit_factor' in result.metrics
        assert 'num_trades' in result.metrics
        
        # Check equity curve
        assert result.equity_curve.iloc[0] == backtester.initial_capital
        assert result.equity_curve.iloc[-1] >= 0  # Should not go negative
    
    def test_calculate_metrics(self, backtester):
        """Test metrics calculation."""
        # Create sample equity curve
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
        equity_values = np.linspace(10000, 12000, 100)  # 20% return
        equity_curve = pd.Series(equity_values, index=dates)
        
        # Create sample trades
        trades = [
            Trade(
                entry_time=dates[10],
                exit_time=dates[20],
                entry_price=100.0,
                exit_price=110.0,
                side='long',
                quantity=10.0,
                stop_loss=95.0,
                take_profit=110.0,
                pnl=100.0,
                commission=5.0,
                slippage=2.0,
                exit_reason='tp'
            ),
            Trade(
                entry_time=dates[30],
                exit_time=dates[40],
                entry_price=110.0,
                exit_price=105.0,
                side='long',
                quantity=10.0,
                stop_loss=105.0,
                take_profit=115.0,
                pnl=-50.0,
                commission=5.0,
                slippage=2.0,
                exit_reason='sl'
            )
        ]
        
        metrics = backtester.calculate_metrics(equity_curve)
        
        # Check basic metrics
        assert 'total_return_pct' in metrics
        assert 'max_drawdown_pct' in metrics
        assert 'volatility_pct' in metrics
        assert 'sharpe_ratio' in metrics
        
        # Check trade metrics
        assert 'num_trades' in metrics
        assert 'win_rate_pct' in metrics
        assert 'profit_factor' in metrics
        assert 'expectancy' in metrics
        
        # Verify calculations
        assert metrics['num_trades'] == 2
        assert metrics['win_rate_pct'] == 50.0  # 1 win out of 2 trades
        assert metrics['total_return_pct'] == 20.0  # 20% return


class TestTradeClass:
    """Test cases for Trade dataclass."""
    
    def test_trade_creation(self):
        """Test trade object creation."""
        timestamp = datetime.now()
        
        trade = Trade(
            entry_time=timestamp,
            exit_time=None,
            entry_price=100.0,
            exit_price=None,
            side='long',
            quantity=10.0,
            stop_loss=95.0,
            take_profit=110.0
        )
        
        assert trade.entry_time == timestamp
        assert trade.exit_time is None
        assert trade.entry_price == 100.0
        assert trade.exit_price is None
        assert trade.side == 'long'
        assert trade.quantity == 10.0
        assert trade.stop_loss == 95.0
        assert trade.take_profit == 110.0
        assert trade.pnl is None
        assert trade.commission is None
        assert trade.slippage is None
        assert trade.exit_reason is None


class TestConvenienceFunction:
    """Test cases for convenience functions."""
    
    def test_run_backtest_function(self):
        """Test run_backtest convenience function."""
        # Create sample data
        dates = pd.date_range(start='2023-01-01', periods=50, freq='1H')
        data = pd.DataFrame({
            'open': np.random.uniform(95, 105, 50),
            'high': np.random.uniform(100, 110, 50),
            'low': np.random.uniform(90, 100, 50),
            'close': np.random.uniform(95, 105, 50),
            'volume': np.random.uniform(1000, 10000, 50)
        }, index=dates)
        
        # Create sample signals
        signals = pd.DataFrame(index=dates)
        signals['buy_final'] = False
        signals['sell_final'] = False
        signals['stop_loss'] = np.nan
        signals['take_profit'] = np.nan
        
        # Add one signal
        signals.iloc[10, signals.columns.get_loc('buy_final')] = True
        signals.iloc[10, signals.columns.get_loc('stop_loss')] = data.iloc[10]['close'] - 5
        signals.iloc[10, signals.columns.get_loc('take_profit')] = data.iloc[10]['close'] + 10
        
        # Run backtest
        result = run_backtest(data, signals, initial_capital=10000.0)
        
        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == len(data)
        assert result.metrics['num_trades'] >= 0


if __name__ == "__main__":
    pytest.main([__file__])
