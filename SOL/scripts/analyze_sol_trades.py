#!/usr/bin/env python3
"""Analyze SOL trades from live logs and state files."""

import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def parse_log_file(log_file):
    """Parse SOL live log to extract trades."""
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
                
                current_entry = {
                    'side': side,
                    'entry_price': entry_price,
                    'entry_time': entry_time,
                    'entry_order_id': None,
                }
        
        # Entry order placed
        if 'Entry order placed:' in line and current_entry:
            order_id = line.split('placed:')[-1].strip()
            current_entry['entry_order_id'] = order_id
        
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
                
                trade = {
                    **current_entry,
                    'exit_price': exit_price,
                    'exit_time': exit_time,
                    'exit_reason': exit_reason,
                    'pnl_pct': pnl_pct,
                }
                trades.append(trade)
                current_entry = {}  # Reset
    
    return trades

def analyze_trades(trades):
    """Analyze trades and generate statistics."""
    if not trades:
        print("❌ No trades found!")
        return
    
    # Filter today's trades
    today = datetime.now().strftime('%Y-%m-%d')
    today_trades = [t for t in trades if t.get('entry_time') and str(t.get('entry_time', '')).startswith(today)]
    
    # If no today trades, show all trades
    if not today_trades and trades:
        print(f"⚠️ No trades found for today ({today}), showing all trades:")
        today_trades = trades
    elif not today_trades:
        print(f"❌ No trades found!")
        return
    
    print(f"\n📊 SOL Trading Analysis - {today}")
    print("=" * 80)
    
    # Separate wins and losses
    wins = [t for t in today_trades if t['pnl_pct'] > 0]
    losses = [t for t in today_trades if t['pnl_pct'] <= 0]
    
    # Statistics
    total_trades = len(today_trades)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    
    total_pnl = sum(t['pnl_pct'] for t in today_trades)
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
    
    # Profit factor
    total_profit = sum(t['pnl_pct'] for t in wins) if wins else 0
    total_loss = abs(sum(t['pnl_pct'] for t in losses)) if losses else 0
    profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 0)
    
    # Max win/loss
    max_win = max((t['pnl_pct'] for t in wins), default=0)
    max_loss = min((t['pnl_pct'] for t in losses), default=0)
    avg_win = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0
    
    print(f"\n📈 Overall Statistics:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {win_count} ({win_rate:.1f}%)")
    print(f"   Losses: {loss_count} ({100-win_rate:.1f}%)")
    print(f"   Total PnL: {total_pnl:+.2f}%")
    print(f"   Average PnL: {avg_pnl:+.2f}%")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"   Max Win: {max_win:+.2f}%")
    print(f"   Max Loss: {max_loss:.2f}%")
    print(f"   Avg Win: {avg_win:+.2f}%")
    print(f"   Avg Loss: {avg_loss:.2f}%")
    
    # Exit reasons
    exit_reasons = defaultdict(int)
    for t in today_trades:
        exit_reasons[t['exit_reason']] += 1
    
    print(f"\n🚪 Exit Reasons:")
    for reason, count in exit_reasons.items():
        print(f"   {reason}: {count}")
    
    # Detailed trade list
    print(f"\n📋 Detailed Trades:")
    print("-" * 80)
    for i, trade in enumerate(today_trades, 1):
        pnl_sign = "+" if trade['pnl_pct'] > 0 else ""
        print(f"{i}. {trade['side']:5s} | Entry: ${trade['entry_price']:.2f} | Exit: ${trade['exit_price']:.2f} | "
              f"PnL: {pnl_sign}{trade['pnl_pct']:.2f}% | {trade['exit_reason']} | "
              f"{trade['entry_time']} → {trade['exit_time']}")
    
    # Win/Loss comparison
    print(f"\n✅ Winning Trades ({len(wins)}):")
    if wins:
        for i, trade in enumerate(wins, 1):
            print(f"   {i}. {trade['side']:5s} ${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} "
                  f"(+{trade['pnl_pct']:.2f}%) - {trade['exit_reason']}")
    else:
        print("   None")
    
    print(f"\n❌ Losing Trades ({len(losses)}):")
    if losses:
        for i, trade in enumerate(losses, 1):
            print(f"   {i}. {trade['side']:5s} ${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} "
                  f"({trade['pnl_pct']:.2f}%) - {trade['exit_reason']}")
    else:
        print("   None")

if __name__ == "__main__":
    log_file = Path("runs/sol_live.log")
    
    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        exit(1)
    
    trades = parse_log_file(log_file)
    analyze_trades(trades)

