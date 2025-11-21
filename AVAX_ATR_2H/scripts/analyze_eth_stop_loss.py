#!/usr/bin/env python3
"""Analyze ETH stop loss positions."""
import ccxt
import json
import pandas as pd
from datetime import datetime, timedelta
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

print('=== ETH STOP LOSS ANALİZİ ===\n')

# Get all trades
symbol = 'ETH/USDT:USDT'
trades = exchange.fetch_my_trades(symbol, limit=200)

if not trades:
    print('⚪ İşlem yok')
    sys.exit(0)

# Sort by timestamp
trades.sort(key=lambda x: x['timestamp'])

# Pair trades into positions
positions = []
i = 0
while i < len(trades):
    trade = trades[i]
    
    if trade['side'] == 'buy':
        # LONG position: find corresponding sell
        for j in range(i+1, len(trades)):
            if trades[j]['side'] == 'sell' and trades[j]['order'] != trade['order']:
                entry_price = float(trade['price'])
                exit_price = float(trades[j]['price'])
                entry_time = datetime.fromtimestamp(trade['timestamp'] / 1000)
                exit_time = datetime.fromtimestamp(trades[j]['timestamp'] / 1000)
                
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                
                # Determine exit reason based on TP/SL
                # TP = 0.5% = entry * 1.005
                # SL = 1.0% = entry * 0.99
                tp_price = entry_price * 1.005
                sl_price = entry_price * 0.99
                
                if abs(exit_price - tp_price) < abs(exit_price - sl_price):
                    exit_reason = 'TP'
                else:
                    exit_reason = 'SL'
                
                positions.append({
                    'side': 'LONG',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'pnl_pct': pnl_pct,
                    'exit_reason': exit_reason,
                    'entry_trade_id': trade['id'],
                    'exit_trade_id': trades[j]['id'],
                })
                i = j + 1
                break
        else:
            i += 1
    elif trade['side'] == 'sell':
        # SHORT position: find corresponding buy
        for j in range(i+1, len(trades)):
            if trades[j]['side'] == 'buy' and trades[j]['order'] != trade['order']:
                entry_price = float(trade['price'])
                exit_price = float(trades[j]['price'])
                entry_time = datetime.fromtimestamp(trade['timestamp'] / 1000)
                exit_time = datetime.fromtimestamp(trades[j]['timestamp'] / 1000)
                
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                
                # Determine exit reason
                tp_price = entry_price * 0.995
                sl_price = entry_price * 1.01
                
                if abs(exit_price - tp_price) < abs(exit_price - sl_price):
                    exit_reason = 'TP'
                else:
                    exit_reason = 'SL'
                
                positions.append({
                    'side': 'SHORT',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'pnl_pct': pnl_pct,
                    'exit_reason': exit_reason,
                    'entry_trade_id': trade['id'],
                    'exit_trade_id': trades[j]['id'],
                })
                i = j + 1
                break
        else:
            i += 1
    else:
        i += 1

# Sort by exit time
positions.sort(key=lambda x: x['exit_time'], reverse=True)

print(f'Toplam Pozisyon: {len(positions)}\n')

# Get SL positions
sl_positions = [p for p in positions if p['exit_reason'] == 'SL']
tp_positions = [p for p in positions if p['exit_reason'] == 'TP']

print(f'❌ Stop Loss: {len(sl_positions)}')
print(f'✅ Take Profit: {len(tp_positions)}\n')

# Analyze last 2 SL positions
print('='*80)
print('📊 SON 2 STOP LOSS POZİSYON ANALİZİ')
print('='*80)

for i, pos in enumerate(sl_positions[:2], 1):
    print(f'\n🔹 Stop Loss {i}:')
    print(f'   Side: {pos["side"]}')
    print(f'   Entry: {pos["entry_time"].strftime("%Y-%m-%d %H:%M:%S")} @ ${pos["entry_price"]:.2f}')
    print(f'   Exit:  {pos["exit_time"].strftime("%Y-%m-%d %H:%M:%S")} @ ${pos["exit_price"]:.2f}')
    print(f'   PnL: {pos["pnl_pct"]:.2f}%')
    print(f'   Süre: {(pos["exit_time"] - pos["entry_time"]).total_seconds() / 60:.1f} dakika')
    
    # Check log file for this position
    print(f'\n   📋 Log analizi için entry time: {pos["entry_time"].strftime("%Y-%m-%d %H:%M")}')

# Compare with TP positions
print('\n' + '='*80)
print('📊 SON 2 TAKE PROFIT POZİSYON (KARŞILAŞTIRMA)')
print('='*80)

for i, pos in enumerate(tp_positions[:2], 1):
    print(f'\n✅ Take Profit {i}:')
    print(f'   Side: {pos["side"]}')
    print(f'   Entry: {pos["entry_time"].strftime("%Y-%m-%d %H:%M:%S")} @ ${pos["entry_price"]:.2f}')
    print(f'   Exit:  {pos["exit_time"].strftime("%Y-%m-%d %H:%M:%S")} @ ${pos["exit_price"]:.2f}')
    print(f'   PnL: {pos["pnl_pct"]:.2f}%')
    print(f'   Süre: {(pos["exit_time"] - pos["entry_time"]).total_seconds() / 60:.1f} dakika')

# Statistics
print('\n' + '='*80)
print('📊 İSTATİSTİKLER')
print('='*80)

if sl_positions:
    avg_sl_duration = sum([(p['exit_time'] - p['entry_time']).total_seconds() / 60 for p in sl_positions]) / len(sl_positions)
    print(f'\n❌ Stop Loss:')
    print(f'   Ortalama Süre: {avg_sl_duration:.1f} dakika')
    print(f'   Min PnL: {min(p["pnl_pct"] for p in sl_positions):.2f}%')
    print(f'   Max PnL: {max(p["pnl_pct"] for p in sl_positions):.2f}%')

if tp_positions:
    avg_tp_duration = sum([(p['exit_time'] - p['entry_time']).total_seconds() / 60 for p in tp_positions]) / len(tp_positions)
    print(f'\n✅ Take Profit:')
    print(f'   Ortalama Süre: {avg_tp_duration:.1f} dakika')
    print(f'   Min PnL: {min(p["pnl_pct"] for p in tp_positions):.2f}%')
    print(f'   Max PnL: {max(p["pnl_pct"] for p in tp_positions):.2f}%')

print('\n' + '='*80)

