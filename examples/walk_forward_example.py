#!/usr/bin/env python3
"""
Example script: Walk-forward analysis demonstration.

This script demonstrates how to perform walk-forward analysis
to test strategy robustness across different time periods.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from atr_st_optimizer import (
    create_data_loader,
    run_walk_forward,
    create_reporter,
    create_visualizer
)


def main():
    """Main walk-forward example function."""
    print("ATR + SuperTrend Strategy Optimizer - Walk-Forward Analysis Example")
    print("=" * 70)
    
    # Configuration
    symbols = ['BTC/USDT']  # Use single symbol for example
    timeframes = ['1h']     # Use single timeframe for example
    days = 180  # Use 180 days for walk-forward analysis
    
    print(f"Testing symbol: {symbols[0]}")
    print(f"Timeframe: {timeframes[0]}")
    print(f"History: {days} days")
    print()
    
    # 1. Load data
    print("1. Loading data...")
    loader = create_data_loader()
    
    data = loader.get_ohlcv(symbols[0], timeframes[0], days=days)
    if data.empty:
        print(f"Error: No data available for {symbols[0]} {timeframes[0]}")
        return
    
    print(f"✓ Loaded {len(data)} candles")
    print(f"  Date range: {data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}")
    print()
    
    # 2. Define parameter combinations for walk-forward
    print("2. Setting up parameter combinations...")
    
    # Define parameter combinations to test
    param_combinations = [
        {'a': 1.5, 'c': 10, 'st_factor': 1.2, 'min_delay_m': 30, 'atr_sl_mult': 1.5, 'atr_rr': 2.0},
        {'a': 2.0, 'c': 10, 'st_factor': 1.5, 'min_delay_m': 60, 'atr_sl_mult': 2.0, 'atr_rr': 2.0},
        {'a': 2.5, 'c': 14, 'st_factor': 1.5, 'min_delay_m': 60, 'atr_sl_mult': 2.0, 'atr_rr': 2.5},
        {'a': 2.0, 'c': 20, 'st_factor': 2.0, 'min_delay_m': 120, 'atr_sl_mult': 2.5, 'atr_rr': 3.0},
        {'a': 1.8, 'c': 12, 'st_factor': 1.8, 'min_delay_m': 45, 'atr_sl_mult': 1.8, 'atr_rr': 2.2},
    ]
    
    print(f"   Testing {len(param_combinations)} parameter combinations")
    print()
    
    # 3. Run walk-forward analysis
    print("3. Running walk-forward analysis...")
    print("   Scheme: Rolling windows")
    print("   Train windows: 3")
    print("   Train window: 60 days")
    print("   Test window: 30 days")
    print()
    
    try:
        wf_results = run_walk_forward(
            symbols=symbols,
            timeframes=timeframes,
            param_combinations=param_combinations,
            output_dir='./reports/wf_example'
        )
        
        print(f"✓ Walk-forward analysis completed: {len(wf_results)} windows")
        print()
        
    except Exception as e:
        print(f"✗ Error during walk-forward analysis: {e}")
        return
    
    # 4. Analyze walk-forward results
    print("4. Analyzing walk-forward results...")
    
    if wf_results:
        # Calculate summary statistics
        test_returns = [r['test_metrics']['total_return_pct'] for r in wf_results]
        test_pfs = [r['test_metrics']['profit_factor'] for r in wf_results]
        test_drawdowns = [r['test_metrics']['max_drawdown_pct'] for r in wf_results]
        test_trades = [r['test_metrics']['num_trades'] for r in wf_results]
        
        # Calculate consistency
        positive_windows = sum(1 for r in test_returns if r > 0)
        consistency = positive_windows / len(test_returns) * 100
        
        print(f"   Walk-Forward Summary:")
        print(f"     Total Windows: {len(wf_results)}")
        print(f"     Average Test Return: {sum(test_returns)/len(test_returns):.2f}%")
        print(f"     Average Test Profit Factor: {sum(test_pfs)/len(test_pfs):.2f}")
        print(f"     Average Test Max Drawdown: {sum(test_drawdowns)/len(test_drawdowns):.2f}%")
        print(f"     Total Test Trades: {sum(test_trades)}")
        print(f"     Consistency: {consistency:.1f}% ({positive_windows}/{len(test_returns)} positive windows)")
        print()
        
        # Show individual window results
        print(f"   Individual Window Results:")
        for i, result in enumerate(wf_results):
            test_metrics = result['test_metrics']
            print(f"     Window {i+1}: Return={test_metrics['total_return_pct']:.2f}%, "
                  f"PF={test_metrics['profit_factor']:.2f}, "
                  f"DD={test_metrics['max_drawdown_pct']:.2f}%, "
                  f"Trades={test_metrics['num_trades']}")
        print()
        
        # Find best performing window
        best_window = max(wf_results, key=lambda x: x['test_metrics']['profit_factor'])
        print(f"   Best Performing Window:")
        print(f"     Window ID: {best_window['window_id']}")
        print(f"     Parameters: {best_window['best_params']}")
        print(f"     Test Return: {best_window['test_metrics']['total_return_pct']:.2f}%")
        print(f"     Test Profit Factor: {best_window['test_metrics']['profit_factor']:.2f}")
        print(f"     Test Max Drawdown: {best_window['test_metrics']['max_drawdown_pct']:.2f}%")
        print()
        
        # Analyze parameter stability
        print(f"   Parameter Stability Analysis:")
        param_counts = {}
        for result in wf_results:
            params = result['best_params']
            param_key = f"a={params['a']}, c={params['c']}, st={params['st_factor']}"
            param_counts[param_key] = param_counts.get(param_key, 0) + 1
        
        for param_key, count in sorted(param_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"     {param_key}: {count} windows ({count/len(wf_results)*100:.1f}%)")
        print()
        
        # 5. Generate walk-forward reports
        print("5. Generating walk-forward reports...")
        
        try:
            reporter = create_reporter('./reports/wf_example')
            reporter.save_summary_tables([], wf_results, filename_prefix='wf_example')
            print("   ✓ Walk-forward summary tables generated")
            
            visualizer = create_visualizer('./reports/wf_example')
            visualizer.save_all_plots([], wf_results, filename_prefix='wf_example')
            print("   ✓ Walk-forward plots generated")
            
        except Exception as e:
            print(f"   ✗ Error generating reports: {e}")
    
    print()
    print("Walk-forward analysis example completed successfully!")
    print("Check the './reports/wf_example' directory for results and visualizations.")


if __name__ == "__main__":
    main()
