#!/usr/bin/env python3
"""Detailed analysis of losing trades with correct entry/exit matching."""

import re
from pathlib import Path

def analyze_losing_trades():
    log_file = Path("runs/sol_live.log")
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    trades = []
    current_entry = None
    
    for i, line in enumerate(lines):
        # Entry order placed (real entry)
        if 'Entry order placed:' in line:
            order_id = line.split('placed:')[-1].strip()
            # Find entry price
            for j in range(max(0, i-10), i):
                if 'Order hook:' in lines[j]:
                    match = re.search(r'@ (\d+\.?\d*)', lines[j])
                    if match:
                        entry_price = float(match.group(1))
                        side_match = re.search(r'(\w+) @', lines[j])
                        side = side_match.group(1) if side_match else 'LONG'
                        
                        time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        entry_time = time_match.group(1) if time_match else None
                        
                        current_entry = {
                            'entry_order_id': order_id,
                            'entry_price': entry_price,
                            'side': side,
                            'entry_time': entry_time,
                        }
                        break
        
        # Exit (Full close)
        if 'Full close order placed:' in line and current_entry:
            exit_order_id = line.split('placed:')[-1].strip()
            
            # Find exit price from trend following exit
            exit_price = None
            exit_reason = 'UNKNOWN'
            bars_after = None
            profit_at_exit = None
            
            for j in range(max(0, i-20), i):
                if 'Trend Following Exit:' in lines[j]:
                    price_match = re.search(r'@ \$(\d+\.?\d*)', lines[j])
                    if price_match:
                        exit_price = float(price_match.group(1))
                        
                        if 'VOLUME_EXIT' in lines[j]:
                            exit_reason = 'VOLUME_EXIT'
                        elif 'TREND_REVERSAL' in lines[j]:
                            exit_reason = 'TREND_REVERSAL'
                        elif 'PARTIAL_EXIT' in lines[j]:
                            exit_reason = 'PARTIAL_EXIT'
                        
                        # Bar count and profit
                        bar_match = re.search(r'after (\d+) bars', lines[j])
                        profit_match = re.search(r'profit: ([-\d.]+)%', lines[j])
                        
                        if bar_match:
                            bars_after = int(bar_match.group(1))
                        if profit_match:
                            profit_at_exit = float(profit_match.group(1))
                        
                        break
            
            if exit_price:
                # Calculate PnL
                if current_entry['side'] == 'LONG':
                    pnl_pct = (exit_price - current_entry['entry_price']) / current_entry['entry_price'] * 100
                else:
                    pnl_pct = (current_entry['entry_price'] - exit_price) / current_entry['entry_price'] * 100
                
                trade = {
                    **current_entry,
                    'exit_price': exit_price,
                    'exit_order_id': exit_order_id,
                    'exit_reason': exit_reason,
                    'pnl_pct': pnl_pct,
                    'bars_after': bars_after,
                    'profit_at_exit': profit_at_exit,
                }
                trades.append(trade)
                current_entry = None
    
    # Filter losing trades
    losing = [t for t in trades if t['pnl_pct'] < 0]
    
    if not losing:
        print("✅ No losing trades found!")
        return
    
    print(f"\n❌ Losing Trades Detailed Analysis - {len(losing)} Trade(s)")
    print("=" * 100)
    
    for i, trade in enumerate(losing, 1):
        print(f"\n{i}. ❌ Losing Trade #{i}")
        print("-" * 100)
        print(f"   Side: {trade['side']}")
        print(f"   Entry: ${trade['entry_price']:.2f} (Order ID: {trade['entry_order_id']})")
        print(f"   Exit: ${trade['exit_price']:.2f} (Order ID: {trade['exit_order_id']})")
        print(f"   PnL: {trade['pnl_pct']:.2f}%")
        print(f"   Exit Reason: {trade['exit_reason']}")
        
        if trade.get('bars_after'):
            print(f"   ⏱️  Bars After Entry: {trade['bars_after']} bars ({trade['bars_after'] * 3} minutes)")
        
        if trade.get('profit_at_exit'):
            profit_status = "📈 Was in profit" if trade['profit_at_exit'] > 0 else "📉 Was in loss"
            print(f"   {profit_status} at exit signal: {trade['profit_at_exit']:.2f}%")
        
        print(f"   Entry Time: {trade.get('entry_time', 'N/A')}")
        
        # Price movement analysis
        price_diff = trade['exit_price'] - trade['entry_price'] if trade['side'] == 'LONG' else trade['entry_price'] - trade['exit_price']
        print(f"   Price Movement: ${abs(price_diff):.2f} ({abs(trade['pnl_pct']):.2f}%)")
    
    print(f"\n📊 Summary:")
    print("-" * 100)
    print(f"   Total Losses: {len(losing)}")
    avg_loss = sum(t['pnl_pct'] for t in losing) / len(losing)
    print(f"   Average Loss: {avg_loss:.2f}%")
    total_loss = sum(t['pnl_pct'] for t in losing)
    print(f"   Total Loss: {total_loss:.2f}%")
    
    # Exit reason analysis
    by_reason = {}
    for trade in losing:
        reason = trade['exit_reason']
        if reason not in by_reason:
            by_reason[reason] = []
        by_reason[reason].append(trade)
    
    print(f"\n🚪 Losses by Exit Reason:")
    for reason, reason_trades in by_reason.items():
        reason_loss = sum(t['pnl_pct'] for t in reason_trades)
        print(f"   {reason}: {len(reason_trades)} trade(s), Total: {reason_loss:.2f}%")
    
    # Pattern analysis
    print(f"\n🔍 Pattern Analysis:")
    print("-" * 100)
    
    # Check if exits were premature
    premature = [t for t in losing if t.get('bars_after') and t['bars_after'] < 10]
    if premature:
        print(f"   ⚠️  {len(premature)} trade(s) closed in < 10 bars (30 minutes):")
        print(f"      - These may be premature exits")
        print(f"      - Consider increasing minimum bars for trend reversal")
    
    # Check if was in profit before exit
    was_profitable = [t for t in losing if t.get('profit_at_exit') and t['profit_at_exit'] > 0]
    if was_profitable:
        print(f"   ⚠️  {len(was_profitable)} trade(s) were in profit before exit:")
        print(f"      - These may indicate profit protection issues")
        for t in was_profitable:
            print(f"      - Entry ${t['entry_price']:.2f}: Was +{t['profit_at_exit']:.2f}%, exited at {t['pnl_pct']:.2f}%")
    
    # Entry price analysis
    entry_prices = [t['entry_price'] for t in losing]
    if entry_prices:
        print(f"\n   Entry Price Analysis:")
        print(f"      Range: ${min(entry_prices):.2f} - ${max(entry_prices):.2f}")
        print(f"      Average: ${sum(entry_prices)/len(entry_prices):.2f}")
    
    # Exit price analysis
    exit_prices = [t['exit_price'] for t in losing]
    if exit_prices:
        print(f"   Exit Price Analysis:")
        print(f"      Range: ${min(exit_prices):.2f} - ${max(exit_prices):.2f}")
        print(f"      Average: ${sum(exit_prices)/len(exit_prices):.2f}")
    
    print(f"\n💡 Recommendations:")
    print("-" * 100)
    
    if all(t.get('exit_reason') == 'TREND_REVERSAL' for t in losing):
        print("   1. All losses from TREND_REVERSAL:")
        print("      - Consider if EMA crossover is too sensitive")
        print("      - Review trend_reversal_min_bars setting (currently 5)")
        print("      - Consider adding trend_reversal_min_profit_pct to prevent exits when in small profit")
    
    if premature:
        print("   2. Quick exits detected:")
        print("      - Increase minimum bars for trend reversal exit")
        print("      - Add confirmation signals (e.g., multiple bars of reversal)")
    
    if was_profitable:
        print("   3. Profit protection needed:")
        print("      - Ensure trailing stop activates early enough")
        print("      - Consider partial exit at profit levels")
        print("      - Review break-even logic")

if __name__ == "__main__":
    analyze_losing_trades()

