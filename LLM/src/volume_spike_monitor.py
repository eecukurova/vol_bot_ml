"""Volume spike monitoring and alerting."""
import logging
from typing import Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)


class VolumeSpikeMonitor:
    """Monitor volume spike values and alert on low values."""
    
    def __init__(self, warning_threshold: float = 0.4, history_size: int = 20):
        """
        Initialize volume spike monitor.
        
        Args:
            warning_threshold: Volume spike threshold for warnings
            history_size: Number of recent values to track
        """
        self.warning_threshold = warning_threshold
        self.history = deque(maxlen=history_size)
        self.low_spike_count = 0
    
    def check(self, vol_spike: float, signal_side: str, confidence: float) -> tuple[bool, str]:
        """
        Check volume spike and return warning if needed.
        
        Args:
            vol_spike: Current volume spike value
            signal_side: Signal side (LONG/SHORT)
            confidence: Signal confidence
        
        Returns:
            (is_warning, message)
        """
        self.history.append(vol_spike)
        
        if vol_spike < self.warning_threshold:
            self.low_spike_count += 1
            
            avg_spike = sum(self.history) / len(self.history) if self.history else vol_spike
            
            message = (
                f"⚠️ Düşük Volume Spike: {vol_spike:.2f} < {self.warning_threshold}\n"
                f"   Son {len(self.history)} sinyalde ortalama: {avg_spike:.2f}\n"
                f"   Düşük spike sayısı: {self.low_spike_count}\n"
                f"   Sinyal: {signal_side} @ {confidence:.1%} confidence"
            )
            
            return True, message
        
        return False, ""
    
    def get_stats(self) -> Dict:
        """Get volume spike statistics."""
        if not self.history:
            return {}
        
        return {
            'avg_spike': sum(self.history) / len(self.history),
            'min_spike': min(self.history),
            'max_spike': max(self.history),
            'low_spike_count': self.low_spike_count,
            'total_signals': len(self.history)
        }

