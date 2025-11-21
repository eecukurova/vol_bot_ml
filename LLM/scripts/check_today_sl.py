#!/usr/bin/env python3
"""Check today's stop loss orders from Binance."""

import json
import ccxt
from datetime import datetime, timedelta
from pathlib import Path

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

print("=" * 100)
print("LLM Today's Stop Loss Orders Check")
print("=" * 100)

# Get today's orders
today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
since = int(today_start.timestamp() * 1000)

try:
    # Get all orders
    orders = exchange.fetch_orders('BTCUSDT', since=since, limit=200)
    print(f"📊 Found {len(orders)} orders today")
    
    # Filter SL orders
    sl_orders = [o for o in orders if 'STOP' in str(o.get('type', '')).upper() and 'TAKE_PROFIT' not in str(o.get('type', '')).upper()]
    closed_sl = [o for o in sl_orders if o.get('status') == 'closed']
    
    print(f"\n❌ Stop Loss Orders: {len(sl_orders)}")
    print(f"   Closed: {len(closed_sl)}")
    
    if closed_sl:
        print(f"\n❌ CLOSED STOP LOSS ORDERS (Today):")
        print("=" * 100)
        
        for i, order in enumerate(closed_sl, 1):
            dt = datetime.fromtimestamp(order['timestamp'] / 1000)
            stop_price = order.get('stopPrice') or order.get('price', 0)
            side = order.get('side', 'N/A')
            
            print(f"\n{i}. Stop Loss Order #{i}")
            print("-" * 100)
            print(f"   Side: {side}")
            print(f"   Stop Price: ${stop_price:.2f}")
            print(f"   Status: {order.get('status', 'N/A')}")
            print(f"   Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Order ID: {order.get('id', 'N/A')}")
            
            # Try to find corresponding entry order
            entry_orders = [o for o in orders if o.get('type') == 'market' and o.get('side') != side and abs(o['timestamp'] - order['timestamp']) < 3600000]
            if entry_orders:
                entry = entry_orders[0]
                entry_price = entry.get('price', 0)
                entry_dt = datetime.fromtimestamp(entry['timestamp'] / 1000)
                
                print(f"\n   📊 Entry Information:")
                print(f"      Entry Price: ${entry_price:.2f}")
                print(f"      Entry Time: {entry_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Calculate PnL
                if side == 'sell':  # LONG position closed
                    pnl_pct = ((stop_price - entry_price) / entry_price) * 100
                else:  # SHORT position closed
                    pnl_pct = ((entry_price - stop_price) / entry_price) * 100
                
                print(f"      PnL: {pnl_pct:.2f}%")
                
                # Compare with config
                sl_pct = cfg['trading_params']['sl_pct'] * 100
                print(f"      Config SL: {sl_pct:.2f}%")
                
                if abs(pnl_pct) > sl_pct * 1.1:
                    print(f"      ⚠️  Overshoot: {abs(pnl_pct) - sl_pct:.2f}%")
                elif abs(pnl_pct) < sl_pct * 0.9:
                    print(f"      ✅ Hit SL early (good execution)")
                else:
                    print(f"      ✅ Hit SL as expected")
    else:
        print("\n⚪ No closed stop loss orders today")
    
    # Also check TP orders
    tp_orders = [o for o in orders if 'TAKE_PROFIT' in str(o.get('type', '')).upper()]
    closed_tp = [o for o in tp_orders if o.get('status') == 'closed']
    
    print(f"\n✅ Take Profit Orders: {len(tp_orders)}")
    print(f"   Closed: {len(closed_tp)}")
    
    # Summary
    print(f"\n📊 Today's Summary:")
    print("=" * 100)
    print(f"   ❌ Stop Loss: {len(closed_sl)}")
    print(f"   ✅ Take Profit: {len(closed_tp)}")
    
    if len(closed_sl) + len(closed_tp) > 0:
        win_rate = len(closed_tp) / (len(closed_sl) + len(closed_tp)) * 100
        print(f"   📈 Win Rate: {win_rate:.1f}%")
        
        if win_rate < 50:
            print(f"\n   ⚠️  Win rate below 50% - Review strategy")
        
        if len(closed_sl) > len(closed_tp):
            print(f"   ⚠️  More SLs than TPs - Review entry strategy")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

