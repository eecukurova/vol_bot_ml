#!/usr/bin/env python3
"""Count positive and negative PnL trades."""
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

print('=== PNL TRADE SAYIMI ===\n')

# ETHUSDT
eth_trades = exchange.fetch_my_trades('ETHUSDT', limit=500)

positive = []
negative = []

for trade in eth_trades:
    if 'info' in trade and 'realizedPnl' in trade['info']:
        pnl = float(trade['info']['realizedPnl'])
        if pnl > 0:
            positive.append(trade)
        elif pnl < 0:
            negative.append(trade)

print(f'📊 ETHUSDT:')
print(f'   ✅ Pozitif PnL: {len(positive)}')
print(f'   ❌ Negatif PnL: {len(negative)}\n')

if negative:
    print('❌ ETH NEGATİF PNL TRADE\'LERİ:')
    for i, trade in enumerate(negative, 1):
        dt = datetime.fromtimestamp(trade['timestamp'] / 1000)
        pnl = float(trade['info']['realizedPnl'])
        print(f'{i}. {trade["side"].upper()} @ ${trade["price"]:.2f} - PnL: ${pnl:.2f}')
        print(f'   Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'   Order ID: {trade.get("id", "N/A")}\n')

# BTCUSDT
btc_trades = exchange.fetch_my_trades('BTCUSDT', limit=500)

positive_btc = []
negative_btc = []

for trade in btc_trades:
    if 'info' in trade and 'realizedPnl' in trade['info']:
        pnl = float(trade['info']['realizedPnl'])
        if pnl > 0:
            positive_btc.append(trade)
        elif pnl < 0:
            negative_btc.append(trade)

print(f'\n📊 BTCUSDT:')
print(f'   ✅ Pozitif PnL: {len(positive_btc)}')
print(f'   ❌ Negatif PnL: {len(negative_btc)}\n')

if negative_btc:
    print('❌ BTC NEGATİF PNL TRADE\'LERİ:')
    for i, trade in enumerate(negative_btc, 1):
        dt = datetime.fromtimestamp(trade['timestamp'] / 1000)
        pnl = float(trade['info']['realizedPnl'])
        print(f'{i}. {trade["side"].upper()} @ ${trade["price"]:.2f} - PnL: ${pnl:.2f}')
        print(f'   Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'   Order ID: {trade.get("id", "N/A")}\n')

