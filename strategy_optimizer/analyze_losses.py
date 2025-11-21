#!/usr/bin/env python3
"""Mevcut backtest kayıplarını analiz et"""

import json
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from optimize_twma_enhanced import download_binance_futures_klines
from src.strategy.twma_trend_enhanced import TWMATrendEnhancedStrategy

# ETH sonuçlarını analiz et
eth_files = sorted(glob.glob('twma_enhanced_optimization_ETHUSDT_*.json'))
if eth_files:
    with open(eth_files[-1], 'r') as f:
        results = json.load(f)
    
    best = results[0]
    
    df = download_binance_futures_klines("ETHUSDT", "4h", days=180)
    strategy = TWMATrendEnhancedStrategy(best['params'])
    backtest_results = strategy.run_backtest(df)
    
    trades = backtest_results['trades']
    
    print("="*70)
    print("MEVCUT BACKTEST - EN BÜYÜK KAYIPLAR")
    print("="*70)
    print()
    
    losing_trades = [t for t in trades if t['pnl_pct'] < 0]
    losing_trades.sort(key=lambda x: x['pnl_pct'])
    
    print(f"Toplam Trade: {len(trades)}")
    print(f"Kaybeden Trade: {len(losing_trades)}")
    print()
    
    print("En Büyük 10 Kayıp:")
    print("-"*70)
    for i, trade in enumerate(losing_trades[:10], 1):
        print(f"{i}. {trade['side'].upper()} @ ${trade['entry_price']:.2f}")
        print(f"   Exit: ${trade['exit_price']:.2f}")
        print(f"   Kayıp: {trade['pnl_pct']:.2f}%")
        print(f"   Sebep: {trade['exit_reason']}")
        print()
    
    max_loss = min([t['pnl_pct'] for t in trades]) if trades else 0
    avg_loss = sum([t['pnl_pct'] for t in losing_trades]) / len(losing_trades) if losing_trades else 0
    
    print(f"En Büyük Kayıp: {max_loss:.2f}%")
    print(f"Ortalama Kayıp: {avg_loss:.2f}%")
    print()
    
    # %1.5'ten büyük kayıpları say
    big_losses = [t for t in losing_trades if abs(t['pnl_pct']) > 1.5]
    print(f"%1.5'ten büyük kayıplar: {len(big_losses)}/{len(losing_trades)} ({len(big_losses)/len(losing_trades)*100:.1f}%)")
    if big_losses:
        print(f"Bu kayıpların toplamı: {sum([t['pnl_pct'] for t in big_losses]):.2f}%")
        print(f"Ortalama büyük kayıp: {sum([t['pnl_pct'] for t in big_losses])/len(big_losses):.2f}%")

