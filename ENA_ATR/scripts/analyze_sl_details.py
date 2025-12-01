#!/usr/bin/env python3
"""Detailed analysis of SL positions from logs."""
import re
from datetime import datetime
from pathlib import Path

log_file = Path('runs/eth_live.log')

if not log_file.exists():
    print('Log dosyası bulunamadı')
    exit(1)

# SL positions from Binance
sl_positions = [
    {'entry_time': datetime(2025, 11, 4, 18, 51, 0), 'entry_price': 3516.83, 'side': 'LONG'},
    {'entry_time': datetime(2025, 11, 4, 18, 23, 21), 'entry_price': 3565.20, 'side': 'LONG'},
]

# TP positions for comparison
tp_positions = [
    {'entry_time': datetime(2025, 11, 4, 6, 50, 27), 'entry_price': 3640.55, 'side': 'SHORT'},
    {'entry_time': datetime(2025, 11, 3, 4, 40, 7), 'entry_price': 3837.50, 'side': 'SHORT'},
]

print('='*80)
print('📊 DETAYLI STOP LOSS ANALİZİ')
print('='*80)

# Read log file
with open(log_file, 'r') as f:
    lines = f.readlines()

# Find signals around SL positions
for sl_pos in sl_positions:
    print(f'\n🔍 STOP LOSS POZİSYON ANALİZİ')
    print(f'   Entry: {sl_pos["entry_time"].strftime("%Y-%m-%d %H:%M")} @ ${sl_pos["entry_price"]:.2f}')
    print(f'   Side: {sl_pos["side"]}')
    print(f'\n   📋 LOG DETAYLARI:')
    
    # Find nearby signals
    for i, line in enumerate(lines):
        # Check if line has signal info
        if 'SIGNAL:' in line and sl_pos['side'] in line:
            # Check if price is close
            price_match = re.search(r'@ \$([\d.]+)', line)
            if price_match:
                log_price = float(price_match.group(1))
                # Check if within $5 of entry price
                if abs(log_price - sl_pos['entry_price']) < 5:
                    # Extract confidence
                    conf_match = re.search(r'Confidence: ([\d.]+)%', line)
                    confidence = float(conf_match.group(1)) if conf_match else None
                    
                    # Get prob info from next lines
                    probs = {}
                    for j in range(i+1, min(i+5, len(lines))):
                        prob_match = re.search(r'Probs: Flat=([\d.]+)%, Long=([\d.]+)%, Short=([\d.]+)%', lines[j])
                        if prob_match:
                            probs = {
                                'flat': float(prob_match.group(1)),
                                'long': float(prob_match.group(2)),
                                'short': float(prob_match.group(3))
                            }
                            break
                    
                    print(f'      ✅ Sinyal bulundu:')
                    print(f'         Log Price: ${log_price:.2f}')
                    print(f'         Confidence: {confidence:.1f}%' if confidence else '         Confidence: N/A')
                    if probs:
                        print(f'         Probs: Flat={probs[\"flat\"]:.1f}%, Long={probs[\"long\"]:.1f}%, Short={probs[\"short\"]:.1f}%')
                    
                    # Check for regime filter info
                    for j in range(max(0, i-20), i):
                        if 'Regime filter' in lines[j] or 'vol_spike' in lines[j].lower():
                            print(f'         {lines[j].strip()}')
                    
                    break

# Compare with TP positions
print(f'\n\n' + '='*80)
print('📊 TAKE PROFIT POZİSYONLAR (KARŞILAŞTIRMA)')
print('='*80)

for tp_pos in tp_positions:
    print(f'\n✅ TAKE PROFIT POZİSYON')
    print(f'   Entry: {tp_pos["entry_time"].strftime("%Y-%m-%d %H:%M")} @ ${tp_pos["entry_price"]:.2f}')
    print(f'   Side: {tp_pos["side"]}')
    
    # Find nearby signals
    for i, line in enumerate(lines):
        if 'SIGNAL:' in line and tp_pos['side'] in line:
            price_match = re.search(r'@ \$([\d.]+)', line)
            if price_match:
                log_price = float(price_match.group(1))
                if abs(log_price - tp_pos['entry_price']) < 5:
                    conf_match = re.search(r'Confidence: ([\d.]+)%', line)
                    confidence = float(conf_match.group(1)) if conf_match else None
                    
                    probs = {}
                    for j in range(i+1, min(i+5, len(lines))):
                        prob_match = re.search(r'Probs: Flat=([\d.]+)%, Long=([\d.]+)%, Short=([\d.]+)%', lines[j])
                        if prob_match:
                            probs = {
                                'flat': float(prob_match.group(1)),
                                'long': float(prob_match.group(2)),
                                'short': float(prob_match.group(3))
                            }
                            break
                    
                    print(f'      ✅ Sinyal bulundu:')
                    print(f'         Log Price: ${log_price:.2f}')
                    print(f'         Confidence: {confidence:.1f}%' if confidence else '         Confidence: N/A')
                    if probs:
                        print(f'         Probs: Flat={probs[\"flat\"]:.1f}%, Long={probs[\"long\"]:.1f}%, Short={probs[\"short\"]:.1f}%')
                    break

print('\n' + '='*80)
print('💡 ÖNERİLER:')
print('='*80)
print('1. SL pozisyonların confidence değerlerini TP pozisyonlarla karşılaştır')
print('2. Model prob dağılımlarını kontrol et (Long/Short/Flat)')
print('3. Volume spike ve EMA durumlarını karşılaştır')
print('4. Market conditions (trend, volatility) farklarını analiz et')
print('='*80)

