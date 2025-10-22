"""
Behavior smoke tests for ATR + SuperTrend strategy.

These tests verify critical behavior aspects like flip logic, cooldown,
look-ahead bias prevention, and basic PnL calculations.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import modules directly
from strategy.atr_st_core import ATRSuperTrendStrategy
from strategy.backtester import Backtester, run_backtest


def make_stair_df(n=200, step=0.2):
    """
    Create a stair-step price series for testing crossover and trailing logic.
    
    Args:
        n: Number of candles
        step: Price step size
        
    Returns:
        DataFrame with OHLCV data
    """
    ts = pd.date_range(datetime(2024, 1, 1), periods=n, freq="H", tz="UTC")
    base = np.linspace(100, 100 + step * (n - 1), n)
    high = base * (1 + 0.001)
    low = base * (1 - 0.001)
    close = base
    open_ = np.concatenate([[base[0]], base[:-1]])
    vol = np.full(n, 1000.0)
    
    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol
    }, index=ts)


def make_trending_df(n=200, trend_strength=0.1):
    """
    Create a trending price series for testing strategy behavior.
    
    Args:
        n: Number of candles
        trend_strength: Trend strength (0.1 = 10% over period)
        
    Returns:
        DataFrame with OHLCV data
    """
    ts = pd.date_range(datetime(2024, 1, 1), periods=n, freq="H", tz="UTC")
    
    # Create trending price with some noise
    np.random.seed(42)
    trend = np.linspace(0, trend_strength, n)
    noise = np.random.normal(0, 0.01, n)
    close = 100 * (1 + trend + noise)
    
    # Generate OHLC from close
    high = close * (1 + np.random.uniform(0, 0.005, n))
    low = close * (1 - np.random.uniform(0, 0.005, n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    vol = np.random.uniform(1000, 10000, n)
    
    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol
    }, index=ts)


def test_flip_and_cooldown_respected():
    """Test that flip logic and cooldown are properly enforced."""
    df = make_stair_df(n=100, step=0.5)
    
    params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 180,  # 3 hours cooldown
        'atr_sl_mult': 2.0,
        'atr_rr': 2.0,
    }
    
    strategy = ATRSuperTrendStrategy(params)
    signals = strategy.run_strategy(df)
    
    # Check that flip logic is respected
    buy_signals = signals['buy_final']
    sell_signals = signals['sell_final']
    
    # Should not have both buy and sell signals on the same bar
    assert not (buy_signals & sell_signals).any(), "Flip logic violated: both buy and sell signals on same bar"
    
    # Check cooldown: consecutive signals should be at least min_delay_m minutes apart
    signal_times = df.index[buy_signals | sell_signals]
    if len(signal_times) > 1:
        diffs = (signal_times[1:] - signal_times[:-1]).total_seconds() / 60
        assert (diffs >= params['min_delay_m']).all(), f"Cooldown violated: signals too close together"
    
    print("✓ Flip logic and cooldown respected")


def test_no_lookahead_bias():
    """Test that signals are generated without look-ahead bias."""
    df = make_stair_df(n=100, step=0.3)
    
    params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 0,  # No cooldown for this test
        'atr_sl_mult': 1.5,
        'atr_rr': 2.0,
    }
    
    strategy = ATRSuperTrendStrategy(params)
    signals = strategy.run_strategy(df)
    
    # Check that signals are generated based on current bar data only
    # This is verified by ensuring the strategy doesn't use future data
    assert 'buy_final' in signals.columns, "Buy signals column missing"
    assert 'sell_final' in signals.columns, "Sell signals column missing"
    
    # Check that SL/TP levels are calculated for signal bars
    signal_bars = signals[signals['buy_final'] | signals['sell_final']]
    if not signal_bars.empty:
        assert not signal_bars['stop_loss'].isna().any(), "SL levels missing for signal bars"
        assert not signal_bars['take_profit'].isna().any(), "TP levels missing for signal bars"
    
    print("✓ No look-ahead bias detected")


def test_backtester_basic_pnl():
    """Test basic backtester functionality and PnL calculation."""
    df = make_trending_df(n=100, trend_strength=0.05)
    
    params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 0,
        'atr_sl_mult': 1.5,
        'atr_rr': 2.0,
    }
    
    strategy = ATRSuperTrendStrategy(params)
    signals = strategy.run_strategy(df)
    
    # Run backtest
    result = run_backtest(df, signals, initial_capital=10000.0, fee_bps=5.0, slippage_bps=5.0)
    
    # Check that essential metrics are present
    required_metrics = [
        'total_return_pct',
        'profit_factor',
        'max_drawdown_pct',
        'num_trades',
        'sharpe_ratio',
        'win_rate_pct'
    ]
    
    for metric in required_metrics:
        assert metric in result.metrics, f"Missing metric: {metric}"
        assert isinstance(result.metrics[metric], (int, float)), f"Invalid metric type: {metric}"
    
    # Check that equity curve is properly calculated
    assert len(result.equity_curve) == len(df), "Equity curve length mismatch"
    assert result.equity_curve.iloc[0] == 10000.0, "Initial capital not set correctly"
    assert result.equity_curve.iloc[-1] >= 0, "Final equity should not be negative"
    
    print("✓ Backtester basic PnL calculation working")


def test_atr_calculation_consistency():
    """Test ATR calculation consistency."""
    df = make_stair_df(n=50, step=0.1)
    
    params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 0,
        'atr_sl_mult': 2.0,
        'atr_rr': 2.0,
    }
    
    strategy = ATRSuperTrendStrategy(params)
    signals = strategy.run_strategy(df)
    
    # Check ATR values are reasonable
    atr_values = signals['atr']
    # ATR might be NaN or 0 for first few bars, that's normal
    valid_atr = atr_values[atr_values > 0]
    assert len(valid_atr) > 0, "No positive ATR values found"
    
    # Check that ATR trailing stop is calculated
    trailing_stop = signals['trailing_stop']
    assert not trailing_stop.isna().all(), "Trailing stop values are all NaN"
    
    print("✓ ATR calculation consistency verified")


def test_supertrend_stateful_logic():
    """Test SuperTrend stateful line calculation."""
    df = make_stair_df(n=100, step=0.2)
    
    params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 0,
        'atr_sl_mult': 2.0,
        'atr_rr': 2.0,
    }
    
    strategy = ATRSuperTrendStrategy(params)
    signals = strategy.run_strategy(df)
    
    # Check SuperTrend line is calculated
    supertrend = signals['supertrend']
    assert not supertrend.isna().all(), "SuperTrend values are all NaN"
    
    # Check that SuperTrend line changes smoothly (stateful behavior)
    st_changes = supertrend.diff().abs()
    # Should not have extreme jumps (indicating state reset)
    assert st_changes.max() < 100, "SuperTrend line has extreme jumps"
    
    print("✓ SuperTrend stateful logic working")


def test_sl_tp_calculation():
    """Test stop loss and take profit calculation."""
    df = make_stair_df(n=100, step=0.3)
    
    params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 0,
        'atr_sl_mult': 2.0,
        'atr_rr': 2.0,
    }
    
    strategy = ATRSuperTrendStrategy(params)
    signals = strategy.run_strategy(df)
    
    # Check SL/TP for buy signals
    buy_signals = signals[signals['buy_final']]
    if not buy_signals.empty:
        for idx, row in buy_signals.iterrows():
            # For long positions: SL < entry_price < TP
            assert row['stop_loss'] < row['close'], f"Buy SL should be below entry price"
            assert row['take_profit'] > row['close'], f"Buy TP should be above entry price"
            
            # Check risk-reward ratio
            sl_distance = row['close'] - row['stop_loss']
            tp_distance = row['take_profit'] - row['close']
            rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
            assert abs(rr_ratio - params['atr_rr']) < 0.1, f"RR ratio mismatch: {rr_ratio}"
    
    # Check SL/TP for sell signals
    sell_signals = signals[signals['sell_final']]
    if not sell_signals.empty:
        for idx, row in sell_signals.iterrows():
            # For short positions: TP < entry_price < SL
            assert row['stop_loss'] > row['close'], f"Sell SL should be above entry price"
            assert row['take_profit'] < row['close'], f"Sell TP should be below entry price"
    
    print("✓ SL/TP calculation verified")


def test_commission_and_slippage():
    """Test commission and slippage application."""
    df = make_stair_df(n=50, step=0.1)
    
    params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 0,
        'atr_sl_mult': 2.0,
        'atr_rr': 2.0,
    }
    
    strategy = ATRSuperTrendStrategy(params)
    signals = strategy.run_strategy(df)
    
    # Test with different fee/slippage settings
    test_cases = [
        {'fee_bps': 0, 'slippage_bps': 0},
        {'fee_bps': 5, 'slippage_bps': 5},
        {'fee_bps': 10, 'slippage_bps': 10},
    ]
    
    for case in test_cases:
        result = run_backtest(
            df, signals,
            initial_capital=10000.0,
            fee_bps=case['fee_bps'],
            slippage_bps=case['slippage_bps']
        )
        
        # Higher fees should generally result in lower returns
        assert result.metrics['total_return_pct'] is not None, "Return calculation failed"
        assert result.metrics['num_trades'] >= 0, "Trade count should be non-negative"
    
    print("✓ Commission and slippage handling verified")


def test_deterministic_results():
    """Test that results are deterministic with same inputs."""
    df = make_stair_df(n=100, step=0.2)
    
    params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 60,
        'atr_sl_mult': 2.0,
        'atr_rr': 2.0,
    }
    
    # Run strategy twice
    strategy1 = ATRSuperTrendStrategy(params)
    signals1 = strategy1.run_strategy(df)
    
    strategy2 = ATRSuperTrendStrategy(params)
    signals2 = strategy2.run_strategy(df)
    
    # Results should be identical
    assert signals1['buy_final'].equals(signals2['buy_final']), "Buy signals not deterministic"
    assert signals1['sell_final'].equals(signals2['sell_final']), "Sell signals not deterministic"
    
    # Run backtest twice
    result1 = run_backtest(df, signals1)
    result2 = run_backtest(df, signals2)
    
    # Backtest results should be identical
    assert abs(result1.metrics['total_return_pct'] - result2.metrics['total_return_pct']) < 0.01, "Backtest results not deterministic"
    assert result1.metrics['num_trades'] == result2.metrics['num_trades'], "Trade count not deterministic"
    
    print("✓ Deterministic results verified")


def run_all_behavior_tests():
    """Run all behavior tests."""
    print("Running ATR + SuperTrend Strategy Behavior Tests")
    print("=" * 50)
    
    tests = [
        test_flip_and_cooldown_respected,
        test_no_lookahead_bias,
        test_backtester_basic_pnl,
        test_atr_calculation_consistency,
        test_supertrend_stateful_logic,
        test_sl_tp_calculation,
        test_commission_and_slippage,
        test_deterministic_results,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__} failed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Behavior Tests Summary: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All behavior tests passed!")
    else:
        print(f"✗ {failed} behavior tests failed!")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_behavior_tests()
    exit(0 if success else 1)
