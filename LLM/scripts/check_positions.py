#!/usr/bin/env python3
"""Check active positions and order status."""
import json
import ccxt
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load config
with open('configs/llm_config.json') as f:
    cfg = json.load(f)

exchange = ccxt.binance({
    'apiKey': cfg['api_key'],
    'secret': cfg['secret'],
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})

print('=== AKTİF POZİSYONLAR VE ORDER DURUMU ===\n')

# Check active positions
positions = exchange.fetch_positions(['BTCUSDT', 'ETHUSDT'])
print('📊 Aktif Pozisyonlar:')
active_found = False
for pos in positions:
    size = float(pos.get('size', pos.get('contracts', 0)))
    if abs(size) > 0:
        active_found = True
        symbol = pos.get('symbol', 'N/A')
        side = pos.get('side', 'N/A')
        entry = pos.get('entryPrice', 0)
        mark = pos.get('markPrice', 0)
        pnl = pos.get('unrealizedPnl', 0)
        leverage = pos.get('leverage', 'N/A')
        print(f'   {symbol}: {side} - Size: {size:.4f}')
        print(f'     Entry: ${entry:.2f} | Mark: ${mark:.2f} | PnL: ${pnl:.2f} | Leverage: {leverage}x')
if not active_found:
    print('   ⚪ Aktif pozisyon yok')

# Check all orders
print(f'\n=== ETHUSDT TÜM EMİRLER ===')
all_eth = exchange.fetch_orders('ETHUSDT', limit=50)
print(f'Toplam: {len(all_eth)}')

entry_orders = [o for o in all_eth if o.get('type') == 'market']
sl_orders = [o for o in all_eth if 'STOP' in str(o.get('type', '')).upper()]
tp_orders = [o for o in all_eth if 'TAKE_PROFIT' in str(o.get('type', '')).upper()]

print(f'Entry Orders: {len(entry_orders)}')
print(f'SL Orders: {len(sl_orders)}')
print(f'TP Orders: {len(tp_orders)}')

# Show open SL/TP orders
open_sl = [o for o in sl_orders if o.get('status') in ['open', 'NEW']]
open_tp = [o for o in tp_orders if o.get('status') in ['open', 'NEW']]

if open_sl:
    print(f'\n📋 Açık Stop Loss Emirleri: {len(open_sl)}')
    for order in open_sl[-3:]:
        dt = datetime.fromtimestamp(order['timestamp'] / 1000)
        stop_price = order.get('stopPrice') or order.get('price', 0)
        print(f'   • {order.get("side")} - Stop: ${stop_price:.2f} - Status: {order.get("status")}')
        print(f'     Zaman: {dt.strftime("%Y-%m-%d %H:%M")}')

if open_tp:
    print(f'\n📋 Açık Take Profit Emirleri: {len(open_tp)}')
    for order in open_tp[-3:]:
        dt = datetime.fromtimestamp(order['timestamp'] / 1000)
        tp_price = order.get('stopPrice') or order.get('price', 0)
        print(f'   • {order.get("side")} - TP: ${tp_price:.2f} - Status: {order.get("status")}')
        print(f'     Zaman: {dt.strftime("%Y-%m-%d %H:%M")}')

# Check closed SL/TP
closed_sl = [o for o in sl_orders if o.get('status') == 'closed']
closed_tp = [o for o in tp_orders if o.get('status') == 'closed']

if closed_sl:
    print(f'\n❌ KAPANAN STOP LOSS: {len(closed_sl)}')
    for order in closed_sl[-5:]:
        dt = datetime.fromtimestamp(order['timestamp'] / 1000)
        stop_price = order.get('stopPrice') or order.get('price', 0)
        print(f'   • {order.get("side")} - Stop: ${stop_price:.2f}')
        print(f'     Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')
else:
    print(f'\n⚪ Stop Loss ile kapanan pozisyon yok')

if closed_tp:
    print(f'\n✅ KAPANAN TAKE PROFIT: {len(closed_tp)}')
    for order in closed_tp[-5:]:
        dt = datetime.fromtimestamp(order['timestamp'] / 1000)
        tp_price = order.get('stopPrice') or order.get('price', 0)
        print(f'   • {order.get("side")} - TP: ${tp_price:.2f}')
        print(f'     Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')
else:
    print(f'\n⚪ Take Profit ile kapanan pozisyon yok')

