#!/usr/bin/env python3
"""Evaluate skipped signals to measure model accuracy."""
import json
import ccxt
from datetime import datetime, timedelta
from pathlib import Path
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load config
with open('configs/llm_config.json') as f:
    cfg = json.load(f)

exchange = ccxt.binance({
    'apiKey': cfg['api_key'],
    'secret': cfg['secret'],
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})

def get_price_at_time(symbol, timestamp_ms):
    """Get price at specific timestamp (approximate)."""
    try:
        # Fetch OHLCV data around the timestamp
        since = timestamp_ms - 3600000  # 1 hour before
        ohlcv = exchange.fetch_ohlcv(symbol, "3m", since=since, limit=20)
        
        # Find closest candle
        closest = None
        min_diff = float('inf')
        
        for candle in ohlcv:
            diff = abs(candle[0] - timestamp_ms)
            if diff < min_diff:
                min_diff = diff
                closest = candle
        
        if closest:
            return closest[4]  # close price
        return None
    except:
        return None

def evaluate_skipped_signal(skipped_signal, closed_positions):
    """Evaluate if a skipped signal would have been profitable."""
    
    signal_time = datetime.fromisoformat(skipped_signal['timestamp'])
    signal_entry = skipped_signal['entry']
    signal_tp = skipped_signal['tp']
    signal_sl = skipped_signal['sl']
    signal_side = skipped_signal['side']
    
    # Find the active position that was closed after this signal
    matching_positions = []
    for pos in closed_positions:
        pos_entry_time = datetime.fromisoformat(pos.get('entry_time', pos['timestamp']))
        pos_exit_time = datetime.fromisoformat(pos.get('exit_time', pos['timestamp']))
        
        # Check if position was active when signal was skipped
        if pos_entry_time < signal_time < pos_exit_time:
            matching_positions.append(pos)
    
    if not matching_positions:
        return None
    
    # Get the position that was active
    active_position = matching_positions[0]
    
    # Simulate what would have happened with skipped signal
    # Check if TP or SL would have been hit before the active position closed
    
    # Get prices at different times
    signal_timestamp_ms = int(signal_time.timestamp() * 1000)
    active_exit_time = datetime.fromisoformat(active_position.get('exit_time', active_position['timestamp']))
    active_exit_timestamp_ms = int(active_exit_time.timestamp() * 1000)
    
    # Check if TP or SL was hit
    # For simplicity, we'll check if price reached TP/SL between signal time and active position exit
    
    # Fetch price data
    symbol = skipped_signal.get('symbol', 'BTCUSDT')
    
    try:
        since = signal_timestamp_ms
        until = active_exit_timestamp_ms
        ohlcv = exchange.fetch_ohlcv(symbol, "3m", since=since, limit=500)
        
        tp_hit = False
        sl_hit = False
        
        for candle in ohlcv:
            if candle[0] > until:
                break
            
            high = candle[2]  # high price
            low = candle[3]   # low price
            
            if signal_side == "LONG":
                if high >= signal_tp:
                    tp_hit = True
                    break
                if low <= signal_sl:
                    sl_hit = True
                    break
            else:  # SHORT
                if low <= signal_tp:
                    tp_hit = True
                    break
                if high >= signal_sl:
                    sl_hit = True
                    break
        
        if tp_hit:
            return {
                'result': 'TP',
                'would_be_profitable': True,
                'active_position_result': active_position.get('exit_reason', 'UNKNOWN'),
                'active_position_pnl': active_position.get('pnl', 0)
            }
        elif sl_hit:
            return {
                'result': 'SL',
                'would_be_profitable': False,
                'active_position_result': active_position.get('exit_reason', 'UNKNOWN'),
                'active_position_pnl': active_position.get('pnl', 0)
            }
        else:
            # Price didn't reach TP or SL
            # Check final price
            final_price = ohlcv[-1][4] if ohlcv else None
            
            if final_price:
                if signal_side == "LONG":
                    pnl_pct = ((final_price - signal_entry) / signal_entry) * 100
                else:
                    pnl_pct = ((signal_entry - final_price) / signal_entry) * 100
                
                return {
                    'result': 'NO_TP_SL',
                    'would_be_profitable': pnl_pct > 0,
                    'pnl_pct': pnl_pct,
                    'final_price': final_price,
                    'active_position_result': active_position.get('exit_reason', 'UNKNOWN'),
                    'active_position_pnl': active_position.get('pnl', 0)
                }
    
    except Exception as e:
        print(f"Error evaluating signal: {e}")
        return None
    
    return None

def main():
    print('=== SKIP EDİLEN SİNYALLERİN DEĞERLENDİRMESİ ===\n')
    
    # Load skipped signals
    skipped_file = Path("runs/skipped_signals.json")
    if not skipped_file.exists():
        print('⚪ Skip edilen sinyal dosyası bulunamadı')
        return
    
    with open(skipped_file) as f:
        skipped_signals = json.load(f)
    
    print(f'📊 Toplam Skip Edilen Sinyal: {len(skipped_signals)}\n')
    
    # Load closed positions
    positions_file = Path("runs/closed_positions.json")
    closed_positions = []
    if positions_file.exists():
        with open(positions_file) as f:
            closed_positions = json.load(f)
    
    print(f'📊 Kapanan Pozisyon: {len(closed_positions)}\n')
    
    # Evaluate each skipped signal
    evaluated = []
    for signal in skipped_signals:
        result = evaluate_skipped_signal(signal, closed_positions)
        if result:
            signal['evaluation'] = result
            evaluated.append(signal)
    
    print(f'✅ Değerlendirilen Sinyal: {len(evaluated)}\n')
    
    if not evaluated:
        print('⚪ Değerlendirilebilir sinyal yok')
        return
    
    # Statistics
    tp_hits = sum(1 for s in evaluated if s['evaluation']['result'] == 'TP')
    sl_hits = sum(1 for s in evaluated if s['evaluation']['result'] == 'SL')
    profitable = sum(1 for s in evaluated if s['evaluation'].get('would_be_profitable', False))
    
    print('=== İSTATİSTİKLER ===\n')
    print(f'✅ TP Hit: {tp_hits} ({tp_hits/len(evaluated)*100:.1f}%)')
    print(f'❌ SL Hit: {sl_hits} ({sl_hits/len(evaluated)*100:.1f}%)')
    print(f'📊 Karlı Sinyal: {profitable} ({profitable/len(evaluated)*100:.1f}%)\n')
    
    # Compare with active positions
    active_sl = sum(1 for s in evaluated if s['evaluation']['active_position_result'] == 'SL')
    active_tp = sum(1 for s in evaluated if s['evaluation']['active_position_result'] == 'TP')
    
    print('=== AKTİF POZİSYONLARLA KARŞILAŞTIRMA ===\n')
    print(f'Aktif Pozisyon SL ile Kapandı: {active_sl}')
    print(f'Aktif Pozisyon TP ile Kapandı: {active_tp}\n')
    
    # Model accuracy analysis
    correct_signals = 0
    incorrect_signals = 0
    
    for signal in evaluated:
        eval_result = signal['evaluation']
        active_result = eval_result['active_position_result']
        
        # If active position hit SL, but skipped signal would hit TP, model was correct
        if active_result == 'SL' and eval_result['result'] == 'TP':
            correct_signals += 1
        # If active position hit TP, but skipped signal would hit SL, model was wrong
        elif active_result == 'TP' and eval_result['result'] == 'SL':
            incorrect_signals += 1
    
    print('=== MODEL DOĞRULUK ANALİZİ ===\n')
    print(f'✅ Model Doğru Sinyal: {correct_signals}')
    print(f'❌ Model Yanlış Sinyal: {incorrect_signals}\n')
    
    if correct_signals + incorrect_signals > 0:
        accuracy = correct_signals / (correct_signals + incorrect_signals) * 100
        print(f'📊 Model Doğruluk Oranı: {accuracy:.1f}%\n')
    
    # Save evaluation results
    eval_file = Path("runs/skipped_signals_evaluated.json")
    with open(eval_file, 'w') as f:
        json.dump(evaluated, f, indent=2)
    
    print(f'💾 Değerlendirme sonuçları kaydedildi: {eval_file}')

if __name__ == "__main__":
    main()

