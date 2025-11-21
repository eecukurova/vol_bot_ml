"""
Entry Features Logger - Entry anındaki tüm feature'ları kaydetmek için
SL/TP pattern'lerini analiz edip model eğitimi için kullanılabilir format oluşturur
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


def save_entry_features(
    side: str,
    entry_price: float,
    tp_price: float,
    sl_price: float,
    confidence: float,
    probs: Dict[str, float],
    window_data: np.ndarray,  # (window_size, n_features) - Entry anındaki window
    feature_cols: List[str],
    market_features: Dict[str, float],  # RSI, volume spike, EMA, etc.
    entry_time: str,
    symbol: str = "BTCUSDT"
) -> None:
    """
    Entry anındaki tüm feature'ları kaydet.
    
    Args:
        side: LONG or SHORT
        entry_price: Entry price
        tp_price: Take profit price
        sl_price: Stop loss price
        confidence: Signal confidence
        probs: Probability distribution
        window_data: Window data (window_size, n_features) numpy array
        feature_cols: List of feature column names
        market_features: Additional market features (RSI, volume spike, etc.)
        entry_time: Entry timestamp
        symbol: Trading symbol
    """
    try:
        entries_file = Path("runs/entry_features.json")
        entries_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing entries
        entries = []
        if entries_file.exists():
            try:
                with open(entries_file, 'r') as f:
                    entries = json.load(f)
            except:
                entries = []
        
        # Convert window_data to list (numpy array is not JSON serializable)
        window_data_list = window_data.tolist() if isinstance(window_data, np.ndarray) else window_data
        
        # Create entry record
        entry_record = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'side': side,
            'entry_price': float(entry_price),
            'tp_price': float(tp_price),
            'sl_price': float(sl_price),
            'confidence': float(confidence),
            'probs': {k: float(v) for k, v in probs.items()},
            'entry_time': entry_time,
            'window_data': window_data_list,  # (window_size, n_features)
            'feature_cols': feature_cols,
            'market_features': {k: float(v) for k, v in market_features.items()},
            'exit_reason': None,  # Will be updated when position closes
            'exit_price': None,
            'exit_time': None,
            'pnl': None
        }
        
        entries.append(entry_record)
        
        # Save (keep last 1000 entries)
        if len(entries) > 1000:
            entries = entries[-1000:]
        
        # Atomic write
        temp_file = entries_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(entries, f, indent=2)
        temp_file.replace(entries_file)
        
        logger.info(f"💾 Entry features saved: {side} @ ${entry_price:.2f} (Window: {len(window_data_list)} bars, Features: {len(feature_cols)})")
        
    except Exception as e:
        logger.error(f"❌ Failed to save entry features: {e}")


def update_entry_with_exit(
    entry_time: str,
    exit_reason: str,  # "TP" or "SL"
    exit_price: float,
    exit_time: str,
    pnl: float
) -> None:
    """
    Entry kaydını exit bilgileriyle güncelle.
    
    Args:
        entry_time: Entry timestamp (to match entry record)
        exit_reason: "TP" or "SL"
        exit_price: Exit price
        exit_time: Exit timestamp
        pnl: Realized PnL
    """
    try:
        entries_file = Path("runs/entry_features.json")
        
        if not entries_file.exists():
            return
        
        # Load entries
        with open(entries_file, 'r') as f:
            entries = json.load(f)
        
        # Find matching entry (most recent entry with matching time)
        for entry in reversed(entries):
            if entry.get('entry_time') == entry_time and entry.get('exit_reason') is None:
                entry['exit_reason'] = exit_reason
                entry['exit_price'] = float(exit_price)
                entry['exit_time'] = exit_time
                entry['pnl'] = float(pnl)
                break
        
        # Save
        temp_file = entries_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(entries, f, indent=2)
        temp_file.replace(entries_file)
        
        logger.debug(f"💾 Entry updated with exit: {exit_reason} @ ${exit_price:.2f}")
        
    except Exception as e:
        logger.error(f"❌ Failed to update entry with exit: {e}")


def get_sl_cluster_data(
    min_entries: int = 5,
    days_back: int = 30
) -> Dict[str, Any]:
    """
    Stop Loss olan işlemlerden küme oluştur.
    
    Args:
        min_entries: Minimum entry sayısı (küme için)
        days_back: Kaç gün geriye bakılacak
    
    Returns:
        Dictionary with SL cluster data ready for model training
    """
    try:
        entries_file = Path("runs/entry_features.json")
        
        if not entries_file.exists():
            return {
                'sl_entries': [],
                'tp_entries': [],
                'sl_clusters': {},
                'total_sl': 0,
                'total_tp': 0
            }
        
        # Load entries
        with open(entries_file, 'r') as f:
            entries = json.load(f)
        
        # Filter by date
        cutoff_date = datetime.now().timestamp() - (days_back * 24 * 60 * 60)
        
        # Separate SL and TP entries
        sl_entries = []
        tp_entries = []
        
        for entry in entries:
            if entry.get('exit_reason') == 'SL':
                entry_timestamp = datetime.fromisoformat(entry.get('entry_time', datetime.now().isoformat())).timestamp()
                if entry_timestamp >= cutoff_date:
                    sl_entries.append(entry)
            elif entry.get('exit_reason') == 'TP':
                entry_timestamp = datetime.fromisoformat(entry.get('entry_time', datetime.now().isoformat())).timestamp()
                if entry_timestamp >= cutoff_date:
                    tp_entries.append(entry)
        
        # Create clusters based on side
        sl_clusters = {
            'LONG': [e for e in sl_entries if e.get('side') == 'LONG'],
            'SHORT': [e for e in sl_entries if e.get('side') == 'SHORT']
        }
        
        return {
            'sl_entries': sl_entries,
            'tp_entries': tp_entries,
            'sl_clusters': sl_clusters,
            'total_sl': len(sl_entries),
            'total_tp': len(tp_entries),
            'sl_long_count': len(sl_clusters['LONG']),
            'sl_short_count': len(sl_clusters['SHORT'])
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get SL cluster data: {e}")
        return {
            'sl_entries': [],
            'tp_entries': [],
            'sl_clusters': {},
            'total_sl': 0,
            'total_tp': 0
        }


def prepare_training_data_from_clusters(
    sl_cluster_data: Dict[str, Any],
    feature_cols: List[str],
    window_size: int
) -> Dict[str, np.ndarray]:
    """
    SL cluster'larından model eğitimi için kullanılabilir format oluştur.
    
    Args:
        sl_cluster_data: get_sl_cluster_data() output
        feature_cols: List of feature column names
        window_size: Window size used in model
    
    Returns:
        Dictionary with X (features) and y (labels) arrays
        - X_sl: (N_sl, window_size, n_features) - SL entries
        - X_tp: (N_tp, window_size, n_features) - TP entries
        - y_sl: (N_sl,) - Labels for SL (should be FLAT or opposite)
        - y_tp: (N_tp,) - Labels for TP (should be correct side)
    """
    try:
        sl_entries = sl_cluster_data.get('sl_entries', [])
        tp_entries = sl_cluster_data.get('tp_entries', [])
        
        X_sl_list = []
        X_tp_list = []
        y_sl_list = []
        y_tp_list = []
        
        # Process SL entries - These are hard negatives (should be FLAT or opposite)
        for entry in sl_entries:
            window_data = entry.get('window_data', [])
            if len(window_data) == window_size:
                X_sl_list.append(window_data)
                # Label as FLAT (0) since these are failed signals
                y_sl_list.append(0)  # FLAT
        
        # Process TP entries - These are positive examples
        for entry in tp_entries:
            window_data = entry.get('window_data', [])
            side = entry.get('side', 'LONG')
            if len(window_data) == window_size:
                X_tp_list.append(window_data)
                # Label based on side: LONG=1, SHORT=2
                if side == 'LONG':
                    y_tp_list.append(1)
                else:
                    y_tp_list.append(2)
        
        X_sl = np.array(X_sl_list) if X_sl_list else np.array([])
        X_tp = np.array(X_tp_list) if X_tp_list else np.array([])
        y_sl = np.array(y_sl_list) if y_sl_list else np.array([])
        y_tp = np.array(y_tp_list) if y_tp_list else np.array([])
        
        return {
            'X_sl': X_sl,
            'X_tp': X_tp,
            'y_sl': y_sl,
            'y_tp': y_tp,
            'n_sl': len(X_sl_list),
            'n_tp': len(X_tp_list)
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to prepare training data: {e}")
        return {
            'X_sl': np.array([]),
            'X_tp': np.array([]),
            'y_sl': np.array([]),
            'y_tp': np.array([]),
            'n_sl': 0,
            'n_tp': 0
        }

