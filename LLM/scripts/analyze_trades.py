#!/usr/bin/env python3
"""Analyze trade history for PnL and stop loss detection."""
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

print('=== TRADE HISTORY ANALİZİ ===\n')

# Get trades (last 30 days)
since = exchange.milliseconds() - 30 * 24 * 60 * 60 * 1000

# ETHUSDT trades
eth_trades = exchange.fetch_my_trades('ETHUSDT', since=since, limit=100)
print(f'📊 ETHUSDT Trades (Son 30 gün): {len(eth_trades)}')

if eth_trades:
    buy_trades = [t for t in eth_trades if t['side'] == 'buy']
    sell_trades = [t for t in eth_trades if t['side'] == 'sell']
    
    print(f'   Alış (Buy): {len(buy_trades)}')
    print(f'   Satış (Sell): {len(sell_trades)}')
    
    # Calculate PnL
    total_pnl = 0
    sl_trades = []
    tp_trades = []
    
    for trade in eth_trades:
        if 'info' in trade:
            pnl = trade['info'].get('realizedPnl', 0)
            if pnl:
                pnl_val = float(pnl)
                total_pnl += pnl_val
                if pnl_val < 0:
                    sl_trades.append(trade)
                elif pnl_val > 0:
                    tp_trades.append(trade)
    
    print(f'   Toplam Realized PnL: ${total_pnl:.2f}')
    print(f'   ❌ Zararlı İşlem (Stop Loss): {len(sl_trades)}')
    print(f'   ✅ Karlı İşlem (Take Profit): {len(tp_trades)}')
    
    if sl_trades:
        print(f'\n   ❌ STOP LOSS İŞLEMLERİ:')
        for trade in sl_trades[-5:]:
            dt = datetime.fromtimestamp(trade['timestamp'] / 1000)
            pnl = float(trade['info'].get('realizedPnl', 0))
            print(f'   • {trade["side"].upper()} @ ${trade["price"]:.2f}')
            print(f'     PnL: ${pnl:.2f} - Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')

# BTCUSDT trades
btc_trades = exchange.fetch_my_trades('BTCUSDT', since=since, limit=100)
print(f'\n📊 BTCUSDT Trades (Son 30 gün): {len(btc_trades)}')

if btc_trades:
    buy_trades = [t for t in btc_trades if t['side'] == 'buy']
    sell_trades = [t for t in btc_trades if t['side'] == 'sell']
    
    print(f'   Alış (Buy): {len(buy_trades)}')
    print(f'   Satış (Sell): {len(sell_trades)}')
    
    total_pnl = 0
    sl_trades = []
    tp_trades = []
    
    for trade in btc_trades:
        if 'info' in trade:
            pnl = trade['info'].get('realizedPnl', 0)
            if pnl:
                pnl_val = float(pnl)
                total_pnl += pnl_val
                if pnl_val < 0:
                    sl_trades.append(trade)
                elif pnl_val > 0:
                    tp_trades.append(trade)
    
    print(f'   Toplam Realized PnL: ${total_pnl:.2f}')
    print(f'   ❌ Zararlı İşlem (Stop Loss): {len(sl_trades)}')
    print(f'   ✅ Karlı İşlem (Take Profit): {len(tp_trades)}')
    
    if sl_trades:
        print(f'\n   ❌ STOP LOSS İŞLEMLERİ:')
        for trade in sl_trades[-5:]:
            dt = datetime.fromtimestamp(trade['timestamp'] / 1000)
            pnl = float(trade['info'].get('realizedPnl', 0))
            print(f'   • {trade["side"].upper()} @ ${trade["price"]:.2f}')
            print(f'     PnL: ${pnl:.2f} - Zaman: {dt.strftime("%Y-%m-%d %H:%M:%S")}')

# Summary
total_sl = len([t for t in eth_trades + btc_trades if 'info' in t and float(t['info'].get('realizedPnl', 0)) < 0])
total_tp = len([t for t in eth_trades + btc_trades if 'info' in t and float(t['info'].get('realizedPnl', 0)) > 0])
total = total_sl + total_tp

print(f'\n=== ÖZET ===')
print(f'Toplam Kapanan Pozisyon: {total}')
if total > 0:
    print(f'✅ Take Profit: {total_tp} ({total_tp/total*100:.1f}%)')
    print(f'❌ Stop Loss: {total_sl} ({total_sl/total*100:.1f}%)')
    print(f'📊 Win Rate: {total_tp/total*100:.1f}%')
else:
    print('⚪ Henüz kapanan pozisyon yok')

