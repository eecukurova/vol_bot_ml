#!/usr/bin/env python3
"""Analyze recent LLM performance and today's stop loss trade."""

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

def analyze_performance(positions):
    """Analyze trading performance."""
    if not positions:
        print("❌ No positions found!")
        return
    
    print("=" * 100)
    print("LLM Trading Performance Analysis")
    print("=" * 100)
    
    # Sort by exit time
    positions.sort(key=lambda x: x.get('exit_time', x.get('timestamp', '')), reverse=True)
    
    # Filter today's positions
    today = datetime.now().date()
    today_positions = []
    recent_positions = []
    
    for pos in positions:
        try:
            exit_time = pos.get('exit_time', pos.get('timestamp', ''))
            if exit_time:
                exit_dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                if exit_dt.date() == today:
                    today_positions.append(pos)
                elif (datetime.now() - exit_dt).days <= 7:
                    recent_positions.append(pos)
        except:
            pass
    
    print(f"\n📅 Today's Positions: {len(today_positions)}")
    print("=" * 100)
    
    if today_positions:
        for i, pos in enumerate(today_positions, 1):
            print(f"\n{i}. {pos.get('exit_reason', 'UNKNOWN')} Trade")
            print("-" * 100)
            print(f"   Side: {pos.get('side', 'N/A')}")
            print(f"   Entry: ${pos.get('entry', 0):.2f}")
            print(f"   Exit: ${pos.get('exit', 0):.2f}")
            print(f"   PnL: {pos.get('pnl', 0)*100:.2f}%")
            print(f"   Confidence: {pos.get('confidence', 0):.1f}%")
            print(f"   Exit Time: {pos.get('exit_time', 'N/A')}")
            
            # Check if SL
            if pos.get('exit_reason') == 'SL':
                sl_price = pos.get('sl', 0)
                entry_price = pos.get('entry', 0)
                exit_price = pos.get('exit', 0)
                
                if pos.get('side') == 'LONG':
                    sl_distance = ((entry_price - sl_price) / entry_price) * 100
                    actual_move = ((exit_price - entry_price) / entry_price) * 100
                else:
                    sl_distance = ((sl_price - entry_price) / entry_price) * 100
                    actual_move = ((entry_price - exit_price) / entry_price) * 100
                
                print(f"   SL Distance: {sl_distance:.2f}%")
                print(f"   Actual Move: {actual_move:.2f}%")
                
                if abs(actual_move) > sl_distance * 1.1:
                    print(f"   ⚠️  Overshoot: {abs(actual_move) - sl_distance:.2f}%")
    
    # Recent performance (last 7 days)
    print(f"\n📊 Recent Performance (Last 7 Days): {len(recent_positions)} positions")
    print("=" * 100)
    
    if recent_positions:
        sl_positions = [p for p in recent_positions if p.get('exit_reason') == 'SL']
        tp_positions = [p for p in recent_positions if p.get('exit_reason') == 'TP']
        
        print(f"   ✅ Take Profit: {len(tp_positions)}")
        print(f"   ❌ Stop Loss: {len(sl_positions)}")
        
        if len(recent_positions) > 0:
            win_rate = len(tp_positions) / len(recent_positions) * 100
            print(f"   📈 Win Rate: {win_rate:.1f}%")
        
        total_pnl = sum(p.get('pnl', 0) for p in recent_positions)
        avg_pnl = total_pnl / len(recent_positions) if recent_positions else 0
        
        print(f"   💰 Total PnL: {total_pnl*100:.2f}%")
        print(f"   📊 Average PnL: {avg_pnl*100:.2f}%")
        
        if sl_positions:
            avg_sl_pnl = sum(p.get('pnl', 0) for p in sl_positions) / len(sl_positions)
            print(f"   ❌ Average SL Loss: {avg_sl_pnl*100:.2f}%")
        
        if tp_positions:
            avg_tp_pnl = sum(p.get('pnl', 0) for p in tp_positions) / len(tp_positions)
            print(f"   ✅ Average TP Gain: {avg_tp_pnl*100:.2f}%")
        
        # Confidence analysis
        confidences = [p.get('confidence', 0) for p in recent_positions if p.get('confidence', 0) > 0]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            print(f"   📊 Average Confidence: {avg_confidence:.1f}%")
            
            sl_confidences = [p.get('confidence', 0) for p in sl_positions if p.get('confidence', 0) > 0]
            if sl_confidences:
                avg_sl_conf = sum(sl_confidences) / len(sl_confidences)
                print(f"   ❌ SL Average Confidence: {avg_sl_conf:.1f}%")
            
            tp_confidences = [p.get('confidence', 0) for p in tp_positions if p.get('confidence', 0) > 0]
            if tp_confidences:
                avg_tp_conf = sum(tp_confidences) / len(tp_confidences)
                print(f"   ✅ TP Average Confidence: {avg_tp_conf:.1f}%")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        print("-" * 100)
        
        if win_rate < 50:
            print(f"   ⚠️  Win rate ({win_rate:.1f}%) is below 50%")
            print(f"      → Consider adjusting entry strategy or model threshold")
        
        if len(sl_positions) > len(tp_positions):
            print(f"   ⚠️  More SLs ({len(sl_positions)}) than TPs ({len(tp_positions)})")
            print(f"      → Review entry timing or stop loss settings")
        
        if avg_pnl < 0:
            print(f"   ⚠️  Negative average PnL ({avg_pnl*100:.2f}%)")
            print(f"      → Model may need retraining or market conditions changed")
        
        if sl_confidences and avg_sl_conf > 90:
            print(f"   ⚠️  High confidence SL trades (avg {avg_sl_conf:.1f}%)")
            print(f"      → Model may be overconfident or market conditions changed")
    
    # Overall performance (all positions)
    print(f"\n📊 Overall Performance (All Positions): {len(positions)} positions")
    print("=" * 100)
    
    all_sl = [p for p in positions if p.get('exit_reason') == 'SL']
    all_tp = [p for p in positions if p.get('exit_reason') == 'TP']
    
    if positions:
        overall_win_rate = len(all_tp) / len(positions) * 100
        overall_pnl = sum(p.get('pnl', 0) for p in positions)
        overall_avg_pnl = overall_pnl / len(positions)
        
        print(f"   ✅ Take Profit: {len(all_tp)}")
        print(f"   ❌ Stop Loss: {len(all_sl)}")
        print(f"   📈 Win Rate: {overall_win_rate:.1f}%")
        print(f"   💰 Total PnL: {overall_pnl*100:.2f}%")
        print(f"   📊 Average PnL: {overall_avg_pnl*100:.2f}%")

if __name__ == "__main__":
    positions = load_closed_positions()
    analyze_performance(positions)

