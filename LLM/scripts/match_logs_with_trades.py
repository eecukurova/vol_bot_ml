#!/usr/bin/env python3
"""Match log entries with trade history to find position details."""
import json
import ccxt
from datetime import datetime
from pathlib import Path
import sys
import re

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

print('=== LOG VE TRADE EŞLEŞTİRME ===\n')

# Get all trades
btc_trades = exchange.fetch_my_trades('BTCUSDT', limit=500)
eth_trades = exchange.fetch_my_trades('ETHUSDT', limit=500)

# Find negative PnL trades
eth_negative = []
for trade in eth_trades:
    if 'info' in trade and 'realizedPnl' in trade['info']:
        pnl = float(trade['info']['realizedPnl'])
        if pnl < 0:
            eth_negative.append(trade)

btc_negative = []
for trade in btc_trades:
    if 'info' in trade and 'realizedPnl' in trade['info']:
        pnl = float(trade['info']['realizedPnl'])
        if pnl < 0:
            btc_negative.append(trade)

# Sort by time (newest first)
eth_negative.sort(key=lambda x: x['timestamp'], reverse=True)
btc_negative.sort(key=lambda x: x['timestamp'], reverse=True)

print(f'=== ETH PROJESİ - STOP LOSS POZİSYONLARI ===\n')
print(f'Toplam Negatif PnL Trade: {len(eth_negative)}\n')

if eth_negative:
    print('❌ EN SON STOP LOSS TRADE\'LERİ:')
    for i, trade in enumerate(eth_negative[:5], 1):
        dt = datetime.fromtimestamp(trade['timestamp'] / 1000)
        pnl = float(trade['info']['realizedPnl'])
        side = trade['side'].upper()
        price = trade['price']
        order_id = trade.get('id', 'N/A')
        
        print(f'\n{i}. {side} @ ${price:.2f}')
        print(f'   PnL: ${pnl:.2f} ❌')
        print(f'   Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'   Order ID: {order_id}')
        
        # Find matching entry trade (before this exit)
        entry_trade = None
        for entry in eth_trades:
            if entry['timestamp'] < trade['timestamp']:
                # Check if they form a pair
                if (entry['side'] == 'buy' and trade['side'] == 'sell') or \
                   (entry['side'] == 'sell' and trade['side'] == 'buy'):
                    entry_trade = entry
                    break
        
        if entry_trade:
            entry_dt = datetime.fromtimestamp(entry_trade['timestamp'] / 1000)
            print(f'   Entry: ${entry_trade["price"]:.2f} ({entry_dt.strftime("%Y-%m-%d %H:%M")})')

print(f'\n=== LLM PROJESİ - STOP LOSS POZİSYONLARI ===\n')
print(f'Toplam Negatif PnL Trade: {len(btc_negative)}\n')

if btc_negative:
    print('❌ EN SON STOP LOSS TRADE\'LERİ:')
    for i, trade in enumerate(btc_negative[:5], 1):
        dt = datetime.fromtimestamp(trade['timestamp'] / 1000)
        pnl = float(trade['info']['realizedPnl'])
        side = trade['side'].upper()
        price = trade['price']
        order_id = trade.get('id', 'N/A')
        
        print(f'\n{i}. {side} @ ${price:.2f}')
        print(f'   PnL: ${pnl:.2f} ❌')
        print(f'   Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'   Order ID: {order_id}')
        
        # Find matching entry trade
        entry_trade = None
        for entry in btc_trades:
            if entry['timestamp'] < trade['timestamp']:
                if (entry['side'] == 'buy' and trade['side'] == 'sell') or \
                   (entry['side'] == 'sell' and trade['side'] == 'buy'):
                    entry_trade = entry
                    break
        
        if entry_trade:
            entry_dt = datetime.fromtimestamp(entry_trade['timestamp'] / 1000)
            print(f'   Entry: ${entry_trade["price"]:.2f} ({entry_dt.strftime("%Y-%m-%d %H:%M")})')

# Summary
print(f'\n=== ÖZET ===')
print(f'ETH Negatif PnL Trade: {len(eth_negative)}')
print(f'BTC Negatif PnL Trade: {len(btc_negative)}')
print(f'\nToplam Stop Loss: {len(eth_negative) + len(btc_negative)}')

