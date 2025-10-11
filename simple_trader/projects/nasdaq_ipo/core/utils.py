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


def calculate_consecutive_business_days_below_1(prices: List[float], dates: List[str], threshold: float = 1.0) -> int:
    """Calculate consecutive business days below $1 (Nasdaq deficiency rule)"""
    if not prices or not dates:
        return 0
    
    consecutive_days = 0
    # Start from most recent and count backwards
    for i in range(len(prices) - 1, -1, -1):
        if prices[i] < threshold:
            consecutive_days += 1
        else:
            break
    
    return consecutive_days


def calculate_deficiency_risk_metrics(symbol: str, prices: List[float], dates: List[str]) -> dict:
    """Calculate Nasdaq deficiency risk metrics"""
    if not prices or not dates:
        return {
            'consecutive_below_1': 0,
            'deficiency_risk_flag': False,
            'deficiency_risk_level': 'NONE',
            'days_since_deficiency_start': 0,
            'compliance_deadline': None,
            'compliance_status': 'COMPLIANT'
        }
    
    consecutive_below_1 = calculate_consecutive_business_days_below_1(prices, dates)
    
    # Deficiency risk levels
    if consecutive_below_1 >= 30:
        deficiency_risk_flag = True
        if consecutive_below_1 >= 180:
            deficiency_risk_level = 'CRITICAL'
        elif consecutive_below_1 >= 150:
            deficiency_risk_level = 'HIGH'
        elif consecutive_below_1 >= 60:
            deficiency_risk_level = 'MEDIUM'
        else:
            deficiency_risk_level = 'LOW'
    else:
        deficiency_risk_flag = False
        deficiency_risk_level = 'NONE'
    
    # Calculate compliance deadline
    compliance_deadline = None
    compliance_status = 'COMPLIANT'
    
    if deficiency_risk_flag:
        # Assume deficiency started 30 days ago (when rule triggers)
        deficiency_start_days = max(0, consecutive_below_1 - 30)
        days_since_deficiency_start = deficiency_start_days
        
        # 180-day compliance period
        if days_since_deficiency_start < 180:
            compliance_deadline = 180 - days_since_deficiency_start
            compliance_status = 'IN_COMPLIANCE_PERIOD'
        else:
            compliance_status = 'COMPLIANCE_EXPIRED'
    else:
        days_since_deficiency_start = 0
    
    return {
        'consecutive_below_1': consecutive_below_1,
        'deficiency_risk_flag': deficiency_risk_flag,
        'deficiency_risk_level': deficiency_risk_level,
        'days_since_deficiency_start': days_since_deficiency_start,
        'compliance_deadline': compliance_deadline,
        'compliance_status': compliance_status
    }


def format_deficiency_warning(symbol: str, days_below: int, days_since_start: int, risk_level: str) -> str:
    """Format deficiency warning message"""
    if risk_level == 'NONE':
        return f"✅ {symbol}: No deficiency risk"
    elif risk_level == 'LOW':
        return f"⚠️ {symbol}: {days_below} days below $1 (deficiency risk)"
    elif risk_level == 'MEDIUM':
        return f"🚨 {symbol}: {days_below} days below $1 (medium risk)"
    elif risk_level == 'HIGH':
        return f"🔥 {symbol}: {days_below} days below $1 (high risk - {days_since_start} days since deficiency)"
    elif risk_level == 'CRITICAL':
        return f"💀 {symbol}: {days_below} days below $1 (CRITICAL - compliance expired)"
    else:
        return f"❓ {symbol}: Unknown deficiency status"


def get_compliance_deadline_warning(days_remaining: int) -> str:
    """Get compliance deadline warning message"""
    if days_remaining is None:
        return ""
    elif days_remaining <= 0:
        return "COMPLIANCE EXPIRED"
    elif days_remaining <= 30:
        return f"⚠️ {days_remaining} days to compliance deadline"
    elif days_remaining <= 60:
        return f"⏰ {days_remaining} days to compliance deadline"
    else:
        return f"📅 {days_remaining} days to compliance deadline"
