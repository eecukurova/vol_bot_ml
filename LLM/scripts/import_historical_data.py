#!/usr/bin/env python3
"""Import historical trade data to create closed_positions.json for analysis."""
import json
import ccxt
from datetime import datetime
from pathlib import Path
import sys

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

def import_historical_positions(symbol="BTCUSDT", days_back=60):
    """Import historical positions from Binance trades."""
    
    print(f'=== GEÇMİŞ POZİSYONLARI İÇE AKTARMA ({symbol}) ===\n')
    
    # Get all trades
    since = exchange.milliseconds() - days_back * 24 * 60 * 60 * 1000
    trades = exchange.fetch_my_trades(symbol, since=since, limit=500)
    
    if not trades:
        print(f'⚪ İşlem yok')
        return []
    
    print(f'📊 Toplam Trade: {len(trades)}\n')
    
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
    
    print(f'📈 Kapanan Pozisyon: {len(positions)}\n')
    
    # Convert to closed_positions.json format
    closed_positions = []
    
    for pos in positions:
        entry_dt = datetime.fromtimestamp(pos['entry_time'] / 1000)
        exit_dt = datetime.fromtimestamp(pos['exit_time'] / 1000)
        
        # Determine exit reason (TP or SL)
        # Approximate: if PnL > 0, likely TP; if PnL < 0, likely SL
        exit_reason = 'TP' if pos['pnl'] > 0 else 'SL'
        
        # Calculate approximate TP/SL (assuming standard 0.5% TP, 1% SL)
        entry_price = pos['entry']['price']
        exit_price = pos['exit']['price']
        
        if pos['type'] == 'LONG':
            tp_price = entry_price * 1.005  # 0.5% TP
            sl_price = entry_price * 0.99   # 1% SL
        else:  # SHORT
            tp_price = entry_price * 0.995  # 0.5% TP
            sl_price = entry_price * 1.01   # 1% SL
        
        closed_position = {
            'timestamp': exit_dt.isoformat(),
            'symbol': symbol,
            'side': pos['type'],
            'entry': entry_price,
            'exit': exit_price,
            'tp': tp_price,
            'sl': sl_price,
            'confidence': 0.75,  # Default (not available from historical data)
            'probs': {
                'flat': 0.25,
                'long': 0.5 if pos['type'] == 'LONG' else 0.25,
                'short': 0.5 if pos['type'] == 'SHORT' else 0.25
            },
            'pnl': pos['pnl'],
            'exit_reason': exit_reason,
            'entry_time': entry_dt.isoformat(),
            'exit_time': exit_dt.isoformat(),
            'features': {}  # Not available from historical data
        }
        
        closed_positions.append(closed_position)
    
    # Sort by exit time
    closed_positions.sort(key=lambda x: x['exit_time'])
    
    return closed_positions

def main():
    print('=== GEÇMİŞ VERİLERİ İÇE AKTARMA ===\n')
    
    # Import BTC positions
    btc_positions = import_historical_positions("BTCUSDT", days_back=60)
    
    print('\n' + '='*60 + '\n')
    
    # Import ETH positions
    eth_positions = import_historical_positions("ETHUSDT", days_back=60)
    
    # Combine and save
    all_positions = btc_positions + eth_positions
    
    if all_positions:
        positions_file = Path("runs/closed_positions.json")
        positions_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing if any
        existing_positions = []
        if positions_file.exists():
            try:
                with open(positions_file) as f:
                    existing_positions = json.load(f)
            except:
                pass
        
        # Merge (avoid duplicates)
        existing_entry_times = {p.get('entry_time') for p in existing_positions}
        new_positions = [p for p in all_positions if p['entry_time'] not in existing_entry_times]
        
        all_merged = existing_positions + new_positions
        all_merged.sort(key=lambda x: x.get('exit_time', x['timestamp']))
        
        # Keep last 500
        if len(all_merged) > 500:
            all_merged = all_merged[-500:]
        
        # Save
        with open(positions_file, 'w') as f:
            json.dump(all_merged, f, indent=2)
        
        print(f'\n✅ {len(new_positions)} yeni pozisyon eklendi')
        print(f'📊 Toplam: {len(all_merged)} pozisyon')
        print(f'💾 Dosya: {positions_file}\n')
        
        # Statistics
        sl_count = sum(1 for p in all_merged if p.get('exit_reason') == 'SL')
        tp_count = sum(1 for p in all_merged if p.get('exit_reason') == 'TP')
        
        print(f'📊 İstatistikler:')
        print(f'   ❌ Stop Loss: {sl_count}')
        print(f'   ✅ Take Profit: {tp_count}\n')
    else:
        print('⚪ İçe aktarılacak pozisyon yok')

if __name__ == "__main__":
    main()

