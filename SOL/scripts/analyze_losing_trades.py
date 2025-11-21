#!/usr/bin/env python3
"""Analyze losing trades in detail."""

import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def parse_log_file(log_file):
    """Parse SOL live log to extract losing trades with context."""
    trades = []
    current_entry = {}
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        # Entry signal
        if '🎯 SIGNAL:' in line:
            match = re.search(r'SIGNAL: (\w+) @ \$(\d+\.?\d*)', line)
            if match:
                side = match.group(1)
                entry_price = float(match.group(2))
                
                # Time
                time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                entry_time = time_match.group(1) if time_match else None
                
                # Confidence
                conf_match = re.search(r'Confidence: ([\d.]+)%', line)
                confidence = float(conf_match.group(1)) if conf_match else None
                
                current_entry = {
                    'side': side,
                    'entry_price': entry_price,
                    'entry_time': entry_time,
                    'entry_order_id': None,
                    'confidence': confidence,
                    'context_before': [],
                    'context_after': [],
                }
        
        # Entry order placed
        if 'Entry order placed:' in line and current_entry:
            order_id = line.split('placed:')[-1].strip()
            current_entry['entry_order_id'] = order_id
        
        # Collect context (lines before entry)
        if current_entry and i < 1000:  # Look back max 1000 lines
            if 'SIGNAL' in line or 'Trend Following' in line or 'EMA' in line or 'Volume' in line:
                if len(current_entry['context_before']) < 5:
                    current_entry['context_before'].append((i, line.strip()))
        
        # Trend Following Exit signals
        if 'Trend Following Exit:' in line:
            match = re.search(r'@ \$(\d+\.?\d*)', line)
            if match and current_entry:
                exit_price = float(match.group(1))
                
                exit_reason = 'UNKNOWN'
                if 'VOLUME_EXIT' in line:
                    exit_reason = 'VOLUME_EXIT'
                elif 'TREND_REVERSAL' in line:
                    exit_reason = 'TREND_REVERSAL'
                elif 'PARTIAL_EXIT' in line:
                    exit_reason = 'PARTIAL_EXIT'
                
                time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                exit_time = time_match.group(1) if time_match else None
                
                # Calculate PnL
                if current_entry['side'] == 'LONG':
                    pnl_pct = (exit_price - current_entry['entry_price']) / current_entry['entry_price'] * 100
                else:
                    pnl_pct = (current_entry['entry_price'] - exit_price) / current_entry['entry_price'] * 100
                
                # Get context after (next few lines)
                context_after = []
                for j in range(i, min(i+10, len(lines))):
                    if 'Trend Following' in lines[j] or 'EMA' in lines[j] or 'Volume' in lines[j]:
                        context_after.append((j, lines[j].strip()))
                
                trade = {
                    **current_entry,
                    'exit_price': exit_price,
                    'exit_time': exit_time,
                    'exit_reason': exit_reason,
                    'pnl_pct': pnl_pct,
                    'context_after': context_after[:5],
                }
                trades.append(trade)
                current_entry = {}  # Reset
    
    return trades

def analyze_losing_trades(trades):
    """Analyze losing trades in detail."""
    losing_trades = [t for t in trades if t['pnl_pct'] <= 0]
    
    if not losing_trades:
        print("✅ No losing trades found!")
        return
    
    print(f"\n❌ Losing Trades Analysis - {len(losing_trades)} Trade(s)")
    print("=" * 100)
    
    # Group by exit reason
    by_reason = defaultdict(list)
    for trade in losing_trades:
        by_reason[trade['exit_reason']].append(trade)
    
    print(f"\n📊 Losses by Exit Reason:")
    for reason, reason_trades in by_reason.items():
        total_loss = sum(t['pnl_pct'] for t in reason_trades)
        avg_loss = total_loss / len(reason_trades) if reason_trades else 0
        print(f"   {reason}: {len(reason_trades)} trade(s), Total: {total_loss:.2f}%, Avg: {avg_loss:.2f}%")
    
    # Detailed analysis of each losing trade
    print(f"\n🔍 Detailed Analysis of Each Losing Trade:")
    print("=" * 100)
    
    for i, trade in enumerate(losing_trades, 1):
        print(f"\n{i}. ❌ Losing Trade #{i}")
        print("-" * 100)
        print(f"   Side: {trade['side']}")
        print(f"   Entry: ${trade['entry_price']:.2f} ({trade['entry_time']})")
        print(f"   Exit: ${trade['exit_price']:.2f} ({trade['exit_time']})")
        print(f"   PnL: {trade['pnl_pct']:.2f}%")
        print(f"   Exit Reason: {trade['exit_reason']}")
        print(f"   Entry Confidence: {trade.get('confidence', 'N/A')}%")
        print(f"   Entry Order ID: {trade.get('entry_order_id', 'N/A')}")
        
        # Calculate price change
        price_change = trade['exit_price'] - trade['entry_price'] if trade['side'] == 'LONG' else trade['entry_price'] - trade['exit_price']
        price_change_pct = (price_change / trade['entry_price']) * 100
        print(f"   Price Movement: ${abs(price_change):.2f} ({price_change_pct:.2f}%)")
        
        # Time analysis
        if trade['entry_time'] and trade['exit_time']:
            try:
                entry_dt = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M:%S')
                exit_dt = datetime.strptime(trade['exit_time'], '%Y-%m-%d %H:%M:%S')
                duration = exit_dt - entry_dt
                print(f"   Duration: {duration}")
                print(f"   Duration (minutes): {duration.total_seconds() / 60:.1f}")
            except:
                pass
        
        # Context analysis
        if trade['context_before']:
            print(f"\n   📝 Context Before Entry:")
            for line_num, line in trade['context_before'][-3:]:  # Last 3
                print(f"      {line}")
        
        if trade['context_after']:
            print(f"\n   📝 Context After Exit:")
            for line_num, line in trade['context_after'][:3]:  # First 3
                print(f"      {line}")
    
    # Pattern analysis
    print(f"\n🔍 Pattern Analysis:")
    print("-" * 100)
    
    # Average loss
    avg_loss = sum(t['pnl_pct'] for t in losing_trades) / len(losing_trades)
    print(f"   Average Loss: {avg_loss:.2f}%")
    
    # Time pattern
    if all(t.get('entry_time') for t in losing_trades):
        print(f"\n   Time Pattern:")
        for trade in losing_trades:
            print(f"      {trade['entry_time']} → {trade['exit_time']} ({trade['pnl_pct']:.2f}%)")
    
    # Entry price pattern
    entry_prices = [t['entry_price'] for t in losing_trades]
    if entry_prices:
        print(f"\n   Entry Price Range: ${min(entry_prices):.2f} - ${max(entry_prices):.2f}")
        print(f"   Average Entry Price: ${sum(entry_prices)/len(entry_prices):.2f}")
    
    # Exit price pattern
    exit_prices = [t['exit_price'] for t in losing_trades]
    if exit_prices:
        print(f"   Exit Price Range: ${min(exit_prices):.2f} - ${max(exit_prices):.2f}")
        print(f"   Average Exit Price: ${sum(exit_prices)/len(exit_prices):.2f}")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    print("-" * 100)
    
    trend_reversal_losses = [t for t in losing_trades if t['exit_reason'] == 'TREND_REVERSAL']
    if trend_reversal_losses:
        print(f"   ⚠️  {len(trend_reversal_losses)} loss(es) from TREND_REVERSAL:")
        print(f"      - Trend reversal exit may be triggering too early")
        print(f"      - Check if minimum bars/minimum profit settings are adequate")
        print(f"      - Consider if these were false reversal signals")
        
        # Check if losses were small
        small_losses = [t for t in trend_reversal_losses if abs(t['pnl_pct']) < 0.5]
        if small_losses:
            print(f"      - {len(small_losses)} loss(es) were small (<0.5%), which is acceptable")
    
    # Check entry confidence
    low_confidence = [t for t in losing_trades if t.get('confidence') and t['confidence'] < 90]
    if low_confidence:
        print(f"   ⚠️  {len(low_confidence)} loss(es) with confidence < 90%:")
        print(f"      - Consider raising confidence threshold")
    
    # Check if losses were quick
    quick_losses = []
    for trade in losing_trades:
        if trade.get('entry_time') and trade.get('exit_time'):
            try:
                entry_dt = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M:%S')
                exit_dt = datetime.strptime(trade['exit_time'], '%Y-%m-%d %H:%M:%S')
                duration_min = (exit_dt - entry_dt).total_seconds() / 60
                if duration_min < 15:  # Less than 15 minutes
                    quick_losses.append(trade)
            except:
                pass
    
    if quick_losses:
        print(f"   ⚠️  {len(quick_losses)} quick loss(es) (< 15 minutes):")
        print(f"      - These may indicate premature exits")
        print(f"      - Review exit strategy timing")

if __name__ == "__main__":
    log_file = Path("runs/sol_live.log")
    
    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        exit(1)
    
    trades = parse_log_file(log_file)
    analyze_losing_trades(trades)

