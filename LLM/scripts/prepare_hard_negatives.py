#!/usr/bin/env python3
"""Prepare hard negative examples for model retraining."""
import json
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

def load_closed_positions():
    """Load closed positions from JSON file."""
    positions_file = Path("runs/closed_positions.json")
    if not positions_file.exists():
        return []
    
    with open(positions_file) as f:
        return json.load(f)

def load_skipped_signals():
    """Load skipped signals from JSON file."""
    skipped_file = Path("runs/skipped_signals.json")
    if not skipped_file.exists():
        return []
    
    with open(skipped_file) as f:
        return json.load(f)

def load_skipped_evaluations():
    """Load skipped signal evaluations."""
    eval_file = Path("runs/skipped_signals_evaluated.json")
    if not eval_file.exists():
        return []
    
    with open(eval_file) as f:
        return json.load(f)

def identify_hard_negatives(closed_positions, skipped_evaluations):
    """Identify hard negative examples for training."""
    
    hard_negatives = []
    
    # 1. Stop Loss positions with high confidence
    for pos in closed_positions:
        if pos.get('exit_reason') == 'SL':
            confidence = pos.get('confidence', 0)
            
            # High confidence SL = hard negative (model was wrong)
            if confidence > 0.75:  # 75% confidence but hit SL
                hard_negatives.append({
                    'type': 'HIGH_CONF_SL',
                    'position': pos,
                    'reason': f'High confidence ({confidence*100:.1f}%) but hit SL',
                    'weight': 2.0  # Higher weight for training
                })
    
    # 2. Skipped signals that would have hit SL
    for signal in skipped_evaluations:
        eval_result = signal.get('evaluation', {})
        if eval_result.get('result') == 'SL':
            # Model generated a signal that would have hit SL
            hard_negatives.append({
                'type': 'SKIPPED_SL',
                'signal': signal,
                'reason': 'Skipped signal would have hit SL',
                'weight': 1.5
            })
    
    # 3. Consecutive negative positions
    # Find sequences of 3+ consecutive SL positions
    sl_positions = [p for p in closed_positions if p.get('exit_reason') == 'SL']
    sl_positions.sort(key=lambda x: x.get('entry_time', x['timestamp']))
    
    consecutive_sequences = []
    current_sequence = []
    
    for i, pos in enumerate(sl_positions):
        if i == 0 or (i > 0 and 
                     datetime.fromisoformat(pos.get('entry_time', pos['timestamp'])) < 
                     datetime.fromisoformat(sl_positions[i-1].get('exit_time', sl_positions[i-1]['timestamp'])) + 
                     pd.Timedelta(hours=24)):
            current_sequence.append(pos)
        else:
            if len(current_sequence) >= 3:
                consecutive_sequences.append(current_sequence)
            current_sequence = [pos]
    
    if len(current_sequence) >= 3:
        consecutive_sequences.append(current_sequence)
    
    for seq in consecutive_sequences:
        hard_negatives.append({
            'type': 'CONSECUTIVE_SL',
            'sequence': seq,
            'reason': f'Consecutive {len(seq)} SL positions',
            'weight': 3.0  # Highest weight
        })
    
    return hard_negatives

def export_for_training(hard_negatives, output_file="models/hard_negatives.json"):
    """Export hard negatives in format suitable for training."""
    
    training_examples = []
    
    for negative in hard_negatives:
        if negative['type'] == 'HIGH_CONF_SL':
            pos = negative['position']
            training_examples.append({
                'timestamp': pos.get('entry_time', pos['timestamp']),
                'side': pos['side'],
                'entry': pos['entry'],
                'confidence': pos.get('confidence', 0),
                'probs': pos.get('probs', {}),
                'features': pos.get('features', {}),
                'label': 'SL',  # Hit stop loss
                'weight': negative['weight'],
                'reason': negative['reason']
            })
        
        elif negative['type'] == 'SKIPPED_SL':
            signal = negative['signal']
            training_examples.append({
                'timestamp': signal['timestamp'],
                'side': signal['side'],
                'entry': signal['entry'],
                'confidence': signal.get('confidence', 0),
                'probs': signal.get('probs', {}),
                'features': signal.get('features', {}),
                'label': 'SL',  # Would have hit SL
                'weight': negative['weight'],
                'reason': negative['reason']
            })
        
        elif negative['type'] == 'CONSECUTIVE_SL':
            # Add all positions in sequence
            for pos in negative['sequence']:
                training_examples.append({
                    'timestamp': pos.get('entry_time', pos['timestamp']),
                    'side': pos['side'],
                    'entry': pos['entry'],
                    'confidence': pos.get('confidence', 0),
                    'probs': pos.get('probs', {}),
                    'features': pos.get('features', {}),
                    'label': 'SL',
                    'weight': negative['weight'],
                    'reason': negative['reason']
                })
    
    # Save
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump({
            'hard_negatives': training_examples,
            'total_examples': len(training_examples),
            'generated_at': datetime.now().isoformat()
        }, f, indent=2)
    
    return training_examples

def main():
    print('=== HARD NEGATIVE EXAMPLES HAZIRLAMA ===\n')
    
    # Load data
    closed_positions = load_closed_positions()
    skipped_evaluations = load_skipped_evaluations()
    
    print(f'📊 Kapanan Pozisyon: {len(closed_positions)}')
    print(f'📊 Değerlendirilen Skip Sinyal: {len(skipped_evaluations)}\n')
    
    # Identify hard negatives
    hard_negatives = identify_hard_negatives(closed_positions, skipped_evaluations)
    
    print(f'🔴 Hard Negative Bulundu: {len(hard_negatives)}\n')
    
    # Categorize
    high_conf_sl = sum(1 for n in hard_negatives if n['type'] == 'HIGH_CONF_SL')
    skipped_sl = sum(1 for n in hard_negatives if n['type'] == 'SKIPPED_SL')
    consecutive_sl = sum(1 for n in hard_negatives if n['type'] == 'CONSECUTIVE_SL')
    
    print('=== KATEGORİLER ===\n')
    print(f'📊 Yüksek Confidence SL: {high_conf_sl}')
    print(f'📊 Skip Edilen SL Sinyal: {skipped_sl}')
    print(f'📊 Arka Arkaya SL: {consecutive_sl}\n')
    
    # Export for training
    training_examples = export_for_training(hard_negatives)
    
    print(f'✅ Training Örneği: {len(training_examples)}')
    print(f'💾 Dosya: models/hard_negatives.json\n')
    
    # Statistics
    if training_examples:
        avg_weight = sum(e['weight'] for e in training_examples) / len(training_examples)
        avg_confidence = sum(e['confidence'] for e in training_examples) / len(training_examples)
        
        print('=== İSTATİSTİKLER ===\n')
        print(f'Ortalama Weight: {avg_weight:.2f}')
        print(f'Ortalama Confidence: {avg_confidence*100:.1f}%\n')
        
        print('💡 Model retraining sırasında bu örneklere daha fazla ağırlık verilecek')

if __name__ == "__main__":
    main()

