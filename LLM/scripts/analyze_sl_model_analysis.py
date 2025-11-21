#!/usr/bin/env python3
"""Analyze Stop Loss trades - Model and Entry Analysis."""

import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def parse_log_file(log_file):
    """Parse LLM live log to extract signal and trade information."""
    signals = []
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    current_signal = {}
    
    for i, line in enumerate(lines):
        # Signal detection
        if '🎯 SIGNAL:' in line:
            match = re.search(r'SIGNAL: (\w+) @ \$([\d,]+\.?\d*)', line)
            if match:
                side = match.group(1)
                price = float(match.group(2).replace(',', ''))
                
                # Time
                time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                signal_time = time_match.group(1) if time_match else None
                
                current_signal = {
                    'side': side,
                    'price': price,
                    'time': signal_time,
                    'line_num': i,
                }
        
        # Confidence
        if current_signal and 'Confidence:' in line:
            conf_match = re.search(r'Confidence: ([\d.]+)%', line)
            if conf_match:
                current_signal['confidence'] = float(conf_match.group(1))
        
        # TP/SL
        if current_signal and 'TP:' in line and 'SL:' in line:
            tp_match = re.search(r'TP: \$([\d,]+\.?\d*)', line)
            sl_match = re.search(r'SL: \$([\d,]+\.?\d*)', line)
            if tp_match:
                current_signal['tp'] = float(tp_match.group(1).replace(',', ''))
            if sl_match:
                current_signal['sl'] = float(sl_match.group(1).replace(',', ''))
        
        # Probabilities
        if current_signal and 'Probs:' in line:
            prob_match = re.search(r'Flat=([\d.]+)%, Long=([\d.]+)%, Short=([\d.]+)%', line)
            if prob_match:
                current_signal['probs'] = {
                    'flat': float(prob_match.group(1)),
                    'long': float(prob_match.group(2)),
                    'short': float(prob_match.group(3)),
                }
        
        # Entry order placed
        if current_signal and 'Entry order placed:' in line:
            order_id = line.split('placed:')[-1].strip()
            current_signal['order_id'] = order_id
            current_signal['entry_placed'] = True
            
            # Save signal
            signals.append(current_signal.copy())
            current_signal = {}
    
    return signals

def get_sl_trades_from_binance():
    """Get SL trades from Binance (simplified - we'll match by time)."""
    # These are the known SL trades from previous analysis
    sl_trades = [
        {
            'side': 'LONG',
            'entry': 101976.00,
            'exit': 101684.60,
            'entry_time': '2025-11-05T07:59:27.121Z',
            'exit_time': '2025-11-05T10:41:49.275Z',
            'pnl': -0.0029,
        },
        {
            'side': 'SHORT',
            'entry': 101557.50,
            'exit': 102682.90,
            'entry_time': '2025-11-05T10:48:05.251Z',
            'exit_time': '2025-11-05T12:25:57.650Z',
            'pnl': -0.0111,
        },
        {
            'side': 'LONG',
            'entry': 103062.20,
            'exit': 102965.70,
            'entry_time': '2025-11-05T14:43:42.623Z',
            'exit_time': '2025-11-05T15:14:43.438Z',
            'pnl': -0.0009,
        },
    ]
    return sl_trades

def match_signals_to_trades(signals, sl_trades):
    """Match log signals to actual SL trades."""
    matched = []
    
    for trade in sl_trades:
        # Find signal around entry time
        entry_time_str = trade['entry_time']
        entry_price = trade['entry']
        
        # Try to match by price and time
        best_match = None
        min_price_diff = float('inf')
        
        for signal in signals:
            if signal.get('side') == trade['side']:
                # Check if price is close
                price_diff = abs(signal['price'] - entry_price) / entry_price
                if price_diff < 0.01:  # Within 1%
                    if price_diff < min_price_diff:
                        min_price_diff = price_diff
                        best_match = signal
        
        if best_match:
            matched.append({
                'trade': trade,
                'signal': best_match,
            })
    
    return matched

def analyze_model_performance(matched_trades):
    """Analyze model performance for SL trades."""
    print("=" * 100)
    print("Stop Loss Trades - Model & Entry Analysis")
    print("=" * 100)
    
    if not matched_trades:
        print("❌ No matched trades found")
        return
    
    print(f"\n📊 Found {len(matched_trades)} Stop Loss Trade(s) with Signal Data")
    print("=" * 100)
    
    confidences = []
    prob_ratios = []
    
    for i, match in enumerate(matched_trades, 1):
        trade = match['trade']
        signal = match['signal']
        
        print(f"\n{i}. ❌ Stop Loss Trade #{i}")
        print("-" * 100)
        
        print(f"   Trade Info:")
        print(f"      Side: {trade['side']}")
        print(f"      Entry: ${trade['entry']:.2f} → Exit: ${trade['exit']:.2f}")
        print(f"      PnL: {trade['pnl']*100:.2f}%")
        
        print(f"\n   📊 Model Signal Analysis:")
        print(f"      Signal Price: ${signal.get('price', 'N/A'):.2f}")
        
        if 'confidence' in signal:
            conf = signal['confidence']
            confidences.append(conf)
            print(f"      Confidence: {conf:.1f}%")
            
            if conf < 85:
                print(f"      ⚠️  LOW CONFIDENCE - Below 85% threshold")
            elif conf < 90:
                print(f"      ⚠️  Medium confidence - Below 90%")
            else:
                print(f"      ✅ High confidence")
        
        if 'probs' in signal:
            probs = signal['probs']
            print(f"      Probabilities:")
            print(f"         Flat: {probs['flat']:.2f}%")
            print(f"         Long: {probs['long']:.2f}%")
            print(f"         Short: {probs['short']:.2f}%")
            
            # Calculate probability ratio
            if trade['side'] == 'LONG':
                prob_ratio = probs['long'] / probs['short'] if probs['short'] > 0 else float('inf')
                print(f"      Long/Short Ratio: {prob_ratio:.2f}")
            else:
                prob_ratio = probs['short'] / probs['long'] if probs['long'] > 0 else float('inf')
                print(f"      Short/Long Ratio: {prob_ratio:.2f}")
            
            prob_ratios.append(prob_ratio)
        
        if 'tp' in signal and 'sl' in signal:
            print(f"\n   🎯 Risk/Reward:")
            print(f"      TP: ${signal['tp']:.2f}")
            print(f"      SL: ${signal['sl']:.2f}")
            
            # Calculate TP/SL distances
            if trade['side'] == 'LONG':
                tp_distance = ((signal['tp'] - signal['price']) / signal['price']) * 100
                sl_distance = ((signal['price'] - signal['sl']) / signal['price']) * 100
            else:
                tp_distance = ((signal['price'] - signal['tp']) / signal['price']) * 100
                sl_distance = ((signal['sl'] - signal['price']) / signal['price']) * 100
            
            print(f"      TP Distance: {tp_distance:.2f}%")
            print(f"      SL Distance: {sl_distance:.2f}%")
            
            risk_reward = tp_distance / sl_distance if sl_distance > 0 else 0
            print(f"      Risk/Reward Ratio: {risk_reward:.2f}")
            
            # Check if SL was hit correctly
            if trade['side'] == 'LONG':
                actual_move = ((trade['exit'] - trade['entry']) / trade['entry']) * 100
            else:
                actual_move = ((trade['entry'] - trade['exit']) / trade['entry']) * 100
            
            print(f"      Actual Move: {actual_move:.2f}%")
            
            if abs(actual_move - sl_distance) < 0.1:
                print(f"      ✅ SL hit correctly")
            else:
                overshoot = actual_move - sl_distance
                print(f"      ⚠️  SL overshoot: {overshoot:.2f}%")
        
        # Entry analysis
        print(f"\n   🔍 Entry Analysis:")
        signal_price = signal.get('price', trade['entry'])
        entry_price = trade['entry']
        price_diff = abs(signal_price - entry_price) / signal_price * 100
        
        print(f"      Signal Price: ${signal_price:.2f}")
        print(f"      Actual Entry: ${entry_price:.2f}")
        print(f"      Price Difference: {price_diff:.2f}%")
        
        if price_diff > 0.1:
            print(f"      ⚠️  Significant slippage ({price_diff:.2f}%)")
        else:
            print(f"      ✅ Entry price close to signal")
        
        # Model assessment
        print(f"\n   🤖 Model Assessment:")
        
        issues = []
        
        if 'confidence' in signal:
            if signal['confidence'] < 85:
                issues.append(f"Low confidence ({signal['confidence']:.1f}%)")
        
        if 'probs' in signal:
            if trade['side'] == 'LONG' and signal['probs']['long'] < 80:
                issues.append(f"Low Long probability ({signal['probs']['long']:.1f}%)")
            elif trade['side'] == 'SHORT' and signal['probs']['short'] < 80:
                issues.append(f"Low Short probability ({signal['probs']['short']:.1f}%)")
        
        if issues:
            print(f"      ⚠️  Potential Issues:")
            for issue in issues:
                print(f"         - {issue}")
        else:
            print(f"      ✅ Model signal looks good")
    
    # Overall analysis
    print(f"\n📊 Overall Model Analysis:")
    print("=" * 100)
    
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        min_conf = min(confidences)
        max_conf = max(confidences)
        
        print(f"\n   Confidence Statistics:")
        print(f"      Average: {avg_conf:.1f}%")
        print(f"      Min: {min_conf:.1f}%")
        print(f"      Max: {max_conf:.1f}%")
        
        low_conf_count = sum(1 for c in confidences if c < 85)
        if low_conf_count > 0:
            print(f"      ⚠️  {low_conf_count} trade(s) with confidence < 85%")
    
    if prob_ratios:
        avg_ratio = sum(prob_ratios) / len(prob_ratios)
        min_ratio = min(prob_ratios)
        
        print(f"\n   Probability Ratio Statistics:")
        print(f"      Average Ratio: {avg_ratio:.2f}")
        print(f"      Min Ratio: {min_ratio:.2f}")
        
        if min_ratio < 3.0:
            print(f"      ⚠️  Some trades have low probability ratio (< 3.0)")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    print("-" * 100)
    
    if confidences and avg_conf < 90:
        print(f"   1. ⚠️  Average confidence is {avg_conf:.1f}% - Consider raising threshold")
        print(f"      Current threshold: 85%, Suggested: 90%+")
    
    if prob_ratios and min_ratio < 3.0:
        print(f"   2. ⚠️  Some trades have low probability ratio")
        print(f"      Current min_prob_ratio: 3.0, Consider increasing")
    
    if confidences:
        high_conf_sl = sum(1 for c in confidences if c >= 90)
        if high_conf_sl > 0:
            print(f"   3. ⚠️  {high_conf_sl} high-confidence trade(s) hit SL")
            print(f"      This may indicate:")
            print(f"         - Market conditions changed after entry")
            print(f"         - Stop loss distance too tight")
            print(f"         - Entry timing issue (model correct, execution wrong)")
    
    print(f"\n   4. Entry Quality Check:")
    print(f"      - Review entry slippage")
    print(f"      - Check if entry was at optimal price")
    print(f"      - Verify market conditions at entry time")

if __name__ == "__main__":
    log_file = Path("runs/llm_live.log")
    
    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        exit(1)
    
    print("📊 Parsing log file...")
    signals = parse_log_file(log_file)
    print(f"   Found {len(signals)} signals")
    
    print("\n📊 Getting SL trades from Binance...")
    sl_trades = get_sl_trades_from_binance()
    print(f"   Found {len(sl_trades)} SL trades")
    
    print("\n📊 Matching signals to trades...")
    matched = match_signals_to_trades(signals, sl_trades)
    print(f"   Matched {len(matched)} trades")
    
    analyze_model_performance(matched)

