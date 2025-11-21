#!/usr/bin/env python3
"""Match trades with log entries to find position details."""
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

def find_positions_with_pnl(symbol, since_days=30):
    """Find all closed positions with PnL."""
    since = exchange.milliseconds() - since_days * 24 * 60 * 60 * 1000
    trades = exchange.fetch_my_trades(symbol, since=since, limit=200)
    
    if not trades:
        return []
    
    # Match entry and exit trades
    positions = []
    used_indices = set()
    
    for i, trade in enumerate(trades):
        if i in used_indices:
            continue
        
        # Find matching exit trade
        for j in range(i+1, len(trades)):
            if j in used_indices:
                continue
            
            exit_trade = trades[j]
            
            # Check if they form a position pair
            is_pair = False
            if trade['side'] == 'buy' and exit_trade['side'] == 'sell':
                is_pair = True
                pos_type = 'LONG'
            elif trade['side'] == 'sell' and exit_trade['side'] == 'buy':
                is_pair = True
                pos_type = 'SHORT'
            
            if is_pair:
                # Get PnL from exit trade
                pnl = 0
                if 'info' in exit_trade and 'realizedPnl' in exit_trade['info']:
                    pnl = float(exit_trade['info']['realizedPnl'])
                
                positions.append({
                    'type': pos_type,
                    'entry': trade,
                    'exit': exit_trade,
                    'pnl': pnl,
                    'entry_time': trade['timestamp'],
                    'exit_time': exit_trade['timestamp']
                })
                
                used_indices.add(i)
                used_indices.add(j)
                break
    
    return positions

print('=== KAPSAMLI POZİSYON EŞLEŞTİRME ===\n')

# ETHUSDT
eth_positions = find_positions_with_pnl('ETHUSDT', since_days=30)
print(f'=== ETH PROJESİ (ETHUSDT) ===')
print(f'Toplam Kapanan Pozisyon: {len(eth_positions)}\n')

if eth_positions:
    profitable = [p for p in eth_positions if p['pnl'] > 0]
    losing = [p for p in eth_positions if p['pnl'] < 0]
    
    print(f'✅ Karlı Pozisyonlar: {len(profitable)}')
    print(f'❌ Zararlı Pozisyonlar: {len(losing)}\n')
    
    if profitable:
        print('✅ KARLI POZİSYONLAR (TAKE PROFIT):')
        for i, pos in enumerate(profitable, 1):
            entry_dt = datetime.fromtimestamp(pos['entry_time'] / 1000)
            exit_dt = datetime.fromtimestamp(pos['exit_time'] / 1000)
            print(f'\n{i}. {pos["type"]} Pozisyon:')
            print(f'   Entry: ${pos["entry"]["price"]:.2f} - {entry_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   Exit: ${pos["exit"]["price"]:.2f} - {exit_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   PnL: ${pos["pnl"]:.2f} ✅')
    
    if losing:
        print(f'\n❌ ZARARLI POZİSYONLAR (STOP LOSS):')
        for i, pos in enumerate(losing, 1):
            entry_dt = datetime.fromtimestamp(pos['entry_time'] / 1000)
            exit_dt = datetime.fromtimestamp(pos['exit_time'] / 1000)
            print(f'\n{i}. {pos["type"]} Pozisyon:')
            print(f'   Entry: ${pos["entry"]["price"]:.2f} - {entry_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   Exit: ${pos["exit"]["price"]:.2f} - {exit_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   PnL: ${pos["pnl"]:.2f} ❌')
            
            # Calculate percentage
            if pos['type'] == 'LONG':
                pct = ((pos['exit']['price'] - pos['entry']['price']) / pos['entry']['price']) * 100
            else:
                pct = ((pos['entry']['price'] - pos['exit']['price']) / pos['entry']['price']) * 100
            print(f'   Loss: {pct:.2f}%')

# BTCUSDT
btc_positions = find_positions_with_pnl('BTCUSDT', since_days=30)
print(f'\n=== LLM PROJESİ (BTCUSDT) ===')
print(f'Toplam Kapanan Pozisyon: {len(btc_positions)}\n')

if btc_positions:
    profitable = [p for p in btc_positions if p['pnl'] > 0]
    losing = [p for p in btc_positions if p['pnl'] < 0]
    
    print(f'✅ Karlı Pozisyonlar: {len(profitable)}')
    print(f'❌ Zararlı Pozisyonlar: {len(losing)}\n')
    
    if profitable:
        print('✅ KARLI POZİSYONLAR:')
        for i, pos in enumerate(profitable, 1):
            entry_dt = datetime.fromtimestamp(pos['entry_time'] / 1000)
            exit_dt = datetime.fromtimestamp(pos['exit_time'] / 1000)
            print(f'\n{i}. {pos["type"]} - Entry: ${pos["entry"]["price"]:.2f} ({entry_dt.strftime("%Y-%m-%d %H:%M")}) - Exit: ${pos["exit"]["price"]:.2f} ({exit_dt.strftime("%Y-%m-%d %H:%M")}) - PnL: ${pos["pnl"]:.2f}')
    
    if losing:
        print(f'\n❌ ZARARLI POZİSYONLAR (STOP LOSS):')
        for i, pos in enumerate(losing, 1):
            entry_dt = datetime.fromtimestamp(pos['entry_time'] / 1000)
            exit_dt = datetime.fromtimestamp(pos['exit_time'] / 1000)
            print(f'\n{i}. {pos["type"]} Pozisyon:')
            print(f'   Entry: ${pos["entry"]["price"]:.2f} - {entry_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   Exit: ${pos["exit"]["price"]:.2f} - {exit_dt.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'   PnL: ${pos["pnl"]:.2f} ❌')

