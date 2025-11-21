#!/usr/bin/env python3
"""
LLM Projesi - Log Dosyasından Stop Loss ve Take Profit Analizi
Log dosyasını analiz ederek SL/TP işlemlerini tespit eder ve detaylı rapor sunar
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

def load_closed_positions():
    """Load closed positions from JSON file."""
    positions_file = Path("runs/closed_positions.json")
    
    if not positions_file.exists():
        return []
    
    try:
        with open(positions_file, 'r') as f:
            return json.load(f)
    except:
        return []

def parse_log_file(log_file_path, days=30):
    """Parse log file to extract position information."""
    if not log_file_path.exists():
        return []
    
    positions = []
    cutoff_date = datetime.now() - timedelta(days=days)
    
    with open(log_file_path, 'r') as f:
        lines = f.readlines()
    
    current_entry = None
    
    for line in lines:
        # Entry order pattern
        entry_match = re.search(r'Order hook: (LONG|SHORT) @ ([\d.]+), TP=([\d.]+), SL=([\d.]+)', line)
        if entry_match:
            side = entry_match.group(1)
            entry_price = float(entry_match.group(2))
            tp_price = float(entry_match.group(3))
            sl_price = float(entry_match.group(4))
            
            # Extract timestamp
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if timestamp_match:
                try:
                    entry_time = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                except:
                    entry_time = datetime.now()
            else:
                entry_time = datetime.now()
            
            if entry_time >= cutoff_date:
                current_entry = {
                    'side': side,
                    'entry_price': entry_price,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'entry_time': entry_time,
                    'exit_reason': None,
                    'exit_price': None,
                    'exit_time': None
                }
        
        # Position closed pattern
        close_match = re.search(r'Pozisyon kapatıldı|Position closed|TP|SL', line, re.IGNORECASE)
        if close_match and current_entry:
            # Try to extract exit price
            exit_price_match = re.search(r'@ ([\d.]+)', line)
            if exit_price_match:
                exit_price = float(exit_price_match.group(1))
            else:
                # Try to infer from TP/SL
                if 'TP' in line.upper() or 'take profit' in line.lower():
                    exit_price = current_entry['tp_price']
                    current_entry['exit_reason'] = 'TP'
                elif 'SL' in line.upper() or 'stop loss' in line.lower():
                    exit_price = current_entry['sl_price']
                    current_entry['exit_reason'] = 'SL'
                else:
                    exit_price = current_entry['entry_price']  # Default
                    current_entry['exit_reason'] = 'UNKNOWN'
            
            # Extract exit timestamp
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if timestamp_match:
                try:
                    exit_time = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                except:
                    exit_time = datetime.now()
            else:
                exit_time = datetime.now()
            
            current_entry['exit_price'] = exit_price
            current_entry['exit_time'] = exit_time
            
            # Calculate PnL
            if current_entry['side'] == 'LONG':
                current_entry['pnl_pct'] = (exit_price - current_entry['entry_price']) / current_entry['entry_price']
            else:
                current_entry['pnl_pct'] = (current_entry['entry_price'] - exit_price) / current_entry['entry_price']
            
            positions.append(current_entry)
            current_entry = None
    
    return positions

def analyze_positions(positions):
    """Analyze positions and generate report."""
    if not positions:
        print("⚠️ Analiz edilecek pozisyon bulunamadı!")
        return
    
    print("=" * 100)
    print("LLM PROJESİ - STOP LOSS VE TAKE PROFIT DETAYLI ANALİZ")
    print("=" * 100)
    print()
    
    # Filter by exit reason
    sl_positions = [p for p in positions if p.get('exit_reason') == 'SL']
    tp_positions = [p for p in positions if p.get('exit_reason') == 'TP']
    unknown_positions = [p for p in positions if p.get('exit_reason') not in ['SL', 'TP']]
    
    total = len(positions)
    
    print("=" * 100)
    print("📊 GENEL İSTATİSTİKLER")
    print("=" * 100)
    print()
    
    print(f"📈 Toplam Pozisyon: {total}")
    print(f"   ✅ Take Profit: {len(tp_positions)} ({len(tp_positions)/total*100:.1f}%)" if total > 0 else "   ✅ Take Profit: 0")
    print(f"   ❌ Stop Loss: {len(sl_positions)} ({len(sl_positions)/total*100:.1f}%)" if total > 0 else "   ❌ Stop Loss: 0")
    print(f"   ❓ Bilinmeyen: {len(unknown_positions)} ({len(unknown_positions)/total*100:.1f}%)" if total > 0 else "   ❓ Bilinmeyen: 0")
    print()
    
    # Win rate
    closed_positions = sl_positions + tp_positions
    if closed_positions:
        win_rate = len(tp_positions) / len(closed_positions) * 100
        print(f"🎯 Win Rate: {win_rate:.1f}%")
        print()
    
    # PnL Analysis
    print("=" * 100)
    print("💰 KAR/ZARAR ANALİZİ")
    print("=" * 100)
    print()
    
    if tp_positions:
        avg_tp_pnl = sum(p.get('pnl_pct', 0) for p in tp_positions) / len(tp_positions)
        total_tp_pnl = sum(p.get('pnl_pct', 0) for p in tp_positions)
        print(f"✅ Take Profit:")
        print(f"   Adet: {len(tp_positions)}")
        print(f"   Ortalama PnL: {avg_tp_pnl*100:.2f}%")
        print(f"   Toplam PnL: {total_tp_pnl*100:.2f}%")
        print()
    
    if sl_positions:
        avg_sl_pnl = sum(p.get('pnl_pct', 0) for p in sl_positions) / len(sl_positions)
        total_sl_pnl = sum(p.get('pnl_pct', 0) for p in sl_positions)
        print(f"❌ Stop Loss:")
        print(f"   Adet: {len(sl_positions)}")
        print(f"   Ortalama PnL: {avg_sl_pnl*100:.2f}%")
        print(f"   Toplam PnL: {total_sl_pnl*100:.2f}%")
        print()
    
    # Side breakdown
    print("=" * 100)
    print("📊 YÖN ANALİZİ")
    print("=" * 100)
    print()
    
    sl_long = [p for p in sl_positions if p['side'] == 'LONG']
    sl_short = [p for p in sl_positions if p['side'] == 'SHORT']
    tp_long = [p for p in tp_positions if p['side'] == 'LONG']
    tp_short = [p for p in tp_positions if p['side'] == 'SHORT']
    
    print(f"LONG Pozisyonlar:")
    long_total = len(tp_long) + len(sl_long)
    if long_total > 0:
        print(f"   TP: {len(tp_long)} ({len(tp_long)/long_total*100:.1f}% win rate)")
        print(f"   SL: {len(sl_long)} ({len(sl_long)/long_total*100:.1f}% loss rate)")
    else:
        print(f"   TP: 0")
        print(f"   SL: 0")
    print()
    
    print(f"SHORT Pozisyonlar:")
    short_total = len(tp_short) + len(sl_short)
    if short_total > 0:
        print(f"   TP: {len(tp_short)} ({len(tp_short)/short_total*100:.1f}% win rate)")
        print(f"   SL: {len(sl_short)} ({len(sl_short)/short_total*100:.1f}% loss rate)")
    else:
        print(f"   TP: 0")
        print(f"   SL: 0")
    print()
    
    # Time analysis
    print("=" * 100)
    print("⏰ ZAMAN ANALİZİ")
    print("=" * 100)
    print()
    
    if sl_positions:
        sl_durations = []
        for p in sl_positions:
            if p.get('entry_time') and p.get('exit_time'):
                duration = (p['exit_time'] - p['entry_time']).total_seconds() / 60
                sl_durations.append(duration)
        
        if sl_durations:
            avg_sl_duration = sum(sl_durations) / len(sl_durations)
            print(f"❌ Stop Loss:")
            print(f"   Ortalama Süre: {avg_sl_duration:.1f} dakika")
            print(f"   En Kısa: {min(sl_durations):.1f} dakika")
            print(f"   En Uzun: {max(sl_durations):.1f} dakika")
            print()
    
    if tp_positions:
        tp_durations = []
        for p in tp_positions:
            if p.get('entry_time') and p.get('exit_time'):
                duration = (p['exit_time'] - p['entry_time']).total_seconds() / 60
                tp_durations.append(duration)
        
        if tp_durations:
            avg_tp_duration = sum(tp_durations) / len(tp_durations)
            print(f"✅ Take Profit:")
            print(f"   Ortalama Süre: {avg_tp_duration:.1f} dakika")
            print(f"   En Kısa: {min(tp_durations):.1f} dakika")
            print(f"   En Uzun: {max(tp_durations):.1f} dakika")
            print()
    
    # Recent SL positions details
    if sl_positions:
        print("=" * 100)
        print("❌ SON STOP LOSS İŞLEMLERİ (Detay)")
        print("=" * 100)
        print()
        
        recent_sl = sorted(sl_positions, key=lambda x: x.get('entry_time', datetime.now()), reverse=True)[:10]
        for i, pos in enumerate(recent_sl, 1):
            entry_time = pos.get('entry_time', datetime.now())
            exit_time = pos.get('exit_time', datetime.now())
            duration = (exit_time - entry_time).total_seconds() / 60 if exit_time and entry_time else 0
            
            print(f"{i}. {pos['side']} - Entry: ${pos['entry_price']:.2f} → Exit: ${pos.get('exit_price', 0):.2f}")
            print(f"   PnL: {pos.get('pnl_pct', 0)*100:.2f}% | Süre: {duration:.1f} dk")
            if entry_time:
                print(f"   Entry: {entry_time.strftime('%Y-%m-%d %H:%M:%S')}")
            if exit_time:
                print(f"   Exit: {exit_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
    
    # Load config for recommendations
    try:
        with open("configs/llm_config.json") as f:
            cfg = json.load(f)
    except:
        cfg = {}
    
    # Recommendations
    print("=" * 100)
    print("💡 STOP LOSS AZALTMA ÖNERİLERİ")
    print("=" * 100)
    print()
    
    sl_rate = len(sl_positions) / total * 100 if total > 0 else 0
    
    recommendations = []
    
    if sl_rate > 50:
        recommendations.append({
            'priority': 'KRİTİK',
            'title': 'Stop Loss oranı %50\'nin üzerinde',
            'actions': [
                'Confidence threshold\'u yükselt (şu an: 0.85 → 0.90 önerilir)',
                'Probability ratio filtresini sıkılaştır (şu an: 5.0 → 7.0 önerilir)',
                'Volume spike threshold\'u yükselt (şu an: 0.4 → 0.5 önerilir)',
                'RSI filtrelerini sıkılaştır (şu an: LONG>75, SHORT<25 → LONG>70, SHORT<30 önerilir)',
                'Minimum bar kontrolünü artır (şu an: 5 bar → 7 bar önerilir)'
            ]
        })
    
    if sl_positions:
        quick_sl = [p for p in sl_positions if p.get('entry_time') and p.get('exit_time') and 
                   (p['exit_time'] - p['entry_time']).total_seconds() < 300]
        if len(quick_sl) > len(sl_positions) * 0.3:
            recommendations.append({
                'priority': 'YÜKSEK',
                'title': 'Hızlı Stop Loss (5 dakikadan kısa)',
                'actions': [
                    'SL seviyesini biraz genişlet (şu an: 0.6% → 0.7% önerilir)',
                    'Entry timing\'i iyileştir (daha iyi fiyat seviyesi bekle)',
                    'Sinyal confirmation süresini artır',
                    'Minimum bar kontrolünü artır (5 → 7 bar)'
                ]
            })
    
    if sl_long and sl_short:
        long_sl_rate = len(sl_long) / (len(tp_long) + len(sl_long)) * 100 if (tp_long or sl_long) else 0
        short_sl_rate = len(sl_short) / (len(tp_short) + len(sl_short)) * 100 if (tp_short or sl_short) else 0
        
        if long_sl_rate > short_sl_rate * 1.5:
            recommendations.append({
                'priority': 'ORTA',
                'title': 'LONG pozisyonlarda yüksek SL oranı',
                'actions': [
                    'LONG sinyalleri için daha sıkı filtreler uygula',
                    'LONG için confidence threshold\'u artır (0.85 → 0.90)',
                    'LONG için probability ratio\'yu artır (5.0 → 7.0)'
                ]
            })
        elif short_sl_rate > long_sl_rate * 1.5:
            recommendations.append({
                'priority': 'ORTA',
                'title': 'SHORT pozisyonlarda yüksek SL oranı',
                'actions': [
                    'SHORT sinyalleri için daha sıkı filtreler uygula',
                    'SHORT için confidence threshold\'u artır (0.85 → 0.90)',
                    'SHORT için probability ratio\'yu artır (5.0 → 7.0)'
                ]
            })
    
    if not recommendations:
        recommendations.append({
            'priority': 'BİLGİ',
            'title': 'Genel İyileştirme Önerileri',
            'actions': [
                'Confidence threshold\'u optimize et',
                'Probability ratio filtresini gözden geçir',
                'Volume spike threshold\'unu optimize et',
                'RSI filtrelerini gözden geçir',
                'Minimum bar kontrolünü optimize et'
            ]
        })
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. [{rec['priority']}] {rec['title']}")
        for action in rec['actions']:
            print(f"   • {action}")
        print()
    
    # Current config summary
    print("=" * 100)
    print("⚙️ MEVCUT AYARLAR")
    print("=" * 100)
    print()
    
    trading_params = cfg.get('trading_params', {})
    print(f"Stop Loss: {trading_params.get('sl_pct', 0)*100:.2f}%")
    print(f"Take Profit: {trading_params.get('tp_pct', 0)*100:.2f}%")
    print(f"Confidence Threshold (LONG): {trading_params.get('thr_long', 0)*100:.0f}%")
    print(f"Confidence Threshold (SHORT): {trading_params.get('thr_short', 0)*100:.0f}%")
    print()
    
    print("=" * 100)

def main():
    # Load from JSON file first
    positions_from_json = load_closed_positions()
    
    # Parse log file
    log_file = Path("runs/llm_live.log")
    positions_from_log = parse_log_file(log_file, days=30)
    
    # Combine (deduplicate)
    all_positions = positions_from_json
    
    # Add unique positions from log
    for pos_log in positions_from_log:
        exists = False
        for pos_json in all_positions:
            try:
                entry_time_json = pos_json.get('entry_time')
                if isinstance(entry_time_json, str):
                    entry_time_json = datetime.fromisoformat(entry_time_json.replace('Z', '+00:00').split('.')[0])
                elif not isinstance(entry_time_json, datetime):
                    entry_time_json = datetime.now()
                
                entry_time_log = pos_log.get('entry_time', datetime.now())
                
                if (abs((entry_time_log - entry_time_json).total_seconds()) < 60 and
                    abs(pos_log['entry_price'] - pos_json.get('entry', 0)) / max(pos_json.get('entry', 1), 1) < 0.001):
                    exists = True
                    break
            except:
                pass
        if not exists:
            all_positions.append(pos_log)
    
    # Convert JSON positions to same format
    converted_positions = []
    for pos in all_positions:
        if isinstance(pos, dict):
            if 'entry' in pos:  # JSON format
                converted = {
                    'side': pos.get('side', 'UNKNOWN'),
                    'entry_price': pos.get('entry', 0),
                    'exit_price': pos.get('exit', 0),
                    'tp_price': pos.get('tp', 0),
                    'sl_price': pos.get('sl', 0),
                    'exit_reason': pos.get('exit_reason', 'UNKNOWN'),
                    'entry_time': datetime.fromisoformat(pos.get('entry_time', datetime.now().isoformat()).replace('Z', '+00:00').split('.')[0]) if isinstance(pos.get('entry_time'), str) else datetime.now(),
                    'exit_time': datetime.fromisoformat(pos.get('exit_time', datetime.now().isoformat()).replace('Z', '+00:00').split('.')[0]) if isinstance(pos.get('exit_time'), str) else datetime.now(),
                    'pnl_pct': pos.get('pnl', 0) if isinstance(pos.get('pnl'), (int, float)) else 0
                }
                converted_positions.append(converted)
            else:  # Log format
                converted_positions.append(pos)
    
    analyze_positions(converted_positions)

if __name__ == "__main__":
    main()

