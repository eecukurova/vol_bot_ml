#!/usr/bin/env python3
"""Comprehensive analysis - run all analysis scripts and show results."""
import json
import ccxt
from datetime import datetime
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

def comprehensive_analysis():
    """Run comprehensive analysis and show all results."""
    
    print('='*70)
    print('📊 KAPSAMLI ANALİZ - TÜM SONUÇLAR')
    print('='*70)
    print()
    
    # 1. Win Rate Analysis
    print('='*70)
    print('1️⃣ WIN RATE ANALİZİ')
    print('='*70)
    print()
    
    positions_file = Path("runs/closed_positions.json")
    if positions_file.exists():
        with open(positions_file) as f:
            positions = json.load(f)
        
        total = len(positions)
        sl_count = sum(1 for p in positions if p.get('exit_reason') == 'SL')
        tp_count = sum(1 for p in positions if p.get('exit_reason') == 'TP')
        
        if total > 0:
            win_rate = tp_count / total * 100
            total_pnl = sum(p.get('pnl', 0) for p in positions)
            avg_pnl = total_pnl / total
            
            print(f'📊 Toplam Pozisyon: {total}')
            print(f'✅ Take Profit: {tp_count} ({tp_count/total*100:.1f}%)')
            print(f'❌ Stop Loss: {sl_count} ({sl_count/total*100:.1f}%)')
            print(f'📈 Win Rate: {win_rate:.1f}%')
            print(f'💰 Toplam PnL: ${total_pnl:.2f}')
            print(f'📊 Ortalama PnL: ${avg_pnl:.2f}')
            
            # SL vs TP PnL
            sl_pnl = sum(p.get('pnl', 0) for p in positions if p.get('exit_reason') == 'SL')
            tp_pnl = sum(p.get('pnl', 0) for p in positions if p.get('exit_reason') == 'TP')
            
            print(f'')
            print(f'💰 PnL Dağılımı:')
            print(f'   TP PnL: ${tp_pnl:.2f}')
            print(f'   SL PnL: ${sl_pnl:.2f}')
            print(f'   Net: ${total_pnl:.2f}')
        else:
            print('⚪ Pozisyon yok')
    else:
        print('⚪ closed_positions.json bulunamadı')
        print('💡 İpucu: python3 scripts/import_historical_data.py çalıştırın')
    
    print()
    
    # 2. Pattern Analysis
    print('='*70)
    print('2️⃣ PATTERN ANALİZİ')
    print('='*70)
    print()
    
    pattern_file = Path("runs/detected_patterns.json")
    if pattern_file.exists():
        with open(pattern_file) as f:
            pattern_data = json.load(f)
        
        patterns = pattern_data.get('patterns', [])
        print(f'🔍 Bulunan Pattern: {len(patterns)}')
        
        if patterns:
            for i, pattern in enumerate(patterns, 1):
                print(f'')
                print(f'Pattern {i}:')
                print(f'   Benzer Pozisyon Sayısı: {pattern.get("count", 0)}')
                
                features = pattern.get('features', {})
                if features.get('hour') is not None:
                    print(f'   ⏰ En Çok Pozisyon Açılan Saat: {features.get("hour")}:00')
                if features.get('confidence'):
                    print(f'   📊 Ortalama Confidence: {features.get("confidence")*100:.1f}%')
                if features.get('vol_spike'):
                    print(f'   📈 Volume Spike: {features.get("vol_spike"):.2f}')
        else:
            print('⚪ Pattern bulunamadı')
    else:
        print('⚪ detected_patterns.json bulunamadı')
        print('💡 İpucu: python3 scripts/pattern_matcher.py çalıştırın')
    
    print()
    
    # 3. Hard Negatives Analysis
    print('='*70)
    print('3️⃣ HARD NEGATIVES ANALİZİ')
    print('='*70)
    print()
    
    hn_file = Path("models/hard_negatives.json")
    if hn_file.exists():
        with open(hn_file) as f:
            hn_data = json.load(f)
        
        examples = hn_data.get('hard_negatives', [])
        print(f'🔴 Toplam Hard Negative: {len(examples)}')
        
        if examples:
            # Categorize
            categories = defaultdict(int)
            for ex in examples:
                reason = ex.get('reason', 'UNKNOWN')
                if 'Consecutive' in reason:
                    categories['Arka Arkaya SL'] += 1
                elif 'High confidence' in reason:
                    categories['Yüksek Confidence SL'] += 1
                elif 'Skipped' in reason:
                    categories['Skip Edilen SL'] += 1
                else:
                    categories['Diğer'] += 1
            
            print(f'')
            print(f'📊 Kategoriler:')
            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                print(f'   • {cat}: {count}')
            
            avg_weight = sum(e.get('weight', 0) for e in examples) / len(examples)
            avg_confidence = sum(e.get('confidence', 0) for e in examples) / len(examples)
            
            print(f'')
            print(f'📈 İstatistikler:')
            print(f'   Ortalama Weight: {avg_weight:.2f}')
            print(f'   Ortalama Confidence: {avg_confidence*100:.1f}%')
            
            print(f'')
            print(f'💡 Bu örneklere model eğitiminde daha fazla ağırlık verilecek')
        else:
            print('⚪ Hard negative örneği yok')
    else:
        print('⚪ hard_negatives.json bulunamadı')
        print('💡 İpucu: python3 scripts/prepare_hard_negatives.py çalıştırın')
    
    print()
    
    # 4. Confidence Analysis (SL vs TP)
    print('='*70)
    print('4️⃣ CONFIDENCE ANALİZİ (SL vs TP)')
    print('='*70)
    print()
    
    if positions_file.exists():
        with open(positions_file) as f:
            positions = json.load(f)
        
        sl_positions = [p for p in positions if p.get('exit_reason') == 'SL']
        tp_positions = [p for p in positions if p.get('exit_reason') == 'TP']
        
        if sl_positions:
            sl_confidences = [p.get('confidence', 0) for p in sl_positions if p.get('confidence', 0) > 0]
            if sl_confidences:
                avg_sl_conf = sum(sl_confidences) / len(sl_confidences)
                min_sl_conf = min(sl_confidences)
                max_sl_conf = max(sl_confidences)
                
                print(f'❌ Stop Loss Pozisyonları:')
                print(f'   Ortalama Confidence: {avg_sl_conf*100:.1f}%')
                print(f'   Min: {min_sl_conf*100:.1f}%')
                print(f'   Max: {max_sl_conf*100:.1f}%')
                print(f'   Sayı: {len(sl_confidences)}')
        
        if tp_positions:
            tp_confidences = [p.get('confidence', 0) for p in tp_positions if p.get('confidence', 0) > 0]
            if tp_confidences:
                avg_tp_conf = sum(tp_confidences) / len(tp_confidences)
                min_tp_conf = min(tp_confidences)
                max_tp_conf = max(tp_confidences)
                
                print(f'')
                print(f'✅ Take Profit Pozisyonları:')
                print(f'   Ortalama Confidence: {avg_tp_conf*100:.1f}%')
                print(f'   Min: {min_tp_conf*100:.1f}%')
                print(f'   Max: {max_tp_conf*100:.1f}%')
                print(f'   Sayı: {len(tp_confidences)}')
        
        if sl_confidences and tp_confidences:
            print(f'')
            print(f'📊 Karşılaştırma:')
            diff = avg_sl_conf - avg_tp_conf
            if diff > 0:
                print(f'   ⚠️ SL pozisyonları {diff*100:.1f}% daha yüksek confidence\'lı')
                print(f'   💡 Öneri: Confidence threshold\'u yükselt')
            else:
                print(f'   ✅ TP pozisyonları {abs(diff)*100:.1f}% daha yüksek confidence\'lı')
                print(f'   💡 Model doğru çalışıyor')
    
    print()
    
    # 5. Recommendations
    print('='*70)
    print('5️⃣ ÖNERİLER VE SONUÇLAR')
    print('='*70)
    print()
    
    if positions_file.exists():
        with open(positions_file) as f:
            positions = json.load(f)
        
        if len(positions) > 0:
            sl_count = sum(1 for p in positions if p.get('exit_reason') == 'SL')
            tp_count = sum(1 for p in positions if p.get('exit_reason') == 'TP')
            win_rate = tp_count / len(positions) * 100
            
            print(f'📊 Genel Durum:')
            print(f'   Win Rate: {win_rate:.1f}%')
            print(f'   Toplam Pozisyon: {len(positions)}')
            print(f'')
            
            if win_rate < 50:
                print(f'⚠️ Win Rate düşük ({win_rate:.1f}%)')
                print(f'💡 Öneriler:')
                print(f'   1. Confidence threshold\'u yükselt')
                print(f'   2. Regime filter\'ı güçlendir')
                print(f'   3. Hard negatives\'i model eğitiminde kullan')
            elif win_rate >= 50 and win_rate < 70:
                print(f'✅ Win Rate orta ({win_rate:.1f}%)')
                print(f'💡 Öneriler:')
                print(f'   1. Pattern\'leri analiz et ve önlem al')
                print(f'   2. Hard negatives\'i model eğitiminde kullan')
            else:
                print(f'🎉 Win Rate yüksek ({win_rate:.1f}%)')
                print(f'💡 Model iyi çalışıyor, pattern\'leri izlemeye devam et')
    
    print()
    print('='*70)
    print('✅ ANALİZ TAMAMLANDI')
    print('='*70)

if __name__ == "__main__":
    comprehensive_analysis()

