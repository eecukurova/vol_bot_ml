"""
ATR with Super Trend Strategy Implementation
Based on Pine Script v4 strategy
"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional


def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Heikin Ashi candles.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        DataFrame with Heikin Ashi OHLC
    """
    ha_df = df.copy()
    
    # HA Close = (O + H + L + C) / 4
    ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    # HA Open = (previous HA Open + previous HA Close) / 2
    # Use iloc for positional indexing (works with datetime index)
    ha_open_values = []
    ha_open_values.append((df.iloc[0]['open'] + df.iloc[0]['close']) / 2)
    
    for i in range(1, len(ha_df)):
        ha_open_values.append((ha_open_values[i-1] + ha_df.iloc[i-1]['ha_close']) / 2)
    
    ha_df['ha_open'] = ha_open_values
    
    # HA High = max(H, HA Open, HA Close)
    ha_df['ha_high'] = ha_df[['high', 'ha_open', 'ha_close']].max(axis=1)
    
    # HA Low = min(L, HA Open, HA Close)
    ha_df['ha_low'] = ha_df[['low', 'ha_open', 'ha_close']].min(axis=1)
    
    return ha_df


def calculate_atr(df: pd.DataFrame, period: int = 10, use_heikin_ashi: bool = False) -> pd.Series:
    """
    Calculate ATR (Average True Range) using Wilder's smoothing.
    
    Args:
        df: DataFrame with OHLCV data
        period: ATR period (default: 10)
        use_heikin_ashi: Use Heikin Ashi candles for ATR calculation (default: False)
        
    Returns:
        ATR values as Series
    """
    # Use Heikin Ashi if enabled
    if use_heikin_ashi:
        ha_df = calculate_heikin_ashi(df)
        high = ha_df['ha_high'].values
        low = ha_df['ha_low'].values
        close = ha_df['ha_close'].values
    else:
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
    
    n = len(close)
    tr = np.zeros(n)
    atr = np.zeros(n)
    
    # Calculate True Range
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    # Calculate ATR using Wilder's smoothing
    if n >= period:
        atr[period-1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    return pd.Series(atr, index=df.index)


def calculate_atr_trailing_stop(
    df: pd.DataFrame,
    atr_period: int = 10,
    key_value: float = 3.0,
    use_heikin_ashi: bool = False
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate ATR Trailing Stop based on Pine Script logic.
    
    Args:
        df: DataFrame with OHLCV data
        atr_period: ATR period (default: 10)
        key_value: Key value for sensitivity (default: 3.0)
        use_heikin_ashi: Use Heikin Ashi candles (default: False)
        
    Returns:
        Tuple of (xATRTrailingStop, position, src)
    """
    # Calculate Heikin Ashi if needed
    if use_heikin_ashi:
        ha_df = calculate_heikin_ashi(df)
        src = ha_df['ha_close']
    else:
        src = df['close']
    
    # Calculate ATR (use Heikin Ashi if enabled)
    xATR = calculate_atr(df, period=atr_period, use_heikin_ashi=use_heikin_ashi)
    nLoss = key_value * xATR
    
    # Initialize arrays
    n = len(df)
    xATRTrailingStop = np.zeros(n)
    pos = np.zeros(n)
    
    # Calculate trailing stop
    for i in range(n):
        if i == 0:
            # Pine Script: xATRTrailingStop[0] = src[0] - nLoss[0] (or src[0] + nLoss[0] if negative)
            # Initial value: src - nLoss (for long) or src + nLoss (for short)
            # Default to src - nLoss
            xATRTrailingStop[i] = src.iloc[i] - nLoss.iloc[i] if nLoss.iloc[i] > 0 else src.iloc[i]
            pos[i] = 0
        else:
            prev_stop = xATRTrailingStop[i-1] if xATRTrailingStop[i-1] != 0 else 0
            prev_src = src.iloc[i-1]
            curr_src = src.iloc[i]
            curr_nLoss = nLoss.iloc[i] if nLoss.iloc[i] > 0 else 0
            
            # Trailing stop calculation (Pine Script logic)
            if curr_src > prev_stop and prev_src > prev_stop:
                xATRTrailingStop[i] = max(prev_stop, curr_src - curr_nLoss)
            elif curr_src < prev_stop and prev_src < prev_stop:
                xATRTrailingStop[i] = min(prev_stop, curr_src + curr_nLoss)
            elif curr_src > prev_stop:
                xATRTrailingStop[i] = curr_src - curr_nLoss
            else:
                xATRTrailingStop[i] = curr_src + curr_nLoss
            
            # Position calculation
            if prev_src < prev_stop and curr_src > prev_stop:
                pos[i] = 1  # Long
            elif prev_src > prev_stop and curr_src < prev_stop:
                pos[i] = -1  # Short
            else:
                pos[i] = pos[i-1] if i > 0 else 0
    
    return pd.Series(xATRTrailingStop, index=df.index), pd.Series(pos, index=df.index), src


def calculate_super_trend(
    df: pd.DataFrame,
    atr_period: int = 10,
    factor: float = 1.5,
    use_heikin_ashi: bool = False
) -> pd.Series:
    """
    Calculate Super Trend indicator.
    
    Args:
        df: DataFrame with OHLCV data
        atr_period: ATR period (default: 10)
        factor: Multiplier for Super Trend (default: 1.5)
        use_heikin_ashi: Use Heikin Ashi candles (default: False)
        
    Returns:
        Super Trend line as Series
    """
    xATR = calculate_atr(df, period=atr_period, use_heikin_ashi=use_heikin_ashi)
    superTrend = xATR * factor
    
    # Use Heikin Ashi if enabled
    if use_heikin_ashi:
        ha_df = calculate_heikin_ashi(df)
        high_col = ha_df['ha_high']
        low_col = ha_df['ha_low']
        close_col = ha_df['ha_close']
    else:
        high_col = df['high']
        low_col = df['low']
        close_col = df['close']
    
    hl2 = (high_col + low_col) / 2
    trendUp = hl2 - superTrend
    trendDown = hl2 + superTrend
    
    n = len(df)
    superTrendLine = np.zeros(n)
    
    for i in range(n):
        if i == 0:
            superTrendLine[i] = trendDown.iloc[i]
        else:
            prev_line = superTrendLine[i-1]
            curr_close = close_col.iloc[i]
            
            if curr_close > prev_line:
                superTrendLine[i] = max(trendUp.iloc[i], prev_line)
            else:
                superTrendLine[i] = min(trendDown.iloc[i], prev_line)
            
            # Final adjustment
            if curr_close > superTrendLine[i]:
                superTrendLine[i] = trendDown.iloc[i]
            else:
                superTrendLine[i] = trendUp.iloc[i]
    
    return pd.Series(superTrendLine, index=df.index)


def get_atr_supertrend_signals(
    df: pd.DataFrame,
    atr_period: int = 10,
    key_value: float = 3.0,
    super_trend_factor: float = 1.5,
    use_heikin_ashi: bool = False,
    use_previous_bar: bool = True  # Pine Script: onlyOnClose = true -> use previous bar for signal
) -> Tuple[Optional[str], dict]:
    """
    Get ATR + Super Trend trading signals.
    
    Args:
        df: DataFrame with OHLCV data (must have at least 2 rows)
        atr_period: ATR period (default: 10)
        key_value: Key value for sensitivity (default: 3.0)
        super_trend_factor: Super Trend multiplier (default: 1.5)
        use_heikin_ashi: Use Heikin Ashi candles (default: False)
        use_previous_bar: If True, check signal on previous bar (barstate.isconfirmed logic)
                          This ensures signal is generated at bar close, not during bar formation
        
    Returns:
        Tuple of (side, signal_info)
        side: "LONG", "SHORT", or None
        signal_info: Dictionary with signal details
    """
    if len(df) < max(atr_period, 2):
        return None, {}
    
    # Pine Script: onlyOnClose = true -> signal is generated on bar close
    # This means we check the PREVIOUS bar for signal, not the current (forming) bar
    if use_previous_bar and len(df) >= 2:
        # Use previous bar for signal detection (bar that just closed)
        signal_df = df.iloc[:-1].copy()  # All bars except the last (current forming bar)
    else:
        # Use current bar (for backtesting or when onlyOnClose = false)
        signal_df = df
    
    if len(signal_df) < max(atr_period, 2):
        return None, {}
    
    # Calculate ATR Trailing Stop on signal_df
    xATRTrailingStop, pos, src = calculate_atr_trailing_stop(
        signal_df, atr_period=atr_period, key_value=key_value, use_heikin_ashi=use_heikin_ashi
    )
    
    # Calculate Super Trend (also use Heikin Ashi if enabled)
    superTrendLine = calculate_super_trend(
        signal_df, 
        atr_period=atr_period, 
        factor=super_trend_factor,
        use_heikin_ashi=use_heikin_ashi
    )
    
    # Get current and previous values from signal_df (the bar that just closed)
    curr_src = src.iloc[-1]
    prev_src = src.iloc[-2] if len(src) > 1 else src.iloc[-1]
    
    curr_stop = xATRTrailingStop.iloc[-1]
    prev_stop = xATRTrailingStop.iloc[-2] if len(xATRTrailingStop) > 1 else xATRTrailingStop.iloc[-1]
    
    curr_pos = pos.iloc[-1]
    prev_pos = pos.iloc[-2] if len(pos) > 1 else 0
    
    # For Super Trend comparison, use the same source as src (Heikin Ashi or regular close)
    if use_heikin_ashi:
        ha_df = calculate_heikin_ashi(signal_df)
        curr_close = ha_df['ha_close'].iloc[-1]
        prev_close = ha_df['ha_close'].iloc[-2] if len(ha_df) > 1 else ha_df['ha_close'].iloc[-1]
    else:
        curr_close = signal_df['close'].iloc[-1]
        prev_close = signal_df['close'].iloc[-2] if len(signal_df) > 1 else signal_df['close'].iloc[-1]
    
    curr_superTrend = superTrendLine.iloc[-1]
    prev_superTrend = superTrendLine.iloc[-2] if len(superTrendLine) > 1 else superTrendLine.iloc[-1]
    
    # Calculate EMA(1) for crossover detection (Pine Script: ema = ema(src, 1))
    # Pine Script EMA formula: ema = (src * 2 + ema[1] * (length - 1)) / (length + 1)
    # For length=1: ema = (src * 2 + ema[1] * 0) / 2 = src
    # But Pine Script uses a different initialization, so we calculate it properly
    # Using pandas ewm with span=1 (which is equivalent to Pine Script's ema(src, 1))
    ema_src = src.ewm(span=1, adjust=False).mean()
    
    curr_ema = ema_src.iloc[-1]
    prev_ema = ema_src.iloc[-2] if len(ema_src) > 1 else ema_src.iloc[-1]
    
    # Pine Script: above = crossover(ema, xATRTrailingStop)
    # crossover(ema, xATRTrailingStop) = ema önceki bar'da <= xATRTrailingStop, şimdi > xATRTrailingStop
    above = curr_ema > curr_stop and prev_ema <= prev_stop
    
    # Pine Script: below = crossover(xATRTrailingStop, ema)
    # crossover(xATRTrailingStop, ema) = xATRTrailingStop önceki bar'da <= ema, şimdi > ema
    # Bu da şu demek: ema önceki bar'da >= xATRTrailingStop, şimdi < xATRTrailingStop
    below = curr_stop > curr_ema and prev_stop <= prev_ema
    
    # Pine Script: buy = src > xATRTrailingStop and above
    buy_signal = curr_src > curr_stop and above
    
    # Pine Script: sell = src < xATRTrailingStop and below
    sell_signal = curr_src < curr_stop and below
    
    # Super Trend signals (sadece alert için, sinyal üretiminde kullanılmıyor)
    buy_super_trend = curr_close > curr_superTrend and prev_close <= prev_superTrend
    sell_super_trend = curr_close < curr_superTrend and prev_close >= prev_superTrend
    
    # Pine Script v4: buy = src > xATRTrailingStop and above
    # Pine Script v4: sell = src < xATRTrailingStop and below
    # SuperTrend sadece alertcondition için, sinyal üretiminde kullanılmıyor!
    side = None
    if buy_signal:
        side = "LONG"
    elif sell_signal:
        side = "SHORT"
    
    signal_info = {
        "atr_trailing_stop": float(curr_stop),
        "current_price": float(curr_close),
        "position": int(curr_pos),
        "super_trend": float(curr_superTrend),
        "buy_signal": bool(buy_signal),
        "sell_signal": bool(sell_signal),
        "buy_super_trend": bool(buy_super_trend),  # Sadece alert için
        "sell_super_trend": bool(sell_super_trend),  # Sadece alert için
        "above": bool(above),
        "below": bool(below)
    }
    
    return side, signal_info

