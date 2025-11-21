#!/usr/bin/env python3
"""Pattern matching algorithm for detecting recurring negative patterns."""
import json
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

def load_data():
    """Load all relevant data files."""
    data = {
        'closed_positions': [],
        'skipped_signals': [],
        'skipped_evaluations': []
    }
    
    # Load closed positions
    positions_file = Path("runs/closed_positions.json")
    if positions_file.exists():
        with open(positions_file) as f:
            data['closed_positions'] = json.load(f)
    
    # Load skipped signals
    skipped_file = Path("runs/skipped_signals.json")
    if skipped_file.exists():
        with open(skipped_file) as f:
            data['skipped_signals'] = json.load(f)
    
    # Load evaluations
    eval_file = Path("runs/skipped_signals_evaluated.json")
    if eval_file.exists():
        with open(eval_file) as f:
            data['skipped_evaluations'] = json.load(f)
    
    return data

def extract_features(position):
    """Extract features from a position for pattern matching."""
    features = {}
    
    # Time features
    entry_time = datetime.fromisoformat(position.get('entry_time', position['timestamp']))
    features['hour'] = entry_time.hour
    features['day_of_week'] = entry_time.weekday()
    features['is_weekend'] = entry_time.weekday() >= 5
    
    # Price features
    features['entry'] = position.get('entry', 0)
    features['tp'] = position.get('tp', 0)
    features['sl'] = position.get('sl', 0)
    features['tp_distance_pct'] = ((position.get('tp', 0) - position.get('entry', 0)) / position.get('entry', 1)) * 100
    features['sl_distance_pct'] = ((position.get('entry', 0) - position.get('sl', 0)) / position.get('entry', 1)) * 100
    
    # Model features
    features['confidence'] = position.get('confidence', 0)
    probs = position.get('probs', {})
    features['prob_long'] = probs.get('long', 0)
    features['prob_short'] = probs.get('short', 0)
    features['prob_flat'] = probs.get('flat', 0)
    
    # Market features
    market_features = position.get('features', {})
    features['ema50'] = market_features.get('ema50', 0)
    features['ema200'] = market_features.get('ema200', 0)
    features['vol_spike'] = market_features.get('vol_spike', 0)
    features['rsi'] = market_features.get('rsi', 0)
    
    # Result
    features['exit_reason'] = position.get('exit_reason', 'UNKNOWN')
    features['pnl'] = position.get('pnl', 0)
    
    return features

def calculate_similarity(features1, features2, weights=None):
    """Calculate similarity between two feature sets."""
    if weights is None:
        weights = {
            'hour': 0.1,
            'confidence': 0.3,
            'prob_long': 0.2,
            'prob_short': 0.2,
            'vol_spike': 0.1,
            'rsi': 0.1
        }
    
    similarity = 0.0
    total_weight = 0.0
    
    for key, weight in weights.items():
        if key in features1 and key in features2:
            val1 = features1[key]
            val2 = features2[key]
            
            # Normalize different types
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if key == 'hour':
                    # Circular distance for hours
                    diff = abs(val1 - val2)
                    if diff > 12:
                        diff = 24 - diff
                    similarity += weight * (1 - diff / 12)
                elif key in ['confidence', 'prob_long', 'prob_short', 'prob_flat']:
                    # Probability similarity
                    similarity += weight * (1 - abs(val1 - val2))
                else:
                    # Normalize by max value
                    max_val = max(abs(val1), abs(val2), 1)
                    similarity += weight * (1 - abs(val1 - val2) / max_val)
                total_weight += weight
    
    return similarity / total_weight if total_weight > 0 else 0.0

def find_patterns(positions, min_pattern_size=3, similarity_threshold=0.7):
    """Find recurring patterns in negative positions."""
    
    # Filter SL positions
    sl_positions = [p for p in positions if p.get('exit_reason') == 'SL']
    
    if len(sl_positions) < min_pattern_size:
        return []
    
    # Extract features
    features_list = [extract_features(p) for p in sl_positions]
    
    # Find similar groups
    patterns = []
    used_indices = set()
    
    for i, features1 in enumerate(features_list):
        if i in used_indices:
            continue
        
        # Find similar positions
        similar_group = [i]
        
        for j, features2 in enumerate(features_list):
            if i == j or j in used_indices:
                continue
            
            similarity = calculate_similarity(features1, features2)
            if similarity >= similarity_threshold:
                similar_group.append(j)
        
        # If group is large enough, it's a pattern
        if len(similar_group) >= min_pattern_size:
            patterns.append({
                'indices': similar_group,
                'positions': [sl_positions[idx] for idx in similar_group],
                'features': features1,
                'count': len(similar_group)
            })
            
            # Mark as used
            for idx in similar_group:
                used_indices.add(idx)
    
    return patterns

def analyze_patterns(patterns):
    """Analyze found patterns and provide insights."""
    
    print('=== PATTERN ANALİZİ ===\n')
    
    for i, pattern in enumerate(patterns, 1):
        print(f'📊 Pattern {i}: {pattern["count"]} benzer pozisyon\n')
        
        features = pattern['features']
        
        print(f'⏰ Zaman Pattern:')
        print(f'   Saat: {features["hour"]}:00')
        print(f'   Haftanın Günü: {features["day_of_week"]}')
        print(f'   Hafta Sonu: {features["is_weekend"]}\n')
        
        print(f'📊 Model Özellikleri:')
        print(f'   Confidence: {features["confidence"]*100:.1f}%')
        print(f'   Prob Long: {features["prob_long"]*100:.1f}%')
        print(f'   Prob Short: {features["prob_short"]*100:.1f}%')
        print(f'   Prob Flat: {features["prob_flat"]*100:.1f}%\n')
        
        print(f'📈 Market Özellikleri:')
        print(f'   EMA50: {features["ema50"]:.2f}')
        print(f'   EMA200: {features["ema200"]:.2f}')
        print(f'   Volume Spike: {features["vol_spike"]:.2f}')
        print(f'   RSI: {features["rsi"]:.2f}\n')
        
        print(f'💰 Risk Parametreleri:')
        print(f'   TP Distance: {features["tp_distance_pct"]:.2f}%')
        print(f'   SL Distance: {features["sl_distance_pct"]:.2f}%\n')
        
        # Recommendations
        print(f'💡 Öneriler:')
        if features['confidence'] > 0.75:
            print(f'   ⚠️ Yüksek confidence ama SL - Model threshold\'u yükselt')
        if features['vol_spike'] < 0.8:
            print(f'   ⚠️ Düşük volume spike - Regime filter\'ı güçlendir')
        if features['hour'] in [0, 1, 2, 3, 4, 5]:
            print(f'   ⚠️ Gece saatleri - Bu saatlerde trading\'i durdur')
        
        print()

def main():
    print('=== PATTERN MATCHING ALGORİTMASI ===\n')
    
    # Load data
    data = load_data()
    
    print(f'📊 Kapanan Pozisyon: {len(data["closed_positions"])}')
    print(f'📊 Skip Edilen Sinyal: {len(data["skipped_signals"])}\n')
    
    # Find patterns in SL positions
    patterns = find_patterns(data['closed_positions'], min_pattern_size=3, similarity_threshold=0.7)
    
    print(f'🔍 Bulunan Pattern: {len(patterns)}\n')
    
    if patterns:
        # Analyze patterns
        analyze_patterns(patterns)
        
        # Save patterns
        patterns_file = Path("runs/detected_patterns.json")
        with open(patterns_file, 'w') as f:
            json.dump({
                'patterns': patterns,
                'total_patterns': len(patterns),
                'generated_at': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f'💾 Patternler kaydedildi: {patterns_file}')
    else:
        print('⚪ Pattern bulunamadı')

if __name__ == "__main__":
    main()

