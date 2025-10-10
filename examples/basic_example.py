#!/usr/bin/env python3
"""
Example script: Basic strategy testing and optimization.

This script demonstrates how to use the ATR + SuperTrend Strategy Optimizer
for basic strategy testing and parameter optimization.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from atr_st_optimizer import (
    create_data_loader,
    create_strategy,
    run_backtest,
    run_grid_search,
    create_reporter,
    create_visualizer
)


def main():
    """Main example function."""
    print("ATR + SuperTrend Strategy Optimizer - Example Script")
    print("=" * 60)
    
    # Configuration
    symbols = ['BTC/USDT', 'ETH/USDT']
    timeframes = ['1h', '4h']
    days = 90  # Use 90 days for faster testing
    
    print(f"Testing symbols: {symbols}")
    print(f"Timeframes: {timeframes}")
    print(f"History: {days} days")
    print()
    
    # 1. Load data
    print("1. Loading data...")
    loader = create_data_loader()
    
    data_results = {}
    for symbol in symbols:
        for timeframe in timeframes:
            print(f"   Loading {symbol} {timeframe}...")
            data = loader.get_ohlcv(symbol, timeframe, days=days)
            if not data.empty:
                data_results[f"{symbol}_{timeframe}"] = data
                print(f"   ✓ Loaded {len(data)} candles")
            else:
                print(f"   ✗ No data available")
    
    if not data_results:
        print("Error: No data loaded. Please check your configuration.")
        return
    
    print(f"Loaded data for {len(data_results)} symbol/timeframe combinations")
    print()
    
    # 2. Test single strategy
    print("2. Testing single strategy...")
    test_params = {
        'a': 2.0,
        'c': 10,
        'st_factor': 1.5,
        'min_delay_m': 60,
        'atr_sl_mult': 2.0,
        'atr_rr': 2.0,
    }
    
    strategy = create_strategy(test_params)
    
    # Test on first available data
    first_key = list(data_results.keys())[0]
    test_data = data_results[first_key]
    
    print(f"   Testing on {first_key}...")
    signals = strategy.run_strategy(test_data)
    result = run_backtest(test_data, signals)
    
    print(f"   Results:")
    print(f"     Total Return: {result.metrics['total_return_pct']:.2f}%")
    print(f"     Profit Factor: {result.metrics['profit_factor']:.2f}")
    print(f"     Max Drawdown: {result.metrics['max_drawdown_pct']:.2f}%")
    print(f"     Sharpe Ratio: {result.metrics['sharpe_ratio']:.2f}")
    print(f"     Number of Trades: {result.metrics['num_trades']}")
    print()
    
    # 3. Run grid search optimization
    print("3. Running grid search optimization...")
    
    # Define smaller parameter space for example
    param_combinations = [
        {'a': 1.5, 'c': 10, 'st_factor': 1.2, 'min_delay_m': 30, 'atr_sl_mult': 1.5, 'atr_rr': 2.0},
        {'a': 2.0, 'c': 10, 'st_factor': 1.5, 'min_delay_m': 60, 'atr_sl_mult': 2.0, 'atr_rr': 2.0},
        {'a': 2.5, 'c': 14, 'st_factor': 1.5, 'min_delay_m': 60, 'atr_sl_mult': 2.0, 'atr_rr': 2.5},
        {'a': 2.0, 'c': 20, 'st_factor': 2.0, 'min_delay_m': 120, 'atr_sl_mult': 2.5, 'atr_rr': 3.0},
    ]
    
    print(f"   Testing {len(param_combinations)} parameter combinations...")
    
    # Run optimization
    results = run_grid_search(
        symbols=symbols,
        timeframes=timeframes,
        param_combinations=param_combinations,
        max_workers=2,  # Use 2 workers for example
        parallel=True,
        output_dir='./reports/example'
    )
    
    print(f"   Optimization completed: {len(results)} results")
    print()
    
    # 4. Analyze results
    print("4. Analyzing results...")
    
    if results:
        # Find best result
        best_result = max(results, key=lambda x: x['metrics']['profit_factor'])
        
        print(f"   Best Result:")
        print(f"     Symbol: {best_result['symbol']}")
        print(f"     Timeframe: {best_result['timeframe']}")
        print(f"     Parameters: {best_result['params']}")
        print(f"     Profit Factor: {best_result['metrics']['profit_factor']:.2f}")
        print(f"     Total Return: {best_result['metrics']['total_return_pct']:.2f}%")
        print(f"     Max Drawdown: {best_result['metrics']['max_drawdown_pct']:.2f}%")
        print(f"     Sharpe Ratio: {best_result['metrics']['sharpe_ratio']:.2f}")
        print(f"     Number of Trades: {best_result['metrics']['num_trades']}")
        print()
        
        # Show top 5 results
        sorted_results = sorted(results, key=lambda x: x['metrics']['profit_factor'], reverse=True)
        print(f"   Top 5 Results:")
        for i, result in enumerate(sorted_results[:5]):
            print(f"     {i+1}. {result['symbol']} {result['timeframe']} - "
                  f"PF: {result['metrics']['profit_factor']:.2f}, "
                  f"Return: {result['metrics']['total_return_pct']:.2f}%, "
                  f"DD: {result['metrics']['max_drawdown_pct']:.2f}%")
        print()
        
        # 5. Generate reports
        print("5. Generating reports...")
        
        try:
            reporter = create_reporter('./reports/example')
            reporter.save_summary_tables(results, filename_prefix='example')
            print("   ✓ Summary tables generated")
            
            visualizer = create_visualizer('./reports/example')
            visualizer.save_all_plots(results, filename_prefix='example')
            print("   ✓ Plots generated")
            
        except Exception as e:
            print(f"   ✗ Error generating reports: {e}")
    
    print()
    print("Example completed successfully!")
    print("Check the './reports/example' directory for results and visualizations.")


if __name__ == "__main__":
    main()
