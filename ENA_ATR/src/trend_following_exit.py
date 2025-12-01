"""Trend Following Exit Strategy for ENA ATR project.
Combines ML entry signals with trend following exit mechanisms.
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class TrendFollowingExit:
    """
    Trend Following Exit Manager.
    
    Features:
    - Trailing Stop Loss
    - Partial Exit
    - Trend Reversal Exit
    - Volume Exit
    """
    
    def __init__(
        self,
        trailing_activation_pct: float = 1.0,  # Activate trailing at 1.0% profit
        trailing_distance_pct: float = 2.0,   # Trailing stop distance
        partial_exit_trigger_pct: float = 1.0,  # Trigger partial exit at 1.0% profit
        partial_exit_pct: float = 75.0,         # Close 75% of position
        use_trend_reversal_exit: bool = True,
        trend_reversal_min_bars: int = 5,  # Minimum bars before trend reversal exit can trigger
        trend_reversal_min_profit_pct: float = 0.0,  # Minimum profit % before trend reversal exit (0 = disabled)
        use_volume_exit: bool = True,
        volume_exit_threshold: float = 3.0,
        volume_exit_min_profit_pct: float = 0.0,  # Minimum profit % before volume exit (0 = disabled)
        volume_exit_min_bars: int = 0,  # Minimum bars before volume exit can trigger (0 = disabled)
        state_file: str = "runs/trend_following_exit_state.json"
    ):
        """
        Initialize trend following exit manager.
        
        Args:
            trailing_activation_pct: Profit % to activate trailing stop
            trailing_distance_pct: Trailing stop distance from price
            partial_exit_trigger_pct: Profit % to trigger partial exit
            partial_exit_pct: Percentage of position to close on partial exit
            use_trend_reversal_exit: Enable trend reversal exit
            use_volume_exit: Enable volume exit
            volume_exit_threshold: Volume ratio threshold for exit
            state_file: Path to state file
        """
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_distance_pct = trailing_distance_pct
        self.partial_exit_trigger_pct = partial_exit_trigger_pct
        self.partial_exit_pct = partial_exit_pct
        self.use_trend_reversal_exit = use_trend_reversal_exit
        self.trend_reversal_min_bars = trend_reversal_min_bars
        self.trend_reversal_min_profit_pct = trend_reversal_min_profit_pct
        self.use_volume_exit = use_volume_exit
        self.volume_exit_threshold = volume_exit_threshold
        self.volume_exit_min_profit_pct = volume_exit_min_profit_pct
        self.volume_exit_min_bars = volume_exit_min_bars
        
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Position tracking
        self.positions: Dict[str, Dict] = {}  # symbol -> position info
        
        self._load_state()
    
    def _load_state(self):
        """Load state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.positions = data.get('positions', {})
                logger.info(f"📂 Loaded trend following exit state: {len(self.positions)} positions")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load trend following exit state: {e}")
            self.positions = {}
    
    def _save_state(self):
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    'positions': self.positions,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save trend following exit state: {e}")
    
    def register_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        position_id: str,
    ):
        """
        Register a new position for trend following exit tracking.
        
        Args:
            symbol: Trading symbol
            side: "LONG" or "SHORT"
            entry_price: Entry price
            position_id: Position identifier
        """
        self.positions[symbol] = {
            'side': side,
            'entry_price': entry_price,
            'position_id': position_id,
            'entry_time': datetime.now().isoformat(),
            'entry_bar_count': 0,  # Track number of bars since entry
            'trailing_stop_price': None,
            'trailing_activated': False,
            'partial_exit_done': False,
            'partial_exit_price': None,
            'remaining_position_pct': 100.0,
        }
        self._save_state()
        logger.info(f"📝 Registered position for trend following: {symbol} {side} @ {entry_price:.2f}")
    
    def check_exit_signals(
        self,
        symbol: str,
        current_price: float,
        high: float,
        low: float,
        ema_fast: float,
        ema_slow: float,
        volume_ratio: float,
        ha_up: bool,
        ha_down: bool,
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Check if exit signals are triggered.
        
        Args:
            symbol: Trading symbol
            current_price: Current price
            high: High price of current bar
            low: Low price of current bar
            ema_fast: Fast EMA value
            ema_slow: Slow EMA value
            volume_ratio: Volume ratio (current / average)
            ha_up: Heikin Ashi up candle
            ha_down: Heikin Ashi down candle
        
        Returns:
            (exit_reason, exit_price, action) or (None, None, None)
            exit_reason: "TRAILING_STOP", "TREND_REVERSAL", "VOLUME_EXIT", "PARTIAL_EXIT"
            exit_price: Price to exit at
            action: "CLOSE_ALL" or "CLOSE_PARTIAL"
        """
        if symbol not in self.positions:
            return None, None, None
        
        pos = self.positions[symbol]
        side = pos['side']
        entry_price = pos['entry_price']
        
        # Increment bar count
        pos['entry_bar_count'] = pos.get('entry_bar_count', 0) + 1
        
        # Calculate current profit
        if side == "LONG":
            current_profit_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            current_profit_pct = ((entry_price - current_price) / entry_price) * 100
        
        # Update trailing stop
        if current_profit_pct >= self.trailing_activation_pct:
            pos['trailing_activated'] = True
            
            if side == "LONG":
                new_trailing = current_price * (1 - self.trailing_distance_pct / 100)
                if pos['trailing_stop_price'] is None or new_trailing > pos['trailing_stop_price']:
                    pos['trailing_stop_price'] = new_trailing
            else:  # SHORT
                new_trailing = current_price * (1 + self.trailing_distance_pct / 100)
                if pos['trailing_stop_price'] is None or new_trailing < pos['trailing_stop_price']:
                    pos['trailing_stop_price'] = new_trailing
        
        # Check partial exit
        if not pos['partial_exit_done'] and current_profit_pct >= self.partial_exit_trigger_pct:
            pos['partial_exit_done'] = True
            pos['partial_exit_price'] = current_price
            pos['remaining_position_pct'] = 100.0 - self.partial_exit_pct
            self._save_state()
            
            logger.info(f"💰 Partial exit triggered: {self.partial_exit_pct}% @ ${current_price:.2f}")
            return "PARTIAL_EXIT", current_price, "CLOSE_PARTIAL"
        
        # Check trailing stop hit
        if pos['trailing_stop_price'] is not None:
            if side == "LONG" and low <= pos['trailing_stop_price']:
                logger.info(f"🛑 Trailing stop hit: ${pos['trailing_stop_price']:.2f}")
                return "TRAILING_STOP", pos['trailing_stop_price'], "CLOSE_ALL"
            elif side == "SHORT" and high >= pos['trailing_stop_price']:
                logger.info(f"🛑 Trailing stop hit: ${pos['trailing_stop_price']:.2f}")
                return "TRAILING_STOP", pos['trailing_stop_price'], "CLOSE_ALL"
        
        # Check trend reversal exit (with minimum bar and profit requirements)
        if self.use_trend_reversal_exit:
            entry_bar_count = pos.get('entry_bar_count', 0)
            
            # Check minimum bars requirement
            if entry_bar_count < self.trend_reversal_min_bars:
                logger.debug(f"⏸️ Trend reversal exit skipped: Only {entry_bar_count} bars since entry (min: {self.trend_reversal_min_bars})")
            # Check minimum profit requirement (if enabled)
            elif self.trend_reversal_min_profit_pct > 0 and current_profit_pct < self.trend_reversal_min_profit_pct:
                logger.debug(f"⏸️ Trend reversal exit skipped: Profit {current_profit_pct:.2f}% < min {self.trend_reversal_min_profit_pct:.2f}%")
            # Check actual reversal
            elif side == "LONG" and ema_fast < ema_slow:  # EMA crossover reversal
                logger.info(f"🔄 Trend reversal exit: EMA fast crossed below slow (after {entry_bar_count} bars, profit: {current_profit_pct:.2f}%)")
                return "TREND_REVERSAL", current_price, "CLOSE_ALL"
            elif side == "SHORT" and ema_fast > ema_slow:  # EMA crossover reversal
                logger.info(f"🔄 Trend reversal exit: EMA fast crossed above slow (after {entry_bar_count} bars, profit: {current_profit_pct:.2f}%)")
                return "TREND_REVERSAL", current_price, "CLOSE_ALL"
        
        # Check volume exit (with minimum profit and bar requirements)
        if self.use_volume_exit:
            entry_bar_count = pos.get('entry_bar_count', 0)
            
            # Check minimum bars requirement
            if self.volume_exit_min_bars > 0 and entry_bar_count < self.volume_exit_min_bars:
                logger.debug(f"⏸️ Volume exit skipped: Only {entry_bar_count} bars since entry (min: {self.volume_exit_min_bars})")
            # Check minimum profit requirement (if enabled)
            elif self.volume_exit_min_profit_pct > 0 and current_profit_pct < self.volume_exit_min_profit_pct:
                logger.debug(f"⏸️ Volume exit skipped: Profit {current_profit_pct:.2f}% < min {self.volume_exit_min_profit_pct:.2f}%")
            # Check volume threshold and HA direction
            elif volume_ratio >= self.volume_exit_threshold:
                if side == "LONG" and ha_down:  # Volume spike + bearish candle
                    logger.info(f"📊 Volume exit: Volume ratio={volume_ratio:.2f}, HA down (after {entry_bar_count} bars, profit: {current_profit_pct:.2f}%)")
                    return "VOLUME_EXIT", current_price, "CLOSE_ALL"
                elif side == "SHORT" and ha_up:  # Volume spike + bullish candle
                    logger.info(f"📊 Volume exit: Volume ratio={volume_ratio:.2f}, HA up (after {entry_bar_count} bars, profit: {current_profit_pct:.2f}%)")
                    return "VOLUME_EXIT", current_price, "CLOSE_ALL"
        
        self._save_state()
        return None, None, None
    
    def get_trailing_stop_price(self, symbol: str) -> Optional[float]:
        """Get current trailing stop price for position."""
        if symbol in self.positions:
            return self.positions[symbol].get('trailing_stop_price')
        return None
    
    def close_position(self, symbol: str):
        """Remove position from tracking."""
        if symbol in self.positions:
            del self.positions[symbol]
            self._save_state()
            logger.info(f"✅ Position closed: {symbol}")


# Global instance
_trend_following_exit: Optional[TrendFollowingExit] = None


def get_trend_following_exit() -> TrendFollowingExit:
    """Get or create global trend following exit instance."""
    global _trend_following_exit
    if _trend_following_exit is None:
        _trend_following_exit = TrendFollowingExit()
    return _trend_following_exit


def init_trend_following_exit(config: Dict):
    """Initialize trend following exit from config."""
    global _trend_following_exit
    
    trend_config = config.get("trend_following_exit", {})
    
    _trend_following_exit = TrendFollowingExit(
        trailing_activation_pct=trend_config.get("trailing_activation_pct", 1.0),
        trailing_distance_pct=trend_config.get("trailing_distance_pct", 2.0),
        partial_exit_trigger_pct=trend_config.get("partial_exit_trigger_pct", 1.0),
        partial_exit_pct=trend_config.get("partial_exit_pct", 75.0),
        use_trend_reversal_exit=trend_config.get("use_trend_reversal_exit", True),
        trend_reversal_min_bars=trend_config.get("trend_reversal_min_bars", 5),
        trend_reversal_min_profit_pct=trend_config.get("trend_reversal_min_profit_pct", 0.0),
        use_volume_exit=trend_config.get("use_volume_exit", True),
        volume_exit_threshold=trend_config.get("volume_exit_threshold", 3.0),
        volume_exit_min_profit_pct=trend_config.get("volume_exit_min_profit_pct", 0.0),
        volume_exit_min_bars=trend_config.get("volume_exit_min_bars", 0),
    )
    
    logger.info("✅ Trend Following Exit initialized")

