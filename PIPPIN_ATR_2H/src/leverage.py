"""Dynamic leverage management using Kelly fraction and drawdown-aware adjustments."""

import numpy as np
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def calculate_kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """
    Calculate Kelly fraction for optimal position sizing.
    
    Kelly = (p * b - q) / b
    where:
    - p = win rate
    - q = loss rate (1 - p)
    - b = avg_win / abs(avg_loss) (odds)
    
    Args:
        win_rate: Win rate (0.0 to 1.0)
        avg_win: Average win amount (as percentage, e.g., 0.005 = 0.5%)
        avg_loss: Average loss amount (as percentage, e.g., -0.008 = -0.8%)
        
    Returns:
        Kelly fraction (0.0 to 1.0)
    """
    if avg_loss == 0 or avg_win == 0:
        return 0.0
    
    p = win_rate
    q = 1 - p
    b = abs(avg_win / avg_loss)
    
    kelly = (p * b - q) / b
    
    # Clamp between 0 and 1
    kelly = max(0.0, min(1.0, kelly))
    
    return kelly


def calculate_half_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Calculate half-Kelly (more conservative).
    
    Args:
        win_rate: Win rate
        avg_win: Average win
        avg_loss: Average loss
        
    Returns:
        Half-Kelly fraction
    """
    kelly = calculate_kelly_fraction(win_rate, avg_win, avg_loss)
    return kelly / 2.0


def calculate_leverage_from_kelly(
    kelly_fraction: float,
    base_leverage: int = 5,
    max_leverage: int = 10,
    min_leverage: int = 1,
) -> int:
    """
    Convert Kelly fraction to leverage.
    
    Args:
        kelly_fraction: Kelly fraction (0.0 to 1.0)
        base_leverage: Base leverage when kelly = 0.5
        max_leverage: Maximum leverage
        min_leverage: Minimum leverage
        
    Returns:
        Leverage as integer
    """
    # Scale: kelly=0 -> min_leverage, kelly=1 -> max_leverage
    leverage = min_leverage + (max_leverage - min_leverage) * kelly_fraction
    
    # Round to integer
    leverage = int(round(leverage))
    
    return leverage


def calculate_drawdown_aware_leverage(
    current_drawdown: float,
    max_allowed_drawdown: float = 0.10,  # 10%
    base_leverage: int = 5,
    max_leverage: int = 10,
    min_leverage: int = 1,
) -> int:
    """
    Adjust leverage based on current drawdown.
    
    If drawdown > threshold, reduce leverage.
    If drawdown < threshold, can increase leverage (up to max).
    
    Args:
        current_drawdown: Current drawdown as percentage (0.0 to 1.0)
        max_allowed_drawdown: Maximum allowed drawdown before reducing leverage
        base_leverage: Base leverage
        max_leverage: Maximum leverage
        min_leverage: Minimum leverage
        
    Returns:
        Adjusted leverage
    """
    # If drawdown exceeds threshold, reduce leverage
    if current_drawdown > max_allowed_drawdown:
        # Reduce leverage proportionally
        reduction_factor = 1.0 - (current_drawdown - max_allowed_drawdown) / max_allowed_drawdown
        leverage = base_leverage * max(0.5, reduction_factor)  # At least 50% of base
    else:
        # Can increase leverage if drawdown is low
        if current_drawdown < max_allowed_drawdown * 0.5:
            # Low drawdown, can increase
            increase_factor = 1.0 + (1.0 - current_drawdown / max_allowed_drawdown) * 0.5
            leverage = base_leverage * min(1.5, increase_factor)  # At most 150% of base
        else:
            leverage = base_leverage
    
    # Clamp to min/max
    leverage = max(min_leverage, min(max_leverage, int(round(leverage))))
    
    return leverage


def get_adaptive_leverage(
    win_rate: Optional[float] = None,
    avg_win: Optional[float] = None,
    avg_loss: Optional[float] = None,
    current_drawdown: Optional[float] = None,
    base_leverage: int = 5,
    method: str = "hybrid",  # "kelly", "drawdown", or "hybrid"
) -> int:
    """
    Get adaptive leverage based on multiple factors.
    
    Args:
        win_rate: Historical win rate
        avg_win: Average win percentage
        avg_loss: Average loss percentage
        current_drawdown: Current drawdown percentage
        base_leverage: Base leverage
        method: "kelly", "drawdown", or "hybrid"
        
    Returns:
        Adaptive leverage
    """
    leverage = base_leverage
    
    if method == "kelly":
        if win_rate and avg_win and avg_loss:
            kelly = calculate_half_kelly(win_rate, avg_win, abs(avg_loss))
            leverage = calculate_leverage_from_kelly(
                kelly,
                base_leverage=base_leverage,
                max_leverage=10,
                min_leverage=1,
            )
    
    elif method == "drawdown":
        if current_drawdown is not None:
            leverage = calculate_drawdown_aware_leverage(
                current_drawdown,
                base_leverage=base_leverage,
                max_leverage=10,
                min_leverage=1,
            )
    
    elif method == "hybrid":
        # Combine both methods (take minimum for safety)
        kelly_leverage = base_leverage
        dd_leverage = base_leverage
        
        if win_rate and avg_win and avg_loss:
            kelly = calculate_half_kelly(win_rate, avg_win, abs(avg_loss))
            kelly_leverage = calculate_leverage_from_kelly(
                kelly,
                base_leverage=base_leverage,
                max_leverage=10,
                min_leverage=1,
            )
        
        if current_drawdown is not None:
            dd_leverage = calculate_drawdown_aware_leverage(
                current_drawdown,
                base_leverage=base_leverage,
                max_leverage=10,
                min_leverage=1,
            )
        
        # Use minimum for safety
        leverage = min(kelly_leverage, dd_leverage)
    
    return leverage

