"""Shadow mode: generate signals but don't place orders."""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import pandas as pd

logger = logging.getLogger(__name__)


class ShadowMode:
    """Shadow mode tracker for comparing shadow vs live performance."""
    
    def __init__(
        self,
        enabled: bool = True,
        duration_days: int = 7,
        state_file: str = "runs/shadow_mode_state.json"
    ):
        """
        Initialize shadow mode.
        
        Args:
            enabled: Whether shadow mode is active
            duration_days: How many days to run shadow mode
            state_file: Path to state file
        """
        self.enabled = enabled
        self.duration_days = duration_days
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.start_time = datetime.now()
        self.signals: list = []
        self.virtual_trades: list = []
        
        self._load_state()
    
    def _load_state(self):
        """Load shadow mode state."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.start_time = datetime.fromisoformat(data.get('start_time', datetime.now().isoformat()))
                    self.signals = data.get('signals', [])
                    self.virtual_trades = data.get('virtual_trades', [])
        except Exception as e:
            logger.warning(f"⚠️ Failed to load shadow state: {e}")
    
    def _save_state(self):
        """Save shadow mode state."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    'start_time': self.start_time.isoformat(),
                    'signals': self.signals,
                    'virtual_trades': self.virtual_trades,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save shadow state: {e}")
    
    def is_active(self) -> bool:
        """Check if shadow mode is still active."""
        if not self.enabled:
            return False
        
        elapsed = datetime.now() - self.start_time
        return elapsed < timedelta(days=self.duration_days)
    
    def should_place_order(self) -> bool:
        """Check if real orders should be placed."""
        return not self.is_active()
    
    def record_signal(
        self,
        side: str,
        entry: float,
        tp: float,
        sl: float,
        confidence: float,
        probs: Dict,
    ):
        """Record a signal (for shadow mode tracking)."""
        if not self.is_active():
            return
        
        signal = {
            'timestamp': datetime.now().isoformat(),
            'side': side,
            'entry': entry,
            'tp': tp,
            'sl': sl,
            'confidence': confidence,
            'probs': probs,
        }
        
        self.signals.append(signal)
        
        # Keep only last 1000 signals
        if len(self.signals) > 1000:
            self.signals = self.signals[-1000:]
        
        self._save_state()
        logger.info(f"👻 Shadow mode: Signal recorded (not placing order)")
    
    def record_virtual_trade(
        self,
        side: str,
        entry: float,
        exit_price: float,
        pnl_pct: float,
        reason: str,
    ):
        """Record a virtual trade result."""
        trade = {
            'timestamp': datetime.now().isoformat(),
            'side': side,
            'entry': entry,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct,
            'reason': reason,
        }
        
        self.virtual_trades.append(trade)
        
        # Keep only last 500 trades
        if len(self.virtual_trades) > 500:
            self.virtual_trades = self.virtual_trades[-500:]
        
        self._save_state()
    
    def get_performance_summary(self) -> Dict:
        """Get shadow mode performance summary."""
        if not self.virtual_trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'total_pnl': 0.0,
            }
        
        df = pd.DataFrame(self.virtual_trades)
        
        wins = (df['pnl_pct'] > 0).sum()
        total = len(df)
        win_rate = wins / total * 100 if total > 0 else 0.0
        avg_pnl = df['pnl_pct'].mean()
        total_pnl = df['pnl_pct'].sum()
        
        return {
            'total_trades': total,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'total_pnl': total_pnl,
            'wins': int(wins),
            'losses': int(total - wins),
        }


# Global instance
_shadow_mode: Optional[ShadowMode] = None


def get_shadow_mode() -> ShadowMode:
    """Get global shadow mode instance."""
    global _shadow_mode
    if _shadow_mode is None:
        _shadow_mode = ShadowMode(enabled=True, duration_days=7)
    return _shadow_mode


def is_shadow_mode_active() -> bool:
    """Check if shadow mode is active."""
    return get_shadow_mode().is_active()

