"""
Grid search optimization module for NASDAQ Strategy Optimizer.

This module implements comprehensive grid search optimization across multiple
NASDAQ symbols, timeframes, and parameter combinations.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Callable
import logging
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import json
import os
from pathlib import Path

from ..config import get_config, get_param_combinations
from ..data.loader import create_data_loader
from ..strategy.nasdaq_atr_supertrend import create_strategy, create_nasdaq_strategy
from ..strategy.backtester import run_backtest

logger = logging.getLogger(__name__)


class GridSearchOptimizer:
    """
    Grid search optimizer for ATR + SuperTrend strategy.
    """
    
    def __init__(self, cache_dir: Optional[str] = None, use_cache: bool = True):
        """
        Initialize grid search optimizer.
        
        Args:
            cache_dir: Cache directory path
            use_cache: Whether to use caching
        """
        self.config = get_config()
        self.data_loader = create_data_loader(cache_dir, use_cache)
        self.results = []
        
    def optimize_single_combination(self, symbol: str, timeframe: str, 
                                 params: Dict[str, Any], data: pd.DataFrame, 
                                 strategy_factory: Callable = create_nasdaq_strategy) -> Dict[str, Any]:
        """
        Optimize a single parameter combination.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            params: Parameter combination
            data: OHLCV data
            
        Returns:
            Optimization result
        """
        try:
            # Select validation function based on strategy
            if strategy_factory == create_volensy_strategy:
                validate_func = validate_volensy_params
            elif strategy_factory == create_atr_supertrend_strategy:
                validate_func = validate_atr_supertrend_params
            else:
                validate_func = validate_strategy_params
            
            # Validate parameters
            if not validate_func(params):
                return {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'params': params,
                    'error': 'Invalid parameters',
                    'success': False
                }
            
            # Create strategy
            strategy = strategy_factory(params)
            
            # Run strategy
            signals = strategy.run_strategy(data)
            
            if signals.empty:
                return {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'params': params,
                    'error': 'No signals generated',
                    'success': False
                }
            
            # Run backtest
            result = run_backtest(
                data=data,
                signals=signals,
                initial_capital=10000,  # Fixed capital
                fee_bps=10,  # 0.1% fee
                slippage_bps=5  # 0.05% slippage
            )
            
            # Add metadata
            result.symbol = symbol
            result.timeframe = timeframe
            result.parameters = params
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'params': params,
                'metrics': result.metrics,
                'num_trades': len(result.trades),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error optimizing {symbol} {timeframe} with params {params}: {e}")
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'params': params,
                'error': str(e),
                'success': False
            }
    
    def optimize_symbol_timeframe(self, symbol: str, timeframe: str, 
                                param_combinations: List[Dict[str, Any]], 
                                strategy_factory: Callable = create_strategy) -> List[Dict[str, Any]]:
        """
        Optimize all parameter combinations for a single symbol/timeframe.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            param_combinations: List of parameter combinations
            
        Returns:
            List of optimization results
        """
        logger.info(f"Optimizing {symbol} {timeframe} with {len(param_combinations)} combinations")
        
        # Load data
        try:
            data = self.data_loader.get_ohlcv(symbol, timeframe)
            if data.empty:
                logger.error(f"No data available for {symbol} {timeframe}")
                return []
        except Exception as e:
            logger.error(f"Failed to load data for {symbol} {timeframe}: {e}")
            return []
        
        results = []
        
        # Optimize each parameter combination
        for params in tqdm(param_combinations, desc=f"{symbol} {timeframe}"):
            result = self.optimize_single_combination(symbol, timeframe, params, data, strategy_factory)
            results.append(result)
        
        return results
    
    def optimize_parallel(self, symbols: List[str], timeframes: List[str], 
                        param_combinations: List[Dict[str, Any]], 
                        strategy_factory: Callable = create_strategy,
                        max_workers: int = 4) -> List[Dict[str, Any]]:
        """
        Run parallel optimization across symbols and timeframes.
        
        Args:
            symbols: List of trading pair symbols
            timeframes: List of timeframes
            param_combinations: List of parameter combinations
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of all optimization results
        """
        logger.info(f"Starting parallel optimization: {len(symbols)} symbols, {len(timeframes)} timeframes, {len(param_combinations)} combinations")
        
        all_results = []
        
        # Create tasks
        tasks = []
        for symbol in symbols:
            for timeframe in timeframes:
                tasks.append((symbol, timeframe, param_combinations))
        
        # Run parallel optimization
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.optimize_symbol_timeframe, symbol, timeframe, param_combinations, strategy_factory): (symbol, timeframe)
                for symbol, timeframe, param_combinations in tasks
            }
            
            # Collect results
            for future in tqdm(as_completed(future_to_task), total=len(tasks), desc="Optimization Progress"):
                symbol, timeframe = future_to_task[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    logger.info(f"Completed {symbol} {timeframe}: {len(results)} results")
                except Exception as e:
                    logger.error(f"Error processing {symbol} {timeframe}: {e}")
        
        return all_results
    
    def optimize_sequential(self, symbols: List[str], timeframes: List[str], 
                          param_combinations: List[Dict[str, Any]], 
                          strategy_factory: Callable = create_strategy) -> List[Dict[str, Any]]:
        """
        Run sequential optimization across symbols and timeframes.
        
        Args:
            symbols: List of trading pair symbols
            timeframes: List of timeframes
            param_combinations: List of parameter combinations
            
        Returns:
            List of all optimization results
        """
        logger.info(f"Starting sequential optimization: {len(symbols)} symbols, {len(timeframes)} timeframes, {len(param_combinations)} combinations")
        
        all_results = []
        
        for symbol in symbols:
            for timeframe in timeframes:
                results = self.optimize_symbol_timeframe(symbol, timeframe, param_combinations, strategy_factory)
                all_results.extend(results)
        
        return all_results
    
    def run_optimization(self, symbols: List[str], timeframes: List[str], 
                         param_combinations: Optional[List[Dict[str, Any]]] = None,
                         strategy_factory: Callable = create_strategy,
                         max_workers: int = 4, parallel: bool = True) -> List[Dict[str, Any]]:
        """
        Run complete optimization.
        
        Args:
            symbols: List of trading pair symbols
            timeframes: List of timeframes
            param_combinations: Parameter combinations (uses config if None)
            max_workers: Maximum number of parallel workers
            parallel: Whether to use parallel processing
            
        Returns:
            List of all optimization results
        """
        if param_combinations is None:
            param_combinations = get_param_combinations()
        
        logger.info(f"Starting optimization with {len(param_combinations)} parameter combinations")
        
        if parallel and max_workers > 1:
            results = self.optimize_parallel(symbols, timeframes, param_combinations, strategy_factory, max_workers)
        else:
            results = self.optimize_sequential(symbols, timeframes, param_combinations, strategy_factory)
        
        # Filter successful results
        successful_results = [r for r in results if r.get('success', False)]
        failed_results = [r for r in results if not r.get('success', False)]
        
        logger.info(f"Optimization completed: {len(successful_results)} successful, {len(failed_results)} failed")
        
        if failed_results:
            logger.warning(f"Failed optimizations: {len(failed_results)}")
            for result in failed_results[:5]:  # Log first 5 failures
                logger.warning(f"Failed: {result['symbol']} {result['timeframe']} - {result.get('error', 'Unknown error')}")
        
        self.results = successful_results
        return successful_results
    
    def get_top_results(self, n: int = 10, metric: str = 'profit_factor') -> List[Dict[str, Any]]:
        """
        Get top N results sorted by metric.
        
        Args:
            n: Number of top results
            metric: Metric to sort by
            
        Returns:
            List of top results
        """
        if not self.results:
            return []
        
        # Filter results with valid metrics
        valid_results = [r for r in self.results if metric in r.get('metrics', {})]
        
        if not valid_results:
            return []
        
        # Sort by metric (descending)
        sorted_results = sorted(valid_results, key=lambda x: x['metrics'][metric], reverse=True)
        
        return sorted_results[:n]
    
    def get_results_by_symbol_timeframe(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Group results by symbol and timeframe.
        
        Returns:
            Nested dictionary: {symbol: {timeframe: [results]}}
        """
        grouped = {}
        
        for result in self.results:
            symbol = result['symbol']
            timeframe = result['timeframe']
            
            if symbol not in grouped:
                grouped[symbol] = {}
            
            if timeframe not in grouped[symbol]:
                grouped[symbol][timeframe] = []
            
            grouped[symbol][timeframe].append(result)
        
        return grouped
    
    def save_results(self, output_dir: str, filename_prefix: str = "grid_search"):
        """
        Save optimization results to files.
        
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
        
        # Save as CSV
        csv_file = output_path / f"{filename_prefix}_results.csv"
        self._save_results_csv(csv_file)
        
        # Save top results
        top_results = self.get_top_results(n=100)
        top_file = output_path / f"{filename_prefix}_top_results.json"
        with open(top_file, 'w') as f:
            json.dump(top_results, f, indent=2, default=str)
        
        # Save summary by symbol/timeframe
        summary_file = output_path / f"{filename_prefix}_summary.json"
        self._save_summary(summary_file)
        
        logger.info(f"Results saved to {output_path}")
    
    def _save_results_csv(self, csv_file: Path):
        """Save results as CSV."""
        if not self.results:
            return
        
        # Flatten results for CSV
        flattened = []
        for result in self.results:
            row = {
                'symbol': result['symbol'],
                'timeframe': result['timeframe'],
                'num_trades': result['num_trades'],
            }
            
            # Add parameters
            for key, value in result['params'].items():
                row[f'param_{key}'] = value
            
            # Add metrics
            for key, value in result['metrics'].items():
                row[f'metric_{key}'] = value
            
            flattened.append(row)
        
        df = pd.DataFrame(flattened)
        df.to_csv(csv_file, index=False)
    
    def _save_summary(self, summary_file: Path):
        """Save optimization summary."""
        summary = {
            'total_combinations': len(self.results),
            'symbols': list(set(r['symbol'] for r in self.results)),
            'timeframes': list(set(r['timeframe'] for r in self.results)),
            'best_results': {}
        }
        
        # Get best result for each symbol/timeframe
        grouped = self.get_results_by_symbol_timeframe()
        for symbol, timeframes in grouped.items():
            summary['best_results'][symbol] = {}
            for timeframe, results in timeframes.items():
                if results:
                    best = max(results, key=lambda x: x['metrics'].get('profit_factor', 0))
                    summary['best_results'][symbol][timeframe] = {
                        'params': best['params'],
                        'profit_factor': best['metrics'].get('profit_factor', 0),
                        'total_return': best['metrics'].get('total_return_pct', 0),
                        'max_drawdown': best['metrics'].get('max_drawdown_pct', 0),
                        'num_trades': best['num_trades'],
                    }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)


def run_grid_search(symbols: List[str], timeframes: List[str], 
                   strategy_type: str = "atr_supertrend",
                   param_space: Optional[Dict[str, List[Any]]] = None,
                   data_loader: Optional[Any] = None,
                   jobs: int = 4, top_n: int = 10,
                   cache_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Run grid search optimization for NASDAQ symbols.
    
    Args:
        symbols: List of NASDAQ symbols to optimize
        timeframes: List of timeframes to test
        strategy_type: Strategy type (default: "atr_supertrend")
        param_space: Parameter space dictionary
        data_loader: Data loader instance
        jobs: Number of parallel jobs
        top_n: Number of top results to keep
        cache_dir: Cache directory
        
    Returns:
        Dictionary with optimization results
    """
    logger.info(f"🚀 Starting NASDAQ grid search optimization")
    logger.info(f"📊 Symbols: {symbols}")
    logger.info(f"⏰ Timeframes: {timeframes}")
    logger.info(f"🔧 Strategy: {strategy_type}")
    
    # Get parameter space
    if param_space is None:
        config = get_config()
        param_space = config.strategy.param_space
    
    # Generate parameter combinations
    param_combinations = get_param_combinations()
    logger.info(f"🔧 Parameter combinations: {len(param_combinations)}")
    
    # Create data loader
    if data_loader is None:
        data_loader = create_data_loader(cache_dir)
    
    # Create optimizer
    optimizer = GridSearchOptimizer(cache_dir)
    
    # Run optimization
    results = optimizer.run_optimization(
        symbols=symbols,
        timeframes=timeframes,
        param_combinations=param_combinations,
        strategy_factory=create_nasdaq_strategy,
        max_workers=jobs,
        parallel=True
    )
    
    # Get top results
    top_results = sorted(results, key=lambda x: x.get('metrics', {}).get('profit_factor', 0), reverse=True)[:top_n]
    
    return {
        'total_combinations': len(results),
        'top_results': top_results,
        'all_results': results,
        'summary': {
            'symbols': symbols,
            'timeframes': timeframes,
            'strategy_type': strategy_type,
            'best_profit_factor': top_results[0].get('metrics', {}).get('profit_factor', 0) if top_results else 0
        }
    }
