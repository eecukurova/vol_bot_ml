"""
Metrics calculation module for backtesting results.

This module provides comprehensive metrics calculation and ranking functions
for strategy optimization results.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from scipy import stats

logger = logging.getLogger(__name__)


def calculate_basic_metrics(equity_curve: pd.Series, trades: List[Any]) -> Dict[str, float]:
    """
    Calculate basic performance metrics.
    
    Args:
        equity_curve: Equity curve series
        trades: List of trade objects
        
    Returns:
        Dictionary of basic metrics
    """
    if len(equity_curve) == 0:
        return {}
    
    # Total return
    total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0] * 100
    
    # Drawdown calculation
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak * 100
    max_drawdown = drawdown.min()
    
    # Volatility (annualized)
    returns = equity_curve.pct_change().dropna()
    volatility = returns.std() * np.sqrt(252) * 100 if len(returns) > 1 else 0
    
    # Sharpe ratio (annualized)
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    
    # Sortino ratio
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
    sortino = returns.mean() / downside_std * np.sqrt(252) if downside_std > 0 else 0
    
    # Calmar ratio
    calmar = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
    
    # MAR ratio (same as Calmar)
    mar = calmar
    
    return {
        'total_return_pct': total_return,
        'max_drawdown_pct': max_drawdown,
        'volatility_pct': volatility,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'calmar_ratio': calmar,
        'mar_ratio': mar,
    }


def calculate_trade_metrics(trades: List[Any]) -> Dict[str, float]:
    """
    Calculate trade-specific metrics.
    
    Args:
        trades: List of trade objects
        
    Returns:
        Dictionary of trade metrics
    """
    if not trades:
        return {
            'num_trades': 0,
            'win_rate_pct': 0,
            'profit_factor': 0,
            'expectancy': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'avg_trade': 0,
            'avg_trade_duration': 0,
        }
    
    # Separate winning and losing trades
    winning_trades = [t for t in trades if t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl < 0]
    
    # Basic counts
    num_trades = len(trades)
    num_wins = len(winning_trades)
    num_losses = len(losing_trades)
    
    # Win rate
    win_rate = num_wins / num_trades * 100 if num_trades > 0 else 0
    
    # Profit and loss calculations
    total_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
    total_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0
    
    # Profit factor
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf') if total_profit > 0 else 0
    
    # Average win and loss
    avg_win = total_profit / num_wins if num_wins > 0 else 0
    avg_loss = total_loss / num_losses if num_losses > 0 else 0
    
    # Largest win and loss
    largest_win = max(t.pnl for t in trades) if trades else 0
    largest_loss = min(t.pnl for t in trades) if trades else 0
    
    # Expectancy
    expectancy = (avg_win * num_wins - avg_loss * num_losses) / num_trades if num_trades > 0 else 0
    
    # Average trade
    avg_trade = sum(t.pnl for t in trades) / num_trades if num_trades > 0 else 0
    
    # Average trade duration
    durations = []
    for trade in trades:
        if trade.exit_time and trade.entry_time:
            duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600  # hours
            durations.append(duration)
    
    avg_trade_duration = np.mean(durations) if durations else 0
    
    return {
        'num_trades': num_trades,
        'win_rate_pct': win_rate,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'largest_win': largest_win,
        'largest_loss': largest_loss,
        'avg_trade': avg_trade,
        'avg_trade_duration': avg_trade_duration,
    }


def calculate_risk_metrics(equity_curve: pd.Series, trades: List[Any]) -> Dict[str, float]:
    """
    Calculate risk-related metrics.
    
    Args:
        equity_curve: Equity curve series
        trades: List of trade objects
        
    Returns:
        Dictionary of risk metrics
    """
    if len(equity_curve) == 0:
        return {}
    
    # Value at Risk (VaR) - 95% confidence
    returns = equity_curve.pct_change().dropna()
    var_95 = np.percentile(returns, 5) * 100 if len(returns) > 0 else 0
    
    # Expected Shortfall (CVaR)
    cvar_95 = returns[returns <= np.percentile(returns, 5)].mean() * 100 if len(returns) > 0 else 0
    
    # Maximum consecutive losses
    consecutive_losses = 0
    max_consecutive_losses = 0
    current_consecutive = 0
    
    for trade in trades:
        if trade.pnl < 0:
            current_consecutive += 1
            max_consecutive_losses = max(max_consecutive_losses, current_consecutive)
        else:
            current_consecutive = 0
    
    # Recovery factor
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak * 100
    max_drawdown = drawdown.min()
    
    # Find recovery periods
    recovery_periods = []
    in_drawdown = False
    drawdown_start = None
    
    for i, dd in enumerate(drawdown):
        if dd < -1 and not in_drawdown:  # Start of drawdown (>1%)
            in_drawdown = True
            drawdown_start = i
        elif dd >= -1 and in_drawdown:  # End of drawdown
            in_drawdown = False
            if drawdown_start is not None:
                recovery_periods.append(i - drawdown_start)
    
    avg_recovery_period = np.mean(recovery_periods) if recovery_periods else 0
    
    # Exposure calculation
    total_time = (equity_curve.index[-1] - equity_curve.index[0]).total_seconds() / 3600  # hours
    exposure_time = sum((t.exit_time - t.entry_time).total_seconds() / 3600 for t in trades if t.exit_time)
    exposure_pct = exposure_time / total_time * 100 if total_time > 0 else 0
    
    return {
        'var_95_pct': var_95,
        'cvar_95_pct': cvar_95,
        'max_consecutive_losses': max_consecutive_losses,
        'avg_recovery_period': avg_recovery_period,
        'exposure_pct': exposure_pct,
    }


def calculate_advanced_metrics(equity_curve: pd.Series, trades: List[Any]) -> Dict[str, float]:
    """
    Calculate advanced performance metrics.
    
    Args:
        equity_curve: Equity curve series
        trades: List of trade objects
        
    Returns:
        Dictionary of advanced metrics
    """
    if len(equity_curve) == 0:
        return {}
    
    returns = equity_curve.pct_change().dropna()
    
    # Skewness and Kurtosis
    skewness = stats.skew(returns) if len(returns) > 2 else 0
    kurtosis = stats.kurtosis(returns) if len(returns) > 2 else 0
    
    # Information ratio (vs benchmark - assuming 0% benchmark return)
    benchmark_returns = pd.Series(0, index=returns.index)
    excess_returns = returns - benchmark_returns
    tracking_error = excess_returns.std()
    information_ratio = excess_returns.mean() / tracking_error if tracking_error > 0 else 0
    
    # Omega ratio
    threshold = 0  # Risk-free rate
    positive_returns = returns[returns > threshold]
    negative_returns = returns[returns <= threshold]
    
    omega = (positive_returns.sum() / abs(negative_returns.sum())) if len(negative_returns) > 0 else float('inf')
    
    # Sterling ratio
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak * 100
    avg_drawdown = drawdown[drawdown < 0].mean() if len(drawdown[drawdown < 0]) > 0 else 0
    sterling_ratio = returns.mean() / abs(avg_drawdown) if avg_drawdown != 0 else 0
    
    # Burke ratio
    drawdown_squared = (drawdown[drawdown < 0] ** 2).sum()
    burke_ratio = returns.mean() / np.sqrt(drawdown_squared) if drawdown_squared > 0 else 0
    
    # Kappa ratio (3rd moment)
    kappa_3 = returns.mean() / (stats.skew(returns) ** (1/3)) if stats.skew(returns) != 0 else 0
    
    return {
        'skewness': skewness,
        'kurtosis': kurtosis,
        'information_ratio': information_ratio,
        'omega_ratio': omega,
        'sterling_ratio': sterling_ratio,
        'burke_ratio': burke_ratio,
        'kappa_ratio': kappa_3,
    }


def calculate_all_metrics(equity_curve: pd.Series, trades: List[Any]) -> Dict[str, float]:
    """
    Calculate all available metrics.
    
    Args:
        equity_curve: Equity curve series
        trades: List of trade objects
        
    Returns:
        Dictionary of all metrics
    """
    metrics = {}
    
    # Basic metrics
    basic_metrics = calculate_basic_metrics(equity_curve, trades)
    metrics.update(basic_metrics)
    
    # Trade metrics
    trade_metrics = calculate_trade_metrics(trades)
    metrics.update(trade_metrics)
    
    # Risk metrics
    risk_metrics = calculate_risk_metrics(equity_curve, trades)
    metrics.update(risk_metrics)
    
    # Advanced metrics
    advanced_metrics = calculate_advanced_metrics(equity_curve, trades)
    metrics.update(advanced_metrics)
    
    return metrics


def rank_results(results: List[Dict[str, Any]], 
                primary_metric: str = 'profit_factor',
                secondary_metric: str = 'total_return_pct',
                ascending: bool = False) -> List[Dict[str, Any]]:
    """
    Rank optimization results by metrics.
    
    Args:
        results: List of optimization results
        primary_metric: Primary metric for ranking
        secondary_metric: Secondary metric for tie-breaking
        ascending: Whether to sort in ascending order
        
    Returns:
        Ranked list of results
    """
    if not results:
        return []
    
    # Filter results with valid metrics
    valid_results = []
    for result in results:
        if 'metrics' in result and primary_metric in result['metrics']:
            valid_results.append(result)
    
    if not valid_results:
        return []
    
    # Sort by primary metric, then secondary metric
    def sort_key(result):
        primary_value = result['metrics'].get(primary_metric, 0)
        secondary_value = result['metrics'].get(secondary_metric, 0)
        return (primary_value, secondary_value)
    
    sorted_results = sorted(valid_results, key=sort_key, reverse=not ascending)
    
    # Add ranking
    for i, result in enumerate(sorted_results):
        result['rank'] = i + 1
    
    return sorted_results


def calculate_portfolio_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate portfolio-level metrics from multiple results.
    
    Args:
        results: List of optimization results
        
    Returns:
        Dictionary of portfolio metrics
    """
    if not results:
        return {}
    
    # Extract metrics
    total_returns = [r['metrics'].get('total_return_pct', 0) for r in results]
    profit_factors = [r['metrics'].get('profit_factor', 0) for r in results]
    max_drawdowns = [r['metrics'].get('max_drawdown_pct', 0) for r in results]
    sharpe_ratios = [r['metrics'].get('sharpe_ratio', 0) for r in results]
    num_trades = [r['metrics'].get('num_trades', 0) for r in results]
    
    # Calculate portfolio statistics
    portfolio_metrics = {
        'num_strategies': len(results),
        'avg_return_pct': np.mean(total_returns),
        'median_return_pct': np.median(total_returns),
        'std_return_pct': np.std(total_returns),
        'avg_profit_factor': np.mean(profit_factors),
        'median_profit_factor': np.median(profit_factors),
        'avg_max_drawdown_pct': np.mean(max_drawdowns),
        'median_max_drawdown_pct': np.median(max_drawdowns),
        'avg_sharpe_ratio': np.mean(sharpe_ratios),
        'median_sharpe_ratio': np.median(sharpe_ratios),
        'total_trades': sum(num_trades),
        'avg_trades_per_strategy': np.mean(num_trades),
        'positive_strategies': sum(1 for r in total_returns if r > 0),
        'consistency_pct': sum(1 for r in total_returns if r > 0) / len(total_returns) * 100,
    }
    
    return portfolio_metrics


def filter_results_by_metrics(results: List[Dict[str, Any]], 
                            filters: Dict[str, Tuple[float, float]]) -> List[Dict[str, Any]]:
    """
    Filter results by metric ranges.
    
    Args:
        results: List of optimization results
        filters: Dictionary mapping metric names to (min, max) tuples
        
    Returns:
        Filtered list of results
    """
    if not results or not filters:
        return results
    
    filtered_results = []
    
    for result in results:
        if 'metrics' not in result:
            continue
        
        metrics = result['metrics']
        include_result = True
        
        for metric_name, (min_val, max_val) in filters.items():
            if metric_name not in metrics:
                include_result = False
                break
            
            value = metrics[metric_name]
            if not (min_val <= value <= max_val):
                include_result = False
                break
        
        if include_result:
            filtered_results.append(result)
    
    return filtered_results


def get_metric_summary(results: List[Dict[str, Any]], metric: str) -> Dict[str, float]:
    """
    Get summary statistics for a specific metric.
    
    Args:
        results: List of optimization results
        metric: Metric name
        
    Returns:
        Dictionary of summary statistics
    """
    if not results:
        return {}
    
    values = []
    for result in results:
        if 'metrics' in result and metric in result['metrics']:
            values.append(result['metrics'][metric])
    
    if not values:
        return {}
    
    return {
        'count': len(values),
        'mean': np.mean(values),
        'median': np.median(values),
        'std': np.std(values),
        'min': np.min(values),
        'max': np.max(values),
        'q25': np.percentile(values, 25),
        'q75': np.percentile(values, 75),
    }
