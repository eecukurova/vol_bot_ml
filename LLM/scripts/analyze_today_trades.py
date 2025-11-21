#!/usr/bin/env python3
"""Analyze today's LLM trades - TP vs SL breakdown and detailed SL analysis."""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

def load_closed_positions():
    """Load closed positions from JSON file."""
    positions_file = Path("runs/closed_positions.json")
    
    if not positions_file.exists():
        print(f"❌ File not found: {positions_file}")
        return []
    
    try:
        with open(positions_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading positions: {e}")
        return []

def filter_today_trades(positions):
    """Filter trades from today."""
    today = datetime.now().date()
    today_trades = []
    
    for pos in positions:
        # Try different time formats
        exit_time_str = pos.get('exit_time', pos.get('timestamp', ''))
        if not exit_time_str:
            continue
        
        try:
            # Try ISO format
            if 'T' in exit_time_str:
                exit_dt = datetime.fromisoformat(exit_time_str.replace('Z', '+00:00'))
            else:
                # Try other formats
                exit_dt = datetime.strptime(exit_time_str, '%Y-%m-%d %H:%M:%S')
            
            if exit_dt.date() == today:
                today_trades.append(pos)
        except:
            continue
    
    return today_trades

def analyze_trades(positions):
    """Analyze trades."""
    if not positions:
        print("❌ No trades found!")
        return
    
    print(f"\n📊 LLM Trading Analysis - Today ({datetime.now().date()})")
    print("=" * 100)
    
    # Separate TP and SL
    tp_trades = [p for p in positions if p.get('exit_reason') == 'TP']
    sl_trades = [p for p in positions if p.get('exit_reason') == 'SL']
    
    print(f"\n📈 Overall Statistics:")
    print("-" * 100)
    print(f"   Total Trades: {len(positions)}")
    print(f"   ✅ Take Profit: {len(tp_trades)} ({len(tp_trades)/len(positions)*100:.1f}%)")
    print(f"   ❌ Stop Loss: {len(sl_trades)} ({len(sl_trades)/len(positions)*100:.1f}%)")
    
    # PnL statistics
    total_pnl = sum(p.get('pnl', 0) for p in positions)
    avg_pnl = total_pnl / len(positions) if positions else 0
    
    tp_pnl = sum(p.get('pnl', 0) for p in tp_trades) if tp_trades else 0
    sl_pnl = sum(p.get('pnl', 0) for p in sl_trades) if sl_trades else 0
    
    print(f"\n💰 PnL Statistics:")
    print(f"   Total PnL: {total_pnl*100:+.2f}%")
    print(f"   Average PnL: {avg_pnl*100:+.2f}%")
    print(f"   TP Total PnL: {tp_pnl*100:+.2f}%")
    print(f"   SL Total PnL: {sl_pnl*100:.2f}%")
    
    # Take Profit analysis
    if tp_trades:
        print(f"\n✅ Take Profit Trades ({len(tp_trades)}):")
        print("-" * 100)
        avg_tp_pnl = sum(p.get('pnl', 0) for p in tp_trades) / len(tp_trades)
        print(f"   Average TP PnL: {avg_tp_pnl*100:+.2f}%")
        
        for i, trade in enumerate(tp_trades, 1):
            side = trade.get('side', 'N/A')
            entry = trade.get('entry', 0)
            exit_price = trade.get('exit', 0)
            pnl = trade.get('pnl', 0) * 100
            conf = trade.get('confidence', 0) * 100 if trade.get('confidence', 0) < 1 else trade.get('confidence', 0)
            
            print(f"   {i}. {side:5s} | Entry: ${entry:.2f} | Exit: ${exit_price:.2f} | "
                  f"PnL: {pnl:+.2f}% | Confidence: {conf:.1f}%")
    
    # Stop Loss analysis
    if sl_trades:
        print(f"\n❌ Stop Loss Trades ({len(sl_trades)}) - Detailed Analysis:")
        print("=" * 100)
        
        avg_sl_pnl = sum(p.get('pnl', 0) for p in sl_trades) / len(sl_trades)
        print(f"\n📊 SL Statistics:")
        print(f"   Average SL PnL: {avg_sl_pnl*100:.2f}%")
        print(f"   Total SL Loss: {sl_pnl*100:.2f}%")
        
        # Group by side
        sl_long = [t for t in sl_trades if t.get('side') == 'LONG']
        sl_short = [t for t in sl_trades if t.get('side') == 'SHORT']
        
        if sl_long:
            avg_long_loss = sum(t.get('pnl', 0) for t in sl_long) / len(sl_long)
            print(f"   LONG SL: {len(sl_long)} trades, Avg: {avg_long_loss*100:.2f}%")
        
        if sl_short:
            avg_short_loss = sum(t.get('pnl', 0) for t in sl_short) / len(sl_short)
            print(f"   SHORT SL: {len(sl_short)} trades, Avg: {avg_short_loss*100:.2f}%")
        
        # Confidence analysis
        confidences = [t.get('confidence', 0) for t in sl_trades if t.get('confidence', 0) > 0]
        if confidences:
            # Normalize if needed
            if all(c < 1 for c in confidences):
                confidences = [c * 100 for c in confidences]
            
            avg_conf = sum(confidences) / len(confidences)
            print(f"\n📊 Confidence Analysis:")
            print(f"   Average Confidence: {avg_conf:.1f}%")
            print(f"   Min Confidence: {min(confidences):.1f}%")
            print(f"   Max Confidence: {max(confidences):.1f}%")
            
            # Low confidence SLs
            low_conf = [t for t in sl_trades if (t.get('confidence', 0) < 0.9 or (t.get('confidence', 0) > 1 and t.get('confidence', 0) < 90))]
            if low_conf:
                print(f"   ⚠️  Low Confidence (<90%): {len(low_conf)} trade(s)")
        
        # Detailed SL trades
        print(f"\n🔍 Detailed SL Trades:")
        print("-" * 100)
        
        for i, trade in enumerate(sl_trades, 1):
            side = trade.get('side', 'N/A')
            entry = trade.get('entry', 0)
            exit_price = trade.get('exit', 0)
            tp = trade.get('tp', 0)
            sl = trade.get('sl', 0)
            pnl = trade.get('pnl', 0) * 100
            conf = trade.get('confidence', 0)
            
            # Normalize confidence
            if conf < 1:
                conf = conf * 100
            
            entry_time = trade.get('entry_time', 'N/A')
            exit_time = trade.get('exit_time', trade.get('timestamp', 'N/A'))
            
            # Calculate distance to TP/SL
            if side == 'LONG':
                entry_to_tp = ((tp - entry) / entry) * 100 if tp > 0 else 0
                entry_to_sl = ((entry - sl) / entry) * 100 if sl > 0 else 0
                actual_move = ((exit_price - entry) / entry) * 100
            else:
                entry_to_tp = ((entry - tp) / entry) * 100 if tp > 0 else 0
                entry_to_sl = ((sl - entry) / entry) * 100 if sl > 0 else 0
                actual_move = ((entry - exit_price) / entry) * 100
            
            print(f"\n{i}. ❌ Stop Loss Trade #{i}")
            print(f"   Side: {side}")
            print(f"   Entry: ${entry:.2f} | Exit: ${exit_price:.2f}")
            print(f"   TP: ${tp:.2f} ({entry_to_tp:+.2f}%) | SL: ${sl:.2f} ({entry_to_sl:.2f}%)")
            print(f"   Actual PnL: {pnl:.2f}% (Price moved {actual_move:.2f}%)")
            print(f"   Confidence: {conf:.1f}%")
            print(f"   Entry Time: {entry_time}")
            print(f"   Exit Time: {exit_time}")
            
            # Market features if available
            features = trade.get('features', {})
            if features:
                print(f"   Market Features:")
                if 'ema50' in features:
                    print(f"      EMA50: {features['ema50']:.2f}")
                if 'ema200' in features:
                    print(f"      EMA200: {features['ema200']:.2f}")
                if 'vol_spike' in features:
                    print(f"      Vol Spike: {features['vol_spike']:.2f}")
        
        # Pattern analysis
        print(f"\n🔍 Pattern Analysis:")
        print("-" * 100)
        
        # Time analysis
        entry_times = []
        for trade in sl_trades:
            et = trade.get('entry_time', '')
            if et:
                try:
                    if 'T' in et:
                        dt = datetime.fromisoformat(et.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(et, '%Y-%m-%d %H:%M:%S')
                    entry_times.append(dt)
                except:
                    pass
        
        if entry_times:
            print(f"   Entry Times: {len(entry_times)} trades")
            for dt in sorted(entry_times):
                print(f"      {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        print("-" * 100)
        
        if confidences:
            if avg_conf < 90:
                print(f"   ⚠️  Average confidence is {avg_conf:.1f}% - Consider raising threshold")
        
        if avg_sl_pnl > -0.01:
            print(f"   ✅ Average SL loss is small ({avg_sl_pnl*100:.2f}%) - Good risk management")
        else:
            print(f"   ⚠️  Average SL loss is {avg_sl_pnl*100:.2f}% - Consider tighter stops")
        
        if len(sl_trades) > len(tp_trades):
            print(f"   ⚠️  More SLs than TPs ({len(sl_trades)} vs {len(tp_trades)}) - Review entry strategy")
    else:
        print("\n✅ No Stop Loss trades today!")

if __name__ == "__main__":
    positions = load_closed_positions()
    
    if not positions:
        print("❌ No closed positions found in runs/closed_positions.json")
        print("   Run import_historical_data.py first to import trades")
        exit(1)
    
    # Filter today's trades
    today_trades = filter_today_trades(positions)
    
    if not today_trades:
        print(f"⚠️  No trades found for today ({datetime.now().date()})")
        print(f"   Total positions in file: {len(positions)}")
        print(f"   Showing last 10 positions:")
        for i, pos in enumerate(positions[-10:], 1):
            exit_reason = pos.get('exit_reason', 'UNKNOWN')
            pnl = pos.get('pnl', 0) * 100
            print(f"   {i}. {exit_reason} | PnL: {pnl:+.2f}% | {pos.get('exit_time', pos.get('timestamp', 'N/A'))}")
    else:
        analyze_trades(today_trades)

