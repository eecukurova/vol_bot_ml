#!/usr/bin/env python3
"""
LLM Projesi - Son İşlemlerin Detaylı PNL Analizi
PNL bazında + ve - işlemleri analiz eder
"""

import json
import ccxt
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

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

def get_recent_trades(symbol="BTCUSDT", days=7):
    """Get recent trades from Binance."""
    since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    try:
        trades = exchange.fetch_my_trades(symbol, since=since, limit=500)
        return trades
    except Exception as e:
        print(f"❌ Error fetching trades: {e}")
        return []

def pair_trades_to_positions(trades):
    """Pair trades to find entry/exit positions."""
    if not trades:
        return []
    
    # Sort by timestamp
    trades.sort(key=lambda x: x.get('timestamp', 0))
    
    positions = []
    i = 0
    
    while i < len(trades):
        trade = trades[i]
        
        # Find entry (first trade of position)
        if trade['side'] == 'buy':
            entry_trade = trade
            entry_price = float(trade['price'])
            entry_amount = float(trade['amount'])
            entry_time = datetime.fromtimestamp(trade['timestamp'] / 1000, tz=timezone.utc)
            
            # Find corresponding exit (sell)
            j = i + 1
            exit_trade = None
            while j < len(trades):
                if trades[j]['side'] == 'sell' and float(trades[j]['amount']) >= entry_amount * 0.95:
                    exit_trade = trades[j]
                    break
                j += 1
            
            if exit_trade:
                exit_price = float(exit_trade['price'])
                exit_time = datetime.fromtimestamp(exit_trade['timestamp'] / 1000, tz=timezone.utc)
                
                # Calculate PnL
                pnl = (exit_price - entry_price) * entry_amount
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                
                # Determine exit reason (approximate)
                # If PnL > 0, likely TP; if PnL < 0, likely SL
                if pnl > 0:
                    exit_reason = "TP"
                else:
                    exit_reason = "SL"
                
                positions.append({
                    'side': 'LONG',
                    'entry_time': entry_time.isoformat(),
                    'exit_time': exit_time.isoformat(),
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'exit_reason': exit_reason,
                    'duration_min': (exit_time - entry_time).total_seconds() / 60
                })
                
                i = j + 1
            else:
                i += 1
        elif trade['side'] == 'sell':
            # SHORT position
            entry_trade = trade
            entry_price = float(trade['price'])
            entry_amount = float(trade['amount'])
            entry_time = datetime.fromtimestamp(trade['timestamp'] / 1000, tz=timezone.utc)
            
            # Find corresponding exit (buy)
            j = i + 1
            exit_trade = None
            while j < len(trades):
                if trades[j]['side'] == 'buy' and float(trades[j]['amount']) >= entry_amount * 0.95:
                    exit_trade = trades[j]
                    break
                j += 1
            
            if exit_trade:
                exit_price = float(exit_trade['price'])
                exit_time = datetime.fromtimestamp(exit_trade['timestamp'] / 1000, tz=timezone.utc)
                
                # Calculate PnL (for SHORT: entry - exit)
                pnl = (entry_price - exit_price) * entry_amount
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                
                if pnl > 0:
                    exit_reason = "TP"
                else:
                    exit_reason = "SL"
                
                positions.append({
                    'side': 'SHORT',
                    'entry_time': entry_time.isoformat(),
                    'exit_time': exit_time.isoformat(),
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'exit_reason': exit_reason,
                    'duration_min': (exit_time - entry_time).total_seconds() / 60
                })
                
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    
    return positions

def analyze_pnl_breakdown(positions):
    """Analyze PNL breakdown by positive and negative trades."""
    
    positive_trades = [p for p in positions if p['pnl'] > 0]
    negative_trades = [p for p in positions if p['pnl'] < 0]
    
    print("\n" + "="*80)
    print("📊 PNL BREAKDOWN ANALİZİ")
    print("="*80)
    
    print(f"\n✅ POZİTİF İŞLEMLER (+): {len(positive_trades)}")
    if positive_trades:
        total_positive_pnl = sum(p['pnl'] for p in positive_trades)
        avg_positive_pnl = total_positive_pnl / len(positive_trades)
        avg_positive_pnl_pct = sum(p['pnl_pct'] for p in positive_trades) / len(positive_trades)
        
        print(f"   Toplam PNL: ${total_positive_pnl:.2f}")
        print(f"   Ortalama PNL: ${avg_positive_pnl:.2f} ({avg_positive_pnl_pct:.2f}%)")
        print(f"   En İyi İşlem: ${max(p['pnl'] for p in positive_trades):.2f} ({max(p['pnl_pct'] for p in positive_trades):.2f}%)")
        
        # TP/SL breakdown
        tp_count = sum(1 for p in positive_trades if p.get('exit_reason') == 'TP')
        print(f"   TP ile Kapanan: {tp_count}")
        
        print(f"\n   📋 Pozitif İşlemler:")
        for i, p in enumerate(sorted(positive_trades, key=lambda x: x['entry_time']), 1):
            print(f"   {i}. {p['side']} @ ${p['entry_price']:.2f} → ${p['exit_price']:.2f}")
            print(f"      PNL: ${p['pnl']:.2f} ({p['pnl_pct']:.2f}%) | {p['exit_reason']} | {p['duration_min']:.1f} min")
            print(f"      Zaman: {p['entry_time']}")
    
    print(f"\n❌ NEGATİF İŞLEMLER (-): {len(negative_trades)}")
    if negative_trades:
        total_negative_pnl = sum(p['pnl'] for p in negative_trades)
        avg_negative_pnl = total_negative_pnl / len(negative_trades)
        avg_negative_pnl_pct = sum(p['pnl_pct'] for p in negative_trades) / len(negative_trades)
        
        print(f"   Toplam PNL: ${total_negative_pnl:.2f}")
        print(f"   Ortalama PNL: ${avg_negative_pnl:.2f} ({avg_negative_pnl_pct:.2f}%)")
        print(f"   En Kötü İşlem: ${min(p['pnl'] for p in negative_trades):.2f} ({min(p['pnl_pct'] for p in negative_trades):.2f}%)")
        
        # TP/SL breakdown
        sl_count = sum(1 for p in negative_trades if p.get('exit_reason') == 'SL')
        print(f"   SL ile Kapanan: {sl_count}")
        
        print(f"\n   📋 Negatif İşlemler:")
        for i, p in enumerate(sorted(negative_trades, key=lambda x: x['entry_time']), 1):
            print(f"   {i}. {p['side']} @ ${p['entry_price']:.2f} → ${p['exit_price']:.2f}")
            print(f"      PNL: ${p['pnl']:.2f} ({p['pnl_pct']:.2f}%) | {p['exit_reason']} | {p['duration_min']:.1f} min")
            print(f"      Zaman: {p['entry_time']}")
    
    # Summary
    total_pnl = sum(p['pnl'] for p in positions)
    total_trades = len(positions)
    win_rate = (len(positive_trades) / total_trades * 100) if total_trades > 0 else 0
    
    print(f"\n" + "="*80)
    print("📈 ÖZET")
    print("="*80)
    print(f"Toplam İşlem: {total_trades}")
    print(f"Kazanma Oranı: {win_rate:.1f}%")
    print(f"Toplam PNL: ${total_pnl:.2f}")
    print(f"Net PNL: ${total_positive_pnl + total_negative_pnl:.2f}")
    
    # Side breakdown
    long_trades = [p for p in positions if p['side'] == 'LONG']
    short_trades = [p for p in positions if p['side'] == 'SHORT']
    
    print(f"\nLONG İşlemler: {len(long_trades)}")
    if long_trades:
        long_positive = [p for p in long_trades if p['pnl'] > 0]
        long_negative = [p for p in long_trades if p['pnl'] < 0]
        print(f"   ✅ Pozitif: {len(long_positive)} | ❌ Negatif: {len(long_negative)}")
        print(f"   Toplam PNL: ${sum(p['pnl'] for p in long_trades):.2f}")
    
    print(f"\nSHORT İşlemler: {len(short_trades)}")
    if short_trades:
        short_positive = [p for p in short_trades if p['pnl'] > 0]
        short_negative = [p for p in short_trades if p['pnl'] < 0]
        print(f"   ✅ Pozitif: {len(short_positive)} | ❌ Negatif: {len(short_negative)}")
        print(f"   Toplam PNL: ${sum(p['pnl'] for p in short_trades):.2f}")

def main():
    print("🔍 LLM Projesi - Son İşlemlerin Detaylı PNL Analizi")
    print("="*80)
    
    # Get recent trades
    trades = get_recent_trades("BTCUSDT", days=7)
    print(f"\n📥 Son 7 günün işlemleri: {len(trades)} trade")
    
    if not trades:
        print("❌ İşlem bulunamadı!")
        return
    
    # Pair trades to positions
    positions = pair_trades_to_positions(trades)
    print(f"📊 Pozisyon sayısı: {len(positions)}")
    
    if not positions:
        print("❌ Pozisyon bulunamadı!")
        return
    
    # Sort by entry time (most recent first)
    positions.sort(key=lambda x: x['entry_time'], reverse=True)
    
    # Analyze
    analyze_pnl_breakdown(positions)
    
    # Save to file
    output_file = Path("runs/recent_pnl_analysis.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(positions, f, indent=2)
    print(f"\n💾 Sonuçlar kaydedildi: {output_file}")

if __name__ == "__main__":
    main()

