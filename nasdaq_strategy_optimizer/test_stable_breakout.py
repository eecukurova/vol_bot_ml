#!/usr/bin/env python3
"""
Quick test script for Stable Breakout Strategy
Tests different parameter combinations to find optimal settings
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from optimize_stable_breakout import StableBreakoutStrategy
import yfinance as yf
import pandas as pd
import json

def test_single_symbol(symbol='AAPL', period='2y'):
    """Test strategy on a single symbol with different parameter sets"""
    
    print(f"\n{'='*80}")
    print(f"🧪 Testing Stable Breakout Strategy on {symbol}")
    print(f"{'='*80}\n")
    
    # Fetch data
    print(f"📥 Fetching data for {symbol}...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval='1d')
    
    if df.empty:
        print(f"❌ No data available for {symbol}")
        return
    
    # Rename columns
    df.columns = [col.replace(' ', '') for col in df.columns]
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    print(f"✅ Data loaded: {len(df)} bars\n")
    
    # Test different parameter sets (from conservative to aggressive)
    test_params = [
        {
            'name': 'Original (Very Conservative)',
            'params': {
                'lenHigh': 200,
                'lenVol': 30,
                'minRise': 4.0,
                'volKatsay': 1.5,
                'useRSI': False,
                'useEMA': False,
                'tpPct': 2.0,
                'slPct': 1.0
            }
        },
        {
            'name': 'Moderate (More Trades)',
            'params': {
                'lenHigh': 100,
                'lenVol': 25,
                'minRise': 2.5,
                'volKatsay': 1.3,
                'useRSI': False,
                'useEMA': False,
                'tpPct': 3.0,
                'slPct': 1.5
            }
        },
        {
            'name': 'Aggressive (Many Trades)',
            'params': {
                'lenHigh': 50,
                'lenVol': 20,
                'minRise': 1.5,
                'volKatsay': 1.2,
                'useRSI': False,
                'useEMA': False,
                'tpPct': 3.0,
                'slPct': 1.5
            }
        },
        {
            'name': 'Very Aggressive (Maximum Trades)',
            'params': {
                'lenHigh': 30,
                'lenVol': 15,
                'minRise': 1.0,
                'volKatsay': 1.0,
                'useRSI': False,
                'useEMA': False,
                'tpPct': 3.5,
                'slPct': 2.0
            }
        },
        {
            'name': 'Balanced with RSI Filter',
            'params': {
                'lenHigh': 50,
                'lenVol': 20,
                'minRise': 1.5,
                'volKatsay': 1.2,
                'useRSI': True,
                'rsiLen': 14,
                'rsiMin': 45.0,
                'rsiMax': 75.0,
                'useEMA': False,
                'tpPct': 3.0,
                'slPct': 1.5
            }
        }
    ]
    
    results = []
    
    for test in test_params:
        print(f"🔍 Testing: {test['name']}")
        print(f"   Params: {test['params']}")
        
        try:
            strategy = StableBreakoutStrategy(test['params'])
            result = strategy.backtest(df)
            
            result['name'] = test['name']
            result['params'] = test['params']
            results.append(result)
            
            print(f"   ✅ Trades: {result['total_trades']}")
            print(f"   📈 Return: {result['total_return']:.2f}%")
            print(f"   🎯 Win Rate: {result['win_rate']:.2f}%")
            print(f"   💰 Profit Factor: {result['profit_factor']:.2f}")
            print(f"   📉 Max DD: {result['max_drawdown']:.2f}%")
            print()
        
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
            continue
    
    # Find best result
    if results:
        # Sort by a combination of trades and return
        for r in results:
            r['score'] = (r['total_trades'] / 50.0 * 0.5) + (r['total_return'] / 50.0 * 0.5)
        
        results.sort(key=lambda x: x['score'], reverse=True)
        best = results[0]
        
        print(f"\n{'='*80}")
        print(f"🏆 BEST RESULT: {best['name']}")
        print(f"{'='*80}")
        print(f"📊 Trades: {best['total_trades']}")
        print(f"📈 Return: {best['total_return']:.2f}%")
        print(f"🎯 Win Rate: {best['win_rate']:.2f}%")
        print(f"💰 Profit Factor: {best['profit_factor']:.2f}")
        print(f"📉 Max Drawdown: {best['max_drawdown']:.2f}%")
        print(f"📋 Parameters:")
        for key, value in best['params'].items():
            print(f"   {key}: {value}")
        print(f"{'='*80}\n")
        
        # Save results
        output_file = f'stable_breakout_test_{symbol}.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"💾 Results saved to: {output_file}\n")
    
    return results


if __name__ == '__main__':
    import sys
    
    symbol = 'AAPL'
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
    
    test_single_symbol(symbol=symbol)

