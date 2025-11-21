"""Advanced position management: break-even, micro-trail, trade blocker."""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class PositionManager:
    """Manage position lifecycle: break-even, trailing stop, trade blocking."""
    
    def __init__(
        self,
        break_even_threshold: float = 0.0025,  # 0.25%
        trail_start: float = 0.0035,  # 0.35%
        trail_step: float = 0.001,  # 0.1%
        state_file: str = "runs/position_manager_state.json"
    ):
        """
        Initialize position manager.
        
        Args:
            break_even_threshold: Move SL to entry when profit reaches this %
            trail_start: Start trailing when profit reaches this %
            trail_step: Trail step size (percentage)
            state_file: Path to state file
        """
        self.break_even_threshold = break_even_threshold
        self.trail_start = trail_start
        self.trail_step = trail_step
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # State tracking
        self.positions: Dict[str, Dict] = {}  # symbol -> position info
        self.trade_history: List[Dict] = []
        
        self._load_state()
    
    def _load_state(self):
        """Load state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.positions = data.get('positions', {})
                    self.trade_history = data.get('trade_history', [])
                logger.info(f"📂 Loaded position state: {len(self.positions)} positions")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load position state: {e}")
            self.positions = {}
            self.trade_history = []
    
    def _save_state(self):
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    'positions': self.positions,
                    'trade_history': self.trade_history,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save position state: {e}")
    
    def register_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        initial_sl: float,
        position_id: str,
    ):
        """
        Register a new position.
        
        Args:
            symbol: Trading symbol
            side: "LONG" or "SHORT"
            entry_price: Entry price
            initial_sl: Initial stop-loss price
            position_id: Position identifier
        """
        self.positions[symbol] = {
            'side': side,
            'entry_price': entry_price,
            'initial_sl': initial_sl,
            'current_sl': initial_sl,
            'position_id': position_id,
            'entry_time': datetime.now().isoformat(),
            'break_even_moved': False,
            'trailing_active': False,
            'highest_profit': 0.0,
        }
        self._save_state()
        logger.info(f"📝 Registered position: {symbol} {side} @ {entry_price:.2f}")
    
    def update_position_price(
        self,
        symbol: str,
        current_price: float,
    ) -> Optional[Dict]:
        """
        Update position with current price and check for break-even/trail adjustments.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            Dict with update actions or None
        """
        if symbol not in self.positions:
            return None
        
        pos = self.positions[symbol]
        side = pos['side']
        entry = pos['entry_price']
        current_sl = pos['current_sl']
        
        # Calculate current profit
        if side == "LONG":
            profit_pct = (current_price - entry) / entry
        else:  # SHORT
            profit_pct = (entry - current_price) / entry
        
        pos['highest_profit'] = max(pos['highest_profit'], profit_pct)
        
        actions = []
        new_sl = current_sl
        
        # Break-even check
        if profit_pct >= self.break_even_threshold and not pos['break_even_moved']:
            new_sl = entry  # Move SL to entry
            pos['break_even_moved'] = True
            pos['current_sl'] = new_sl
            actions.append({
                'type': 'break_even',
                'old_sl': current_sl,
                'new_sl': new_sl,
                'profit_pct': profit_pct,
            })
            logger.info(f"✅ Break-even: {symbol} SL moved to entry @ {entry:.2f} (profit: {profit_pct*100:.2f}%)")
        
        # Trailing stop check
        if profit_pct >= self.trail_start:
            pos['trailing_active'] = True
            
            # Calculate trailing stop
            if side == "LONG":
                # For LONG: trail upward, SL below current price
                trail_sl = current_price * (1 - self.trail_step)
                if trail_sl > pos['current_sl']:
                    old_sl = pos['current_sl']
                    new_sl = trail_sl
                    pos['current_sl'] = new_sl
                    actions.append({
                        'type': 'trail',
                        'old_sl': old_sl,
                        'new_sl': new_sl,
                        'profit_pct': profit_pct,
                    })
                    logger.info(f"📈 Trail: {symbol} SL moved to {new_sl:.2f} (profit: {profit_pct*100:.2f}%)")
            else:  # SHORT
                # For SHORT: trail downward, SL above current price
                trail_sl = current_price * (1 + self.trail_step)
                if trail_sl < pos['current_sl'] or pos['current_sl'] == pos['initial_sl']:
                    old_sl = pos['current_sl']
                    new_sl = trail_sl
                    pos['current_sl'] = new_sl
                    actions.append({
                        'type': 'trail',
                        'old_sl': old_sl,
                        'new_sl': new_sl,
                        'profit_pct': profit_pct,
                    })
                    logger.info(f"📉 Trail: {symbol} SL moved to {new_sl:.2f} (profit: {profit_pct*100:.2f}%)")
        
        if actions:
            self._save_state()
            return {
                'symbol': symbol,
                'actions': actions,
                'current_sl': new_sl,
            }
        
        return None
    
    def close_position(self, symbol: str, exit_price: float, reason: str):
        """
        Close position and record trade.
        
        Args:
            symbol: Trading symbol
            exit_price: Exit price
            reason: "TP", "SL", "MANUAL"
        """
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        side = pos['side']
        entry = pos['entry_price']
        
        # Calculate PnL
        if side == "LONG":
            pnl_pct = (exit_price - entry) / entry
        else:
            pnl_pct = (entry - exit_price) / entry
        
        # Record trade
        trade = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct,
            'entry_time': pos['entry_time'],
            'exit_time': datetime.now().isoformat(),
            'reason': reason,
            'break_even_moved': pos['break_even_moved'],
            'trailing_active': pos['trailing_active'],
            'highest_profit': pos['highest_profit'],
        }
        
        self.trade_history.append(trade)
        
        # Keep only last 100 trades
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]
        
        # Remove position
        del self.positions[symbol]
        
        self._save_state()
        logger.info(f"📊 Closed {symbol}: {reason}, PnL: {pnl_pct*100:.2f}%")
    
    def should_block_trades(
        self,
        max_consecutive_losses: int = 5,
        cooldown_minutes: int = 60,
    ) -> tuple[bool, str]:
        """
        Check if trading should be blocked due to consecutive losses.
        
        Args:
            max_consecutive_losses: Block after this many consecutive losses
            cooldown_minutes: Cooldown period in minutes
            
        Returns:
            (should_block, reason)
        """
        if len(self.trade_history) < max_consecutive_losses:
            return False, ""
        
        # Check last N trades
        recent_trades = self.trade_history[-max_consecutive_losses:]
        all_losses = all(t['pnl_pct'] < 0 for t in recent_trades)
        
        if not all_losses:
            return False, ""
        
        # Check if in cooldown
        if recent_trades:
            last_trade_time = datetime.fromisoformat(recent_trades[-1]['exit_time'])
            time_since = datetime.now() - last_trade_time
            
            if time_since < timedelta(minutes=cooldown_minutes):
                remaining = (timedelta(minutes=cooldown_minutes) - time_since).total_seconds() / 60
                return True, f"{max_consecutive_losses} consecutive losses. Cooldown: {remaining:.1f} min remaining"
        
        return True, f"{max_consecutive_losses} consecutive losses. Trading blocked."
    
    def get_position_info(self, symbol: str) -> Optional[Dict]:
        """Get current position information."""
        return self.positions.get(symbol)


# Global instance
_position_manager: Optional[PositionManager] = None


def get_position_manager() -> PositionManager:
    """Get global position manager instance."""
    global _position_manager
    if _position_manager is None:
        _position_manager = PositionManager()
    return _position_manager

