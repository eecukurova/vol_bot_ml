#!/usr/bin/env python3
"""
Complete workflow demonstration script.

This script demonstrates the complete workflow of the ATR + SuperTrend Strategy Optimizer:
1. Data fetching
2. Strategy testing
3. Grid search optimization
4. Walk-forward analysis
5. Report generation
"""

import sys
import os
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from atr_st_optimizer import (
    create_data_loader,
    create_strategy,
    run_backtest,
    run_grid_search,
    run_walk_forward,
    create_reporter,
    create_visualizer
)


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_step(step_num, title):
    """Print a formatted step header."""
    print(f"\n{step_num}. {title}")
    print("-" * 40)


def main():
    """Main demonstration function."""
    print("ATR + SuperTrend Strategy Optimizer - Complete Workflow Demo")
    print("=" * 70)
    print("This script demonstrates the complete workflow:")
    print("1. Data fetching and caching")
    print("2. Single strategy testing")
    print("3. Grid search optimization")
    print("4. Walk-forward analysis")
    print("5. Report generation and visualization")
    
    start_time = time.time()
    
    # Configuration
    symbols = ['BTC/USDT', 'ETH/USDT']
    timeframes = ['1h', '4h']
    days = 120  # Use 120 days for comprehensive testing
    
    print_section("CONFIGURATION")
    print(f"Symbols: {symbols}")
    print(f"Timeframes: {timeframes}")
    print(f"History: {days} days")
    print(f"Output directory: ./reports/demo")
    
    # Step 1: Data Management
    print_step(1, "DATA FETCHING AND CACHING")
    
    loader = create_data_loader()
    data_results = {}
    
    for symbol in symbols:
        for timeframe in timeframes:
            print(f"   Loading {symbol} {timeframe}...")
            try:
                data = loader.get_ohlcv(symbol, timeframe, days=days)
                if not data.empty:
                    data_results[f"{symbol}_{timeframe}"] = data
                    print(f"   ✓ Loaded {len(data)} candles")
                    print(f"     Date range: {data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}")
                else:
                    print(f"   ✗ No data available")
            except Exception as e:
                print(f"   ✗ Error: {e}")
    
    if not data_results:
        print("Error: No data loaded. Please check your configuration.")
        return
    
    print(f"\n✓ Successfully loaded data for {len(data_results)} combinations")
    
    # Step 2: Single Strategy Testing
    print_step(2, "SINGLE STRATEGY TESTING")
    
    # Test multiple parameter sets
    test_params = [
        {
            'name': 'Conservative',
            'params': {'a': 1.5, 'c': 14, 'st_factor': 1.2, 'min_delay_m': 120, 'atr_sl_mult': 1.5, 'atr_rr': 2.0}
        },
        {
            'name': 'Balanced',
            'params': {'a': 2.0, 'c': 10, 'st_factor': 1.5, 'min_delay_m': 60, 'atr_sl_mult': 2.0, 'atr_rr': 2.0}
        },
        {
            'name': 'Aggressive',
            'params': {'a': 2.5, 'c': 7, 'st_factor': 2.0, 'min_delay_m': 30, 'atr_sl_mult': 2.5, 'atr_rr': 3.0}
        }
    ]
    
    strategy_results = {}
    
    for test_config in test_params:
        print(f"\n   Testing {test_config['name']} strategy...")
        strategy = create_strategy(test_config['params'])
        
        # Test on first available data
        first_key = list(data_results.keys())[0]
        test_data = data_results[first_key]
        
        signals = strategy.run_strategy(test_data)
        result = run_backtest(test_data, signals)
        
        strategy_results[test_config['name']] = {
            'params': test_config['params'],
            'metrics': result.metrics
        }
        
        print(f"     Total Return: {result.metrics['total_return_pct']:.2f}%")
        print(f"     Profit Factor: {result.metrics['profit_factor']:.2f}")
        print(f"     Max Drawdown: {result.metrics['max_drawdown_pct']:.2f}%")
        print(f"     Sharpe Ratio: {result.metrics['sharpe_ratio']:.2f}")
        print(f"     Number of Trades: {result.metrics['num_trades']}")
    
    # Find best single strategy
    best_single = max(strategy_results.items(), key=lambda x: x[1]['metrics']['profit_factor'])
    print(f"\n   Best Single Strategy: {best_single[0]}")
    print(f"     Profit Factor: {best_single[1]['metrics']['profit_factor']:.2f}")
    
    # Step 3: Grid Search Optimization
    print_step(3, "GRID SEARCH OPTIMIZATION")
    
    # Define parameter space
    param_combinations = []
    for a in [1.5, 2.0, 2.5]:
        for c in [7, 10, 14]:
            for st_factor in [1.2, 1.5, 2.0]:
                for min_delay_m in [30, 60, 120]:
                    for atr_sl_mult in [1.5, 2.0, 2.5]:
                        for atr_rr in [1.5, 2.0, 2.5]:
                            param_combinations.append({
                                'a': a, 'c': c, 'st_factor': st_factor,
                                'min_delay_m': min_delay_m, 'atr_sl_mult': atr_sl_mult, 'atr_rr': atr_rr
                            })
    
    print(f"   Testing {len(param_combinations)} parameter combinations...")
    print(f"   Using {len(symbols)} symbols × {len(timeframes)} timeframes = {len(symbols) * len(timeframes)} combinations")
    print(f"   Total tests: {len(param_combinations) * len(symbols) * len(timeframes)}")
    
    try:
        grid_results = run_grid_search(
            symbols=symbols,
            timeframes=timeframes,
            param_combinations=param_combinations,
            max_workers=2,  # Use 2 workers for demo
            parallel=True,
            output_dir='./reports/demo/grid'
        )
        
        print(f"   ✓ Grid search completed: {len(grid_results)} results")
        
        if grid_results:
            best_grid = max(grid_results, key=lambda x: x['metrics']['profit_factor'])
            print(f"   Best Grid Result:")
            print(f"     Symbol: {best_grid['symbol']}")
            print(f"     Timeframe: {best_grid['timeframe']}")
            print(f"     Profit Factor: {best_grid['metrics']['profit_factor']:.2f}")
            print(f"     Total Return: {best_grid['metrics']['total_return_pct']:.2f}%")
            print(f"     Parameters: {best_grid['params']}")
        
    except Exception as e:
        print(f"   ✗ Error during grid search: {e}")
        grid_results = []
    
    # Step 4: Walk-Forward Analysis
    print_step(4, "WALK-FORWARD ANALYSIS")
    
    # Use best parameters from grid search for walk-forward
    if grid_results:
        best_params = [best_grid['params']]
        print(f"   Using best parameters from grid search for walk-forward analysis")
    else:
        # Use balanced strategy if no grid results
        best_params = [test_params[1]['params']]
        print(f"   Using balanced strategy parameters for walk-forward analysis")
    
    try:
        wf_results = run_walk_forward(
            symbols=symbols[:1],  # Use only first symbol for WF demo
            timeframes=timeframes[:1],  # Use only first timeframe for WF demo
            param_combinations=best_params,
            output_dir='./reports/demo/wf'
        )
        
        print(f"   ✓ Walk-forward analysis completed: {len(wf_results)} windows")
        
        if wf_results:
            test_returns = [r['test_metrics']['total_return_pct'] for r in wf_results]
            test_pfs = [r['test_metrics']['profit_factor'] for r in wf_results]
            positive_windows = sum(1 for r in test_returns if r > 0)
            
            print(f"   Walk-Forward Summary:")
            print(f"     Average Test Return: {sum(test_returns)/len(test_returns):.2f}%")
            print(f"     Average Test Profit Factor: {sum(test_pfs)/len(test_pfs):.2f}")
            print(f"     Consistency: {positive_windows}/{len(test_returns)} ({positive_windows/len(test_returns)*100:.1f}%)")
        
    except Exception as e:
        print(f"   ✗ Error during walk-forward analysis: {e}")
        wf_results = []
    
    # Step 5: Report Generation
    print_step(5, "REPORT GENERATION AND VISUALIZATION")
    
    try:
        # Create output directory
        output_dir = Path('./reports/demo')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate reports
        reporter = create_reporter(str(output_dir))
        reporter.save_summary_tables(grid_results, wf_results, filename_prefix='demo')
        print("   ✓ Summary tables generated")
        
        # Generate visualizations
        visualizer = create_visualizer(str(output_dir))
        visualizer.save_all_plots(grid_results, wf_results, filename_prefix='demo')
        print("   ✓ Plots generated")
        
        # Create final summary
        summary_file = output_dir / 'demo_summary.txt'
        with open(summary_file, 'w') as f:
            f.write("ATR + SuperTrend Strategy Optimizer - Demo Summary\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Demo completed: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total runtime: {time.time() - start_time:.1f} seconds\n\n")
            
            f.write("Configuration:\n")
            f.write(f"  Symbols: {symbols}\n")
            f.write(f"  Timeframes: {timeframes}\n")
            f.write(f"  History: {days} days\n\n")
            
            f.write("Single Strategy Results:\n")
            for name, result in strategy_results.items():
                f.write(f"  {name}: PF={result['metrics']['profit_factor']:.2f}, "
                       f"Return={result['metrics']['total_return_pct']:.2f}%, "
                       f"DD={result['metrics']['max_drawdown_pct']:.2f}%\n")
            
            if grid_results:
                f.write(f"\nGrid Search Results:\n")
                f.write(f"  Total combinations tested: {len(grid_results)}\n")
                best_grid = max(grid_results, key=lambda x: x['metrics']['profit_factor'])
                f.write(f"  Best result: {best_grid['symbol']} {best_grid['timeframe']} - "
                       f"PF={best_grid['metrics']['profit_factor']:.2f}\n")
            
            if wf_results:
                f.write(f"\nWalk-Forward Results:\n")
                f.write(f"  Total windows: {len(wf_results)}\n")
                test_returns = [r['test_metrics']['total_return_pct'] for r in wf_results]
                positive_windows = sum(1 for r in test_returns if r > 0)
                f.write(f"  Consistency: {positive_windows}/{len(wf_results)} "
                       f"({positive_windows/len(wf_results)*100:.1f}%)\n")
        
        print(f"   ✓ Final summary saved to {summary_file}")
        
    except Exception as e:
        print(f"   ✗ Error generating reports: {e}")
    
    # Final Summary
    print_section("DEMO COMPLETED")
    
    total_time = time.time() - start_time
    print(f"Total runtime: {total_time:.1f} seconds")
    print(f"Data combinations tested: {len(data_results)}")
    print(f"Single strategies tested: {len(test_params)}")
    print(f"Grid search combinations: {len(param_combinations) if 'param_combinations' in locals() else 0}")
    print(f"Walk-forward windows: {len(wf_results) if wf_results else 0}")
    
    print(f"\nResults saved to: ./reports/demo/")
    print("Check the following files:")
    print("  - demo_summary.txt: Complete summary")
    print("  - demo_top_results.csv: Top optimization results")
    print("  - demo_by_symbol_timeframe.csv: Results by symbol/timeframe")
    print("  - demo_plots_*.png: Various visualizations")
    
    if grid_results:
        best_result = max(grid_results, key=lambda x: x['metrics']['profit_factor'])
        print(f"\nBest Overall Result:")
        print(f"  Symbol: {best_result['symbol']}")
        print(f"  Timeframe: {best_result['timeframe']}")
        print(f"  Profit Factor: {best_result['metrics']['profit_factor']:.2f}")
        print(f"  Total Return: {best_result['metrics']['total_return_pct']:.2f}%")
        print(f"  Max Drawdown: {best_result['metrics']['max_drawdown_pct']:.2f}%")
        print(f"  Parameters: {best_result['params']}")


if __name__ == "__main__":
    main()
