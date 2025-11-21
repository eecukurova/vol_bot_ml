#!/usr/bin/env python3
"""Analyze today's stop loss trade in detail."""

import json
import ccxt
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Load config
config_path = Path("configs/llm_config.json")
with open(config_path) as f:
    cfg = json.load(f)

exchange = ccxt.binance({
    'apiKey': cfg['api_key'],
    'secret': cfg['secret'],
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})

def get_recent_trades(symbol="BTCUSDT", days=7):
    """Get recent trades from Binance."""
    print(f"📊 Fetching recent trades for {symbol} (last {days} days)...")
    
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    
    try:
        trades = exchange.fetch_my_trades(symbol, since=since, limit=100)
        print(f"   Found {len(trades)} trades")
        return trades
    except Exception as e:
        print(f"   Error: {e}")
        return []

def analyze_trades(trades):
    """Analyze trades to find positions."""
    if not trades:
        print("❌ No trades found!")
        return
    
    # Sort by time (newest first)
    trades.sort(key=lambda x: x['timestamp'], reverse=True)
    
    print(f"\n📊 Recent Trades Analysis")
    print("=" * 100)
    
    # Group by side and find pairs
    positions = []
    i = 0
    
    while i < len(trades) - 1:
        entry = trades[i]
        exit_trade = trades[i + 1]
        
        # Check if it's a position pair
        if entry['side'] != exit_trade['side']:
            entry_price = entry['price']
            exit_price = exit_trade['price']
            
            if entry['side'] == 'buy':  # LONG
                pnl_pct = (exit_price - entry_price) / entry_price
                side = 'LONG'
            else:  # SHORT
                pnl_pct = (entry_price - exit_price) / entry_price
                side = 'SHORT'
            
            # Get realized PnL if available
            realized_pnl = None
            if 'info' in entry and 'realizedPnl' in entry['info']:
                realized_pnl = float(entry['info']['realizedPnl'])
            elif 'info' in exit_trade and 'realizedPnl' in exit_trade['info']:
                realized_pnl = float(exit_trade['info']['realizedPnl'])
            
            exit_reason = 'TP' if pnl_pct > 0 else 'SL'
            
            position = {
                'side': side,
                'entry': entry_price,
                'exit': exit_price,
                'pnl': pnl_pct,
                'realized_pnl': realized_pnl,
                'exit_reason': exit_reason,
                'entry_time': entry['datetime'],
                'exit_time': exit_trade['datetime'],
                'entry_timestamp': entry['timestamp'],
                'exit_timestamp': exit_trade['timestamp'],
            }
            positions.append(position)
            i += 2
        else:
            i += 1
    
    # Filter today's positions
    today = datetime.now().date()
    today_positions = []
    
    for pos in positions:
        try:
            exit_dt = datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00'))
            if exit_dt.date() == today:
                today_positions.append(pos)
        except:
            pass
    
    print(f"\n📅 Today's Positions: {len(today_positions)}")
    print("=" * 100)
    
    if not today_positions:
        print("❌ No positions closed today!")
        print("\n📊 Recent Positions (Last 7 Days):")
        print("-" * 100)
        for i, pos in enumerate(positions[:10], 1):
            print(f"{i}. {pos['side']:5s} | Entry: ${pos['entry']:.2f} | Exit: ${pos['exit']:.2f} | "
                  f"PnL: {pos['pnl']*100:+.2f}% | {pos['exit_reason']:2s} | {pos['exit_time']}")
        return
    
    # Analyze today's positions
    sl_positions = [p for p in today_positions if p['exit_reason'] == 'SL']
    tp_positions = [p for p in today_positions if p['exit_reason'] == 'TP']
    
    print(f"\n✅ Take Profit: {len(tp_positions)}")
    print(f"❌ Stop Loss: {len(sl_positions)}")
    
    if sl_positions:
        print(f"\n❌ STOP LOSS TRADE(S) - DETAILED ANALYSIS")
        print("=" * 100)
        
        for i, pos in enumerate(sl_positions, 1):
            print(f"\n{i}. Stop Loss Trade #{i}")
            print("-" * 100)
            print(f"   Side: {pos['side']}")
            print(f"   Entry: ${pos['entry']:.2f}")
            print(f"   Exit: ${pos['exit']:.2f}")
            print(f"   PnL: {pos['pnl']*100:.2f}%")
            if pos['realized_pnl']:
                print(f"   Realized PnL: ${pos['realized_pnl']:.2f}")
            print(f"   Entry Time: {pos['entry_time']}")
            print(f"   Exit Time: {pos['exit_time']}")
            
            # Duration
            try:
                entry_dt = datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00'))
                exit_dt = datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00'))
                duration = exit_dt - entry_dt
                duration_min = duration.total_seconds() / 60
                print(f"   Duration: {duration_min:.1f} minutes ({duration})")
            except:
                pass
            
            # Price movement
            if pos['side'] == 'LONG':
                price_move = ((pos['exit'] - pos['entry']) / pos['entry']) * 100
            else:
                price_move = ((pos['entry'] - pos['exit']) / pos['entry']) * 100
            
            print(f"   Price Movement: {price_move:.2f}%")
            
            # Compare with config
            sl_pct = cfg['trading_params']['sl_pct'] * 100
            tp_pct = cfg['trading_params']['tp_pct'] * 100
            
            print(f"\n   📊 Config Comparison:")
            print(f"      Config SL: {sl_pct:.2f}%")
            print(f"      Actual Move: {abs(price_move):.2f}%")
            
            if abs(price_move) > sl_pct * 1.1:
                print(f"      ⚠️  Overshoot: {abs(price_move) - sl_pct:.2f}%")
            elif abs(price_move) < sl_pct * 0.9:
                print(f"      ✅ Hit SL early (good execution)")
            else:
                print(f"      ✅ Hit SL as expected")
        
        # Overall analysis
        print(f"\n📊 Overall Analysis:")
        print("=" * 100)
        
        avg_sl_pnl = sum(p['pnl'] for p in sl_positions) / len(sl_positions)
        total_sl_pnl = sum(p['pnl'] for p in sl_positions)
        
        print(f"   Total SL Trades: {len(sl_positions)}")
        print(f"   Average SL PnL: {avg_sl_pnl*100:.2f}%")
        print(f"   Total SL Loss: {total_sl_pnl*100:.2f}%")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        print("-" * 100)
        
        if avg_sl_pnl < -0.008:
            print(f"   ⚠️  Average SL loss ({avg_sl_pnl*100:.2f}%) is higher than config ({sl_pct:.2f}%)")
            print(f"      → Consider tighter stop loss or better entry timing")
        
        if len(sl_positions) > len(tp_positions):
            print(f"   ⚠️  More SLs ({len(sl_positions)}) than TPs ({len(tp_positions)})")
            print(f"      → Review entry strategy or model confidence threshold")
        
        # Check if model is still profitable
        total_pnl = sum(p['pnl'] for p in today_positions)
        if total_pnl < 0:
            print(f"   ⚠️  Today's total PnL: {total_pnl*100:.2f}% (negative)")
            print(f"      → Model may need adjustment or market conditions changed")
        else:
            print(f"   ✅ Today's total PnL: {total_pnl*100:.2f}% (positive)")

if __name__ == "__main__":
    print("=" * 100)
    print("LLM Today's Stop Loss Analysis")
    print("=" * 100)
    
    trades = get_recent_trades("BTCUSDT", days=7)
    if trades:
        analyze_trades(trades)
    else:
        print("❌ No trades found")

