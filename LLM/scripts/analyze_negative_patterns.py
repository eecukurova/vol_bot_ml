#!/usr/bin/env python3
"""Analyze negative position patterns for model training."""
import json
import ccxt
from datetime import datetime, timedelta
from pathlib import Path
import sys
from collections import defaultdict
import statistics

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

def analyze_negative_positions(symbol="BTCUSDT", min_consecutive=5):
    """Analyze patterns in consecutive negative positions."""
    
    print(f'=== NEGATİF POZİSYON PATTERN ANALİZİ ({symbol}) ===\n')
    
    # Get all trades
    since = exchange.milliseconds() - 60 * 24 * 60 * 60 * 1000  # 60 days
    trades = exchange.fetch_my_trades(symbol, since=since, limit=500)
    
    if not trades:
        print(f'⚪ İşlem yok')
        return
    
    # Pair trades to find positions
    positions = []
    i = 0
    while i < len(trades):
        trade = trades[i]
        
        if trade['side'] == 'buy':
            for j in range(i+1, len(trades)):
                if trades[j]['side'] == 'sell':
                    pnl = 0
                    if 'info' in trades[j] and 'realizedPnl' in trades[j]['info']:
                        pnl = float(trades[j]['info']['realizedPnl'])
                    
                    positions.append({
                        'type': 'LONG',
                        'entry': trade,
                        'exit': trades[j],
                        'pnl': pnl,
                        'entry_time': trade['timestamp'],
                        'exit_time': trades[j]['timestamp']
                    })
                    i = j + 1
                    break
            else:
                i += 1
        elif trade['side'] == 'sell':
            for j in range(i+1, len(trades)):
                if trades[j]['side'] == 'buy':
                    pnl = 0
                    if 'info' in trades[j] and 'realizedPnl' in trades[j]['info']:
                        pnl = float(trades[j]['info']['realizedPnl'])
                    
                    positions.append({
                        'type': 'SHORT',
                        'entry': trade,
                        'exit': trades[j],
                        'pnl': pnl,
                        'entry_time': trade['timestamp'],
                        'exit_time': trades[j]['timestamp']
                    })
                    i = j + 1
                    break
            else:
                i += 1
        else:
            i += 1
    
    # Sort by exit time
    positions.sort(key=lambda x: x['exit_time'])
    
    # Find consecutive negative positions
    negative_positions = [p for p in positions if p['pnl'] < 0]
    
    print(f'📊 Toplam Pozisyon: {len(positions)}')
    print(f'❌ Negatif Pozisyon: {len(negative_positions)}')
    print(f'✅ Pozitif Pozisyon: {len(positions) - len(negative_positions)}\n')
    
    if len(negative_positions) < min_consecutive:
        print(f'⚪ En az {min_consecutive} negatif pozisyon bulunamadı')
        return
    
    # Find consecutive sequences
    consecutive_sequences = []
    current_sequence = []
    
    for i, pos in enumerate(positions):
        if pos['pnl'] < 0:
            current_sequence.append(pos)
        else:
            if len(current_sequence) >= min_consecutive:
                consecutive_sequences.append(current_sequence)
            current_sequence = []
    
    # Add last sequence if it ends with negatives
    if len(current_sequence) >= min_consecutive:
        consecutive_sequences.append(current_sequence)
    
    print(f'📋 Arka Arkaya {min_consecutive}+ Negatif Pozisyon: {len(consecutive_sequences)}\n')
    
    # Analyze patterns
    if consecutive_sequences:
        print('=== PATTERN ANALİZİ ===\n')
        
        for seq_idx, sequence in enumerate(consecutive_sequences, 1):
            print(f'📊 Sequence {seq_idx}: {len(sequence)} negatif pozisyon\n')
            
            # Time pattern
            entry_times = [datetime.fromtimestamp(p['entry_time'] / 1000) for p in sequence]
            exit_times = [datetime.fromtimestamp(p['exit_time'] / 1000) for p in sequence]
            
            print(f'⏰ Zaman Pattern:')
            print(f'   İlk Entry: {entry_times[0].strftime("%Y-%m-%d %H:%M")}')
            print(f'   Son Exit: {exit_times[-1].strftime("%Y-%m-%d %H:%M")}')
            print(f'   Süre: {(exit_times[-1] - entry_times[0]).total_seconds() / 3600:.1f} saat\n')
            
            # Hour distribution
            hours = [dt.hour for dt in entry_times]
            hour_counts = defaultdict(int)
            for h in hours:
                hour_counts[h] += 1
            
            most_common_hour = max(hour_counts.items(), key=lambda x: x[1])[0]
            print(f'   En çok pozisyon açılan saat: {most_common_hour}:00 ({hour_counts[most_common_hour]} pozisyon)\n')
            
            # PnL distribution
            pnls = [p['pnl'] for p in sequence]
            avg_pnl = statistics.mean(pnls)
            min_pnl = min(pnls)
            max_pnl = max(pnls)
            
            print(f'💰 PnL Dağılımı:')
            print(f'   Ortalama: ${avg_pnl:.2f}')
            print(f'   Min: ${min_pnl:.2f}')
            print(f'   Max: ${max_pnl:.2f}\n')
            
            # Side distribution
            sides = [p['type'] for p in sequence]
            long_count = sides.count('LONG')
            short_count = sides.count('SHORT')
            
            print(f'📊 Side Dağılımı:')
            print(f'   LONG: {long_count}')
            print(f'   SHORT: {short_count}\n')
            
            # Price movement
            first_entry = sequence[0]['entry']['price']
            last_exit = sequence[-1]['exit']['price']
            price_change = ((last_exit - first_entry) / first_entry) * 100
            
            print(f'📈 Fiyat Hareketi:')
            print(f'   İlk Entry: ${first_entry:.2f}')
            print(f'   Son Exit: ${last_exit:.2f}')
            print(f'   Değişim: {price_change:.2f}%\n')
            
            # Position details
            print(f'📋 Pozisyon Detayları:')
            for i, pos in enumerate(sequence, 1):
                entry_dt = datetime.fromtimestamp(pos['entry_time'] / 1000)
                exit_dt = datetime.fromtimestamp(pos['exit_time'] / 1000)
                duration = (exit_dt - entry_dt).total_seconds() / 3600
                
                print(f'   {i}. {pos["type"]} @ ${pos["entry"]["price"]:.2f} → ${pos["exit"]["price"]:.2f}')
                print(f'      PnL: ${pos["pnl"]:.2f} | Süre: {duration:.1f}s')
            
            print()
    
    # Overall statistics
    print('=== GENEL İSTATİSTİKLER ===\n')
    
    if negative_positions:
        # Confidence analysis (if available from closed_positions.json)
        closed_positions_file = Path("runs/closed_positions.json")
        if closed_positions_file.exists():
            try:
                with open(closed_positions_file) as f:
                    closed_positions_data = json.load(f)
                
                # Match by entry price and time
                sl_positions = [p for p in closed_positions_data if p.get('exit_reason') == 'SL']
                
                if sl_positions:
                    confidences = [p.get('confidence', 0) for p in sl_positions if 'confidence' in p]
                    if confidences:
                        avg_confidence = statistics.mean(confidences)
                        min_confidence = min(confidences)
                        max_confidence = max(confidences)
                        
                        print(f'📊 SL Pozisyonlarının Confidence Analizi:')
                        print(f'   Ortalama: {avg_confidence*100:.2f}%')
                        print(f'   Min: {min_confidence*100:.2f}%')
                        print(f'   Max: {max_confidence*100:.2f}%\n')
            except:
                pass
        
        # Feature patterns (if available)
        print(f'💡 Öneriler:')
        print(f'   1. Arka arkaya {min_consecutive}+ negatif pozisyon varsa, trading\'i durdur')
        print(f'   2. Bu pattern\'leri model eğitiminde hard negative olarak işaretle')
        print(f'   3. Confidence threshold\'u yükselt (eğer SL pozisyonları yüksek confidence\'lı ise)')
        print(f'   4. Market regime\'lerini kontrol et (volatilite, trend)')

if __name__ == "__main__":
    print('Analyzing negative position patterns...\n')
    
    # Analyze BTC
    analyze_negative_positions("BTCUSDT", min_consecutive=5)
    
    print('\n' + '='*60 + '\n')
    
    # Analyze ETH
    analyze_negative_positions("ETHUSDT", min_consecutive=5)

