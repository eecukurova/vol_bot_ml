"""
Reporting module for optimization results.

This module provides comprehensive reporting functionality for grid search
and walk-forward optimization results.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
import json
import os
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ResultsReporter:
    """
    Reporter for optimization results.
    """
    
    def __init__(self, output_dir: str = "./reports"):
        """
        Initialize reporter.
        
        Args:
            output_dir: Output directory for reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_results(self, results_file: str) -> List[Dict[str, Any]]:
        """
        Load results from JSON file.
        
        Args:
            results_file: Path to results JSON file
            
        Returns:
            List of results
        """
        try:
            with open(results_file, 'r') as f:
                results = json.load(f)
            logger.info(f"Loaded {len(results)} results from {results_file}")
            return results
        except Exception as e:
            logger.error(f"Failed to load results from {results_file}: {e}")
            return []
    
    def create_summary_table(self, results: List[Dict[str, Any]], 
                           top_n: int = 10) -> pd.DataFrame:
        """
        Create summary table of top results.
        
        Args:
            results: List of optimization results
            top_n: Number of top results to include
            
        Returns:
            Summary DataFrame
        """
        if not results:
            return pd.DataFrame()
        
        # Sort by profit factor
        sorted_results = sorted(results, key=lambda x: x.get('metrics', {}).get('profit_factor', 0), reverse=True)
        top_results = sorted_results[:top_n]
        
        # Create summary data
        summary_data = []
        for i, result in enumerate(top_results):
            metrics = result.get('metrics', {})
            params = result.get('params', {})
            
            summary_data.append({
                'Rank': i + 1,
                'Symbol': result.get('symbol', ''),
                'Timeframe': result.get('timeframe', ''),
                'Total_Return_%': round(metrics.get('total_return_pct', 0), 2),
                'Max_Drawdown_%': round(metrics.get('max_drawdown_pct', 0), 2),
                'Profit_Factor': round(metrics.get('profit_factor', 0), 2),
                'Sharpe_Ratio': round(metrics.get('sharpe_ratio', 0), 2),
                'Win_Rate_%': round(metrics.get('win_rate_pct', 0), 2),
                'Num_Trades': metrics.get('num_trades', 0),
                'MAR_Ratio': round(metrics.get('mar_ratio', 0), 2),
                'ATR_Sensitivity': params.get('a', 0),
                'ATR_Period': params.get('c', 0),
                'ST_Factor': params.get('st_factor', 0),
                'Min_Delay_Min': params.get('min_delay_m', 0),
                'SL_Multiplier': params.get('atr_sl_mult', 0),
                'RR_Ratio': params.get('atr_rr', 0),
            })
        
        return pd.DataFrame(summary_data)
    
    def create_symbol_timeframe_summary(self, results: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Create summary table grouped by symbol and timeframe.
        
        Args:
            results: List of optimization results
            
        Returns:
            Summary DataFrame grouped by symbol/timeframe
        """
        if not results:
            return pd.DataFrame()
        
        # Group results by symbol/timeframe
        grouped = {}
        for result in results:
            symbol = result.get('symbol', '')
            timeframe = result.get('timeframe', '')
            key = f"{symbol}_{timeframe}"
            
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)
        
        # Create summary for each group
        summary_data = []
        for key, group_results in grouped.items():
            if not group_results:
                continue
            
            symbol, timeframe = key.split('_', 1)
            
            # Calculate statistics
            total_returns = [r.get('metrics', {}).get('total_return_pct', 0) for r in group_results]
            profit_factors = [r.get('metrics', {}).get('profit_factor', 0) for r in group_results]
            max_drawdowns = [r.get('metrics', {}).get('max_drawdown_pct', 0) for r in group_results]
            sharpe_ratios = [r.get('metrics', {}).get('sharpe_ratio', 0) for r in group_results]
            num_trades = [r.get('metrics', {}).get('num_trades', 0) for r in group_results]
            
            # Find best result
            best_result = max(group_results, key=lambda x: x.get('metrics', {}).get('profit_factor', 0))
            best_params = best_result.get('params', {})
            
            summary_data.append({
                'Symbol': symbol,
                'Timeframe': timeframe,
                'Num_Combinations': len(group_results),
                'Best_Return_%': round(max(total_returns), 2),
                'Avg_Return_%': round(np.mean(total_returns), 2),
                'Best_PF': round(max(profit_factors), 2),
                'Avg_PF': round(np.mean(profit_factors), 2),
                'Best_Sharpe': round(max(sharpe_ratios), 2),
                'Avg_Sharpe': round(np.mean(sharpe_ratios), 2),
                'Best_MaxDD_%': round(min(max_drawdowns), 2),
                'Avg_MaxDD_%': round(np.mean(max_drawdowns), 2),
                'Total_Trades': sum(num_trades),
                'Best_ATR_Sensitivity': best_params.get('a', 0),
                'Best_ATR_Period': best_params.get('c', 0),
                'Best_ST_Factor': best_params.get('st_factor', 0),
            })
        
        return pd.DataFrame(summary_data)
    
    def create_parameter_analysis(self, results: List[Dict[str, Any]]) -> Dict[str, pd.DataFrame]:
        """
        Create parameter analysis tables.
        
        Args:
            results: List of optimization results
            
        Returns:
            Dictionary of parameter analysis DataFrames
        """
        if not results:
            return {}
        
        # Extract parameter data
        param_data = []
        for result in results:
            params = result.get('params', {})
            metrics = result.get('metrics', {})
            
            param_data.append({
                'symbol': result.get('symbol', ''),
                'timeframe': result.get('timeframe', ''),
                'a': params.get('a', 0),
                'c': params.get('c', 0),
                'st_factor': params.get('st_factor', 0),
                'min_delay_m': params.get('min_delay_m', 0),
                'atr_sl_mult': params.get('atr_sl_mult', 0),
                'atr_rr': params.get('atr_rr', 0),
                'total_return_pct': metrics.get('total_return_pct', 0),
                'profit_factor': metrics.get('profit_factor', 0),
                'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'num_trades': metrics.get('num_trades', 0),
            })
        
        df = pd.DataFrame(param_data)
        
        # Create parameter analysis tables
        analysis = {}
        
        # ATR Sensitivity analysis
        if 'a' in df.columns:
            a_analysis = df.groupby('a').agg({
                'total_return_pct': ['mean', 'std', 'count'],
                'profit_factor': ['mean', 'std'],
                'max_drawdown_pct': ['mean', 'std'],
                'sharpe_ratio': ['mean', 'std'],
                'num_trades': ['mean', 'sum'],
            }).round(2)
            analysis['atr_sensitivity'] = a_analysis
        
        # ATR Period analysis
        if 'c' in df.columns:
            c_analysis = df.groupby('c').agg({
                'total_return_pct': ['mean', 'std', 'count'],
                'profit_factor': ['mean', 'std'],
                'max_drawdown_pct': ['mean', 'std'],
                'sharpe_ratio': ['mean', 'std'],
                'num_trades': ['mean', 'sum'],
            }).round(2)
            analysis['atr_period'] = c_analysis
        
        # SuperTrend Factor analysis
        if 'st_factor' in df.columns:
            st_analysis = df.groupby('st_factor').agg({
                'total_return_pct': ['mean', 'std', 'count'],
                'profit_factor': ['mean', 'std'],
                'max_drawdown_pct': ['mean', 'std'],
                'sharpe_ratio': ['mean', 'std'],
                'num_trades': ['mean', 'sum'],
            }).round(2)
            analysis['supertrend_factor'] = st_analysis
        
        return analysis
    
    def create_walk_forward_summary(self, wf_results: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Create walk-forward analysis summary.
        
        Args:
            wf_results: List of walk-forward results
            
        Returns:
            Walk-forward summary DataFrame
        """
        if not wf_results:
            return pd.DataFrame()
        
        # Group by symbol/timeframe
        grouped = {}
        for result in wf_results:
            symbol = result.get('symbol', '')
            timeframe = result.get('timeframe', '')
            key = f"{symbol}_{timeframe}"
            
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)
        
        # Create summary for each group
        summary_data = []
        for key, group_results in grouped.items():
            if not group_results:
                continue
            
            symbol, timeframe = key.split('_', 1)
            
            # Calculate walk-forward metrics
            test_returns = [r.get('test_metrics', {}).get('total_return_pct', 0) for r in group_results]
            test_pfs = [r.get('test_metrics', {}).get('profit_factor', 0) for r in group_results]
            test_drawdowns = [r.get('test_metrics', {}).get('max_drawdown_pct', 0) for r in group_results]
            test_trades = [r.get('test_metrics', {}).get('num_trades', 0) for r in group_results]
            
            # Calculate stability metrics
            positive_windows = sum(1 for r in test_returns if r > 0)
            consistency = positive_windows / len(test_returns) * 100 if test_returns else 0
            
            # Get best parameters
            best_result = max(group_results, key=lambda x: x.get('test_metrics', {}).get('profit_factor', 0))
            best_params = best_result.get('best_params', {})
            
            summary_data.append({
                'Symbol': symbol,
                'Timeframe': timeframe,
                'Num_Windows': len(group_results),
                'Avg_Return_%': round(np.mean(test_returns), 2),
                'Std_Return_%': round(np.std(test_returns), 2),
                'Best_Window_Return_%': round(max(test_returns), 2),
                'Worst_Window_Return_%': round(min(test_returns), 2),
                'Avg_Profit_Factor': round(np.mean(test_pfs), 2),
                'Avg_MaxDD_%': round(np.mean(test_drawdowns), 2),
                'Total_Trades': sum(test_trades),
                'Consistency_%': round(consistency, 2),
                'Best_ATR_Sensitivity': best_params.get('a', 0),
                'Best_ATR_Period': best_params.get('c', 0),
                'Best_ST_Factor': best_params.get('st_factor', 0),
            })
        
        return pd.DataFrame(summary_data)
    
    def save_summary_tables(self, results: List[Dict[str, Any]], 
                          wf_results: Optional[List[Dict[str, Any]]] = None,
                          filename_prefix: str = "summary"):
        """
        Save all summary tables to files.
        
        Args:
            results: Grid search results
            wf_results: Walk-forward results (optional)
            filename_prefix: Filename prefix
        """
        # Create summary tables
        top_results = self.create_summary_table(results, top_n=50)
        symbol_tf_summary = self.create_symbol_timeframe_summary(results)
        param_analysis = self.create_parameter_analysis(results)
        
        # Save top results
        top_results_file = self.output_dir / f"{filename_prefix}_top_results.csv"
        top_results.to_csv(top_results_file, index=False)
        
        # Save symbol/timeframe summary
        symbol_tf_file = self.output_dir / f"{filename_prefix}_by_symbol_timeframe.csv"
        symbol_tf_summary.to_csv(symbol_tf_file, index=False)
        
        # Save parameter analysis
        for param_name, analysis_df in param_analysis.items():
            param_file = self.output_dir / f"{filename_prefix}_param_{param_name}.csv"
            analysis_df.to_csv(param_file)
        
        # Save walk-forward summary if provided
        if wf_results:
            wf_summary = self.create_walk_forward_summary(wf_results)
            wf_file = self.output_dir / f"{filename_prefix}_walk_forward.csv"
            wf_summary.to_csv(wf_file, index=False)
        
        logger.info(f"Summary tables saved to {self.output_dir}")
    
    def create_parameter_heatmap_data(self, results: List[Dict[str, Any]], 
                                    param1: str, param2: str, 
                                    metric: str = 'profit_factor') -> pd.DataFrame:
        """
        Create data for parameter heatmap visualization.
        
        Args:
            results: List of optimization results
            param1: First parameter for heatmap
            param2: Second parameter for heatmap
            metric: Metric to display in heatmap
            
        Returns:
            DataFrame suitable for heatmap
        """
        if not results:
            return pd.DataFrame()
        
        # Extract data
        heatmap_data = []
        for result in results:
            params = result.get('params', {})
            metrics = result.get('metrics', {})
            
            if param1 in params and param2 in params and metric in metrics:
                heatmap_data.append({
                    param1: params[param1],
                    param2: params[param2],
                    metric: metrics[metric]
                })
        
        if not heatmap_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(heatmap_data)
        
        # Create pivot table
        pivot = df.pivot_table(
            values=metric,
            index=param1,
            columns=param2,
            aggfunc='mean'
        )
        
        return pivot
    
    def generate_report(self, results_file: str, wf_results_file: Optional[str] = None,
                       output_prefix: str = "optimization_report"):
        """
        Generate comprehensive optimization report.
        
        Args:
            results_file: Path to grid search results JSON file
            wf_results_file: Path to walk-forward results JSON file (optional)
            output_prefix: Output file prefix
        """
        logger.info(f"Generating optimization report from {results_file}")
        
        # Load results
        results = self.load_results(results_file)
        wf_results = None
        if wf_results_file and os.path.exists(wf_results_file):
            wf_results = self.load_results(wf_results_file)
        
        if not results:
            logger.error("No results to generate report")
            return
        
        # Save summary tables
        self.save_summary_tables(results, wf_results, output_prefix)
        
        # Create parameter heatmap data
        heatmap_data = {}
        param_pairs = [
            ('a', 'c'),
            ('a', 'st_factor'),
            ('c', 'st_factor'),
            ('atr_sl_mult', 'atr_rr'),
        ]
        
        for param1, param2 in param_pairs:
            heatmap = self.create_parameter_heatmap_data(results, param1, param2)
            if not heatmap.empty:
                heatmap_data[f"{param1}_vs_{param2}"] = heatmap
        
        # Save heatmap data
        for name, heatmap_df in heatmap_data.items():
            heatmap_file = self.output_dir / f"{output_prefix}_heatmap_{name}.csv"
            heatmap_df.to_csv(heatmap_file)
        
        # Generate text report
        self._generate_text_report(results, wf_results, output_prefix)
        
        logger.info(f"Optimization report generated in {self.output_dir}")
    
    def _generate_text_report(self, results: List[Dict[str, Any]], 
                            wf_results: Optional[List[Dict[str, Any]]],
                            output_prefix: str):
        """Generate text summary report."""
        report_file = self.output_dir / f"{output_prefix}_summary.txt"
        
        with open(report_file, 'w') as f:
            f.write("ATR + SuperTrend Strategy Optimization Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Grid search summary
            f.write("GRID SEARCH RESULTS\n")
            f.write("-" * 20 + "\n")
            f.write(f"Total combinations tested: {len(results)}\n")
            
            if results:
                # Best result
                best_result = max(results, key=lambda x: x.get('metrics', {}).get('profit_factor', 0))
                best_metrics = best_result.get('metrics', {})
                best_params = best_result.get('params', {})
                
                f.write(f"Best result:\n")
                f.write(f"  Symbol: {best_result.get('symbol', '')}\n")
                f.write(f"  Timeframe: {best_result.get('timeframe', '')}\n")
                f.write(f"  Total Return: {best_metrics.get('total_return_pct', 0):.2f}%\n")
                f.write(f"  Profit Factor: {best_metrics.get('profit_factor', 0):.2f}\n")
                f.write(f"  Max Drawdown: {best_metrics.get('max_drawdown_pct', 0):.2f}%\n")
                f.write(f"  Sharpe Ratio: {best_metrics.get('sharpe_ratio', 0):.2f}\n")
                f.write(f"  Parameters: {best_params}\n\n")
                
                # Statistics
                total_returns = [r.get('metrics', {}).get('total_return_pct', 0) for r in results]
                profit_factors = [r.get('metrics', {}).get('profit_factor', 0) for r in results]
                
                f.write(f"Statistics:\n")
                f.write(f"  Average Return: {np.mean(total_returns):.2f}%\n")
                f.write(f"  Average Profit Factor: {np.mean(profit_factors):.2f}\n")
                f.write(f"  Positive Results: {sum(1 for r in total_returns if r > 0)}/{len(total_returns)}\n\n")
            
            # Walk-forward summary
            if wf_results:
                f.write("WALK-FORWARD ANALYSIS\n")
                f.write("-" * 20 + "\n")
                f.write(f"Total windows tested: {len(wf_results)}\n")
                
                # Calculate WF statistics
                wf_returns = [r.get('test_metrics', {}).get('total_return_pct', 0) for r in wf_results]
                wf_pfs = [r.get('test_metrics', {}).get('profit_factor', 0) for r in wf_results]
                
                f.write(f"Average WF Return: {np.mean(wf_returns):.2f}%\n")
                f.write(f"Average WF Profit Factor: {np.mean(wf_pfs):.2f}\n")
                f.write(f"Consistent Windows: {sum(1 for r in wf_returns if r > 0)}/{len(wf_returns)}\n\n")
            
            f.write("Report generated by ATR + SuperTrend Strategy Optimizer\n")


def create_reporter(output_dir: str = "./reports") -> ResultsReporter:
    """
    Create a results reporter instance.
    
    Args:
        output_dir: Output directory for reports
        
    Returns:
        ResultsReporter instance
    """
    return ResultsReporter(output_dir)
