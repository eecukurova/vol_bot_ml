#!/usr/bin/env python3
"""Analyze LLM positions and confidence levels"""
import json
import ccxt
import re
from datetime import datetime

# Load config
with open('configs/llm_config.json', 'r') as f:
    llm_cfg = json.load(f)

exchange = ccxt.binance({
    'apiKey': llm_cfg['api_key'],
    'secret': llm_cfg['secret'],
    'sandbox': False,
    'options': {'defaultType': 'future'}
})

symbol = 'BTCUSDT'

print('=== LLM POSITION CONFIDENCE ANALYSIS ===\n')

# Step 1: Parse log file for signals
signals = []
current_signal = {}

with open('runs/llm_live.log', 'r') as f:
    lines = f.readlines()
    
    for i, line in enumerate(lines):
        # Find SIGNAL line
        if '🎯 SIGNAL:' in line or 'SIGNAL:' in line:
            # Reset current signal
            current_signal = {}
            
            # Extract entry price
            if '@ $' in line:
                try:
                    price_str = line.split('@ $')[1].strip().split()[0]
                    current_signal['entry'] = float(price_str)
                except:
                    pass
            
            # Look ahead for confidence, TP, SL
            for j in range(i, min(i+5, len(lines))):
                next_line = lines[j]
                
                if 'Confidence:' in next_line:
                    try:
                        conf_str = next_line.split('Confidence:')[1].strip().replace('%', '').strip()
                        current_signal['confidence'] = float(conf_str)
                    except:
                        pass
                
                if 'TP: $' in next_line:
                    try:
                        tp_str = next_line.split('TP: $')[1].strip().split(',')[0].strip()
                        current_signal['tp'] = float(tp_str)
                    except:
                        pass
                
                if 'SL: $' in next_line or 'SL=' in next_line:
                    try:
                        if 'SL: $' in next_line:
                            sl_str = next_line.split('SL: $')[1].strip()
                        else:
                            sl_str = next_line.split('SL=')[1].strip()
                        current_signal['sl'] = float(sl_str)
                    except:
                        pass
                
                # If we found entry order placement, link it
                if 'Entry order placed:' in next_line:
                    try:
                        order_id = next_line.split('Entry order placed:')[1].strip()
                        current_signal['entry_order_id'] = order_id
                    except:
                        pass
            
            # Save signal if we have entry and confidence
            if 'entry' in current_signal and 'confidence' in current_signal:
                signals.append(current_signal.copy())

print(f'Signals found in log: {len(signals)}')

# Step 2: Get SL closures
orders = exchange.fetch_orders(symbol, limit=500)
sl_closed = []

for order in orders:
    client_id = order.get('clientOrderId', '')
    if 'EMA-' in client_id and '-sl-' in client_id and order.get('status') == 'closed':
        sl_closed.append({
            'stop_price': float(order.get('stopPrice', 0)),
            'time': datetime.fromtimestamp(order['timestamp'] / 1000)
        })

print(f'SL closures: {len(sl_closed)}\n')

# Step 3: Match SL closures with signals
sl_signals = []

for sl in sl_closed:
    # Find signal with matching SL price
    for sig in signals:
        if 'sl' in sig and abs(sig['sl'] - sl['stop_price']) / sl['stop_price'] < 0.01:
            sl_signals.append(sig)
            break

print('=== SL POSITIONS ANALYSIS ===')
if sl_signals:
    print(f'Matched SL positions: {len(sl_signals)}\n')
    
    sl_confs = [s['confidence'] for s in sl_signals]
    print('SL Position Confidence:')
    print(f'  Average: {sum(sl_confs) / len(sl_confs):.1f}%')
    print(f'  Range: {min(sl_confs):.1f}% - {max(sl_confs):.1f}%')
    
    print('\nSL Positions Details:')
    for sig in sl_signals:
        loss_pct = ((sig['entry'] - sig['sl']) / sig['entry']) * 100
        print(f"  Entry: ${sig['entry']:.2f} | SL: ${sig['sl']:.2f} | Conf: {sig['confidence']:.1f}% | Loss: {loss_pct:.2f}%")
else:
    print('Could not match SL positions with signals')

# Step 4: Compare with all opened positions
print('\n=== ALL OPENED POSITIONS ===')
all_confs = [s['confidence'] for s in signals if 'entry_order_id' in s or 'entry' in s]
if all_confs:
    print(f'Total opened: {len(all_confs)}')
    print(f'Average confidence: {sum(all_confs) / len(all_confs):.1f}%')
    print(f'Range: {min(all_confs):.1f}% - {max(all_confs):.1f}%')
    
    # Group by confidence
    high = [c for c in all_confs if c >= 80]
    med = [c for c in all_confs if 70 <= c < 80]
    low = [c for c in all_confs if c < 70]
    
    print(f'\nDistribution:')
    print(f'  High (>=80%): {len(high)} ({len(high)/len(all_confs)*100:.1f}%)')
    print(f'  Medium (70-80%): {len(med)} ({len(med)/len(all_confs)*100:.1f}%)')
    print(f'  Low (<70%): {len(low)} ({len(low)/len(all_confs)*100:.1f}%)')

# Step 5: Recommendation
print('\n=== RECOMMENDATION ===')
if sl_signals:
    avg_sl_conf = sum(sl_confs) / len(sl_confs)
    avg_all_conf = sum(all_confs) / len(all_confs) if all_confs else 0
    
    if avg_sl_conf < avg_all_conf:
        diff = avg_all_conf - avg_sl_conf
        print(f'⚠️ SL positions have {diff:.1f}% LOWER confidence on average')
        print(f'   SL avg: {avg_sl_conf:.1f}% vs All avg: {avg_all_conf:.1f}%')
        print('\n✅ RECOMMENDATION: Increase minimum confidence threshold')
        print(f'   Current: 65% (from config)')
        print(f'   Suggested: {int(avg_sl_conf + 5)}% or higher')
    else:
        print(f'SL positions confidence similar to all ({avg_sl_conf:.1f}% vs {avg_all_conf:.1f}%)')
        print('Model performance issue - consider retraining or adjusting TP/SL ratios')

