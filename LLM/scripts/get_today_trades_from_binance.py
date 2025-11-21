#!/usr/bin/env python3
"""Get today's trades from Binance and analyze TP vs SL."""

import json
import ccxt
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

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

def get_today_trades(symbol="BTCUSDT"):
    """Get today's trades from Binance."""
    print(f"📊 Fetching today's trades for {symbol}...")
    
    # Get trades from today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    since = int(today_start.timestamp() * 1000)
    
    try:
        trades = exchange.fetch_my_trades(symbol, since=since, limit=500)
        print(f"   Found {len(trades)} trades")
        return trades
    except Exception as e:
        print(f"   Error: {e}")
        return []

def pair_trades_to_positions(trades):
    """Pair trades to find entry/exit positions."""
    if not trades:
        return []
    
    positions = []
    i = 0
    
    while i < len(trades):
        entry_trade = trades[i]
        
        # Find corresponding exit trade
        if i + 1 < len(trades):
            exit_trade = trades[i + 1]
            
            # Check if it's a position pair (entry + exit)
            if entry_trade['side'] != exit_trade['side']:
                # Calculate PnL
                entry_price = entry_trade['price']
                exit_price = exit_trade['price']
                
                if entry_trade['side'] == 'buy':  # LONG
                    pnl_pct = (exit_price - entry_price) / entry_price
                    side = 'LONG'
                else:  # SHORT
                    pnl_pct = (entry_price - exit_price) / entry_price
                    side = 'SHORT'
                
                # Determine exit reason (approximate - check if hit TP or SL)
                # This is simplified - in real system, you'd check order history
                exit_reason = 'TP' if pnl_pct > 0 else 'SL'
                
                position = {
                    'side': side,
                    'entry': entry_price,
                    'exit': exit_price,
                    'pnl': pnl_pct,
                    'exit_reason': exit_reason,
                    'entry_time': entry_trade['datetime'],
                    'exit_time': exit_trade['datetime'],
                    'entry_amount': entry_trade['amount'],
                    'exit_amount': exit_trade['amount'],
                }
                positions.append(position)
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    return positions

def analyze_positions(positions):
    """Analyze positions."""
    if not positions:
        print("❌ No positions found!")
        return
    
    print(f"\n📊 Today's Trading Analysis ({datetime.now().date()})")
    print("=" * 100)
    
    # Separate TP and SL
    tp_positions = [p for p in positions if p.get('exit_reason') == 'TP']
    sl_positions = [p for p in positions if p.get('exit_reason') == 'SL']
    
    print(f"\n📈 Overall Statistics:")
    print("-" * 100)
    print(f"   Total Positions: {len(positions)}")
    print(f"   ✅ Take Profit: {len(tp_positions)} ({len(tp_positions)/len(positions)*100:.1f}%)")
    print(f"   ❌ Stop Loss: {len(sl_positions)} ({len(sl_positions)/len(positions)*100:.1f}%)")
    
    # PnL
    total_pnl = sum(p['pnl'] for p in positions)
    tp_pnl = sum(p['pnl'] for p in tp_positions) if tp_positions else 0
    sl_pnl = sum(p['pnl'] for p in sl_positions) if sl_positions else 0
    
    print(f"\n💰 PnL Statistics:")
    print(f"   Total PnL: {total_pnl*100:+.2f}%")
    print(f"   TP PnL: {tp_pnl*100:+.2f}%")
    print(f"   SL PnL: {sl_pnl*100:.2f}%")
    
    # TP trades
    if tp_positions:
        print(f"\n✅ Take Profit Trades ({len(tp_positions)}):")
        print("-" * 100)
        for i, pos in enumerate(tp_positions, 1):
            print(f"   {i}. {pos['side']:5s} | Entry: ${pos['entry']:.2f} | Exit: ${pos['exit']:.2f} | "
                  f"PnL: {pos['pnl']*100:+.2f}% | {pos['exit_time']}")
    
    # SL trades - detailed analysis
    if sl_positions:
        print(f"\n❌ Stop Loss Trades ({len(sl_positions)}) - Detailed Analysis:")
        print("=" * 100)
        
        avg_sl_pnl = sum(p['pnl'] for p in sl_positions) / len(sl_positions)
        print(f"\n📊 SL Statistics:")
        print(f"   Average SL PnL: {avg_sl_pnl*100:.2f}%")
        print(f"   Total SL Loss: {sl_pnl*100:.2f}%")
        
        # Group by side
        sl_long = [p for p in sl_positions if p['side'] == 'LONG']
        sl_short = [p for p in sl_positions if p['side'] == 'SHORT']
        
        if sl_long:
            avg_long = sum(p['pnl'] for p in sl_long) / len(sl_long)
            print(f"   LONG SL: {len(sl_long)} trades, Avg: {avg_long*100:.2f}%")
        
        if sl_short:
            avg_short = sum(p['pnl'] for p in sl_short) / len(sl_short)
            print(f"   SHORT SL: {len(sl_short)} trades, Avg: {avg_short*100:.2f}%")
        
        print(f"\n🔍 Detailed SL Trades:")
        print("-" * 100)
        
        for i, pos in enumerate(sl_positions, 1):
            print(f"\n{i}. ❌ Stop Loss Trade #{i}")
            print(f"   Side: {pos['side']}")
            print(f"   Entry: ${pos['entry']:.2f} | Exit: ${pos['exit']:.2f}")
            print(f"   PnL: {pos['pnl']*100:.2f}%")
            print(f"   Entry Time: {pos['entry_time']}")
            print(f"   Exit Time: {pos['exit_time']}")
            
            # Price movement
            if pos['side'] == 'LONG':
                price_move = ((pos['exit'] - pos['entry']) / pos['entry']) * 100
            else:
                price_move = ((pos['entry'] - pos['exit']) / pos['entry']) * 100
            
            print(f"   Price Movement: {price_move:.2f}%")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        print("-" * 100)
        
        if avg_sl_pnl < -0.01:
            print(f"   ⚠️  Average SL loss is {avg_sl_pnl*100:.2f}% - Consider tighter stops")
        
        if len(sl_positions) > len(tp_positions):
            print(f"   ⚠️  More SLs than TPs ({len(sl_positions)} vs {len(tp_positions)}) - Review entry strategy")
    else:
        print("\n✅ No Stop Loss trades today!")

if __name__ == "__main__":
    print("=" * 100)
    print("LLM Today's Trades Analysis from Binance")
    print("=" * 100)
    
    # Get BTC trades
    btc_trades = get_today_trades("BTCUSDT")
    
    if btc_trades:
        positions = pair_trades_to_positions(btc_trades)
        analyze_positions(positions)
    else:
        print("❌ No trades found for today")

