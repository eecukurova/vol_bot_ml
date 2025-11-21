"""Pattern blocker - prevent trading when patterns match detected negative patterns."""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class PatternBlocker:
    """Block signals that match detected negative patterns."""
    
    def __init__(self, patterns_file: Path = Path("runs/detected_patterns.json")):
        """
        Initialize pattern blocker.
        
        Args:
            patterns_file: Path to detected patterns JSON file
        """
        self.patterns_file = patterns_file
        self.patterns = []
        self.load_patterns()
    
    def load_patterns(self):
        """Load detected patterns from JSON file."""
        try:
            if self.patterns_file.exists():
                with open(self.patterns_file) as f:
                    data = json.load(f)
                self.patterns = data.get('patterns', [])
                logger.info(f"📋 Loaded {len(self.patterns)} patterns from {self.patterns_file}")
            else:
                logger.debug(f"Pattern file not found: {self.patterns_file}")
                self.patterns = []
        except Exception as e:
            logger.error(f"❌ Failed to load patterns: {e}")
            self.patterns = []
    
    def check_pattern_match(
        self,
        side: str,
        confidence: float,
        probs: Dict[str, float],
        features: Dict[str, Any],
        current_hour: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Check if signal matches a negative pattern.
        
        Args:
            side: LONG or SHORT
            confidence: Signal confidence
            probs: Probability distribution
            features: Market features (ema50, ema200, vol_spike, rsi)
            current_hour: Current hour (0-23), if None will use current time
        
        Returns:
            (should_block, reason)
        """
        if not self.patterns:
            return False, None
        
        if current_hour is None:
            current_hour = datetime.now().hour
        
        # Check each pattern
        for pattern in self.patterns:
            pattern_features = pattern.get('features', {})
            pattern_count = pattern.get('count', 0)
            
            # Skip if pattern has too few examples
            if pattern_count < 3:
                continue
            
            # Check time match
            pattern_hour = pattern_features.get('hour')
            if pattern_hour is not None:
                # Allow 1 hour tolerance
                hour_diff = abs(current_hour - pattern_hour)
                if hour_diff > 1 and hour_diff < 23:
                    continue  # Not matching time
            
            # Check confidence match (if pattern has high confidence SL)
            pattern_conf = pattern_features.get('confidence', 0)
            if pattern_conf > 0:
                # If pattern has high confidence but hit SL, and current signal has similar confidence
                conf_diff = abs(confidence - pattern_conf)
                if conf_diff < 0.1:  # Within 10%
                    # Check side match
                    pattern_positions = pattern.get('positions', [])
                    if pattern_positions:
                        pattern_sides = [p.get('side', '').upper() for p in pattern_positions]
                        if side.upper() in pattern_sides:
                            # Check volume spike
                            pattern_vol = pattern_features.get('vol_spike', 0)
                            current_vol = features.get('vol_spike', 1.0)
                            
                            # If pattern has low volume spike and current also has low volume spike
                            if pattern_vol < 0.8 and current_vol < 0.8:
                                reason = f"Pattern match: {pattern_count} similar SL positions at {pattern_hour}:00 (conf: {pattern_conf*100:.0f}%, vol: {pattern_vol:.2f})"
                                return True, reason
        
        return False, None
    
    def should_block_signal(
        self,
        side: str,
        confidence: float,
        probs: Dict[str, float],
        features: Dict[str, Any],
        current_hour: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Check if signal should be blocked based on patterns.
        
        Returns:
            (should_block, reason)
        """
        # Reload patterns periodically (every check)
        self.load_patterns()
        
        return self.check_pattern_match(side, confidence, probs, features, current_hour)


def check_volume_spike_warning(vol_spike: float, threshold: float = 0.8) -> tuple[bool, str]:
    """
    Check if volume spike is low and issue warning.
    
    Args:
        vol_spike: Current volume spike value
        threshold: Minimum volume spike threshold
    
    Returns:
        (is_warning, message)
    """
    if vol_spike < threshold:
        return True, f"⚠️ Düşük volume spike ({vol_spike:.2f} < {threshold}) - Regime filter riski"
    return False, ""

