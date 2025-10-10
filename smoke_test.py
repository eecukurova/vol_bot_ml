#!/usr/bin/env python3
"""
Smoke test script for ATR + SuperTrend Strategy Optimizer.

This script runs a comprehensive smoke test to verify:
1. Data fetching and caching
2. Strategy execution
3. Grid search optimization
4. Walk-forward analysis
5. Report generation
"""

import subprocess
import sys
import os
from pathlib import Path
import time


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✓ SUCCESS ({elapsed:.1f}s)")
            if result.stdout:
                print("Output:")
                print(result.stdout[-1000:])  # Show last 1000 chars
            return True
        else:
            print(f"✗ FAILED ({elapsed:.1f}s)")
            print(f"Return code: {result.returncode}")
            if result.stderr:
                print("Error:")
                print(result.stderr)
            if result.stdout:
                print("Output:")
                print(result.stdout[-1000:])
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ TIMEOUT (300s)")
        return False
    except Exception as e:
        print(f"✗ EXCEPTION: {e}")
        return False


def check_file_exists(file_path, description):
    """Check if a file exists and show its size."""
    path = Path(file_path)
    if path.exists():
        size = path.stat().st_size
        print(f"✓ {description}: {file_path} ({size:,} bytes)")
        return True
    else:
        print(f"✗ {description}: {file_path} (not found)")
        return False


def main():
    """Main smoke test function."""
    print("ATR + SuperTrend Strategy Optimizer - Smoke Test")
    print("=" * 70)
    print("This script will run a comprehensive smoke test to verify")
    print("all major components are working correctly.")
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Track test results
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Data fetching
    print("\n" + "="*70)
    print("TEST 1: DATA FETCHING")
    print("="*70)
    
    cmd1 = """python3 atr_st_optimizer/src/cli.py fetch \
  --coins BTC/USDT,SOL/USDT \
  --timeframes 1h \
  --since 2024-10-01 --until 2024-12-01 \
  --no-validate"""
    
    if run_command(cmd1, "Fetching data for BTC/USDT and SOL/USDT (1h, Oct-Dec 2024)"):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 2: Grid search optimization
    print("\n" + "="*70)
    print("TEST 2: GRID SEARCH OPTIMIZATION")
    print("="*70)
    
    cmd2 = """python3 atr_st_optimizer/src/cli.py optimize \
  --coins BTC/USDT \
  --timeframes 1h \
  --param-string "a=1.5,2.0 c=10,14 st_factor=1.2,1.5 min_delay_m=0,60 atr_sl_mult=1.5 atr_rr=2.0" \
  --jobs 2 --out reports/grid_smoke"""
    
    if run_command(cmd2, "Running grid search optimization"):
        tests_passed += 1
        
        # Check output files
        print("\nChecking output files:")
        check_file_exists("reports/grid_smoke/grid_search_results.json", "Grid search results JSON")
        check_file_exists("reports/grid_smoke/grid_search_results.csv", "Grid search results CSV")
        check_file_exists("reports/grid_smoke/grid_search_top_results.json", "Top results JSON")
        check_file_exists("reports/grid_smoke/grid_search_summary.json", "Summary JSON")
    else:
        tests_failed += 1
    
    # Test 3: Walk-forward analysis
    print("\n" + "="*70)
    print("TEST 3: WALK-FORWARD ANALYSIS")
    print("="*70)
    
    cmd3 = """python3 atr_st_optimizer/src/cli.py walk-forward \
  --coins BTC/USDT \
  --timeframes 1h \
  --scheme rolling --train-steps 2 --train-window 30d --test-window 7d \
  --out reports/wf_smoke"""
    
    if run_command(cmd3, "Running walk-forward analysis"):
        tests_passed += 1
        
        # Check output files
        print("\nChecking output files:")
        check_file_exists("reports/wf_smoke/walk_forward_results.json", "Walk-forward results JSON")
        check_file_exists("reports/wf_smoke/walk_forward_metrics.json", "Walk-forward metrics JSON")
        check_file_exists("reports/wf_smoke/walk_forward_summary.json", "Walk-forward summary JSON")
    else:
        tests_failed += 1
    
    # Test 4: Report generation
    print("\n" + "="*70)
    print("TEST 4: REPORT GENERATION")
    print("="*70)
    
    cmd4 = """python3 atr_st_optimizer/src/cli.py report \
  --in reports/grid_smoke \
  --plots \
  --out reports/smoke_reports"""
    
    if run_command(cmd4, "Generating reports and plots"):
        tests_passed += 1
        
        # Check output files
        print("\nChecking output files:")
        check_file_exists("reports/smoke_reports/optimization_report_top_results.csv", "Top results CSV")
        check_file_exists("reports/smoke_reports/optimization_report_by_symbol_timeframe.csv", "Symbol/TF summary CSV")
        check_file_exists("reports/smoke_reports/optimization_report_summary.txt", "Summary text report")
        
        # Check for plot files
        plot_files = list(Path("reports/smoke_reports").glob("optimization_plots_*.png"))
        if plot_files:
            print(f"✓ Generated {len(plot_files)} plot files")
        else:
            print("✗ No plot files generated")
    else:
        tests_failed += 1
    
    # Test 5: Behavior tests
    print("\n" + "="*70)
    print("TEST 5: BEHAVIOR TESTS")
    print("="*70)
    
    cmd5 = "python3 atr_st_optimizer/tests/test_behavior_smoke.py"
    
    if run_command(cmd5, "Running behavior smoke tests"):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 6: Configuration info
    print("\n" + "="*70)
    print("TEST 6: CONFIGURATION")
    print("="*70)
    
    cmd6 = "python3 atr_st_optimizer/src/cli.py config-info"
    
    if run_command(cmd6, "Showing configuration info"):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Final summary
    print("\n" + "="*70)
    print("SMOKE TEST SUMMARY")
    print("="*70)
    
    print(f"Tests passed: {tests_passed}")
    print(f"Tests failed: {tests_failed}")
    print(f"Success rate: {tests_passed/(tests_passed+tests_failed)*100:.1f}%")
    
    if tests_failed == 0:
        print("\n🎉 ALL SMOKE TESTS PASSED!")
        print("The ATR + SuperTrend Strategy Optimizer is working correctly.")
        print("\nNext steps:")
        print("1. Check the generated reports in reports/ directory")
        print("2. Run with larger datasets for production use")
        print("3. Customize parameters for your specific needs")
    else:
        print(f"\n❌ {tests_failed} SMOKE TESTS FAILED!")
        print("Please check the error messages above and fix the issues.")
        print("Common issues:")
        print("- Missing API keys for data fetching")
        print("- Network connectivity problems")
        print("- Insufficient disk space")
        print("- Python environment issues")
    
    return tests_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
