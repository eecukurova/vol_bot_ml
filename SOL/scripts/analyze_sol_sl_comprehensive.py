#!/usr/bin/env python3
"""
SOL Live Projesi - Stop Loss İşlemleri Kapsamlı Analiz
Log dosyası ve position manager state'inden SL/TP işlemlerini analiz eder
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

def load_position_manager_state():
    """Load position manager state (trade history)."""
    state_file = Path("runs/position_manager_state.json")
    
    if not state_file.exists():
        return []
    
    try:
        with open(state_file, 'r') as f:
            data = json.load(f)
            return data.get('trade_history', [])
    except:
        return []

def parse_log_for_signals(log_file, days=30):
    """Parse log file to extract signal and position information."""
    if not log_file.exists():
        return []
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    signals = []
    positions = []
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        # Entry signals
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
                # Get confidence and probs from nearby lines
                confidence = None
                probs = {}
                rsi = None
                vol_spike = None
                
                for j in range(max(0, i-10), min(i+10, len(lines))):
                    conf_match = re.search(r'Confidence: ([\d.]+)%', lines[j])
                    if conf_match:
                        confidence = float(conf_match.group(1))
                    
                    prob_match = re.search(r'Probs: Flat=([\d.]+)%, Long=([\d.]+)%, Short=([\d.]+)%', lines[j])
                    if prob_match:
                        probs = {
                            'flat': float(prob_match.group(1)),
                            'long': float(prob_match.group(2)),
                            'short': float(prob_match.group(3))
                        }
                    
                    rsi_match = re.search(r'RSI: ([\d.]+)', lines[j])
                    if rsi_match:
                        rsi = float(rsi_match.group(1))
                    
                    vol_match = re.search(r'Volume Spike: ([\d.]+)', lines[j])
                    if vol_match:
                        vol_spike = float(vol_match.group(1))
                
                signal = {
                    'side': side,
                    'entry_price': entry_price,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'entry_time': entry_time,
                    'confidence': confidence,
                    'probs': probs,
                    'rsi': rsi,
                    'vol_spike': vol_spike,
                    'exit_reason': None,
                    'exit_price': None,
                    'exit_time': None,
                    'pnl_pct': None
                }
                signals.append(signal)
        
        # Exit signals (from trend following exit or TP/SL)
        exit_match = re.search(r'Position closed|Pozisyon kapatıldı|SL|TP|Trend Following Exit', line, re.IGNORECASE)
        if exit_match and signals:
            # Try to match with most recent signal
            for signal in reversed(signals):
                if signal.get('exit_reason') is None:
                    # Extract exit price
                    exit_price_match = re.search(r'@ \$([\d.]+)', line)
                    if exit_price_match:
                        exit_price = float(exit_price_match.group(1))
                    else:
                        continue
                    
                    # Determine exit reason
                    if 'SL' in line.upper() or 'stop' in line.lower():
                        exit_reason = 'SL'
                    elif 'TP' in line.upper() or 'take profit' in line.lower():
                        exit_reason = 'TP'
                    elif 'TREND_REVERSAL' in line.upper():
                        exit_reason = 'TREND_REVERSAL'
                    elif 'VOLUME_EXIT' in line.upper():
                        exit_reason = 'VOLUME_EXIT'
                    elif 'PARTIAL_EXIT' in line.upper():
                        exit_reason = 'PARTIAL_EXIT'
                    else:
                        exit_reason = 'UNKNOWN'
                    
                    # Extract exit timestamp
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if timestamp_match:
                        try:
                            exit_time = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                        except:
                            exit_time = datetime.now()
                    else:
                        exit_time = datetime.now()
                    
                    # Calculate PnL
                    if signal['side'] == 'LONG':
                        pnl_pct = (exit_price - signal['entry_price']) / signal['entry_price']
                    else:
                        pnl_pct = (signal['entry_price'] - exit_price) / signal['entry_price']
                    
                    signal['exit_reason'] = exit_reason
                    signal['exit_price'] = exit_price
                    signal['exit_time'] = exit_time
                    signal['pnl_pct'] = pnl_pct
                    break
    
    return signals

def analyze_positions(positions_from_manager, signals_from_log):
    """Analyze positions and generate comprehensive report."""
    # Combine data sources
    all_positions = []
    
    # Add positions from position manager
    for pos in positions_from_manager:
        all_positions.append({
            'side': pos.get('side', 'UNKNOWN'),
            'entry_price': pos.get('entry_price', 0),
            'exit_price': pos.get('exit_price', 0),
            'pnl_pct': pos.get('pnl_pct', 0),
            'exit_reason': pos.get('reason', 'UNKNOWN'),
            'entry_time': datetime.fromisoformat(pos.get('entry_time', datetime.now().isoformat())) if isinstance(pos.get('entry_time'), str) else datetime.now(),
            'exit_time': datetime.fromisoformat(pos.get('exit_time', datetime.now().isoformat())) if isinstance(pos.get('exit_time'), str) else datetime.now(),
            'break_even_moved': pos.get('break_even_moved', False),
            'trailing_active': pos.get('trailing_active', False),
            'highest_profit': pos.get('highest_profit', 0)
        })
    
    # Add signals from log (with exit info)
    for sig in signals_from_log:
        if sig.get('exit_reason'):
            all_positions.append({
                'side': sig['side'],
                'entry_price': sig['entry_price'],
                'exit_price': sig['exit_price'],
                'pnl_pct': sig['pnl_pct'],
                'exit_reason': sig['exit_reason'],
                'entry_time': sig['entry_time'],
                'exit_time': sig['exit_time'],
                'confidence': sig.get('confidence'),
                'probs': sig.get('probs', {}),
                'rsi': sig.get('rsi'),
                'vol_spike': sig.get('vol_spike')
            })
    
    if not all_positions:
        print("⚠️ Analiz edilecek pozisyon bulunamadı!")
        return
    
    # Filter by date (last 30 days)
    cutoff_date = datetime.now() - timedelta(days=30)
    recent_positions = [p for p in all_positions if p['entry_time'] >= cutoff_date]
    
    if not recent_positions:
        print("⚠️ Son 30 günde pozisyon bulunamadı!")
        return
    
    print("=" * 100)
    print("SOL LIVE PROJESİ - STOP LOSS VE TAKE PROFIT DETAYLI ANALİZ")
    print("=" * 100)
    print()
    
    # Categorize
    sl_positions = [p for p in recent_positions if p.get('exit_reason') in ['SL', 'stop', 'STOP']]
    tp_positions = [p for p in recent_positions if p.get('exit_reason') in ['TP', 'take profit', 'TAKE_PROFIT']]
    other_exits = [p for p in recent_positions if p.get('exit_reason') not in ['SL', 'TP', 'stop', 'STOP', 'take profit', 'TAKE_PROFIT']]
    
    total = len(recent_positions)
    
    print("=" * 100)
    print("📊 GENEL İSTATİSTİKLER")
    print("=" * 100)
    print()
    
    print(f"📈 Toplam Pozisyon: {total}")
    print(f"   ✅ Take Profit: {len(tp_positions)} ({len(tp_positions)/total*100:.1f}%)" if total > 0 else "   ✅ Take Profit: 0")
    print(f"   ❌ Stop Loss: {len(sl_positions)} ({len(sl_positions)/total*100:.1f}%)" if total > 0 else "   ❌ Stop Loss: 0")
    print(f"   🔄 Diğer: {len(other_exits)} ({len(other_exits)/total*100:.1f}%)" if total > 0 else "   🔄 Diğer: 0")
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
    
    # Detailed SL analysis
    if sl_positions:
        print("=" * 100)
        print("❌ STOP LOSS İŞLEMLERİ DETAYLI ANALİZ")
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
            
            # Additional info if available
            if pos.get('confidence'):
                print(f"   Confidence: {pos['confidence']:.1f}%")
            if pos.get('probs'):
                probs = pos['probs']
                print(f"   Probs: Flat={probs.get('flat', 0):.1f}%, Long={probs.get('long', 0):.1f}%, Short={probs.get('short', 0):.1f}%")
            if pos.get('rsi'):
                print(f"   RSI: {pos['rsi']:.1f}")
            if pos.get('vol_spike'):
                print(f"   Volume Spike: {pos['vol_spike']:.2f}")
            if pos.get('break_even_moved'):
                print(f"   Break Even Moved: ✅")
            if pos.get('trailing_active'):
                print(f"   Trailing Active: ✅")
            if pos.get('highest_profit'):
                print(f"   Highest Profit: {pos['highest_profit']*100:.2f}%")
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
                'Probability ratio filtresini sıkılaştır (şu an: 3.0 → 5.0 önerilir)',
                'Volume spike threshold\'u kontrol et',
                'RSI filtrelerini sıkılaştır',
                'Trend following exit ayarlarını gözden geçir'
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
                    'SL seviyesini biraz genişlet (şu an: 1.0% → 1.2% önerilir)',
                    'Entry timing\'i iyileştir',
                    'Minimum bar kontrolü ekle',
                    'Trend following exit\'i optimize et'
                ]
            })
    
    # Confidence analysis
    if sl_positions:
        sl_confidences = [p.get('confidence') for p in sl_positions if p.get('confidence')]
        if sl_confidences:
            avg_sl_conf = sum(sl_confidences) / len(sl_confidences)
            if avg_sl_conf < 90:
                recommendations.append({
                    'priority': 'ORTA',
                    'title': 'SL pozisyonlarında düşük confidence',
                    'actions': [
                        f'Ortalama SL confidence: {avg_sl_conf:.1f}% (düşük)',
                        'Confidence threshold\'u yükselt',
                        'Düşük confidence sinyallerini filtrele'
                    ]
                })
    
    # Volume spike analysis
    if sl_positions:
        sl_vol_spikes = [p.get('vol_spike') for p in sl_positions if p.get('vol_spike')]
        if sl_vol_spikes:
            avg_sl_vol = sum(sl_vol_spikes) / len(sl_vol_spikes)
            if avg_sl_vol < 0.5:
                recommendations.append({
                    'priority': 'ORTA',
                    'title': 'SL pozisyonlarında düşük volume spike',
                    'actions': [
                        f'Ortalama SL volume spike: {avg_sl_vol:.2f} (düşük)',
                        'Volume spike threshold\'u yükselt',
                        'Düşük volume\'de işlem yapmayı engelle'
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
                'Trend following exit ayarlarını optimize et'
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
    print(f"Probability Ratio: {trading_params.get('min_prob_ratio', 0)}")
    print()
    
    trend_following = cfg.get('trend_following_exit', {})
    print(f"Trend Following Exit: {'Aktif' if trend_following.get('enabled', False) else 'Pasif'}")
    if trend_following.get('enabled'):
        print(f"   Trailing Activation: {trend_following.get('trailing_activation_pct', 0)*100:.1f}%")
        print(f"   Trailing Distance: {trend_following.get('trailing_distance_pct', 0)*100:.1f}%")
    print()
    
    print("=" * 100)

def main():
    # Load data
    print("📊 Veriler yükleniyor...")
    positions_from_manager = load_position_manager_state()
    print(f"   Position Manager: {len(positions_from_manager)} işlem")
    
    log_file = Path("runs/sol_live.log")
    signals_from_log = parse_log_for_signals(log_file, days=30)
    print(f"   Log Dosyası: {len(signals_from_log)} sinyal")
    print()
    
    # Analyze
    analyze_positions(positions_from_manager, signals_from_log)

if __name__ == "__main__":
    main()

