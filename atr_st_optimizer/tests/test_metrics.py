"""
Tests for metrics calculation functionality.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from atr_st_optimizer.optimize.metrics import (
    calculate_basic_metrics,
    calculate_trade_metrics,
    calculate_risk_metrics,
    calculate_advanced_metrics,
    calculate_all_metrics,
    rank_results,
    calculate_portfolio_metrics,
    filter_results_by_metrics,
    get_metric_summary,
)
from atr_st_optimizer.strategy.backtester import Trade


class TestBasicMetrics:
    """Test cases for basic metrics calculation."""
    
    @pytest.fixture
    def sample_equity_curve(self):
        """Create sample equity curve."""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
        # Create equity curve with 20% total return
        equity_values = np.linspace(10000, 12000, 100)
        return pd.Series(equity_values, index=dates)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trades."""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
        
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
        
        return trades
    
    def test_calculate_basic_metrics(self, sample_equity_curve, sample_trades):
        """Test basic metrics calculation."""
        metrics = calculate_basic_metrics(sample_equity_curve, sample_trades)
        
        # Check required metrics are present
        required_metrics = [
            'total_return_pct',
            'max_drawdown_pct',
            'volatility_pct',
            'sharpe_ratio',
            'sortino_ratio',
            'calmar_ratio',
            'mar_ratio'
        ]
        
        for metric in required_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
        
        # Check total return calculation
        expected_return = (sample_equity_curve.iloc[-1] - sample_equity_curve.iloc[0]) / sample_equity_curve.iloc[0] * 100
        assert abs(metrics['total_return_pct'] - expected_return) < 0.01
        
        # Check that volatility is positive
        assert metrics['volatility_pct'] >= 0
    
    def test_calculate_basic_metrics_empty_data(self):
        """Test basic metrics with empty data."""
        empty_series = pd.Series(dtype=float)
        metrics = calculate_basic_metrics(empty_series, [])
        
        assert metrics == {}
    
    def test_calculate_trade_metrics(self, sample_trades):
        """Test trade metrics calculation."""
        metrics = calculate_trade_metrics(sample_trades)
        
        # Check required metrics are present
        required_metrics = [
            'num_trades',
            'win_rate_pct',
            'profit_factor',
            'expectancy',
            'avg_win',
            'avg_loss',
            'largest_win',
            'largest_loss',
            'avg_trade',
            'avg_trade_duration'
        ]
        
        for metric in required_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
        
        # Check specific calculations
        assert metrics['num_trades'] == 2
        assert metrics['win_rate_pct'] == 50.0  # 1 win out of 2 trades
        
        # Profit factor should be > 1 (100 profit / 50 loss = 2)
        assert metrics['profit_factor'] == 2.0
        
        # Expectancy should be positive (100 - 50) / 2 = 25
        assert metrics['expectancy'] == 25.0
    
    def test_calculate_trade_metrics_empty_trades(self):
        """Test trade metrics with no trades."""
        metrics = calculate_trade_metrics([])
        
        assert metrics['num_trades'] == 0
        assert metrics['win_rate_pct'] == 0
        assert metrics['profit_factor'] == 0
        assert metrics['expectancy'] == 0
    
    def test_calculate_risk_metrics(self, sample_equity_curve, sample_trades):
        """Test risk metrics calculation."""
        metrics = calculate_risk_metrics(sample_equity_curve, sample_trades)
        
        # Check required metrics are present
        required_metrics = [
            'var_95_pct',
            'cvar_95_pct',
            'max_consecutive_losses',
            'avg_recovery_period',
            'exposure_pct'
        ]
        
        for metric in required_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
        
        # VaR should be negative (worst case scenario)
        assert metrics['var_95_pct'] <= 0
        
        # CVaR should be worse than VaR
        assert metrics['cvar_95_pct'] <= metrics['var_95_pct']
    
    def test_calculate_advanced_metrics(self, sample_equity_curve, sample_trades):
        """Test advanced metrics calculation."""
        metrics = calculate_advanced_metrics(sample_equity_curve, sample_trades)
        
        # Check required metrics are present
        required_metrics = [
            'skewness',
            'kurtosis',
            'information_ratio',
            'omega_ratio',
            'sterling_ratio',
            'burke_ratio',
            'kappa_ratio'
        ]
        
        for metric in required_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
    
    def test_calculate_all_metrics(self, sample_equity_curve, sample_trades):
        """Test calculation of all metrics."""
        metrics = calculate_all_metrics(sample_equity_curve, sample_trades)
        
        # Should contain metrics from all categories
        basic_metrics = ['total_return_pct', 'max_drawdown_pct', 'volatility_pct', 'sharpe_ratio']
        trade_metrics = ['num_trades', 'win_rate_pct', 'profit_factor', 'expectancy']
        risk_metrics = ['var_95_pct', 'cvar_95_pct', 'max_consecutive_losses']
        advanced_metrics = ['skewness', 'kurtosis', 'information_ratio']
        
        all_required = basic_metrics + trade_metrics + risk_metrics + advanced_metrics
        
        for metric in all_required:
            assert metric in metrics


class TestResultsRanking:
    """Test cases for results ranking and filtering."""
    
    @pytest.fixture
    def sample_results(self):
        """Create sample optimization results."""
        return [
            {
                'symbol': 'BTC/USDT',
                'timeframe': '1h',
                'metrics': {
                    'profit_factor': 2.5,
                    'total_return_pct': 15.0,
                    'max_drawdown_pct': -5.0,
                    'sharpe_ratio': 1.8
                }
            },
            {
                'symbol': 'ETH/USDT',
                'timeframe': '4h',
                'metrics': {
                    'profit_factor': 1.8,
                    'total_return_pct': 12.0,
                    'max_drawdown_pct': -8.0,
                    'sharpe_ratio': 1.2
                }
            },
            {
                'symbol': 'SOL/USDT',
                'timeframe': '1h',
                'metrics': {
                    'profit_factor': 3.0,
                    'total_return_pct': 20.0,
                    'max_drawdown_pct': -10.0,
                    'sharpe_ratio': 2.0
                }
            }
        ]
    
    def test_rank_results(self, sample_results):
        """Test results ranking."""
        ranked = rank_results(sample_results, 'profit_factor')
        
        # Should be sorted by profit factor (descending)
        assert ranked[0]['metrics']['profit_factor'] == 3.0  # SOL/USDT
        assert ranked[1]['metrics']['profit_factor'] == 2.5  # BTC/USDT
        assert ranked[2]['metrics']['profit_factor'] == 1.8  # ETH/USDT
        
        # Should have rank field
        assert ranked[0]['rank'] == 1
        assert ranked[1]['rank'] == 2
        assert ranked[2]['rank'] == 3
    
    def test_rank_results_ascending(self, sample_results):
        """Test results ranking in ascending order."""
        ranked = rank_results(sample_results, 'profit_factor', ascending=True)
        
        # Should be sorted by profit factor (ascending)
        assert ranked[0]['metrics']['profit_factor'] == 1.8  # ETH/USDT
        assert ranked[1]['metrics']['profit_factor'] == 2.5  # BTC/USDT
        assert ranked[2]['metrics']['profit_factor'] == 3.0  # SOL/USDT
    
    def test_rank_results_empty(self):
        """Test ranking with empty results."""
        ranked = rank_results([], 'profit_factor')
        assert ranked == []
    
    def test_rank_results_missing_metric(self, sample_results):
        """Test ranking with missing metric."""
        # Add result without the metric
        sample_results.append({
            'symbol': 'ADA/USDT',
            'timeframe': '1h',
            'metrics': {
                'total_return_pct': 10.0,
                # Missing profit_factor
            }
        })
        
        ranked = rank_results(sample_results, 'profit_factor')
        
        # Should only include results with the metric
        assert len(ranked) == 3  # Original 3 results
        assert all('profit_factor' in r['metrics'] for r in ranked)
    
    def test_calculate_portfolio_metrics(self, sample_results):
        """Test portfolio metrics calculation."""
        metrics = calculate_portfolio_metrics(sample_results)
        
        # Check required metrics
        required_metrics = [
            'num_strategies',
            'avg_return_pct',
            'median_return_pct',
            'std_return_pct',
            'avg_profit_factor',
            'median_profit_factor',
            'total_trades',
            'consistency_pct'
        ]
        
        for metric in required_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
        
        # Check specific calculations
        assert metrics['num_strategies'] == 3
        assert metrics['avg_return_pct'] == (15.0 + 12.0 + 20.0) / 3
        assert metrics['avg_profit_factor'] == (2.5 + 1.8 + 3.0) / 3
    
    def test_filter_results_by_metrics(self, sample_results):
        """Test results filtering by metrics."""
        # Filter by profit factor > 2.0
        filtered = filter_results_by_metrics(sample_results, {
            'profit_factor': (2.0, float('inf'))
        })
        
        assert len(filtered) == 2  # BTC/USDT and SOL/USDT
        assert all(r['metrics']['profit_factor'] > 2.0 for r in filtered)
        
        # Filter by multiple metrics
        filtered = filter_results_by_metrics(sample_results, {
            'profit_factor': (2.0, float('inf')),
            'total_return_pct': (10.0, float('inf'))
        })
        
        assert len(filtered) == 2  # BTC/USDT and SOL/USDT
        
        # Filter by max drawdown
        filtered = filter_results_by_metrics(sample_results, {
            'max_drawdown_pct': (-10.0, -5.0)
        })
        
        assert len(filtered) == 1  # Only ETH/USDT
    
    def test_get_metric_summary(self, sample_results):
        """Test metric summary calculation."""
        summary = get_metric_summary(sample_results, 'profit_factor')
        
        # Check summary structure
        required_fields = ['count', 'mean', 'median', 'std', 'min', 'max', 'q25', 'q75']
        for field in required_fields:
            assert field in summary
            assert isinstance(summary[field], (int, float))
        
        # Check calculations
        assert summary['count'] == 3
        assert summary['mean'] == (2.5 + 1.8 + 3.0) / 3
        assert summary['min'] == 1.8
        assert summary['max'] == 3.0
    
    def test_get_metric_summary_empty(self):
        """Test metric summary with empty results."""
        summary = get_metric_summary([], 'profit_factor')
        assert summary == {}
    
    def test_get_metric_summary_missing_metric(self, sample_results):
        """Test metric summary with missing metric."""
        # Add result without the metric
        sample_results.append({
            'symbol': 'ADA/USDT',
            'timeframe': '1h',
            'metrics': {
                'total_return_pct': 10.0,
                # Missing profit_factor
            }
        })
        
        summary = get_metric_summary(sample_results, 'profit_factor')
        
        # Should only include results with the metric
        assert summary['count'] == 3  # Original 3 results


if __name__ == "__main__":
    pytest.main([__file__])
