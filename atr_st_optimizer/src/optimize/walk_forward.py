"""
Walk-forward optimization module for ATR + SuperTrend strategy.

This module implements walk-forward analysis with rolling and expanding windows
to test strategy robustness across different time periods.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
from tqdm import tqdm
import json
import os
from pathlib import Path

from config import get_config, get_wf_windows
from data.loader import create_data_loader
from strategy.atr_st_core import create_strategy, validate_strategy_params
from strategy.backtester import run_backtest
from .grid_search import GridSearchOptimizer

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """
    Walk-forward optimizer for ATR + SuperTrend strategy.
    """
    
    def __init__(self, cache_dir: Optional[str] = None, use_cache: bool = True):
        """
        Initialize walk-forward optimizer.
        
        Args:
            cache_dir: Cache directory path
            use_cache: Whether to use caching
        """
        self.config = get_config()
        self.data_loader = create_data_loader(cache_dir, use_cache)
        self.results = []
        
    def optimize_window(self, symbol: str, timeframe: str, 
                       train_data: pd.DataFrame, test_data: pd.DataFrame,
                       param_combinations: List[Dict[str, Any]],
                       window_id: int) -> Dict[str, Any]:
        """
        Optimize parameters on training data and test on test data.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            train_data: Training data
            test_data: Test data
            param_combinations: Parameter combinations to test
            window_id: Window identifier
            
        Returns:
            Walk-forward result
        """
        logger.info(f"Processing window {window_id} for {symbol} {timeframe}")
        
        # Find best parameters on training data
        best_params = None
        best_metric = -float('inf')
        
        for params in param_combinations:
            try:
                # Validate parameters
                if not validate_strategy_params(params):
                    continue
                
                # Create strategy
                strategy = create_strategy(params)
                
                # Run strategy on training data
                train_signals = strategy.run_strategy(train_data)
                
                if train_signals.empty:
                    continue
                
                # Run backtest on training data
                train_result = run_backtest(
                    data=train_data,
                    signals=train_signals,
                    initial_capital=10000.0,
                    fee_bps=self.config.strategy.fee_bps,
                    slippage_bps=self.config.strategy.slippage_bps
                )
                
                # Use profit factor as optimization metric
                metric_value = train_result.metrics.get('profit_factor', 0)
                
                if metric_value > best_metric:
                    best_metric = metric_value
                    best_params = params
                    
            except Exception as e:
                logger.warning(f"Error optimizing params {params} on training data: {e}")
                continue
        
        if best_params is None:
            logger.warning(f"No valid parameters found for window {window_id}")
            return {
                'window_id': window_id,
                'symbol': symbol,
                'timeframe': timeframe,
                'best_params': None,
                'train_metrics': {},
                'test_metrics': {},
                'success': False,
                'error': 'No valid parameters found'
            }
        
        # Test best parameters on test data
        try:
            # Create strategy with best parameters
            strategy = create_strategy(best_params)
            
            # Run strategy on test data
            test_signals = strategy.run_strategy(test_data)
            
            if test_signals.empty:
                return {
                    'window_id': window_id,
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'best_params': best_params,
                    'train_metrics': {},
                    'test_metrics': {},
                    'success': False,
                    'error': 'No signals generated on test data'
                }
            
            # Run backtest on test data
            test_result = run_backtest(
                data=test_data,
                signals=test_signals,
                initial_capital=10000.0,
                fee_bps=self.config.strategy.fee_bps,
                slippage_bps=self.config.strategy.slippage_bps
            )
            
            return {
                'window_id': window_id,
                'symbol': symbol,
                'timeframe': timeframe,
                'best_params': best_params,
                'train_metrics': {'profit_factor': best_metric},
                'test_metrics': test_result.metrics,
                'train_start': train_data.index[0],
                'train_end': train_data.index[-1],
                'test_start': test_data.index[0],
                'test_end': test_data.index[-1],
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error testing best parameters on test data: {e}")
            return {
                'window_id': window_id,
                'symbol': symbol,
                'timeframe': timeframe,
                'best_params': best_params,
                'train_metrics': {'profit_factor': best_metric},
                'test_metrics': {},
                'success': False,
                'error': str(e)
            }
    
    def run_walk_forward(self, symbol: str, timeframe: str, 
                        data: pd.DataFrame, param_combinations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run walk-forward analysis for a single symbol/timeframe.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            data: Complete dataset
            param_combinations: Parameter combinations to test
            
        Returns:
            List of walk-forward results
        """
        logger.info(f"Running walk-forward analysis for {symbol} {timeframe}")
        
        # Generate walk-forward windows
        total_days = (data.index[-1] - data.index[0]).days
        windows = get_wf_windows(total_days)
        
        if not windows:
            logger.error(f"No walk-forward windows generated for {symbol} {timeframe}")
            return []
        
        results = []
        
        # Process each window
        for window in tqdm(windows, desc=f"WF {symbol} {timeframe}"):
            try:
                # Extract training data
                train_start = data.index[0] + timedelta(days=window['train_start'])
                train_end = data.index[0] + timedelta(days=window['train_end'])
                train_data = data[(data.index >= train_start) & (data.index <= train_end)]
                
                # Extract test data
                test_start = data.index[0] + timedelta(days=window['test_start'])
                test_end = data.index[0] + timedelta(days=window['test_end'])
                test_data = data[(data.index >= test_start) & (data.index <= test_end)]
                
                if train_data.empty or test_data.empty:
                    logger.warning(f"Empty data for window {window['window_id']}")
                    continue
                
                # Optimize and test window
                result = self.optimize_window(
                    symbol, timeframe, train_data, test_data, 
                    param_combinations, window['window_id']
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing window {window['window_id']}: {e}")
                continue
        
        return results
    
    def run_multi_symbol_walk_forward(self, symbols: List[str], timeframes: List[str],
                                    param_combinations: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Run walk-forward analysis across multiple symbols and timeframes.
        
        Args:
            symbols: List of trading pair symbols
            timeframes: List of timeframes
            param_combinations: Parameter combinations (uses config if None)
            
        Returns:
            List of all walk-forward results
        """
        if param_combinations is None:
            param_combinations = get_param_combinations()
        
        logger.info(f"Starting walk-forward analysis: {len(symbols)} symbols, {len(timeframes)} timeframes")
        
        all_results = []
        
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    # Load data
                    data = self.data_loader.get_ohlcv(symbol, timeframe)
                    if data.empty:
                        logger.error(f"No data available for {symbol} {timeframe}")
                        continue
                    
                    # Run walk-forward analysis
                    results = self.run_walk_forward(symbol, timeframe, data, param_combinations)
                    all_results.extend(results)
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol} {timeframe}: {e}")
                    continue
        
        # Filter successful results
        successful_results = [r for r in all_results if r.get('success', False)]
        failed_results = [r for r in all_results if not r.get('success', False)]
        
        logger.info(f"Walk-forward analysis completed: {len(successful_results)} successful, {len(failed_results)} failed")
        
        if failed_results:
            logger.warning(f"Failed walk-forward windows: {len(failed_results)}")
        
        self.results = successful_results
        return successful_results
    
    def calculate_wf_metrics(self) -> Dict[str, Any]:
        """
        Calculate walk-forward specific metrics.
        
        Returns:
            Dictionary of walk-forward metrics
        """
        if not self.results:
            return {}
        
        # Group results by symbol/timeframe
        grouped_results = {}
        for result in self.results:
            key = f"{result['symbol']}_{result['timeframe']}"
            if key not in grouped_results:
                grouped_results[key] = []
            grouped_results[key].append(result)
        
        wf_metrics = {}
        
        for key, results in grouped_results.items():
            if not results:
                continue
            
            # Calculate metrics across all windows
            test_returns = [r['test_metrics'].get('total_return_pct', 0) for r in results]
            test_pfs = [r['test_metrics'].get('profit_factor', 0) for r in results]
            test_drawdowns = [r['test_metrics'].get('max_drawdown_pct', 0) for r in results]
            test_trades = [r['test_metrics'].get('num_trades', 0) for r in results]
            
            # Calculate stability metrics
            return_std = np.std(test_returns) if len(test_returns) > 1 else 0
            pf_std = np.std(test_pfs) if len(test_pfs) > 1 else 0
            
            # Calculate consistency
            positive_windows = sum(1 for r in test_returns if r > 0)
            consistency = positive_windows / len(test_returns) * 100 if test_returns else 0
            
            # Calculate average metrics
            avg_return = np.mean(test_returns) if test_returns else 0
            avg_pf = np.mean(test_pfs) if test_pfs else 0
            avg_drawdown = np.mean(test_drawdowns) if test_drawdowns else 0
            total_trades = sum(test_trades)
            
            wf_metrics[key] = {
                'num_windows': len(results),
                'avg_return_pct': avg_return,
                'avg_profit_factor': avg_pf,
                'avg_drawdown_pct': avg_drawdown,
                'total_trades': total_trades,
                'consistency_pct': consistency,
                'return_std': return_std,
                'pf_std': pf_std,
                'best_window_return': max(test_returns) if test_returns else 0,
                'worst_window_return': min(test_returns) if test_returns else 0,
            }
        
        return wf_metrics
    
    def get_best_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Get best parameters for each symbol/timeframe combination.
        
        Returns:
            Dictionary mapping symbol/timeframe to best parameters
        """
        if not self.results:
            return {}
        
        # Group results by symbol/timeframe
        grouped_results = {}
        for result in self.results:
            key = f"{result['symbol']}_{result['timeframe']}"
            if key not in grouped_results:
                grouped_results[key] = []
            grouped_results[key].append(result)
        
        best_params = {}
        
        for key, results in grouped_results.items():
            if not results:
                continue
            
            # Find best parameters based on average test performance
            best_result = None
            best_score = -float('inf')
            
            for result in results:
                # Use profit factor as primary metric
                score = result['test_metrics'].get('profit_factor', 0)
                
                if score > best_score:
                    best_score = score
                    best_result = result
            
            if best_result:
                best_params[key] = {
                    'params': best_result['best_params'],
                    'test_metrics': best_result['test_metrics'],
                    'window_id': best_result['window_id']
                }
        
        return best_params
    
    def save_results(self, output_dir: str, filename_prefix: str = "walk_forward"):
        """
        Save walk-forward results to files.
        
        Args:
            output_dir: Output directory
            filename_prefix: Filename prefix
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save all results as JSON
        json_file = output_path / f"{filename_prefix}_results.json"
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Save walk-forward metrics
        wf_metrics = self.calculate_wf_metrics()
        metrics_file = output_path / f"{filename_prefix}_metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(wf_metrics, f, indent=2, default=str)
        
        # Save best parameters
        best_params = self.get_best_parameters()
        params_file = output_path / f"{filename_prefix}_best_params.json"
        with open(params_file, 'w') as f:
            json.dump(best_params, f, indent=2, default=str)
        
        # Save summary
        summary_file = output_path / f"{filename_prefix}_summary.json"
        self._save_summary(summary_file, wf_metrics, best_params)
        
        logger.info(f"Walk-forward results saved to {output_path}")
    
    def _save_summary(self, summary_file: Path, wf_metrics: Dict[str, Any], 
                     best_params: Dict[str, Any]):
        """Save walk-forward summary."""
        summary = {
            'total_windows': len(self.results),
            'symbols': list(set(r['symbol'] for r in self.results)),
            'timeframes': list(set(r['timeframe'] for r in self.results)),
            'wf_metrics': wf_metrics,
            'best_parameters': best_params,
            'overall_stats': self._calculate_overall_stats()
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
    
    def _calculate_overall_stats(self) -> Dict[str, Any]:
        """Calculate overall walk-forward statistics."""
        if not self.results:
            return {}
        
        all_test_returns = [r['test_metrics'].get('total_return_pct', 0) for r in self.results]
        all_test_pfs = [r['test_metrics'].get('profit_factor', 0) for r in self.results]
        all_test_drawdowns = [r['test_metrics'].get('max_drawdown_pct', 0) for r in self.results]
        
        return {
            'avg_return_pct': np.mean(all_test_returns) if all_test_returns else 0,
            'avg_profit_factor': np.mean(all_test_pfs) if all_test_pfs else 0,
            'avg_drawdown_pct': np.mean(all_test_drawdowns) if all_test_drawdowns else 0,
            'total_windows': len(self.results),
            'positive_windows': sum(1 for r in all_test_returns if r > 0),
            'consistency_pct': sum(1 for r in all_test_returns if r > 0) / len(all_test_returns) * 100 if all_test_returns else 0,
        }


def run_walk_forward(symbols: List[str], timeframes: List[str], 
                    param_combinations: Optional[List[Dict[str, Any]]] = None,
                    output_dir: str = "./reports/wf") -> List[Dict[str, Any]]:
    """
    Convenience function to run walk-forward analysis.
    
    Args:
        symbols: List of trading pair symbols
        timeframes: List of timeframes
        param_combinations: Parameter combinations
        output_dir: Output directory
        
    Returns:
        List of walk-forward results
    """
    optimizer = WalkForwardOptimizer()
    results = optimizer.run_multi_symbol_walk_forward(symbols, timeframes, param_combinations)
    optimizer.save_results(output_dir)
    return results
