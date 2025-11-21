#!/usr/bin/env python3
"""Comprehensive position analysis - match trades with logs."""
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

print('=== KAPSAMLI POZİSYON ANALİZİ ===\n')

# Get all trades (last 60 days)
since = exchange.milliseconds() - 60 * 24 * 60 * 60 * 1000

def analyze_positions(symbol, project_name):
    """Analyze positions for a symbol."""
    trades = exchange.fetch_my_trades(symbol, since=since, limit=200)
    
    print(f'=== {project_name} ({symbol}) ===\n')
    print(f'Toplam Trade: {len(trades)}\n')
    
    if not trades:
        print('⚪ İşlem yok\n')
        return
    
    # Pair trades to find positions
    positions = []
    i = 0
    while i < len(trades):
        trade = trades[i]
        
        if trade['side'] == 'buy':
            # LONG position: buy entry, sell exit
            for j in range(i+1, len(trades)):
                if trades[j]['side'] == 'sell':
                    pnl = 0
                    if 'info' in trades[j] and 'realizedPnl' in trades[j]['info']:
                        pnl = float(trades[j]['info']['realizedPnl'])
                    
                    positions.append({
                        'type': 'LONG',
                        'entry': trade,
                        'exit': trades[j],
                        'pnl': pnl,
                        'entry_time': trade['timestamp'],
                        'exit_time': trades[j]['timestamp']
                    })
                    i = j + 1
                    break
            else:
                i += 1
        elif trade['side'] == 'sell':
            # SHORT position: sell entry, buy exit
            for j in range(i+1, len(trades)):
                if trades[j]['side'] == 'buy':
                    pnl = 0
                    if 'info' in trades[j] and 'realizedPnl' in trades[j]['info']:
                        pnl = float(trades[j]['info']['realizedPnl'])
                    
                    positions.append({
                        'type': 'SHORT',
                        'entry': trade,
                        'exit': trades[j],
                        'pnl': pnl,
                        'entry_time': trade['timestamp'],
                        'exit_time': trades[j]['timestamp']
                    })
                    i = j + 1
                    break
            else:
                i += 1
        else:
            i += 1
    
    if not positions:
        print('⚪ Kapanan pozisyon yok\n')
        return
    
    # Sort by exit time
    positions.sort(key=lambda x: x['exit_time'])
    
    profitable = [p for p in positions if p['pnl'] > 0]
    losing = [p for p in positions if p['pnl'] < 0]
    
    print(f'📈 Toplam Kapanan Pozisyon: {len(positions)}')
    print(f'✅ Karlı (Take Profit): {len(profitable)}')
    print(f'❌ Zararlı (Stop Loss): {len(losing)}\n')
    
    if profitable:
        print('✅ KARLI POZİSYONLAR:')
        for i, pos in enumerate(profitable, 1):
            entry_dt = datetime.fromtimestamp(pos['entry_time'] / 1000)
            exit_dt = datetime.fromtimestamp(pos['exit_time'] / 1000)
            entry_price = pos['entry']['price']
            exit_price = pos['exit']['price']
            
            print(f'\n{i}. {pos["type"]} Pozisyon:')
            print(f'   Entry: ${entry_price:.2f} - {entry_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   Exit: ${exit_price:.2f} - {exit_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   PnL: ${pos["pnl"]:.2f} ✅')
            print(f'   Entry Order ID: {pos["entry"].get("id", "N/A")}')
            print(f'   Exit Order ID: {pos["exit"].get("id", "N/A")}')
    
    if losing:
        print(f'\n❌ ZARARLI POZİSYONLAR (STOP LOSS):')
        for i, pos in enumerate(losing, 1):
            entry_dt = datetime.fromtimestamp(pos['entry_time'] / 1000)
            exit_dt = datetime.fromtimestamp(pos['exit_time'] / 1000)
            entry_price = pos['entry']['price']
            exit_price = pos['exit']['price']
            
            print(f'\n{i}. {pos["type"]} Pozisyon:')
            print(f'   Entry: ${entry_price:.2f} - {entry_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   Exit: ${exit_price:.2f} - {exit_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   PnL: ${pos["pnl"]:.2f} ❌')
            print(f'   Entry Order ID: {pos["entry"].get("id", "N/A")}')
            print(f'   Exit Order ID: {pos["exit"].get("id", "N/A")}')
            
            # Calculate loss percentage
            if pos['type'] == 'LONG':
                loss_pct = ((exit_price - entry_price) / entry_price) * 100
            else:
                loss_pct = ((entry_price - exit_price) / entry_price) * 100
            print(f'   Loss: {loss_pct:.2f}%')
    
    print()

# Analyze both
analyze_positions('ETHUSDT', 'ETH Projesi')
analyze_positions('BTCUSDT', 'LLM Projesi')

