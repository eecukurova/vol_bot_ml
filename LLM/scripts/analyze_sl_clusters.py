#!/usr/bin/env python3
"""
SL Cluster Analizi ve Model Eğitimi için Veri Hazırlama
Entry features'larından SL/TP kümelerini oluşturur ve model eğitimi için formatlar
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.entry_features_logger import get_sl_cluster_data, prepare_training_data_from_clusters
from src.utils import load_feat_cols

def main():
    print("=" * 100)
    print("LLM PROJESİ - SL CLUSTER ANALİZİ VE MODEL EĞİTİMİ VERİ HAZIRLAMA")
    print("=" * 100)
    print()
    
    # Load feature columns
    feat_cols_path = Path("models/feat_cols.json")
    if not feat_cols_path.exists():
        print("❌ Feature columns file not found!")
        return
    
    feat_cols = load_feat_cols(feat_cols_path)
    print(f"📊 Feature columns loaded: {len(feat_cols)} features")
    print()
    
    # Load training config for window size
    with open("configs/train_3m.json", "r") as f:
        train_cfg = json.load(f)
    window_size = train_cfg.get("window", 64)
    print(f"📊 Window size: {window_size}")
    print()
    
    # Get SL cluster data
    print("🔍 SL cluster verileri analiz ediliyor...")
    cluster_data = get_sl_cluster_data(min_entries=5, days_back=30)
    
    print("=" * 100)
    print("📊 CLUSTER İSTATİSTİKLERİ")
    print("=" * 100)
    print()
    
    print(f"Toplam SL Entry: {cluster_data['total_sl']}")
    print(f"   LONG SL: {cluster_data['sl_long_count']}")
    print(f"   SHORT SL: {cluster_data['sl_short_count']}")
    print()
    
    print(f"Toplam TP Entry: {cluster_data['total_tp']}")
    print()
    
    if cluster_data['total_sl'] == 0:
        print("⚠️ Henüz SL entry bulunamadı. Daha fazla veri toplanması gerekiyor.")
        return
    
    # Prepare training data
    print("=" * 100)
    print("🔄 MODEL EĞİTİMİ İÇİN VERİ HAZIRLANIYOR")
    print("=" * 100)
    print()
    
    training_data = prepare_training_data_from_clusters(
        sl_cluster_data=cluster_data,
        feature_cols=feat_cols,
        window_size=window_size
    )
    
    print(f"✅ Training data hazırlandı:")
    print(f"   SL Samples: {training_data['n_sl']}")
    print(f"   TP Samples: {training_data['n_tp']}")
    print()
    
    if training_data['n_sl'] == 0:
        print("⚠️ SL training data bulunamadı. Window size veya feature columns uyumsuz olabilir.")
        return
    
    # Save training data
    output_file = Path("runs/sl_training_data.json")
    output_data = {
        'timestamp': datetime.now().isoformat(),
        'window_size': window_size,
        'n_features': len(feat_cols),
        'feature_cols': feat_cols,
        'n_sl': training_data['n_sl'],
        'n_tp': training_data['n_tp'],
        'sl_cluster_stats': {
            'total_sl': cluster_data['total_sl'],
            'sl_long': cluster_data['sl_long_count'],
            'sl_short': cluster_data['sl_short_count']
        }
    }
    
    # Note: X_sl and X_tp are numpy arrays, we'll save them separately as .npy files
    if training_data['n_sl'] > 0:
        np.save("runs/X_sl.npy", training_data['X_sl'])
        np.save("runs/y_sl.npy", training_data['y_sl'])
        output_data['X_sl_shape'] = list(training_data['X_sl'].shape)
        output_data['y_sl_shape'] = list(training_data['y_sl'].shape)
        print(f"💾 SL training data saved: X_sl.npy ({training_data['X_sl'].shape}), y_sl.npy ({training_data['y_sl'].shape})")
    
    if training_data['n_tp'] > 0:
        np.save("runs/X_tp.npy", training_data['X_tp'])
        np.save("runs/y_tp.npy", training_data['y_tp'])
        output_data['X_tp_shape'] = list(training_data['X_tp'].shape)
        output_data['y_tp_shape'] = list(training_data['y_tp'].shape)
        print(f"💾 TP training data saved: X_tp.npy ({training_data['X_tp'].shape}), y_tp.npy ({training_data['y_tp'].shape})")
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print()
    print("=" * 100)
    print("💡 KULLANIM ÖNERİLERİ")
    print("=" * 100)
    print()
    print("1. Bu verileri model eğitiminde hard negatives olarak kullanabilirsiniz")
    print("2. SL entries (X_sl, y_sl) modelin öğrenmesi gereken 'kaçınılması gereken' pattern'lerdir")
    print("3. TP entries (X_tp, y_tp) modelin öğrenmesi gereken 'başarılı' pattern'lerdir")
    print("4. Model eğitimi sırasında bu verileri training set'e ekleyerek model performansını artırabilirsiniz")
    print()
    print("=" * 100)

if __name__ == "__main__":
    main()

