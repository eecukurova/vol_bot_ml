#!/usr/bin/env python3
import ccxt
import json

# Config yükle
with open('sol_macd_config.json', 'r') as f:
    config = json.load(f)

# Exchange bağlantısı
exchange = ccxt.binance({
    'apiKey': config['api_key'],
    'secret': config['secret'],
    'sandbox': config['sandbox'],
    'options': {'defaultType': 'future'}
})

# Mevcut pozisyonları kontrol et
positions = exchange.fetch_positions(['SOL/USDT'])
print('=== MEVCUT POZİSYONLAR ===')
for pos in positions:
    if pos['contracts'] > 0:
        print(f'Symbol: {pos["symbol"]}')
        print(f'Side: {pos["side"]}')
        print(f'Contracts: {pos["contracts"]}')
        print(f'Entry Price: {pos["entryPrice"]}')
        print(f'Mark Price: {pos["markPrice"]}')
        print(f'Unrealized PnL: {pos["unrealizedPnl"]}')
        print('---')

# Açık order'ları kontrol et
open_orders = exchange.fetch_open_orders('SOL/USDT')
print('=== AÇIK ORDERLAR ===')
for order in open_orders:
    print(f'Order ID: {order["id"]}')
    print(f'Type: {order["type"]}')
    print(f'Side: {order["side"]}')
    print(f'Status: {order["status"]}')
    print(f'Price: {order["price"]}')
    print('---')
