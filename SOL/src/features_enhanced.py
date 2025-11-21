"""Enhanced feature engineering for early trend reversal detection."""

import pandas as pd
import numpy as np
from typing import List


def add_reversal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add trend reversal detection features.
    
    These features help detect trend reversals EARLY (before they happen).
    
    Args:
        df: DataFrame with OHLCV and existing features
        
    Returns:
        DataFrame with added reversal features
    """
    df = df.copy()
    
    # 1. ADX (Average Directional Index) - Trend strength
    # ADX > 25 = Strong trend, ADX < 20 = Weak trend (reversal possible)
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    
    # True Range
    tr = np.zeros(len(df))
    tr[0] = high[0] - low[0]
    for i in range(1, len(df)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    # Directional Movement
    plus_dm = np.zeros(len(df))
    minus_dm = np.zeros(len(df))
    
    for i in range(1, len(df)):
        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
    
    # Smooth TR, +DM, -DM
    period = 14
    atr = pd.Series(tr).rolling(period).mean()
    plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / atr)
    
    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    
    df["adx"] = adx.fillna(0)
    df["plus_di"] = plus_di.fillna(0)
    df["minus_di"] = minus_di.fillna(0)
    
    # 2. RSI Divergence Detection
    # Price makes higher high but RSI makes lower high = Bearish divergence
    rsi = df.get("rsi", pd.Series(50, index=df.index))
    
    # Find local peaks and troughs
    df["price_peak"] = (df["high"] > df["high"].shift(1)) & (df["high"] > df["high"].shift(-1))
    df["price_trough"] = (df["low"] < df["low"].shift(1)) & (df["low"] < df["low"].shift(-1))
    
    # RSI peaks and troughs
    df["rsi_peak"] = (rsi > rsi.shift(1)) & (rsi > rsi.shift(-1))
    df["rsi_trough"] = (rsi < rsi.shift(1)) & (rsi < rsi.shift(-1))
    
    # Divergence signals
    df["bearish_divergence"] = 0
    df["bullish_divergence"] = 0
    
    # Look back 10 bars for divergence
    for i in range(10, len(df)):
        # Bearish divergence: Price higher high, RSI lower high
        recent_price_peaks = df["high"].iloc[i-10:i][df["price_peak"].iloc[i-10:i]]
        recent_rsi_peaks = rsi.iloc[i-10:i][df["rsi_peak"].iloc[i-10:i]]
        
        if len(recent_price_peaks) >= 2 and len(recent_rsi_peaks) >= 2:
            price_trend = recent_price_peaks.iloc[-1] > recent_price_peaks.iloc[-2]
            rsi_trend = recent_rsi_peaks.iloc[-1] < recent_rsi_peaks.iloc[-2]
            
            if price_trend and rsi_trend:
                df.loc[df.index[i], "bearish_divergence"] = 1
        
        # Bullish divergence: Price lower low, RSI higher low
        recent_price_troughs = df["low"].iloc[i-10:i][df["price_trough"].iloc[i-10:i]]
        recent_rsi_troughs = rsi.iloc[i-10:i][df["rsi_trough"].iloc[i-10:i]]
        
        if len(recent_price_troughs) >= 2 and len(recent_rsi_troughs) >= 2:
            price_trend = recent_price_troughs.iloc[-1] < recent_price_troughs.iloc[-2]
            rsi_trend = recent_rsi_troughs.iloc[-1] > recent_rsi_troughs.iloc[-2]
            
            if price_trend and rsi_trend:
                df.loc[df.index[i], "bullish_divergence"] = 1
    
    # 3. MACD Histogram Momentum
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_histogram"] = histogram
    df["macd_histogram_momentum"] = histogram.diff(3)  # 3-bar momentum
    
    # 4. Stochastic Oscillator
    period = 14
    low_min = df["low"].rolling(period).min()
    high_max = df["high"].rolling(period).max()
    df["stoch_k"] = 100 * (df["close"] - low_min) / (high_max - low_min)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()
    df["stoch_overbought"] = (df["stoch_k"] > 80).astype(int)
    df["stoch_oversold"] = (df["stoch_k"] < 20).astype(int)
    
    # 5. Volume-Price Divergence
    volume = df["volume"]
    price_change = df["close"].pct_change()
    volume_change = volume.pct_change()
    
    # Price up but volume down = Weak move (reversal possible)
    df["volume_price_divergence"] = np.where(
        (price_change > 0) & (volume_change < 0), 1,
        np.where(
            (price_change < 0) & (volume_change > 0), -1,
            0
        )
    )
    
    # 6. Momentum Exhaustion
    # RSI overbought/oversold zones
    df["rsi_overbought"] = (rsi > 70).astype(int)
    df["rsi_oversold"] = (rsi < 30).astype(int)
    
    # ATR expansion (volatility increase = trend continuation or reversal)
    atr_val = pd.Series(tr).rolling(14).mean()
    atr_expansion = atr_val / atr_val.rolling(20).mean()
    df["atr_expansion"] = atr_expansion.fillna(1.0)
    
    # 7. Trend Strength Score
    # Combine multiple indicators
    trend_strength = (
        (df["adx"] > 25).astype(int) * 0.3 +  # Strong trend
        (abs(df["ema50_dist"]) < 0.01).astype(int) * 0.2 +  # Price near EMA50
        (df["vol_spike"] > 1.5).astype(int) * 0.2 +  # High volume
        (df["atr_expansion"] > 1.2).astype(int) * 0.3  # Volatility expansion
    )
    df["trend_strength"] = trend_strength
    
    # Clean NaN
    df = df.fillna(0).replace([np.inf, -np.inf], 0)
    
    return df


def get_reversal_feature_columns() -> List[str]:
    """
    Get list of reversal feature column names.
    
    Returns:
        List of feature column names for reversal detection
    """
    return [
        "adx",
        "plus_di",
        "minus_di",
        "bearish_divergence",
        "bullish_divergence",
        "macd",
        "macd_signal",
        "macd_histogram",
        "macd_histogram_momentum",
        "stoch_k",
        "stoch_d",
        "stoch_overbought",
        "stoch_oversold",
        "volume_price_divergence",
        "rsi_overbought",
        "rsi_oversold",
        "atr_expansion",
        "trend_strength"
    ]

