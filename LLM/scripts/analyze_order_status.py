#!/usr/bin/env python3
"""Analyze order status from Binance."""
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

print('=== ORDER STATUS DETAYLI ANALİZİ ===\n')

# ETHUSDT
all_eth = exchange.fetch_orders('ETHUSDT', limit=50)

# Analyze by status
status_count = {}
for order in all_eth:
    status = order.get('status', 'unknown')
    status_count[status] = status_count.get(status, 0) + 1

print('📊 ETHUSDT Order Status Dağılımı:')
for status, count in sorted(status_count.items()):
    print(f'   {status}: {count}')

# SL orders detail
sl_orders = [o for o in all_eth if 'STOP' in str(o.get('type', '')).upper()]
print(f'\n📋 Stop Loss Emirleri ({len(sl_orders)}):')
for order in sl_orders:
    status = order.get('status', 'unknown')
    stop_price = order.get('stopPrice') or order.get('price', 0)
    dt = datetime.fromtimestamp(order['timestamp'] / 1000)
    print(f'   • Status: {status} - Stop: ${stop_price:.2f} - {dt.strftime("%Y-%m-%d %H:%M")}')
    if 'clientOrderId' in order:
        print(f'     Client ID: {order["clientOrderId"]}')

closed_sl = [o for o in sl_orders if o.get('status') == 'closed']
if closed_sl:
    print(f'\n❌ KAPANAN STOP LOSS: {len(closed_sl)}')
    for order in closed_sl[-5:]:
        dt = datetime.fromtimestamp(order['timestamp'] / 1000)
        stop_price = order.get('stopPrice') or order.get('price', 0)
        print(f'   • Stop: ${stop_price:.2f} - {dt.strftime("%Y-%m-%d %H:%M:%S")}')

# TP orders
tp_orders = [o for o in all_eth if 'TAKE_PROFIT' in str(o.get('type', '')).upper()]
closed_tp = [o for o in tp_orders if o.get('status') == 'closed']
if closed_tp:
    print(f'\n✅ KAPANAN TAKE PROFIT: {len(closed_tp)}')
    for order in closed_tp[-5:]:
        dt = datetime.fromtimestamp(order['timestamp'] / 1000)
        tp_price = order.get('stopPrice') or order.get('price', 0)
        print(f'   • TP: ${tp_price:.2f} - {dt.strftime("%Y-%m-%d %H:%M:%S")}')

# BTCUSDT
print(f'\n=== BTCUSDT ORDER STATUS ANALİZİ ===')
all_btc = exchange.fetch_orders('BTCUSDT', limit=50)
print(f'Toplam: {len(all_btc)}')

btc_status_count = {}
for order in all_btc:
    status = order.get('status', 'unknown')
    btc_status_count[status] = btc_status_count.get(status, 0) + 1

print('📊 Order Status Dağılımı:')
for status, count in sorted(btc_status_count.items()):
    print(f'   {status}: {count}')

btc_sl = [o for o in all_btc if 'STOP' in str(o.get('type', '')).upper()]
btc_tp = [o for o in all_btc if 'TAKE_PROFIT' in str(o.get('type', '')).upper()]

closed_btc_sl = [o for o in btc_sl if o.get('status') == 'closed']
closed_btc_tp = [o for o in btc_tp if o.get('status') == 'closed']

if closed_btc_sl:
    print(f'\n❌ BTC Stop Loss (Kapanan): {len(closed_btc_sl)}')
    for order in closed_btc_sl[-3:]:
        dt = datetime.fromtimestamp(order['timestamp'] / 1000)
        stop_price = order.get('stopPrice') or order.get('price', 0)
        print(f'   • Stop: ${stop_price:.2f} - {dt.strftime("%Y-%m-%d %H:%M")}')

if closed_btc_tp:
    print(f'\n✅ BTC Take Profit (Kapanan): {len(closed_btc_tp)}')
    for order in closed_btc_tp[-3:]:
        dt = datetime.fromtimestamp(order['timestamp'] / 1000)
        tp_price = order.get('stopPrice') or order.get('price', 0)
        print(f'   • TP: ${tp_price:.2f} - {dt.strftime("%Y-%m-%d %H:%M")}')

# Summary
total_sl_closed = len(closed_sl) + len(closed_btc_sl)
total_tp_closed = len(closed_tp) + len(closed_btc_tp)
total_closed = total_sl_closed + total_tp_closed

print(f'\n=== ÖZET ===')
print(f'Toplam Kapanan Pozisyon: {total_closed}')
if total_closed > 0:
    print(f'✅ Take Profit: {total_tp_closed} ({total_tp_closed/total_closed*100:.1f}%)')
    print(f'❌ Stop Loss: {total_sl_closed} ({total_sl_closed/total_closed*100:.1f}%)')
    print(f'📊 Win Rate: {total_tp_closed/total_closed*100:.1f}%')
else:
    print('⚪ Henüz kapanan pozisyon yok (tüm pozisyonlar açık veya emirler henüz tetiklenmedi)')

