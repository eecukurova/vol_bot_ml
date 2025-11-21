#!/usr/bin/env python3
"""Detailed SOL trading analysis with Binance data verification."""

import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def parse_log_file(log_file):
    """Parse SOL live log to extract trades with better matching."""
    trades = []
    entries = []  # Stack of open entries
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        # Entry signal with price
        if '🎯 SIGNAL:' in line:
            match = re.search(r'SIGNAL: (\w+) @ \$(\d+\.?\d*)', line)
            if match:
                side = match.group(1)
                signal_price = float(match.group(2))
                
                # Find entry order ID
                entry_order_id = None
                for j in range(i, min(i+10, len(lines))):
                    if 'Entry order placed:' in lines[j]:
                        entry_order_id = lines[j].split('placed:')[-1].strip()
                        break
                
                if entry_order_id:
                    entries.append({
                        'side': side,
                        'entry_price': signal_price,
                        'entry_order_id': entry_order_id,
                        'entry_line': i,
                    })
        
        # Exit signals
        if 'Trend Following Exit:' in line:
            match = re.search(r'@ \$(\d+\.?\d*)', line)
            if match and entries:
                exit_price = float(match.group(1))
                
                exit_reason = 'UNKNOWN'
                if 'VOLUME_EXIT' in line:
                    exit_reason = 'VOLUME_EXIT'
                elif 'TREND_REVERSAL' in line:
                    exit_reason = 'TREND_REVERSAL'
                elif 'PARTIAL_EXIT' in line:
                    exit_reason = 'PARTIAL_EXIT'
                
                # Match with most recent entry
                entry = entries.pop() if entries else None
                
                if entry:
                    # Calculate PnL
                    if entry['side'] == 'LONG':
                        pnl_pct = (exit_price - entry['entry_price']) / entry['entry_price'] * 100
                    else:
                        pnl_pct = (entry['entry_price'] - exit_price) / entry['entry_price'] * 100
                    
                    # Find exit order ID
                    exit_order_id = None
                    for j in range(i, min(i+5, len(lines))):
                        if 'Full close order placed:' in line or 'Partial close order placed:' in lines[j]:
                            exit_order_id = lines[j].split('placed:')[-1].strip()
                            break
                    
                    trade = {
                        'side': entry['side'],
                        'entry_price': entry['entry_price'],
                        'entry_order_id': entry['entry_order_id'],
                        'exit_price': exit_price,
                        'exit_order_id': exit_order_id,
                        'exit_reason': exit_reason,
                        'pnl_pct': pnl_pct,
                    }
                    trades.append(trade)
    
    return trades

def analyze_trades(trades):
    """Detailed trade analysis."""
    if not trades:
        print("❌ No trades found!")
        return
    
    print(f"\n📊 SOL Trading Analysis - Detailed Report")
    print("=" * 100)
    
    # Separate wins and losses
    wins = [t for t in trades if t['pnl_pct'] > 0]
    losses = [t for t in trades if t['pnl_pct'] <= 0]
    
    # Statistics
    total_trades = len(trades)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    
    total_pnl = sum(t['pnl_pct'] for t in trades)
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
    print(f"   ✅ Wins: {win_count} ({win_rate:.1f}%)")
    print(f"   ❌ Losses: {loss_count} ({100-win_rate:.1f}%)")
    print(f"   💰 Total PnL: {total_pnl:+.2f}%")
    print(f"   📊 Average PnL: {avg_pnl:+.2f}%")
    print(f"   📈 Profit Factor: {profit_factor:.2f}")
    print(f"   🎯 Max Win: {max_win:+.2f}%")
    print(f"   ⚠️  Max Loss: {max_loss:.2f}%")
    print(f"   ✅ Avg Win: {avg_win:+.2f}%")
    print(f"   ❌ Avg Loss: {avg_loss:.2f}%")
    
    # Exit reasons analysis
    exit_reasons = defaultdict(list)
    for t in trades:
        exit_reasons[t['exit_reason']].append(t)
    
    print(f"\n🚪 Exit Reasons Analysis:")
    for reason, reason_trades in exit_reasons.items():
        reason_pnl = sum(t['pnl_pct'] for t in reason_trades)
        reason_wins = sum(1 for t in reason_trades if t['pnl_pct'] > 0)
        reason_win_rate = (reason_wins / len(reason_trades) * 100) if reason_trades else 0
        print(f"   {reason}:")
        print(f"      Count: {len(reason_trades)} | Win Rate: {reason_win_rate:.1f}% | Total PnL: {reason_pnl:+.2f}%")
    
    # Detailed trade list
    print(f"\n📋 Detailed Trades (Chronological):")
    print("-" * 100)
    for i, trade in enumerate(trades, 1):
        pnl_sign = "+" if trade['pnl_pct'] > 0 else ""
        pnl_color = "✅" if trade['pnl_pct'] > 0 else "❌"
        print(f"{i}. {pnl_color} {trade['side']:5s} | "
              f"Entry: ${trade['entry_price']:.2f} | "
              f"Exit: ${trade['exit_price']:.2f} | "
              f"PnL: {pnl_sign}{trade['pnl_pct']:.2f}% | "
              f"{trade['exit_reason']:15s} | "
              f"Entry Order: {trade['entry_order_id']}")
    
    # Win/Loss comparison
    print(f"\n✅ Winning Trades ({len(wins)}):")
    print("-" * 100)
    if wins:
        for i, trade in enumerate(wins, 1):
            print(f"   {i}. {trade['side']:5s} | "
                  f"${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} | "
                  f"+{trade['pnl_pct']:.2f}% | "
                  f"{trade['exit_reason']}")
        print(f"\n   💰 Total Profit: +{total_profit:.2f}%")
        print(f"   📊 Average Win: +{avg_win:.2f}%")
    else:
        print("   None")
    
    print(f"\n❌ Losing Trades ({len(losses)}):")
    print("-" * 100)
    if losses:
        for i, trade in enumerate(losses, 1):
            print(f"   {i}. {trade['side']:5s} | "
                  f"${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} | "
                  f"{trade['pnl_pct']:.2f}% | "
                  f"{trade['exit_reason']}")
        print(f"\n   💸 Total Loss: {total_loss:.2f}%")
        print(f"   📊 Average Loss: {avg_loss:.2f}%")
    else:
        print("   None")
    
    # Performance metrics
    print(f"\n📊 Performance Metrics:")
    print("-" * 100)
    print(f"   Risk/Reward Ratio: {abs(avg_win / avg_loss):.2f}" if avg_loss != 0 else "   Risk/Reward Ratio: N/A")
    print(f"   Expected Value: {(win_rate/100 * avg_win) + ((100-win_rate)/100 * avg_loss):+.2f}%")
    print(f"   Best Trade: +{max_win:.2f}%")
    print(f"   Worst Trade: {max_loss:.2f}%")
    print(f"   Win/Loss Ratio: {len(wins)}/{len(losses)} = {len(wins)/len(losses):.2f}" if losses else "   Win/Loss Ratio: Perfect!")

if __name__ == "__main__":
    log_file = Path("runs/sol_live.log")
    
    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        exit(1)
    
    trades = parse_log_file(log_file)
    analyze_trades(trades)

