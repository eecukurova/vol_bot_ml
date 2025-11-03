#!/usr/bin/env python3
"""
Test higher take profit rates for PENGU EMA strategy
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

def calculate_ema(prices, period):
    """Calculate EMA"""
    if len(prices) < period:
        return None
    
    # Convert to list if pandas Series
    if hasattr(prices, 'iloc'):
        prices_list = prices.tolist()
    else:
        prices_list = prices
    
    if len(prices_list) < period:
        return None
    
    multiplier = 2 / (period + 1)
    ema = prices_list[0]
    
    for price in prices_list[1:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))
    
    return ema

def calculate_heikin_ashi(df):
    """Calculate Heikin Ashi"""
    ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = ha_close.copy()
    
    for i in range(1, len(ha_open)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
    
    df['ha_close'] = ha_close
    return df

def backtest_pengu_strategy(df, ema_fast=10, ema_slow=26, take_profit_pct=0.01, stop_loss_pct=0.015):
    """Backtest PENGU EMA strategy"""
    # Calculate Heikin Ashi
    df = calculate_heikin_ashi(df)
    src = df['ha_close']
    
    # Calculate EMAs
    ema_fast_values = []
    ema_slow_values = []
    
    for i in range(26, len(df)):
        window = src.iloc[i-25:i+1]
        ema_fast_val = calculate_ema(window, ema_fast)
        ema_slow_val = calculate_ema(window, ema_slow)
        ema_fast_values.append(ema_fast_val)
        ema_slow_values.append(ema_slow_val)
    
    # Find crossovers
    signals = []
    position = None
    
    for i in range(1, len(ema_fast_values)):
        prev_fast = ema_fast_values[i-1]
        curr_fast = ema_fast_values[i]
        prev_slow = ema_slow_values[i-1]
        curr_slow = ema_slow_values[i]
        
        # Buy signal
        if prev_fast <= prev_slow and curr_fast > curr_slow and position is None:
            position = {
                'entry_idx': i + 26,
                'entry_price': df['close'].iloc[i + 26],
                'entry_date': df['date'].iloc[i + 26]
            }
        
        # Sell signal
        elif prev_fast >= prev_slow and curr_fast < curr_slow and position is not None:
            exit_price = df['close'].iloc[i + 26]
            entry_price = position['entry_price']
            
            # Calculate PnL with TP/SL
            if exit_price > entry_price:
                # Long position
                if (exit_price - entry_price) / entry_price >= take_profit_pct:
                    pnl = take_profit_pct
                elif (exit_price - entry_price) / entry_price <= -stop_loss_pct:
                    pnl = -stop_loss_pct
                else:
                    pnl = (exit_price - entry_price) / entry_price
            else:
                # Shouldn't happen in this case
                pnl = -stop_loss_pct
            
            signals.append({
                'entry': position['entry_idx'],
                'exit': i + 26,
                'entry_date': position['entry_date'],
                'exit_date': df['date'].iloc[i + 26],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl
            })
            position = None
    
    # Close open position at the end
    if position:
        exit_price = df['close'].iloc[-1]
        entry_price = position['entry_price']
        
        if (exit_price - entry_price) / entry_price >= take_profit_pct:
            pnl = take_profit_pct
        elif (exit_price - entry_price) / entry_price <= -stop_loss_pct:
            pnl = -stop_loss_pct
        else:
            pnl = (exit_price - entry_price) / entry_price
        
        signals.append({
            'entry': position['entry_idx'],
            'exit': len(df) - 1,
            'entry_date': position['entry_date'],
            'exit_date': df['date'].iloc[-1],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl
        })
    
    if signals:
        profitable = [s for s in signals if s['pnl'] > 0]
        total_return = sum(s['pnl'] for s in signals)
        win_rate = len(profitable) / len(signals) * 100
        
        return {
            'trades': len(signals),
            'win_rate': win_rate,
            'total_return': total_return,
            'avg_return': total_return / len(signals),
            'signals': signals
        }
    
    return None

def test_different_tp_levels():
    """Test different TP levels"""
    print("🚀 PENGU EMA - Testing Different Take Profit Levels")
    print("="*80)
    
    try:
        exchange = ccxt.binance()
        
        # Fetch data
        print("📊 Fetching PENGU/USDT data...")
        ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=500)
        
        if not ohlcv or len(ohlcv) < 100:
            print("❌ Not enough data")
            return
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f"✅ Fetched {len(df)} candles")
        print(f"📅 Date range: {df['date'].min()} to {df['date'].max()}")
        print()
        
        # Test different TP levels
        tp_levels = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]
        stop_loss = 0.015  # 1.5% stop loss
        
        results = []
        
        for tp in tp_levels:
            print(f"🧪 Testing TP={tp:.1%}, SL={stop_loss:.1%}...")
            
            result = backtest_pengu_strategy(df, 
                                            ema_fast=10, 
                                            ema_slow=26, 
                                            take_profit_pct=tp, 
                                            stop_loss_pct=stop_loss)
            
            if result:
                print(f"   ✅ {result['trades']} trades, WR: {result['win_rate']:.1f}%, Return: {result['total_return']:.2%}")
                results.append({
                    'take_profit': tp,
                    'stop_loss': stop_loss,
                    **result
                })
            else:
                print(f"   ⚠️ No signals")
        
        # Find best TP level
        if results:
            print(f"\n📊 RESULTS SUMMARY:")
            print("="*80)
            
            # Sort by total return
            results.sort(key=lambda x: x['total_return'], reverse=True)
            
            print(f"\n🏆 TOP TP LEVELS BY RETURN:")
            for i, r in enumerate(results[:5], 1):
                print(f"{i}. TP={r['take_profit']:.1%} → {r['total_return']:.2%} "
                      f"({r['trades']} trades, {r['win_rate']:.1f}% WR)")
            
            # Sort by win rate
            results_by_wr = sorted(results, key=lambda x: x['win_rate'], reverse=True)
            
            print(f"\n🎯 TOP TP LEVELS BY WIN RATE:")
            for i, r in enumerate(results_by_wr[:5], 1):
                print(f"{i}. TP={r['take_profit']:.1%} → {r['win_rate']:.1f}% WR "
                      f"({r['total_return']:.2%} return, {r['trades']} trades)")
            
            # Find best balanced
            balanced = max(results, key=lambda x: x['win_rate'] * x['total_return'])
            
            print(f"\n⚖️ BEST BALANCED:")
            print(f"   TP: {balanced['take_profit']:.1%}")
            print(f"   SL: {balanced['stop_loss']:.1%}")
            print(f"   Return: {balanced['total_return']:.2%}")
            print(f"   Win Rate: {balanced['win_rate']:.1f}%")
            print(f"   Trades: {balanced['trades']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_different_tp_levels()
