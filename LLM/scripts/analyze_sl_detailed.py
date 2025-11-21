#!/usr/bin/env python3
"""Detailed analysis of Stop Loss trades from logs and Binance data."""

import json
import re
from datetime import datetime
from pathlib import Path
import ccxt

# Load config
config_path = Path("configs/llm_config.json")
with open(config_path) as f:
    cfg = json.load(f)

exchange = ccxt.binance({
    'apiKey': cfg['api_key'],
    'secret': cfg['secret'],
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})

def get_today_trades():
    """Get today's trades from Binance."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    since = int(today_start.timestamp() * 1000)
    
    try:
        trades = exchange.fetch_my_trades("BTCUSDT", since=since, limit=500)
        return trades
    except Exception as e:
        print(f"Error fetching trades: {e}")
        return []

def pair_trades_to_positions(trades):
    """Pair trades to find positions."""
    positions = []
    i = 0
    
    while i < len(trades):
        entry_trade = trades[i]
        
        if i + 1 < len(trades):
            exit_trade = trades[i + 1]
            
            if entry_trade['side'] != exit_trade['side']:
                entry_price = entry_trade['price']
                exit_price = exit_trade['price']
                
                if entry_trade['side'] == 'buy':
                    pnl_pct = (exit_price - entry_price) / entry_price
                    side = 'LONG'
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price
                    side = 'SHORT'
                
                exit_reason = 'TP' if pnl_pct > 0 else 'SL'
                
                position = {
                    'side': side,
                    'entry': entry_price,
                    'exit': exit_price,
                    'pnl': pnl_pct,
                    'exit_reason': exit_reason,
                    'entry_time': entry_trade['datetime'],
                    'exit_time': exit_trade['datetime'],
                    'entry_order_id': entry_trade.get('id'),
                    'exit_order_id': exit_trade.get('id'),
                }
                positions.append(position)
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    return positions

def get_signal_from_logs(entry_time_str, exit_time_str):
    """Get signal details from logs around entry/exit times."""
    log_file = Path("runs/llm_live.log")
    
    if not log_file.exists():
        return {}
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Parse times
        try:
            entry_dt = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(exit_time_str.replace('Z', '+00:00'))
        except:
            return {}
        
        signal_info = {}
        
        # Find entry signal
        for i, line in enumerate(lines):
            if 'SIGNAL:' in line and entry_time_str[:10] in line:
                # Extract confidence
                conf_match = re.search(r'Confidence: ([\d.]+)%', line)
                if conf_match:
                    signal_info['confidence'] = float(conf_match.group(1))
                
                # Extract side and price
                signal_match = re.search(r'SIGNAL: (\w+) @ \$([\d,]+\.?\d*)', line)
                if signal_match:
                    signal_info['side'] = signal_match.group(1)
                    signal_info['signal_price'] = float(signal_match.group(2).replace(',', ''))
                
                # Get TP/SL from next lines
                for j in range(i, min(i+5, len(lines))):
                    if 'TP:' in lines[j] and 'SL:' in lines[j]:
                        tp_match = re.search(r'TP: \$([\d,]+\.?\d*)', lines[j])
                        sl_match = re.search(r'SL: \$([\d,]+\.?\d*)', lines[j])
                        if tp_match:
                            signal_info['tp'] = float(tp_match.group(1).replace(',', ''))
                        if sl_match:
                            signal_info['sl'] = float(sl_match.group(1).replace(',', ''))
                        break
                break
        
        return signal_info
    except Exception as e:
        print(f"Error reading logs: {e}")
        return {}

def analyze_sl_trades():
    """Analyze Stop Loss trades in detail."""
    print("=" * 100)
    print("LLM Stop Loss Trades - Detailed Analysis")
    print("=" * 100)
    
    # Get trades
    trades = get_today_trades()
    if not trades:
        print("❌ No trades found for today")
        return
    
    positions = pair_trades_to_positions(trades)
    sl_positions = [p for p in positions if p.get('exit_reason') == 'SL']
    
    if not sl_positions:
        print("✅ No Stop Loss trades today!")
        return
    
    print(f"\n📊 Found {len(sl_positions)} Stop Loss Trade(s)")
    print("=" * 100)
    
    for i, pos in enumerate(sl_positions, 1):
        print(f"\n{i}. ❌ Stop Loss Trade #{i}")
        print("-" * 100)
        
        # Basic info
        print(f"   Side: {pos['side']}")
        print(f"   Entry: ${pos['entry']:.2f}")
        print(f"   Exit: ${pos['exit']:.2f}")
        print(f"   PnL: {pos['pnl']*100:.2f}%")
        print(f"   Entry Time: {pos['entry_time']}")
        print(f"   Exit Time: {pos['exit_time']}")
        
        # Calculate duration
        try:
            entry_dt = datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00'))
            duration = exit_dt - entry_dt
            duration_min = duration.total_seconds() / 60
            print(f"   Duration: {duration} ({duration_min:.1f} minutes)")
        except:
            pass
        
        # Price movement analysis
        if pos['side'] == 'LONG':
            price_move = ((pos['exit'] - pos['entry']) / pos['entry']) * 100
            move_direction = "down"
        else:
            price_move = ((pos['entry'] - pos['exit']) / pos['entry']) * 100
            move_direction = "up"
        
        print(f"   Price Movement: {price_move:.2f}% ({move_direction})")
        
        # Get signal info from logs
        signal_info = get_signal_from_logs(pos['entry_time'], pos['exit_time'])
        
        if signal_info:
            print(f"\n   📊 Signal Information:")
            if 'confidence' in signal_info:
                print(f"      Confidence: {signal_info['confidence']:.1f}%")
            if 'tp' in signal_info and 'sl' in signal_info:
                print(f"      TP: ${signal_info['tp']:.2f}")
                print(f"      SL: ${signal_info['sl']:.2f}")
                
                # Calculate distance to SL
                if pos['side'] == 'LONG':
                    entry_to_sl = ((pos['entry'] - signal_info['sl']) / pos['entry']) * 100
                    actual_move = ((pos['exit'] - pos['entry']) / pos['entry']) * 100
                else:
                    entry_to_sl = ((signal_info['sl'] - pos['entry']) / pos['entry']) * 100
                    actual_move = ((pos['entry'] - pos['exit']) / pos['entry']) * 100
                
                print(f"      SL Distance: {entry_to_sl:.2f}%")
                print(f"      Actual Move: {actual_move:.2f}%")
                
                # Check if hit SL exactly or overshoot
                if abs(actual_move - entry_to_sl) < 0.05:
                    print(f"      ✅ Hit SL exactly")
                elif actual_move > entry_to_sl:
                    print(f"      ⚠️  Overshoot SL by {abs(actual_move - entry_to_sl):.2f}%")
        
        # Analysis
        print(f"\n   🔍 Analysis:")
        
        # Quick loss
        if duration_min < 60:
            print(f"      ⚠️  Quick loss (< 1 hour) - Possible premature entry or market reversal")
        
        # Large loss
        if abs(pos['pnl']) > 0.01:
            print(f"      ⚠️  Large loss ({abs(pos['pnl'])*100:.2f}%) - Consider tighter stop or better entry timing")
        
        # Small loss
        if abs(pos['pnl']) < 0.002:
            print(f"      ✅ Small loss ({abs(pos['pnl'])*100:.2f}%) - Good risk management")
        
        # Confidence check
        if signal_info.get('confidence', 100) < 90:
            print(f"      ⚠️  Low confidence signal ({signal_info.get('confidence', 0):.1f}%) - Consider raising threshold")
    
    # Overall analysis
    print(f"\n📊 Overall SL Analysis:")
    print("=" * 100)
    
    avg_sl_pnl = sum(p['pnl'] for p in sl_positions) / len(sl_positions)
    total_sl_pnl = sum(p['pnl'] for p in sl_positions)
    
    print(f"   Total SL Trades: {len(sl_positions)}")
    print(f"   Average SL PnL: {avg_sl_pnl*100:.2f}%")
    print(f"   Total SL Loss: {total_sl_pnl*100:.2f}%")
    
    # Side breakdown
    sl_long = [p for p in sl_positions if p['side'] == 'LONG']
    sl_short = [p for p in sl_positions if p['side'] == 'SHORT']
    
    if sl_long:
        avg_long = sum(p['pnl'] for p in sl_long) / len(sl_long)
        print(f"   LONG SL: {len(sl_long)} trades, Avg: {avg_long*100:.2f}%")
    
    if sl_short:
        avg_short = sum(p['pnl'] for p in sl_short) / len(sl_short)
        print(f"   SHORT SL: {len(sl_short)} trades, Avg: {avg_short*100:.2f}%")
    
    # Duration analysis
    durations = []
    for pos in sl_positions:
        try:
            entry_dt = datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00'))
            durations.append((exit_dt - entry_dt).total_seconds() / 60)
        except:
            pass
    
    if durations:
        avg_duration = sum(durations) / len(durations)
        print(f"   Average Duration: {avg_duration:.1f} minutes")
        print(f"   Min Duration: {min(durations):.1f} minutes")
        print(f"   Max Duration: {max(durations):.1f} minutes")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    print("-" * 100)
    
    if len(sl_positions) > 2:
        print(f"   ⚠️  High number of SLs ({len(sl_positions)}) - Review entry strategy")
    
    if avg_sl_pnl < -0.005:
        print(f"   ⚠️  Average SL loss is {avg_sl_pnl*100:.2f}% - Consider tighter stops")
    
    if durations and avg_duration < 120:
        print(f"   ⚠️  Quick SLs (avg {avg_duration:.1f} min) - May indicate poor entry timing")
    
    if sl_short and len(sl_short) > len(sl_long):
        print(f"   ⚠️  More SHORT SLs than LONG - Review SHORT entry strategy")

if __name__ == "__main__":
    analyze_sl_trades()

