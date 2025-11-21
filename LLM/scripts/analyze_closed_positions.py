#!/usr/bin/env python3
"""Analyze closed positions from Binance API."""
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

print('=== DETAYLI POZİSYON ANALİZİ ===\n')

# Get all orders (last 30 days)
since = exchange.milliseconds() - 30 * 24 * 60 * 60 * 1000

try:
    # BTCUSDT
    all_orders_btc = exchange.fetch_orders('BTCUSDT', since=since, limit=200)
    
    # ETHUSDT
    all_orders_eth = exchange.fetch_orders('ETHUSDT', since=since, limit=200)
    
    print(f'📊 BTCUSDT Toplam Emir: {len(all_orders_btc)}')
    print(f'📊 ETHUSDT Toplam Emir: {len(all_orders_eth)}')
    
    # Analyze BTC orders
    btc_entry = [o for o in all_orders_btc if o.get('type') == 'market' and o.get('status') == 'closed']
    btc_sl = [o for o in all_orders_btc if 'STOP' in str(o.get('type', '')).upper() and o.get('status') == 'closed']
    btc_tp = [o for o in all_orders_btc if 'TAKE_PROFIT' in str(o.get('type', '')).upper() and o.get('status') == 'closed']
    
    print(f'\n=== LLM (BTCUSDT) ===')
    print(f'Entry Orders: {len(btc_entry)}')
    print(f'Stop Loss (Kapanan): {len(btc_sl)}')
    print(f'Take Profit (Kapanan): {len(btc_tp)}')
    
    if btc_sl:
        print(f'\n❌ STOP LOSS DETAYLARI:')
        for i, order in enumerate(btc_sl[-5:], 1):
            dt = datetime.fromtimestamp(order['timestamp'] / 1000)
            stop_price = order.get('stopPrice') or order.get('price', 0)
            print(f'{i}. {order.get("side", "N/A")} - Stop: ${stop_price:.2f}')
            print(f'   Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   Order ID: {order.get("id", "N/A")}')
    
    # Analyze ETH orders
    eth_entry = [o for o in all_orders_eth if o.get('type') == 'market' and o.get('status') == 'closed']
    eth_sl = [o for o in all_orders_eth if 'STOP' in str(o.get('type', '')).upper() and o.get('status') == 'closed']
    eth_tp = [o for o in all_orders_eth if 'TAKE_PROFIT' in str(o.get('type', '')).upper() and o.get('status') == 'closed']
    
    print(f'\n=== ETH (ETHUSDT) ===')
    print(f'Entry Orders: {len(eth_entry)}')
    print(f'Stop Loss (Kapanan): {len(eth_sl)}')
    print(f'Take Profit (Kapanan): {len(eth_tp)}')
    
    if eth_sl:
        print(f'\n❌ STOP LOSS DETAYLARI:')
        for i, order in enumerate(eth_sl[-5:], 1):
            dt = datetime.fromtimestamp(order['timestamp'] / 1000)
            stop_price = order.get('stopPrice') or order.get('price', 0)
            print(f'{i}. {order.get("side", "N/A")} - Stop: ${stop_price:.2f}')
            print(f'   Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   Order ID: {order.get("id", "N/A")}')
    
    # Overall stats
    total_sl = len(btc_sl) + len(eth_sl)
    total_tp = len(btc_tp) + len(eth_tp)
    total = total_sl + total_tp
    
    print(f'\n=== GENEL ÖZET ===')
    print(f'Toplam Kapanan Pozisyon: {total}')
    if total > 0:
        print(f'✅ Take Profit: {total_tp} ({total_tp/total*100:.1f}%)')
        print(f'❌ Stop Loss: {total_sl} ({total_sl/total*100:.1f}%)')
        print(f'📊 Win Rate: {total_tp/total*100:.1f}%')
    
except Exception as e:
    print(f'❌ Hata: {e}')
    import traceback
    traceback.print_exc()

