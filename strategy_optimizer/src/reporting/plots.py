"""
Visualization module for optimization results.

This module provides comprehensive plotting functionality for equity curves,
drawdown charts, parameter heatmaps, and other visualizations.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, Any, List, Optional, Tuple
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Set matplotlib style
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class ResultsVisualizer:
    """
    Visualizer for optimization results.
    """
    
    def __init__(self, output_dir: str = "./reports", dpi: int = 300):
        """
        Initialize visualizer.
        
        Args:
            output_dir: Output directory for plots
            dpi: DPI for saved plots
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = dpi
        
        # Set up matplotlib
        plt.rcParams['figure.figsize'] = (12, 8)
        plt.rcParams['figure.dpi'] = dpi
        plt.rcParams['savefig.dpi'] = dpi
        plt.rcParams['font.size'] = 10
    
    def plot_equity_curve(self, equity_curve: pd.Series, title: str = "Equity Curve",
                          save_path: Optional[str] = None) -> None:
        """
        Plot equity curve.
        
        Args:
            equity_curve: Equity curve series
            title: Plot title
            save_path: Path to save plot
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot equity curve
        ax.plot(equity_curve.index, equity_curve.values, linewidth=2, color='blue')
        ax.fill_between(equity_curve.index, equity_curve.values, alpha=0.3, color='blue')
        
        # Formatting
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Equity', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.xticks(rotation=45)
        
        # Add performance metrics
        total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0] * 100
        ax.text(0.02, 0.98, f'Total Return: {total_return:.2f}%', 
                transform=ax.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"Equity curve saved to {save_path}")
        
        plt.show()
    
    def plot_drawdown(self, equity_curve: pd.Series, title: str = "Drawdown Chart",
                     save_path: Optional[str] = None) -> None:
        """
        Plot drawdown chart.
        
        Args:
            equity_curve: Equity curve series
            title: Plot title
            save_path: Path to save plot
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Calculate drawdown
        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak * 100
        
        # Plot drawdown
        ax.fill_between(drawdown.index, drawdown.values, 0, alpha=0.7, color='red')
        ax.plot(drawdown.index, drawdown.values, linewidth=1, color='darkred')
        
        # Formatting
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.xticks(rotation=45)
        
        # Add max drawdown
        max_dd = drawdown.min()
        ax.text(0.02, 0.02, f'Max Drawdown: {max_dd:.2f}%', 
                transform=ax.transAxes, verticalalignment='bottom',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"Drawdown chart saved to {save_path}")
        
        plt.show()
    
    def plot_equity_and_drawdown(self, equity_curve: pd.Series, 
                                title: str = "Equity Curve & Drawdown",
                                save_path: Optional[str] = None) -> None:
        """
        Plot equity curve and drawdown together.
        
        Args:
            equity_curve: Equity curve series
            title: Plot title
            save_path: Path to save plot
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        
        # Calculate drawdown
        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak * 100
        
        # Plot equity curve
        ax1.plot(equity_curve.index, equity_curve.values, linewidth=2, color='blue')
        ax1.fill_between(equity_curve.index, equity_curve.values, alpha=0.3, color='blue')
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.set_ylabel('Equity', fontsize=12)
        ax1.grid(True, alpha=0.3)
        
        # Add performance metrics
        total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0] * 100
        ax1.text(0.02, 0.98, f'Total Return: {total_return:.2f}%', 
                transform=ax1.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Plot drawdown
        ax2.fill_between(drawdown.index, drawdown.values, 0, alpha=0.7, color='red')
        ax2.plot(drawdown.index, drawdown.values, linewidth=1, color='darkred')
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylabel('Drawdown (%)', fontsize=12)
        ax2.grid(True, alpha=0.3)
        
        # Add max drawdown
        max_dd = drawdown.min()
        ax2.text(0.02, 0.02, f'Max Drawdown: {max_dd:.2f}%', 
                transform=ax2.transAxes, verticalalignment='bottom',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Format x-axis dates
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"Equity and drawdown plot saved to {save_path}")
        
        plt.show()
    
    def plot_parameter_heatmap(self, results: List[Dict[str, Any]], 
                              param1: str, param2: str, metric: str = 'profit_factor',
                              title: Optional[str] = None, save_path: Optional[str] = None) -> None:
        """
        Plot parameter heatmap.
        
        Args:
            results: List of optimization results
            param1: First parameter for heatmap
            param2: Second parameter for heatmap
            metric: Metric to display in heatmap
            title: Plot title
            save_path: Path to save plot
        """
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
            logger.warning(f"No data available for heatmap {param1} vs {param2}")
            return
        
        df = pd.DataFrame(heatmap_data)
        
        # Create pivot table
        pivot = df.pivot_table(
            values=metric,
            index=param1,
            columns=param2,
            aggfunc='mean'
        )
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=(10, 8))
        
        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn', 
                   center=0, ax=ax, cbar_kws={'label': metric})
        
        if title is None:
            title = f"{metric.title()} Heatmap: {param1} vs {param2}"
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(param2, fontsize=12)
        ax.set_ylabel(param1, fontsize=12)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"Parameter heatmap saved to {save_path}")
        
        plt.show()
    
    def plot_metric_distribution(self, results: List[Dict[str, Any]], 
                               metric: str, title: Optional[str] = None,
                               save_path: Optional[str] = None) -> None:
        """
        Plot distribution of a metric across all results.
        
        Args:
            results: List of optimization results
            metric: Metric to plot
            title: Plot title
            save_path: Path to save plot
        """
        # Extract metric values
        values = []
        for result in results:
            metrics = result.get('metrics', {})
            if metric in metrics:
                values.append(metrics[metric])
        
        if not values:
            logger.warning(f"No data available for metric {metric}")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Histogram
        ax1.hist(values, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
        ax1.set_xlabel(metric, fontsize=12)
        ax1.set_ylabel('Frequency', fontsize=12)
        ax1.set_title(f'{metric} Distribution', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Box plot
        ax2.boxplot(values, patch_artist=True, boxprops=dict(facecolor='lightblue'))
        ax2.set_ylabel(metric, fontsize=12)
        ax2.set_title(f'{metric} Box Plot', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # Add statistics
        mean_val = np.mean(values)
        median_val = np.median(values)
        std_val = np.std(values)
        
        ax1.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.2f}')
        ax1.axvline(median_val, color='green', linestyle='--', linewidth=2, label=f'Median: {median_val:.2f}')
        ax1.legend()
        
        ax2.text(0.02, 0.98, f'Mean: {mean_val:.2f}\nMedian: {median_val:.2f}\nStd: {std_val:.2f}', 
                transform=ax2.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        if title:
            fig.suptitle(title, fontsize=16, fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"Metric distribution plot saved to {save_path}")
        
        plt.show()
    
    def plot_top_results_comparison(self, results: List[Dict[str, Any]], 
                                  top_n: int = 10, metric: str = 'profit_factor',
                                  save_path: Optional[str] = None) -> None:
        """
        Plot comparison of top N results.
        
        Args:
            results: List of optimization results
            top_n: Number of top results to compare
            metric: Metric to sort by
            save_path: Path to save plot
        """
        # Sort and get top results
        sorted_results = sorted(results, key=lambda x: x.get('metrics', {}).get(metric, 0), reverse=True)
        top_results = sorted_results[:top_n]
        
        if not top_results:
            logger.warning("No results to plot")
            return
        
        # Extract data
        labels = []
        returns = []
        profit_factors = []
        drawdowns = []
        
        for i, result in enumerate(top_results):
            symbol = result.get('symbol', '')
            timeframe = result.get('timeframe', '')
            metrics = result.get('metrics', {})
            
            labels.append(f"{symbol}\n{timeframe}")
            returns.append(metrics.get('total_return_pct', 0))
            profit_factors.append(metrics.get('profit_factor', 0))
            drawdowns.append(abs(metrics.get('max_drawdown_pct', 0)))
        
        # Create subplots
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
        
        # Total Return
        bars1 = ax1.bar(range(len(labels)), returns, color='green', alpha=0.7)
        ax1.set_title('Total Return (%)', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Return (%)', fontsize=12)
        ax1.set_xticks(range(len(labels)))
        ax1.set_xticklabels(labels, rotation=45, ha='right')
        ax1.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar, value in zip(bars1, returns):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                    f'{value:.1f}', ha='center', va='bottom')
        
        # Profit Factor
        bars2 = ax2.bar(range(len(labels)), profit_factors, color='blue', alpha=0.7)
        ax2.set_title('Profit Factor', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Profit Factor', fontsize=12)
        ax2.set_xticks(range(len(labels)))
        ax2.set_xticklabels(labels, rotation=45, ha='right')
        ax2.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar, value in zip(bars2, profit_factors):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, 
                    f'{value:.2f}', ha='center', va='bottom')
        
        # Max Drawdown
        bars3 = ax3.bar(range(len(labels)), drawdowns, color='red', alpha=0.7)
        ax3.set_title('Max Drawdown (%)', fontsize=14, fontweight='bold')
        ax3.set_ylabel('Drawdown (%)', fontsize=12)
        ax3.set_xticks(range(len(labels)))
        ax3.set_xticklabels(labels, rotation=45, ha='right')
        ax3.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar, value in zip(bars3, drawdowns):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                    f'{value:.1f}', ha='center', va='bottom')
        
        plt.suptitle(f'Top {top_n} Results Comparison (Sorted by {metric})', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"Top results comparison plot saved to {save_path}")
        
        plt.show()
    
    def plot_walk_forward_results(self, wf_results: List[Dict[str, Any]], 
                                 symbol: str, timeframe: str,
                                 save_path: Optional[str] = None) -> None:
        """
        Plot walk-forward analysis results.
        
        Args:
            wf_results: List of walk-forward results
            symbol: Symbol to plot
            timeframe: Timeframe to plot
            save_path: Path to save plot
        """
        # Filter results for specific symbol/timeframe
        filtered_results = [
            r for r in wf_results 
            if r.get('symbol') == symbol and r.get('timeframe') == timeframe
        ]
        
        if not filtered_results:
            logger.warning(f"No walk-forward results found for {symbol} {timeframe}")
            return
        
        # Extract data
        window_ids = [r['window_id'] for r in filtered_results]
        train_returns = [r['train_metrics'].get('profit_factor', 0) for r in filtered_results]
        test_returns = [r['test_metrics'].get('total_return_pct', 0) for r in filtered_results]
        test_pfs = [r['test_metrics'].get('profit_factor', 0) for r in filtered_results]
        
        # Create subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Train vs Test Performance
        x = np.arange(len(window_ids))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, train_returns, width, label='Train PF', alpha=0.7)
        bars2 = ax1.bar(x + width/2, test_pfs, width, label='Test PF', alpha=0.7)
        
        ax1.set_title(f'Walk-Forward Analysis: {symbol} {timeframe}', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Profit Factor', fontsize=12)
        ax1.set_xlabel('Window', fontsize=12)
        ax1.set_xticks(x)
        ax1.set_xticklabels([f'W{i}' for i in window_ids])
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Test Returns
        colors = ['green' if r > 0 else 'red' for r in test_returns]
        bars3 = ax2.bar(x, test_returns, color=colors, alpha=0.7)
        
        ax2.set_title('Test Period Returns', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Return (%)', fontsize=12)
        ax2.set_xlabel('Window', fontsize=12)
        ax2.set_xticks(x)
        ax2.set_xticklabels([f'W{i}' for i in window_ids])
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        
        # Add value labels
        for bar, value in zip(bars3, test_returns):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (0.5 if value > 0 else -0.5), 
                    f'{value:.1f}%', ha='center', va='bottom' if value > 0 else 'top')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"Walk-forward results plot saved to {save_path}")
        
        plt.show()
    
    def create_interactive_plotly_chart(self, results: List[Dict[str, Any]], 
                                     metric: str = 'profit_factor') -> go.Figure:
        """
        Create interactive Plotly chart for results.
        
        Args:
            results: List of optimization results
            metric: Metric to plot
            
        Returns:
            Plotly figure
        """
        # Extract data
        symbols = [r.get('symbol', '') for r in results]
        timeframes = [r.get('timeframe', '') for r in results]
        values = [r.get('metrics', {}).get(metric, 0) for r in results]
        
        # Create hover text
        hover_text = []
        for result in results:
            params = result.get('params', {})
            metrics = result.get('metrics', {})
            
            text = f"Symbol: {result.get('symbol', '')}<br>"
            text += f"Timeframe: {result.get('timeframe', '')}<br>"
            text += f"{metric}: {metrics.get(metric, 0):.2f}<br>"
            text += f"Total Return: {metrics.get('total_return_pct', 0):.2f}%<br>"
            text += f"Max DD: {metrics.get('max_drawdown_pct', 0):.2f}%<br>"
            text += f"Parameters: {params}"
            hover_text.append(text)
        
        # Create scatter plot
        fig = go.Figure(data=go.Scatter(
            x=symbols,
            y=timeframes,
            mode='markers',
            marker=dict(
                size=values,
                sizemode='diameter',
                sizeref=2.*max(values)/(40.**2),
                sizemin=4,
                color=values,
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title=metric)
            ),
            text=hover_text,
            hovertemplate='%{text}<extra></extra>'
        ))
        
        fig.update_layout(
            title=f'{metric.title()} by Symbol and Timeframe',
            xaxis_title='Symbol',
            yaxis_title='Timeframe',
            width=800,
            height=600
        )
        
        return fig
    
    def save_all_plots(self, results: List[Dict[str, Any]], 
                      wf_results: Optional[List[Dict[str, Any]]] = None,
                      filename_prefix: str = "plots"):
        """
        Generate and save all standard plots.
        
        Args:
            results: Grid search results
            wf_results: Walk-forward results (optional)
            filename_prefix: Filename prefix
        """
        logger.info("Generating all standard plots")
        
        # Parameter heatmaps
        param_pairs = [
            ('a', 'c', 'ATR Sensitivity vs ATR Period'),
            ('a', 'st_factor', 'ATR Sensitivity vs SuperTrend Factor'),
            ('c', 'st_factor', 'ATR Period vs SuperTrend Factor'),
            ('atr_sl_mult', 'atr_rr', 'SL Multiplier vs Risk-Reward Ratio'),
        ]
        
        for param1, param2, title in param_pairs:
            try:
                save_path = self.output_dir / f"{filename_prefix}_heatmap_{param1}_vs_{param2}.png"
                self.plot_parameter_heatmap(results, param1, param2, title=title, save_path=str(save_path))
            except Exception as e:
                logger.error(f"Failed to create heatmap {param1} vs {param2}: {e}")
        
        # Metric distributions
        metrics = ['profit_factor', 'total_return_pct', 'max_drawdown_pct', 'sharpe_ratio']
        for metric in metrics:
            try:
                save_path = self.output_dir / f"{filename_prefix}_distribution_{metric}.png"
                self.plot_metric_distribution(results, metric, save_path=str(save_path))
            except Exception as e:
                logger.error(f"Failed to create distribution plot for {metric}: {e}")
        
        # Top results comparison
        try:
            save_path = self.output_dir / f"{filename_prefix}_top_results_comparison.png"
            self.plot_top_results_comparison(results, top_n=15, save_path=str(save_path))
        except Exception as e:
            logger.error(f"Failed to create top results comparison: {e}")
        
        # Walk-forward plots
        if wf_results:
            # Group by symbol/timeframe
            grouped = {}
            for result in wf_results:
                key = f"{result.get('symbol', '')}_{result.get('timeframe', '')}"
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(result)
            
            # Plot for each symbol/timeframe
            for key, group_results in list(grouped.items())[:5]:  # Limit to first 5
                try:
                    symbol, timeframe = key.split('_', 1)
                    save_path = self.output_dir / f"{filename_prefix}_wf_{symbol}_{timeframe}.png"
                    self.plot_walk_forward_results(wf_results, symbol, timeframe, save_path=str(save_path))
                except Exception as e:
                    logger.error(f"Failed to create walk-forward plot for {key}: {e}")
        
        logger.info(f"All plots saved to {self.output_dir}")


def create_visualizer(output_dir: str = "./reports", dpi: int = 300) -> ResultsVisualizer:
    """
    Create a results visualizer instance.
    
    Args:
        output_dir: Output directory for plots
        dpi: DPI for saved plots
        
    Returns:
        ResultsVisualizer instance
    """
    return ResultsVisualizer(output_dir, dpi)
