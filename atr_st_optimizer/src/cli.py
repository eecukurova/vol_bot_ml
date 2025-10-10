"""
Command-line interface for ATR + SuperTrend Strategy Optimizer.

This module provides a comprehensive CLI for data fetching, optimization,
walk-forward analysis, and reporting.
"""

import typer
from typing import List, Optional, Dict, Any
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
import json

from config import get_config, validate_coins, validate_timeframes
from data.loader import create_data_loader, validate_symbols
from optimize.grid_search import run_grid_search
from optimize.walk_forward import run_walk_forward
from reporting.reporter import create_reporter
from reporting.plots import create_visualizer

# Initialize Typer app
app = typer.Typer(
    name="atr-optimizer",
    help="ATR + SuperTrend Strategy Optimizer",
    add_completion=False
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_param_string(param_string: str) -> List[Dict[str, Any]]:
    """
    Parse parameter string like 'a=1.5,2.0 c=10,14 st_factor=1.2,1.5'.
    
    Args:
        param_string: Parameter string
        
    Returns:
        List of parameter combinations
    """
    import itertools
    
    # Parse parameter groups
    param_groups = {}
    for group in param_string.split():
        if '=' in group:
            param_name, values_str = group.split('=', 1)
            values = []
            for val in values_str.split(','):
                val = val.strip()
                # Try to convert to appropriate type
                try:
                    if '.' in val:
                        values.append(float(val))
                    else:
                        values.append(int(val))
                except ValueError:
                    values.append(val)
            param_groups[param_name] = values
    
    # Generate all combinations
    param_names = list(param_groups.keys())
    param_values = list(param_groups.values())
    
    combinations = []
    for combo in itertools.product(*param_values):
        combinations.append(dict(zip(param_names, combo)))
    
    return combinations


@app.command()
def fetch(
    coins: str = typer.Option(None, "--coins", "-c", help="Comma-separated list of coins (e.g., BTC/USDT,SOL/USDT)"),
    timeframes: str = typer.Option(None, "--timeframes", "-t", help="Comma-separated list of timeframes (e.g., 15m,1h,4h,1d)"),
    since: str = typer.Option(None, "--since", "-s", help="Start date (YYYY-MM-DD)"),
    until: str = typer.Option(None, "--until", "-u", help="End date (YYYY-MM-DD)"),
    days: int = typer.Option(None, "--days", "-d", help="Number of days of historical data"),
    cache_dir: str = typer.Option(None, "--cache-dir", help="Cache directory"),
    csv_dir: str = typer.Option(None, "--csv", help="CSV fallback directory"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Validate symbols against exchange"),
):
    """
    Fetch OHLCV data for specified coins and timeframes.
    """
    config = get_config()
    
    # Parse inputs
    if coins:
        coin_list = [c.strip() for c in coins.split(",")]
    else:
        coin_list = config.strategy.default_coins
    
    if timeframes:
        timeframe_list = [t.strip() for t in timeframes.split(",")]
    else:
        timeframe_list = config.strategy.default_timeframes
    
    # Validate inputs
    coin_list = validate_coins(coin_list)
    timeframe_list = validate_timeframes(timeframe_list)
    
    if not coin_list:
        typer.echo("Error: No valid coins specified")
        raise typer.Exit(1)
    
    if not timeframe_list:
        typer.echo("Error: No valid timeframes specified")
        raise typer.Exit(1)
    
    # Calculate date range
    if since:
        start_date = datetime.strptime(since, "%Y-%m-%d")
    elif days:
        start_date = datetime.now() - timedelta(days=days)
    else:
        start_date = datetime.now() - timedelta(days=config.strategy.history_days)
    
    if until:
        end_date = datetime.strptime(until, "%Y-%m-%d")
    else:
        end_date = datetime.now()
    
    typer.echo(f"Fetching data for {len(coin_list)} coins and {len(timeframe_list)} timeframes")
    typer.echo(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Validate symbols if requested
    if validate:
        typer.echo("Validating symbols against exchange...")
        valid_coins = validate_symbols(coin_list)
        if len(valid_coins) != len(coin_list):
            typer.echo(f"Warning: {len(coin_list) - len(valid_coins)} invalid symbols removed")
        coin_list = valid_coins
    
    if not coin_list:
        typer.echo("Error: No valid coins after validation")
        raise typer.Exit(1)
    
    # Create data loader
    loader = create_data_loader(cache_dir)
    
    if csv_dir:
        loader.set_csv_fallback(csv_dir)
        typer.echo(f"CSV fallback directory set to: {csv_dir}")
    
    # Fetch data
    total_combinations = len(coin_list) * len(timeframe_list)
    typer.echo(f"Fetching {total_combinations} combinations...")
    
    success_count = 0
    for coin in coin_list:
        for timeframe in timeframe_list:
            try:
                typer.echo(f"Fetching {coin} {timeframe}...")
                data = loader.get_ohlcv(coin, timeframe, start_date, end_date)
                
                if not data.empty:
                    typer.echo(f"  ✓ {len(data)} candles loaded")
                    success_count += 1
                else:
                    typer.echo(f"  ✗ No data available")
                    
            except Exception as e:
                typer.echo(f"  ✗ Error: {e}")
    
    typer.echo(f"\nData fetching completed: {success_count}/{total_combinations} successful")
    
    # Show cache info
    cache_info = loader.get_data_info()
    if cache_info.get('cache_info'):
        typer.echo(f"Cache info: {cache_info['cache_info']['total_files']} files, "
                  f"{cache_info['cache_info']['total_size_mb']:.1f} MB")


@app.command()
def optimize(
    coins: str = typer.Option(None, "--coins", "-c", help="Comma-separated list of coins"),
    timeframes: str = typer.Option(None, "--timeframes", "-t", help="Comma-separated list of timeframes"),
    jobs: int = typer.Option(None, "--jobs", "-j", help="Number of parallel jobs"),
    parallel: bool = typer.Option(True, "--parallel/--no-parallel", help="Use parallel processing"),
    output_dir: str = typer.Option(None, "--out", "-o", help="Output directory"),
    cache_dir: str = typer.Option(None, "--cache-dir", help="Cache directory"),
    csv_dir: str = typer.Option(None, "--csv", help="CSV fallback directory"),
    param_file: str = typer.Option(None, "--params", "-p", help="JSON file with custom parameters"),
    param_string: str = typer.Option(None, "--param-string", help="Parameter string like 'a=1.5,2.0 c=10,14'"),
):
    """
    Run grid search optimization.
    """
    config = get_config()
    
    # Parse inputs
    if coins:
        coin_list = [c.strip() for c in coins.split(",")]
    else:
        coin_list = config.strategy.default_coins
    
    if timeframes:
        timeframe_list = [t.strip() for t in timeframes.split(",")]
    else:
        timeframe_list = config.strategy.default_timeframes
    
    if jobs is None:
        jobs = config.optimization.default_jobs
    
    if output_dir is None:
        output_dir = "./reports/grid"
    
    # Validate inputs
    coin_list = validate_coins(coin_list)
    timeframe_list = validate_timeframes(timeframe_list)
    
    if not coin_list or not timeframe_list:
        typer.echo("Error: Invalid coins or timeframes")
        raise typer.Exit(1)
    
    # Load custom parameters if provided
    param_combinations = None
    if param_file:
        try:
            with open(param_file, 'r') as f:
                param_data = json.load(f)
            param_combinations = param_data.get('combinations', [])
            typer.echo(f"Loaded {len(param_combinations)} custom parameter combinations")
        except Exception as e:
            typer.echo(f"Error loading parameter file: {e}")
            raise typer.Exit(1)
    elif param_string:
        try:
            param_combinations = parse_param_string(param_string)
            typer.echo(f"Parsed {len(param_combinations)} parameter combinations from string")
        except Exception as e:
            typer.echo(f"Error parsing parameter string: {e}")
            raise typer.Exit(1)
    
    typer.echo(f"Starting grid search optimization...")
    typer.echo(f"Coins: {coin_list}")
    typer.echo(f"Timeframes: {timeframe_list}")
    typer.echo(f"Jobs: {jobs}")
    typer.echo(f"Parallel: {parallel}")
    typer.echo(f"Output: {output_dir}")
    
    # Create data loader
    loader = create_data_loader(cache_dir)
    if csv_dir:
        loader.set_csv_fallback(csv_dir)
    
    # Run optimization
    try:
        results = run_grid_search(
            symbols=coin_list,
            timeframes=timeframe_list,
            param_combinations=param_combinations,
            max_workers=jobs,
            parallel=parallel,
            output_dir=output_dir
        )
        
        typer.echo(f"\nOptimization completed!")
        typer.echo(f"Total results: {len(results)}")
        
        if results:
            # Show top 5 results
            sorted_results = sorted(results, key=lambda x: x.get('metrics', {}).get('profit_factor', 0), reverse=True)
            typer.echo(f"\nTop 5 results:")
            for i, result in enumerate(sorted_results[:5]):
                metrics = result.get('metrics', {})
                typer.echo(f"{i+1}. {result.get('symbol', '')} {result.get('timeframe', '')} - "
                          f"PF: {metrics.get('profit_factor', 0):.2f}, "
                          f"Return: {metrics.get('total_return_pct', 0):.2f}%, "
                          f"DD: {metrics.get('max_drawdown_pct', 0):.2f}%")
        
    except Exception as e:
        typer.echo(f"Error during optimization: {e}")
        raise typer.Exit(1)


@app.command()
def walk_forward(
    coins: str = typer.Option(None, "--coins", "-c", help="Comma-separated list of coins"),
    timeframes: str = typer.Option(None, "--timeframes", "-t", help="Comma-separated list of timeframes"),
    scheme: str = typer.Option(None, "--scheme", help="WF scheme: rolling or expanding"),
    train_steps: int = typer.Option(None, "--train-steps", help="Number of training windows"),
    train_window: str = typer.Option(None, "--train-window", help="Training window size (e.g., 90d)"),
    test_window: str = typer.Option(None, "--test-window", help="Test window size (e.g., 30d)"),
    output_dir: str = typer.Option(None, "--out", "-o", help="Output directory"),
    cache_dir: str = typer.Option(None, "--cache-dir", help="Cache directory"),
    csv_dir: str = typer.Option(None, "--csv", help="CSV fallback directory"),
    param_file: str = typer.Option(None, "--params", "-p", help="JSON file with custom parameters"),
):
    """
    Run walk-forward analysis.
    """
    config = get_config()
    
    # Parse inputs
    if coins:
        coin_list = [c.strip() for c in coins.split(",")]
    else:
        coin_list = config.strategy.default_coins
    
    if timeframes:
        timeframe_list = [t.strip() for t in timeframes.split(",")]
    else:
        timeframe_list = config.strategy.default_timeframes
    
    if scheme is None:
        scheme = config.optimization.wf_scheme
    
    if train_steps is None:
        train_steps = config.optimization.train_windows
    
    if train_window:
        train_window_days = int(train_window.replace('d', ''))
    else:
        train_window_days = config.optimization.train_window_days
    
    if test_window:
        test_window_days = int(test_window.replace('d', ''))
    else:
        test_window_days = config.optimization.test_window_days
    
    if output_dir is None:
        output_dir = "./reports/wf"
    
    # Validate inputs
    coin_list = validate_coins(coin_list)
    timeframe_list = validate_timeframes(timeframe_list)
    
    if not coin_list or not timeframe_list:
        typer.echo("Error: Invalid coins or timeframes")
        raise typer.Exit(1)
    
    if scheme not in ['rolling', 'expanding']:
        typer.echo("Error: Scheme must be 'rolling' or 'expanding'")
        raise typer.Exit(1)
    
    # Load custom parameters if provided
    param_combinations = None
    if param_file:
        try:
            with open(param_file, 'r') as f:
                param_data = json.load(f)
            param_combinations = param_data.get('combinations', [])
            typer.echo(f"Loaded {len(param_combinations)} custom parameter combinations")
        except Exception as e:
            typer.echo(f"Error loading parameter file: {e}")
            raise typer.Exit(1)
    
    typer.echo(f"Starting walk-forward analysis...")
    typer.echo(f"Coins: {coin_list}")
    typer.echo(f"Timeframes: {timeframe_list}")
    typer.echo(f"Scheme: {scheme}")
    typer.echo(f"Train windows: {train_steps}")
    typer.echo(f"Train window: {train_window_days} days")
    typer.echo(f"Test window: {test_window_days} days")
    typer.echo(f"Output: {output_dir}")
    
    # Create data loader
    loader = create_data_loader(cache_dir)
    if csv_dir:
        loader.set_csv_fallback(csv_dir)
    
    # Run walk-forward analysis
    try:
        results = run_walk_forward(
            symbols=coin_list,
            timeframes=timeframe_list,
            param_combinations=param_combinations,
            output_dir=output_dir
        )
        
        typer.echo(f"\nWalk-forward analysis completed!")
        typer.echo(f"Total windows: {len(results)}")
        
        if results:
            # Calculate summary statistics
            test_returns = [r.get('test_metrics', {}).get('total_return_pct', 0) for r in results]
            test_pfs = [r.get('test_metrics', {}).get('profit_factor', 0) for r in results]
            
            typer.echo(f"\nSummary:")
            typer.echo(f"Average test return: {sum(test_returns)/len(test_returns):.2f}%")
            typer.echo(f"Average test profit factor: {sum(test_pfs)/len(test_pfs):.2f}")
            typer.echo(f"Positive windows: {sum(1 for r in test_returns if r > 0)}/{len(test_returns)}")
        
    except Exception as e:
        typer.echo(f"Error during walk-forward analysis: {e}")
        raise typer.Exit(1)


@app.command()
def report(
    input_dir: str = typer.Option(None, "--in", "-i", help="Input directory with results"),
    top: int = typer.Option(10, "--top", "-t", help="Number of top results to show"),
    output_dir: str = typer.Option(None, "--out", "-o", help="Output directory for reports"),
    plots: bool = typer.Option(True, "--plots/--no-plots", help="Generate plots"),
    interactive: bool = typer.Option(False, "--interactive/--no-interactive", help="Show interactive plots"),
):
    """
    Generate reports and visualizations from optimization results.
    """
    if input_dir is None:
        input_dir = "./reports/grid"
    
    if output_dir is None:
        output_dir = "./reports"
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        typer.echo(f"Error: Input directory {input_dir} does not exist")
        raise typer.Exit(1)
    
    typer.echo(f"Generating reports from {input_dir}")
    typer.echo(f"Output directory: {output_dir}")
    typer.echo(f"Top results: {top}")
    typer.echo(f"Generate plots: {plots}")
    
    # Find results files
    results_file = input_path / "grid_search_results.json"
    wf_results_file = input_path / "walk_forward_results.json"
    
    if not results_file.exists():
        typer.echo(f"Error: Results file {results_file} not found")
        raise typer.Exit(1)
    
    # Load results
    try:
        with open(results_file, 'r') as f:
            results = json.load(f)
        typer.echo(f"Loaded {len(results)} grid search results")
    except Exception as e:
        typer.echo(f"Error loading results: {e}")
        raise typer.Exit(1)
    
    wf_results = None
    if wf_results_file.exists():
        try:
            with open(wf_results_file, 'r') as f:
                wf_results = json.load(f)
            typer.echo(f"Loaded {len(wf_results)} walk-forward results")
        except Exception as e:
            typer.echo(f"Warning: Could not load walk-forward results: {e}")
    
    # Generate reports
    try:
        reporter = create_reporter(str(output_path))
        reporter.save_summary_tables(results, wf_results, "optimization_report")
        typer.echo("Summary tables generated")
        
        if plots:
            visualizer = create_visualizer(str(output_path))
            visualizer.save_all_plots(results, wf_results, "optimization_plots")
            typer.echo("Plots generated")
        
        # Show top results
        sorted_results = sorted(results, key=lambda x: x.get('metrics', {}).get('profit_factor', 0), reverse=True)
        typer.echo(f"\nTop {top} results:")
        for i, result in enumerate(sorted_results[:top]):
            metrics = result.get('metrics', {})
            typer.echo(f"{i+1}. {result.get('symbol', '')} {result.get('timeframe', '')} - "
                      f"PF: {metrics.get('profit_factor', 0):.2f}, "
                      f"Return: {metrics.get('total_return_pct', 0):.2f}%, "
                      f"DD: {metrics.get('max_drawdown_pct', 0):.2f}%, "
                      f"Trades: {metrics.get('num_trades', 0)}")
        
        typer.echo(f"\nReports generated successfully in {output_dir}")
        
    except Exception as e:
        typer.echo(f"Error generating reports: {e}")
        raise typer.Exit(1)


@app.command()
def config_info():
    """
    Show current configuration.
    """
    config = get_config()
    
    typer.echo("Current Configuration:")
    typer.echo("=" * 30)
    
    typer.echo(f"Exchange: {config.data.exchange}")
    typer.echo(f"Cache directory: {config.data.cache_dir}")
    typer.echo(f"Sandbox mode: {config.data.sandbox_mode}")
    
    typer.echo(f"\nDefault coins: {config.strategy.default_coins}")
    typer.echo(f"Default timeframes: {config.strategy.default_timeframes}")
    typer.echo(f"History days: {config.strategy.history_days}")
    typer.echo(f"Fee (bps): {config.strategy.fee_bps}")
    typer.echo(f"Slippage (bps): {config.strategy.slippage_bps}")
    
    typer.echo(f"\nParameter space:")
    for param, values in config.strategy.param_space.items():
        typer.echo(f"  {param}: {values}")
    
    typer.echo(f"\nOptimization settings:")
    typer.echo(f"  Default jobs: {config.optimization.default_jobs}")
    typer.echo(f"  Top N results: {config.optimization.top_n_results}")
    typer.echo(f"  WF scheme: {config.optimization.wf_scheme}")
    typer.echo(f"  Train windows: {config.optimization.train_windows}")
    typer.echo(f"  Train window days: {config.optimization.train_window_days}")
    typer.echo(f"  Test window days: {config.optimization.test_window_days}")


@app.command()
def clear_cache(
    cache_dir: str = typer.Option(None, "--cache-dir", help="Cache directory"),
    symbol: str = typer.Option(None, "--symbol", help="Specific symbol to clear"),
    timeframe: str = typer.Option(None, "--timeframe", help="Specific timeframe to clear"),
):
    """
    Clear cached data.
    """
    config = get_config()
    
    if cache_dir is None:
        cache_dir = config.data.cache_dir
    
    typer.echo(f"Clearing cache in {cache_dir}")
    
    try:
        loader = create_data_loader(cache_dir)
        loader.clear_cache(symbol, timeframe)
        
        if symbol and timeframe:
            typer.echo(f"Cleared cache for {symbol} {timeframe}")
        else:
            typer.echo("Cleared all cache")
            
    except Exception as e:
        typer.echo(f"Error clearing cache: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
