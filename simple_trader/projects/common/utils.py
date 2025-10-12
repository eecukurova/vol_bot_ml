"""
Common utilities for trading applications
Production-ready helpers for precision, time, retry, and validation
"""

import time
import logging
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import ccxt
import pandas as pd
import numpy as np


def now_utc() -> datetime:
    """Get current UTC datetime"""
    return datetime.now(timezone.utc)


def format_utc_timestamp(dt: datetime = None) -> str:
    """Format datetime as UTC string"""
    if dt is None:
        dt = now_utc()
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def quantize_amount(exchange: ccxt.Exchange, symbol: str, amount: float) -> float:
    """
    Quantize amount to exchange lot size requirements
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading symbol
        amount: Raw amount to quantize
        
    Returns:
        Quantized amount as float
    """
    try:
        return float(exchange.amount_to_precision(symbol, amount))
    except Exception as e:
        logging.warning(f"Amount quantization failed: {e}, using original: {amount}")
        return amount


def quantize_price(exchange: ccxt.Exchange, symbol: str, price: float) -> float:
    """
    Quantize price to exchange tick size requirements
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading symbol
        price: Raw price to quantize
        
    Returns:
        Quantized price as float
    """
    try:
        return float(exchange.price_to_precision(symbol, price))
    except Exception as e:
        logging.warning(f"Price quantization failed: {e}, using original: {price}")
        return price


def retry_with_backoff(func, max_retries: int = 3, backoff_factor: float = 0.5, 
                      exceptions: tuple = (Exception,), *args, **kwargs):
    """
    Retry function with exponential backoff
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        backoff_factor: Backoff multiplier
        exceptions: Tuple of exceptions to catch
        *args, **kwargs: Arguments to pass to function
        
    Returns:
        Function result or raises last exception
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = backoff_factor * (2 ** attempt)
                logging.warning(f"Attempt {attempt + 1} failed: {e}, retrying in {wait_time}s")
                time.sleep(wait_time)
            else:
                logging.error(f"All {max_retries + 1} attempts failed, last error: {e}")
    
    raise last_exception


def safe_fetch_ticker(exchange: ccxt.Exchange, symbol: str, max_retries: int = 3) -> Dict[str, Any]:
    """Safely fetch ticker with retry"""
    return retry_with_backoff(
        exchange.fetch_ticker,
        max_retries=max_retries,
        exceptions=(ccxt.NetworkError, ccxt.ExchangeError),
        symbol=symbol
    )


def safe_fetch_ohlcv(exchange: ccxt.Exchange, symbol: str, timeframe: str, 
                    limit: int = 100, max_retries: int = 3) -> List[List]:
    """Safely fetch OHLCV with retry"""
    return retry_with_backoff(
        exchange.fetch_ohlcv,
        max_retries=max_retries,
        exceptions=(ccxt.NetworkError, ccxt.ExchangeError),
        symbol=symbol,
        timeframe=timeframe,
        limit=limit
    )


def safe_fetch_positions(exchange: ccxt.Exchange, symbols: List[str] = None, 
                        max_retries: int = 3) -> List[Dict[str, Any]]:
    """Safely fetch positions with retry"""
    return retry_with_backoff(
        exchange.fetch_positions,
        max_retries=max_retries,
        exceptions=(ccxt.NetworkError, ccxt.ExchangeError),
        symbols=symbols
    )


def safe_fetch_open_orders(exchange: ccxt.Exchange, symbol: str = None, 
                          max_retries: int = 3) -> List[Dict[str, Any]]:
    """Safely fetch open orders with retry"""
    return retry_with_backoff(
        exchange.fetch_open_orders,
        max_retries=max_retries,
        exceptions=(ccxt.NetworkError, ccxt.ExchangeError),
        symbol=symbol
    )


def safe_telegram_send(bot_token: str, chat_id: str, message: str, 
                      max_retries: int = 3) -> bool:
    """Safely send Telegram message with retry"""
    def send_message():
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        return True
    
    try:
        return retry_with_backoff(
            send_message,
            max_retries=max_retries,
            exceptions=(requests.RequestException,),
        )
    except Exception as e:
        logging.error(f"Telegram send failed after {max_retries + 1} attempts: {e}")
        return False


def ema_tv(series: pd.Series, period: int) -> pd.Series:
    """
    TradingView-compatible EMA calculation (adjust=False)
    
    Args:
        series: Price series
        period: EMA period
        
    Returns:
        EMA series
    """
    return series.ewm(span=period, adjust=False).mean()


def rsi_wilder(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI calculation (EMA-based)
    
    Args:
        series: Price series
        period: RSI period
        
    Returns:
        RSI series
    """
    delta = series.diff()
    up = (delta.clip(lower=0)).ewm(alpha=1/period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def select_series_for_signal(series: pd.Series, use_intrabar: bool) -> pd.Series:
    """
    Select series for signal generation based on intrabar setting
    
    Args:
        series: Price/indicator series
        use_intrabar: True for intrabar signals, False for confirmed bar signals
        
    Returns:
        Selected series for signal generation
    """
    if use_intrabar:
        return series
    else:
        # Return series excluding last bar (confirmed bars only)
        return series.iloc[:-1] if len(series) > 1 else series


def detect_ema_crossover(fast_ema: pd.Series, slow_ema: pd.Series, 
                         hysteresis: float = 0.0) -> pd.Series:
    """
    Detect EMA crossover with optional hysteresis
    
    Args:
        fast_ema: Fast EMA series
        slow_ema: Slow EMA series
        hysteresis: Minimum difference threshold (0.0 = no hysteresis)
        
    Returns:
        Series with 'long', 'short', or 'none' values
    """
    diff = fast_ema - slow_ema
    prev_diff = diff.shift(1)
    
    # Apply hysteresis filter
    if hysteresis > 0:
        diff_threshold = abs(diff) >= hysteresis
    else:
        diff_threshold = pd.Series([True] * len(diff), index=diff.index)
    
    # Detect crossovers
    long_signal = (prev_diff <= 0) & (diff > 0) & diff_threshold
    short_signal = (prev_diff >= 0) & (diff < 0) & diff_threshold
    
    result = pd.Series(['none'] * len(diff), index=diff.index)
    result[long_signal] = 'long'
    result[short_signal] = 'short'
    
    return result


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and set defaults for configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Validated configuration with defaults
    """
    defaults = {
        'symbol': 'BTC/USDT',
        'futures_suffix': ':USDT',
        'use_futures': True,
        'margin_mode': 'isolated',
        'leverage': 10,
        'hedge_mode': False,
        'reduce_only_default': True,
        'trade_amount_usd': 100.0,
        'dry_run': False,
        'ema': {
            'fast_period': 50,
            'slow_period': 200
        },
        'heikin_ashi': {
            'enabled': True
        },
        'multi_timeframe': {
            'timeframes': {
                '1h': {'enabled': True, 'take_profit': 0.006, 'stop_loss': 0.015},
                '15m': {'enabled': True, 'take_profit': 0.006, 'stop_loss': 0.015}
            },
            'filter_tf': '1h',
            'trigger_tf': '15m'
        },
        'signal_management': {
            'single_position_only': True,
            'cooldown_after_exit': 600,
            'use_intrabar_signals': True,
            'ema_cross_hysteresis': 0.0,
            'tf_cooldown_bars': {'15m': 1, '1h': 1},
            'timeframe_validation': {
                'enabled': True,
                'min_candles_for_signal': 120,
                'require_confirmed_candle': False
            }
        },
        'risk_management': {
            'break_even_enabled': True,
            'break_even_percentage': 0.005
        },
        'logging': {
            'level': 'INFO',
            'file': 'logs/multi_ema.log',
            'detailed_timeframes': True
        },
        'telegram': {
            'enabled': True,
            'bot_token': '',
            'chat_id': ''
        }
    }
    
    # Apply defaults for missing keys
    def apply_defaults(d: Dict, defaults: Dict):
        for key, value in defaults.items():
            if key not in d:
                d[key] = value
                logging.warning(f"Missing config key '{key}', using default: {value}")
            elif isinstance(value, dict) and isinstance(d[key], dict):
                apply_defaults(d[key], value)
    
    validated_config = config.copy()
    apply_defaults(validated_config, defaults)
    
    return validated_config


def generate_signal_id() -> str:
    """Generate unique signal ID based on timestamp"""
    return f"sig_{int(time.time() * 1000)}"


def log_signal_details(logger: logging.Logger, signal_id: str, symbol: str, 
                     timeframe: str, signal_type: str, price: float, 
                     ema_fast: float, ema_slow: float, **kwargs):
    """Log detailed signal information"""
    logger.info(f"🎯 SIGNAL [{signal_id}] {symbol} {timeframe}: {signal_type.upper()} @ ${price:.4f} | EMA: Fast=${ema_fast:.4f}, Slow=${ema_slow:.4f}")
    
    for key, value in kwargs.items():
        logger.info(f"   {key}: {value}")


def log_position_details(logger: logging.Logger, symbol: str, side: str, 
                        entry_price: float, size: float, timeframe: str,
                        sl_price: float = None, tp_price: float = None,
                        leverage: int = 1, **kwargs):
    """Log detailed position information"""
    logger.info(f"📊 POSITION {symbol} {side.upper()}: {size:.4f} @ ${entry_price:.4f} ({timeframe}) | Leverage: {leverage}x")
    
    if sl_price:
        logger.info(f"   🛡️ Stop Loss: ${sl_price:.4f}")
    if tp_price:
        logger.info(f"   🎯 Take Profit: ${tp_price:.4f}")
    
    for key, value in kwargs.items():
        logger.info(f"   {key}: {value}")


def calculate_pnl_percentage(entry_price: float, current_price: float, side: str) -> float:
    """
    Calculate PnL percentage
    
    Args:
        entry_price: Entry price
        current_price: Current price
        side: Position side ('long' or 'short')
        
    Returns:
        PnL percentage
    """
    if side == 'long':
        return ((current_price - entry_price) / entry_price) * 100
    else:
        return ((entry_price - current_price) / entry_price) * 100


def format_pnl_message(pnl_pct: float) -> str:
    """Format PnL message with emoji"""
    if pnl_pct > 0:
        return f"📈 +{pnl_pct:.2f}%"
    elif pnl_pct < 0:
        return f"📉 {pnl_pct:.2f}%"
    else:
        return f"➡️ {pnl_pct:.2f}%"
