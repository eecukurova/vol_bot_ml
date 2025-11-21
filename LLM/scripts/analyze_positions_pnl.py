#!/usr/bin/env python3
"""
LLM Projesi - Pozisyonların PNL Analizi
positions_post_deploy.json ve closed_positions_remote.json dosyalarından analiz yapar
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def load_positions_file(file_path):
    """Load positions from JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return []

def analyze_pnl_breakdown(positions):
    """Analyze PNL breakdown by positive and negative trades."""
    
    # Filter out positions without pnl_pct
    valid_positions = [p for p in positions if 'pnl_pct' in p or 'pnl' in p]
    
    # Normalize pnl_pct
    for p in valid_positions:
        if 'pnl_pct' not in p:
            if 'pnl' in p:
                # Calculate pnl_pct from pnl
                entry = p.get('entry_price') or p.get('entry')
                if entry:
                    p['pnl_pct'] = (p['pnl'] / entry) * 100 if p['pnl'] else 0
                else:
                    p['pnl_pct'] = 0
            else:
                p['pnl_pct'] = 0
    
    positive_trades = [p for p in valid_positions if (p.get('pnl_pct', 0) > 0 or p.get('pnl', 0) > 0)]
    negative_trades = [p for p in valid_positions if (p.get('pnl_pct', 0) < 0 or p.get('pnl', 0) < 0)]
    
    print("\n" + "="*80)
    print("📊 PNL BREAKDOWN ANALİZİ")
    print("="*80)
    
    print(f"\n✅ POZİTİF İŞLEMLER (+): {len(positive_trades)}")
    if positive_trades:
        # Calculate totals
        total_positive_pnl = sum(p.get('pnl', 0) for p in positive_trades)
        total_positive_pnl_pct = sum(p.get('pnl_pct', 0) for p in positive_trades)
        avg_positive_pnl_pct = total_positive_pnl_pct / len(positive_trades)
        
        print(f"   Toplam PNL: ${total_positive_pnl:.2f}")
        print(f"   Ortalama PNL %: {avg_positive_pnl_pct:.4f}%")
        print(f"   En İyi İşlem: {max(p.get('pnl_pct', 0) for p in positive_trades):.4f}%")
        
        # TP/SL breakdown
        tp_count = sum(1 for p in positive_trades if p.get('exit_reason') == 'TP')
        print(f"   TP ile Kapanan: {tp_count}")
        
        print(f"\n   📋 Pozitif İşlemler (Son 10):")
        for i, p in enumerate(sorted(positive_trades, key=lambda x: x.get('entry_time', ''), reverse=True)[:10], 1):
            side = p.get('side', 'UNKNOWN')
            entry = p.get('entry_price') or p.get('entry', 0)
            exit_p = p.get('exit_price') or p.get('exit', 0)
            pnl_pct = p.get('pnl_pct', 0)
            exit_reason = p.get('exit_reason', 'UNKNOWN')
            duration = p.get('duration_min', 0)
            entry_time = p.get('entry_time', 'N/A')
            
            print(f"   {i}. {side} @ ${entry:.2f} → ${exit_p:.2f}")
            print(f"      PNL: {pnl_pct:.4f}% | {exit_reason} | {duration:.1f} min")
            print(f"      Zaman: {entry_time}")
    
    print(f"\n❌ NEGATİF İŞLEMLER (-): {len(negative_trades)}")
    if negative_trades:
        # Calculate totals
        total_negative_pnl = sum(p.get('pnl', 0) for p in negative_trades)
        total_negative_pnl_pct = sum(p.get('pnl_pct', 0) for p in negative_trades)
        avg_negative_pnl_pct = total_negative_pnl_pct / len(negative_trades)
        
        print(f"   Toplam PNL: ${total_negative_pnl:.2f}")
        print(f"   Ortalama PNL %: {avg_negative_pnl_pct:.4f}%")
        print(f"   En Kötü İşlem: {min(p.get('pnl_pct', 0) for p in negative_trades):.4f}%")
        
        # TP/SL breakdown
        sl_count = sum(1 for p in negative_trades if p.get('exit_reason') == 'SL')
        print(f"   SL ile Kapanan: {sl_count}")
        
        print(f"\n   📋 Negatif İşlemler (Son 10):")
        for i, p in enumerate(sorted(negative_trades, key=lambda x: x.get('entry_time', ''), reverse=True)[:10], 1):
            side = p.get('side', 'UNKNOWN')
            entry = p.get('entry_price') or p.get('entry', 0)
            exit_p = p.get('exit_price') or p.get('exit', 0)
            pnl_pct = p.get('pnl_pct', 0)
            exit_reason = p.get('exit_reason', 'UNKNOWN')
            duration = p.get('duration_min', 0)
            entry_time = p.get('entry_time', 'N/A')
            
            print(f"   {i}. {side} @ ${entry:.2f} → ${exit_p:.2f}")
            print(f"      PNL: {pnl_pct:.4f}% | {exit_reason} | {duration:.1f} min")
            print(f"      Zaman: {entry_time}")
    
    # Summary
    total_trades = len(valid_positions)
    win_rate = (len(positive_trades) / total_trades * 100) if total_trades > 0 else 0
    total_pnl = sum(p.get('pnl', 0) for p in valid_positions)
    total_pnl_pct = sum(p.get('pnl_pct', 0) for p in valid_positions)
    
    print(f"\n" + "="*80)
    print("📈 ÖZET")
    print("="*80)
    print(f"Toplam İşlem: {total_trades}")
    print(f"Kazanma Oranı: {win_rate:.1f}%")
    print(f"Toplam PNL: ${total_pnl:.2f}")
    print(f"Toplam PNL %: {total_pnl_pct:.4f}%")
    
    # Side breakdown
    long_trades = [p for p in valid_positions if p.get('side') == 'LONG']
    short_trades = [p for p in valid_positions if p.get('side') == 'SHORT']
    
    print(f"\nLONG İşlemler: {len(long_trades)}")
    if long_trades:
        long_positive = [p for p in long_trades if p.get('pnl_pct', 0) > 0 or p.get('pnl', 0) > 0]
        long_negative = [p for p in long_trades if p.get('pnl_pct', 0) < 0 or p.get('pnl', 0) < 0]
        print(f"   ✅ Pozitif: {len(long_positive)} | ❌ Negatif: {len(long_negative)}")
        long_total_pnl = sum(p.get('pnl_pct', 0) for p in long_trades)
        print(f"   Toplam PNL %: {long_total_pnl:.4f}%")
        
        # Son 3 LONG işlem
        print(f"\n   🔍 Son 3 LONG İşlem:")
        for i, p in enumerate(sorted(long_trades, key=lambda x: x.get('entry_time', ''), reverse=True)[:3], 1):
            entry = p.get('entry_price') or p.get('entry', 0)
            exit_p = p.get('exit_price') or p.get('exit', 0)
            pnl_pct = p.get('pnl_pct', 0)
            exit_reason = p.get('exit_reason', 'UNKNOWN')
            entry_time = p.get('entry_time', 'N/A')
            print(f"   {i}. ${entry:.2f} → ${exit_p:.2f} | PNL: {pnl_pct:.4f}% | {exit_reason} | {entry_time}")
    
    print(f"\nSHORT İşlemler: {len(short_trades)}")
    if short_trades:
        short_positive = [p for p in short_trades if p.get('pnl_pct', 0) > 0 or p.get('pnl', 0) > 0]
        short_negative = [p for p in short_trades if p.get('pnl_pct', 0) < 0 or p.get('pnl', 0) < 0]
        print(f"   ✅ Pozitif: {len(short_positive)} | ❌ Negatif: {len(short_negative)}")
        short_total_pnl = sum(p.get('pnl_pct', 0) for p in short_trades)
        print(f"   Toplam PNL %: {short_total_pnl:.4f}%")

def main():
    print("🔍 LLM Projesi - Pozisyonların PNL Analizi")
    print("="*80)
    
    # Load positions from both files
    positions_post_deploy = Path("runs/positions_post_deploy.json")
    closed_positions_remote = Path("runs/closed_positions_remote.json")
    
    all_positions = []
    
    if positions_post_deploy.exists():
        print(f"\n📥 Loading: {positions_post_deploy}")
        positions = load_positions_file(positions_post_deploy)
        print(f"   Found {len(positions)} positions")
        all_positions.extend(positions)
    
    if closed_positions_remote.exists():
        print(f"\n📥 Loading: {closed_positions_remote}")
        positions = load_positions_file(closed_positions_remote)
        print(f"   Found {len(positions)} positions")
        all_positions.extend(positions)
    
    if not all_positions:
        print("❌ Hiç pozisyon bulunamadı!")
        return
    
    print(f"\n📊 Toplam pozisyon: {len(all_positions)}")
    
    # Remove duplicates based on entry_time
    seen = set()
    unique_positions = []
    for p in all_positions:
        entry_time = p.get('entry_time', '')
        if entry_time and entry_time not in seen:
            seen.add(entry_time)
            unique_positions.append(p)
    
    print(f"📊 Benzersiz pozisyon: {len(unique_positions)}")
    
    # Sort by entry time (most recent first)
    unique_positions.sort(key=lambda x: x.get('entry_time', ''), reverse=True)
    
    # Analyze
    analyze_pnl_breakdown(unique_positions)
    
    print("\n" + "="*80)
    print("✅ Analiz tamamlandı!")
    print("="*80)

if __name__ == "__main__":
    main()

