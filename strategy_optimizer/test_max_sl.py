#!/usr/bin/env python3
"""Test max SL %1.5"""

import json
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from optimize_twma_enhanced import download_binance_futures_klines
from src.strategy.twma_trend_enhanced import TWMATrendEnhancedStrategy

eth_files = sorted(glob.glob('twma_enhanced_optimization_ETHUSDT_*.json'))
if eth_files:
    with open(eth_files[-1], 'r') as f:
        results = json.load(f)
    
    best = results[0]
    
    df = download_binance_futures_klines("ETHUSDT", "4h", days=180)
    strategy = TWMATrendEnhancedStrategy(best['params'])
    backtest_results = strategy.run_backtest(df)
    
    trades = backtest_results['trades']
    losing_trades = [t for t in trades if t['pnl_pct'] < 0]
    
    print("="*70)
    print("REVİZE EDİLMİŞ BACKTEST - %1.5 MAX SL İLE")
    print("="*70)
    print()
    print(f"Toplam Trade: {len(trades)}")
    print(f"Kaybeden Trade: {len(losing_trades)}")
    print()
    
    if losing_trades:
        max_loss = min([t['pnl_pct'] for t in trades])
        avg_loss = sum([t['pnl_pct'] for t in losing_trades]) / len(losing_trades)
        
        print(f"En Büyük Kayıp: {max_loss:.2f}%")
        print(f"Ortalama Kayıp: {avg_loss:.2f}%")
        print()
        
        big_losses = [t for t in losing_trades if abs(t['pnl_pct']) > 1.5]
        print(f"%1.5'ten büyük kayıplar: {len(big_losses)}/{len(losing_trades)}")
        print()
        
        print("Performans Metrikleri:")
        print(f"  Win Rate: {backtest_results['win_rate']:.2f}%")
        print(f"  Profit Factor: {backtest_results['profit_factor']:.2f}")
        print(f"  Total Return: {backtest_results['total_return_pct']:.2f}%")
        print(f"  Max Drawdown: {backtest_results['max_drawdown_pct']:.2f}%")

