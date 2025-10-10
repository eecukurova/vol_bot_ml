"""
Utility functions for date/format/log helpers
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import pandas as pd


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def days_ago(days: int) -> datetime:
    """Get datetime N days ago"""
    return datetime.now() - timedelta(days=days)


def format_date(date: datetime) -> str:
    """Format datetime to YYYY-MM-DD string"""
    return date.strftime('%Y-%m-%d')


def format_currency(amount: float, decimals: int = 2) -> str:
    """Format currency with specified decimals"""
    return f"${amount:.{decimals}f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format percentage with specified decimals"""
    return f"{value:.{decimals}f}%"


def format_volume(volume: int) -> str:
    """Format volume with K/M/B suffixes"""
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.1f}B"
    elif volume >= 1_000_000:
        return f"{volume / 1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"{volume / 1_000:.1f}K"
    else:
        return str(volume)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with default fallback"""
    if denominator == 0:
        return default
    return numerator / denominator


def consecutive_days_below_threshold(prices: List[float], threshold: float = 1.0) -> int:
    """Calculate maximum consecutive days below threshold"""
    if not prices:
        return 0
    
    max_consecutive = 0
    current_consecutive = 0
    
    for price in prices:
        if price < threshold:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    return max_consecutive


def calculate_drawdown_from_high(prices: List[float]) -> float:
    """Calculate drawdown from highest point"""
    if not prices:
        return 0.0
    
    highest = max(prices)
    current = prices[-1]
    
    if highest == 0:
        return 0.0
    
    drawdown = ((highest - current) / highest) * 100
    return max(0.0, drawdown)


def validate_date_range(start_date: datetime, end_date: datetime) -> bool:
    """Validate that start_date is before end_date"""
    return start_date < end_date


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime object"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None


def get_market_cap_estimate(price: float, shares_outstanding: Optional[int] = None) -> Optional[float]:
    """Estimate market cap if shares outstanding available"""
    if shares_outstanding is None:
        return None
    return price * shares_outstanding
