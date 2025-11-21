"""Feature engineering for Volensy LLM."""

import pandas as pd
import numpy as np
from typing import List


def add_features(df: pd.DataFrame, use_previous_bar: bool = True) -> pd.DataFrame:
    """
    Add engineered features to OHLCV DataFrame.
    
    CRITICAL: If use_previous_bar=True, features are calculated using previous bar
    to prevent data leakage (no lookahead bias).

    Features:
    - Log returns (multiple periods)
    - Rolling sums (3 periods)
    - HL range and body
    - Upper/lower wick ratios
    - EMA(10/20/50/200) distances and slopes
    - RSI(14)
    - Volume spike (vol / rolling mean(20))
    - 200-period rolling z-score for all features

    Args:
        df: DataFrame with open, high, low, close, volume
        use_previous_bar: If True, use previous bar's OHLC for current bar features
                         (prevents data leakage). If False, use current bar (legacy).

    Returns:
        DataFrame with added feature columns
    """
    df = df.copy()
    
    # DATA LEAKAGE PREVENTION: Use previous bar's close for calculations
    # This ensures features don't include information from the current bar
    if use_previous_bar:
        # Shift close prices forward so we use previous bar's close
        close_for_calc = df["close"].shift(1).fillna(df["close"].iloc[0])
    else:
        close_for_calc = df["close"]
    
    # Log returns (multiple periods) - uses previous bar
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
    df["log_ret_3"] = df["log_ret"].rolling(3).sum()
    df["log_ret_5"] = df["log_ret"].rolling(5).sum()
    
    # HL range and body - use PREVIOUS bar's high/low/open/close
    if use_previous_bar:
        prev_high = df["high"].shift(1).fillna(df["high"].iloc[0])
        prev_low = df["low"].shift(1).fillna(df["low"].iloc[0])
        prev_open = df["open"].shift(1).fillna(df["open"].iloc[0])
        prev_close = df["close"].shift(1).fillna(df["close"].iloc[0])
        
        df["hl_range"] = prev_high - prev_low
        df["body"] = abs(prev_close - prev_open)
        df["hl_range_norm"] = df["hl_range"] / prev_close
        df["body_norm"] = df["body"] / prev_close
        
        # Upper/lower wick ratios - use previous bar
        prev_max_oc = pd.concat([prev_open, prev_close], axis=1).max(axis=1)
        prev_min_oc = pd.concat([prev_open, prev_close], axis=1).min(axis=1)
        df["upper_wick"] = prev_high - prev_max_oc
        df["lower_wick"] = prev_min_oc - prev_low
    else:
        # Legacy: use current bar (may cause data leakage)
        df["hl_range"] = df["high"] - df["low"]
        df["body"] = abs(df["close"] - df["open"])
        df["hl_range_norm"] = df["hl_range"] / df["close"]
        df["body_norm"] = df["body"] / df["close"]
        
        df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
        df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    
    df["upper_wick_ratio"] = np.where(df["hl_range"] > 0, df["upper_wick"] / df["hl_range"], 0)
    df["lower_wick_ratio"] = np.where(df["hl_range"] > 0, df["lower_wick"] / df["hl_range"], 0)
    
    # EMA distances and slopes - use previous bar's close for distance
    # Note: EMA itself can use all historical data, but distance calculation uses previous bar
    for period in [10, 20, 50, 200]:
        # EMA can use current close (it's a lagging indicator)
        ema = df["close"].ewm(span=period, adjust=False).mean()
        df[f"ema{period}"] = ema
        # Distance uses previous bar's close to prevent leakage
        df[f"ema{period}_dist"] = (close_for_calc - ema.shift(1).fillna(ema.iloc[0])) / close_for_calc  # Relative distance
        df[f"ema{period}_slope"] = ema.diff(3) / ema  # 3-bar slope
    
    # RSI(14) - uses previous bar's close for delta calculation
    delta = close_for_calc.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # Volume spike - use previous bar's volume to prevent leakage
    if use_previous_bar:
        prev_volume = df["volume"].shift(1).fillna(df["volume"].iloc[0])
        vol_mean = prev_volume.rolling(20, min_periods=1).mean()
        df["vol_spike"] = np.where(vol_mean > 0, prev_volume / vol_mean, 0)
    else:
        vol_mean = df["volume"].rolling(20).mean()
        df["vol_spike"] = np.where(vol_mean > 0, df["volume"] / vol_mean, 0)
    
    # ============================================================================
    # TREND REVERSAL DETECTION FEATURES (Early Signal Detection)
    # ============================================================================
    
    # 1. ADX (Average Directional Index) - Trend strength
    # ADX > 25 = Strong trend, ADX < 20 = Weak trend (reversal possible)
    high_vals = df["high"].values
    low_vals = df["low"].values
    close_vals = df["close"].values
    
    # True Range
    tr = np.zeros(len(df))
    tr[0] = high_vals[0] - low_vals[0]
    for i in range(1, len(df)):
        tr[i] = max(
            high_vals[i] - low_vals[i],
            abs(high_vals[i] - close_vals[i-1]),
            abs(low_vals[i] - close_vals[i-1])
        )
    
    # Directional Movement
    plus_dm = np.zeros(len(df))
    minus_dm = np.zeros(len(df))
    
    for i in range(1, len(df)):
        up_move = high_vals[i] - high_vals[i-1]
        down_move = low_vals[i-1] - low_vals[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
    
    # Smooth TR, +DM, -DM
    period_adx = 14
    atr_smooth = pd.Series(tr, index=df.index).rolling(period_adx, min_periods=1).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(period_adx, min_periods=1).mean() / atr_smooth)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(period_adx, min_periods=1).mean() / atr_smooth)
    
    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.rolling(period_adx, min_periods=1).mean()
    
    df["adx"] = adx.fillna(0)
    df["plus_di"] = plus_di.fillna(0)
    df["minus_di"] = minus_di.fillna(0)
    df["adx_weak_trend"] = (adx < 20).astype(int)  # Weak trend = reversal possible
    
    # 2. Stochastic Oscillator - Overbought/Oversold
    period_stoch = 14
    low_min = df["low"].rolling(period_stoch, min_periods=1).min()
    high_max = df["high"].rolling(period_stoch, min_periods=1).max()
    df["stoch_k"] = 100 * (close_for_calc - low_min) / (high_max - low_min + 1e-10)
    df["stoch_d"] = df["stoch_k"].rolling(3, min_periods=1).mean()
    df["stoch_overbought"] = (df["stoch_k"] > 80).astype(int)  # Overbought = SHORT signal
    df["stoch_oversold"] = (df["stoch_k"] < 20).astype(int)  # Oversold = LONG signal
    
    # 3. MACD Histogram Momentum
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    
    df["macd_histogram"] = histogram
    df["macd_histogram_momentum"] = histogram.diff(3).fillna(0)  # 3-bar momentum
    df["macd_bearish"] = ((macd_line < signal_line) & (histogram < 0)).astype(int)
    df["macd_bullish"] = ((macd_line > signal_line) & (histogram > 0)).astype(int)
    
    # 4. Volume-Price Divergence (Early Reversal Signal)
    price_change = close_for_calc.pct_change().fillna(0)
    if use_previous_bar:
        prev_volume = df["volume"].shift(1).fillna(df["volume"].iloc[0])
        volume_change = prev_volume.pct_change().fillna(0)
    else:
        volume_change = df["volume"].pct_change().fillna(0)
    
    # Price up but volume down = Weak move (reversal possible)
    # Price down but volume up = Strong move (continuation or reversal)
    df["volume_price_divergence"] = np.where(
        (price_change > 0) & (volume_change < -0.1), 1,  # Bearish divergence
        np.where(
            (price_change < 0) & (volume_change > 0.1), -1,  # Bullish divergence
            0
        )
    )
    
    # 5. RSI Overbought/Oversold Zones
    df["rsi_overbought"] = (df["rsi"] > 70).astype(int)
    df["rsi_oversold"] = (df["rsi"] < 30).astype(int)
    
    # 6. ATR Expansion (Volatility increase = trend continuation or reversal)
    atr_val = pd.Series(tr, index=df.index).rolling(14, min_periods=1).mean()
    atr_expansion = atr_val / (atr_val.rolling(20, min_periods=1).mean() + 1e-10)
    df["atr_expansion"] = atr_expansion.fillna(1.0)
    
    # 7. RSI Divergence Detection (Improved Algorithm)
    # Price makes higher high but RSI makes lower high = Bearish divergence
    # Price makes lower low but RSI makes higher low = Bullish divergence
    df["rsi_divergence_bearish"] = 0
    df["rsi_divergence_bullish"] = 0
    
    # Look for peaks and troughs in last 20 bars
    lookback_divergence = 20
    for i in range(lookback_divergence, len(df)):
        # Get recent price and RSI values
        recent_prices = df["high"].iloc[i-lookback_divergence:i+1].values
        recent_lows = df["low"].iloc[i-lookback_divergence:i+1].values
        recent_rsi = df["rsi"].iloc[i-lookback_divergence:i+1].values
        
        # Find two most recent peaks (for bearish divergence)
        peaks_price = []
        peaks_rsi = []
        for j in range(1, len(recent_prices)-1):
            if recent_prices[j] > recent_prices[j-1] and recent_prices[j] > recent_prices[j+1]:
                peaks_price.append((j, recent_prices[j]))
            if recent_rsi[j] > recent_rsi[j-1] and recent_rsi[j] > recent_rsi[j+1]:
                peaks_rsi.append((j, recent_rsi[j]))
        
        # Find two most recent troughs (for bullish divergence)
        troughs_price = []
        troughs_rsi = []
        for j in range(1, len(recent_lows)-1):
            if recent_lows[j] < recent_lows[j-1] and recent_lows[j] < recent_lows[j+1]:
                troughs_price.append((j, recent_lows[j]))
            if recent_rsi[j] < recent_rsi[j-1] and recent_rsi[j] < recent_rsi[j+1]:
                troughs_rsi.append((j, recent_rsi[j]))
        
        # Bearish divergence: Price higher high, RSI lower high
        if len(peaks_price) >= 2 and len(peaks_rsi) >= 2:
            price_trend = peaks_price[-1][1] > peaks_price[-2][1]  # Higher high
            rsi_trend = peaks_rsi[-1][1] < peaks_rsi[-2][1]  # Lower high
            if price_trend and rsi_trend:
                df.loc[df.index[i], "rsi_divergence_bearish"] = 1
        
        # Bullish divergence: Price lower low, RSI higher low
        if len(troughs_price) >= 2 and len(troughs_rsi) >= 2:
            price_trend = troughs_price[-1][1] < troughs_price[-2][1]  # Lower low
            rsi_trend = troughs_rsi[-1][1] > troughs_rsi[-2][1]  # Higher low
            if price_trend and rsi_trend:
                df.loc[df.index[i], "rsi_divergence_bullish"] = 1
    
    # 8. MACD Divergence Detection
    # Price vs MACD histogram divergence
    df["macd_divergence_bearish"] = 0
    df["macd_divergence_bullish"] = 0
    
    for i in range(lookback_divergence, len(df)):
        recent_prices = df["high"].iloc[i-lookback_divergence:i+1].values
        recent_lows = df["low"].iloc[i-lookback_divergence:i+1].values
        recent_macd = df["macd_histogram"].iloc[i-lookback_divergence:i+1].values
        
        # Find peaks and troughs
        peaks_price = []
        peaks_macd = []
        for j in range(1, len(recent_prices)-1):
            if recent_prices[j] > recent_prices[j-1] and recent_prices[j] > recent_prices[j+1]:
                peaks_price.append((j, recent_prices[j]))
            if recent_macd[j] > recent_macd[j-1] and recent_macd[j] > recent_macd[j+1]:
                peaks_macd.append((j, recent_macd[j]))
        
        troughs_price = []
        troughs_macd = []
        for j in range(1, len(recent_lows)-1):
            if recent_lows[j] < recent_lows[j-1] and recent_lows[j] < recent_lows[j+1]:
                troughs_price.append((j, recent_lows[j]))
            if recent_macd[j] < recent_macd[j-1] and recent_macd[j] < recent_macd[j+1]:
                troughs_macd.append((j, recent_macd[j]))
        
        # Bearish divergence: Price higher high, MACD lower high
        if len(peaks_price) >= 2 and len(peaks_macd) >= 2:
            price_trend = peaks_price[-1][1] > peaks_price[-2][1]
            macd_trend = peaks_macd[-1][1] < peaks_macd[-2][1]
            if price_trend and macd_trend:
                df.loc[df.index[i], "macd_divergence_bearish"] = 1
        
        # Bullish divergence: Price lower low, MACD higher low
        if len(troughs_price) >= 2 and len(troughs_macd) >= 2:
            price_trend = troughs_price[-1][1] < troughs_price[-2][1]
            macd_trend = troughs_macd[-1][1] > troughs_macd[-2][1]
            if price_trend and macd_trend:
                df.loc[df.index[i], "macd_divergence_bullish"] = 1
    
    # 9. Support/Resistance (Pivot Points) Detection
    # Pivot high/low detection - Break of pivot = Trend reversal
    pivot_period = 5
    df["pivot_high"] = 0.0  # Float type
    df["pivot_low"] = 0.0  # Float type
    df["pivot_high_break"] = 0
    df["pivot_low_break"] = 0
    
    # Store recent pivot levels
    recent_pivot_highs = []
    recent_pivot_lows = []
    
    for i in range(pivot_period, len(df) - pivot_period):
        # Pivot High: High is highest in pivot_period bars on both sides
        is_pivot_high = True
        center_high = df["high"].iloc[i]
        for j in range(i - pivot_period, i + pivot_period + 1):
            if j != i and df["high"].iloc[j] >= center_high:
                is_pivot_high = False
                break
        
        if is_pivot_high:
            df.loc[df.index[i], "pivot_high"] = float(center_high)
            recent_pivot_highs.append((i, center_high))
            # Keep only last 5 pivots
            if len(recent_pivot_highs) > 5:
                recent_pivot_highs.pop(0)
        
        # Pivot Low: Low is lowest in pivot_period bars on both sides
        is_pivot_low = True
        center_low = df["low"].iloc[i]
        for j in range(i - pivot_period, i + pivot_period + 1):
            if j != i and df["low"].iloc[j] <= center_low:
                is_pivot_low = False
                break
        
        if is_pivot_low:
            df.loc[df.index[i], "pivot_low"] = float(center_low)
            recent_pivot_lows.append((i, center_low))
            # Keep only last 5 pivots
            if len(recent_pivot_lows) > 5:
                recent_pivot_lows.pop(0)
        
        # Check for pivot breaks (trend reversal signal)
        current_price = df["close"].iloc[i]
        
        # Break below pivot high = Bearish reversal
        if recent_pivot_highs:
            latest_pivot_high = recent_pivot_highs[-1][1]
            if current_price < latest_pivot_high * 0.998:  # 0.2% below pivot
                df.loc[df.index[i], "pivot_high_break"] = 1
        
        # Break above pivot low = Bullish reversal
        if recent_pivot_lows:
            latest_pivot_low = recent_pivot_lows[-1][1]
            if current_price > latest_pivot_low * 1.002:  # 0.2% above pivot
                df.loc[df.index[i], "pivot_low_break"] = 1
    
    # 10. Volume Profile Analysis (Enhanced)
    # Volume clustering and exhaustion detection
    df["volume_cluster_high"] = 0
    df["volume_exhaustion"] = 0
    
    # Volume clustering: High volume areas (potential support/resistance)
    volume_ma = df["volume"].rolling(20, min_periods=1).mean()
    volume_std = df["volume"].rolling(20, min_periods=1).std()
    
    # High volume cluster: Volume > MA + 2*STD
    df["volume_cluster_high"] = (df["volume"] > (volume_ma + 2 * volume_std)).astype(int)
    
    # Volume exhaustion: High volume followed by decreasing volume (reversal signal)
    for i in range(10, len(df)):
        recent_volumes = df["volume"].iloc[i-10:i+1].values
        if len(recent_volumes) >= 5:
            # Check if volume was high and now decreasing
            max_vol_idx = np.argmax(recent_volumes[:-1])  # Max in last 10 bars (excluding current)
            if max_vol_idx < len(recent_volumes) - 3:  # Max was at least 3 bars ago
                if recent_volumes[-1] < recent_volumes[max_vol_idx] * 0.7:  # Volume dropped 30%
                    df.loc[df.index[i], "volume_exhaustion"] = 1
    
    # 11. Trend Exhaustion Score (Enhanced - Combined indicator)
    # High score = Trend is exhausted, reversal likely
    trend_exhaustion = (
        (df["rsi_overbought"] * 0.20) +  # RSI overbought
        (df["stoch_overbought"] * 0.20) +  # Stochastic overbought
        (df["adx_weak_trend"] * 0.15) +  # Weak trend
        ((df["volume_price_divergence"] > 0) * 0.10) +  # Volume divergence
        ((df["macd_histogram_momentum"] < 0) * 0.10) +  # MACD momentum weakening
        (df["rsi_divergence_bearish"] * 0.10) +  # RSI bearish divergence
        (df["macd_divergence_bearish"] * 0.10) +  # MACD bearish divergence
        (df["pivot_high_break"] * 0.05)  # Pivot break
    )
    df["trend_exhaustion"] = trend_exhaustion
    
    # 200-period rolling z-score normalization for all features
    feature_cols = [
        "log_ret", "log_ret_3", "log_ret_5",
        "hl_range_norm", "body_norm",
        "upper_wick_ratio", "lower_wick_ratio",
        "ema10_dist", "ema10_slope",
        "ema20_dist", "ema20_slope",
        "ema50_dist", "ema50_slope",
        "ema200_dist", "ema200_slope",
        "rsi",
        "vol_spike",
        # Trend reversal detection features
        "adx", "plus_di", "minus_di", "adx_weak_trend",
        "stoch_k", "stoch_d", "stoch_overbought", "stoch_oversold",
        "macd_histogram", "macd_histogram_momentum", "macd_bearish", "macd_bullish",
        "volume_price_divergence",
        "rsi_overbought", "rsi_oversold",
        "atr_expansion",
        # Enhanced divergence detection
        "rsi_divergence_bearish", "rsi_divergence_bullish",
        "macd_divergence_bearish", "macd_divergence_bullish",
        # Support/Resistance
        "pivot_high", "pivot_low", "pivot_high_break", "pivot_low_break",
        # Volume profile
        "volume_cluster_high", "volume_exhaustion",
        # Combined indicator
        "trend_exhaustion"
    ]
    
    for col in feature_cols:
        if col in df.columns:
            rolling_mean = df[col].rolling(200, min_periods=1).mean()
            rolling_std = df[col].rolling(200, min_periods=1).std()
            df[f"{col}_z"] = np.where(
                rolling_std > 0,
                (df[col] - rolling_mean) / rolling_std,
                0
            )
    
    # Clean NaN
    df = df.fillna(0).replace([np.inf, -np.inf], 0)
    
    return df


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """
    Extract feature column names (ending with _z).

    Args:
        df: DataFrame with engineered features

    Returns:
        List of feature column names
    """
    return [col for col in df.columns if col.endswith("_z")]


def prepare_feature_matrix(df: pd.DataFrame, feature_cols: List[str]) -> np.ndarray:
    """
    Extract feature matrix from DataFrame.

    Args:
        df: DataFrame with features
        feature_cols: List of feature column names

    Returns:
        (N, F) numpy array
    """
    feature_df = df[feature_cols].copy()
    # Fill any remaining NaN/Inf
    feature_df = feature_df.fillna(0).replace([np.inf, -np.inf], 0)
    return feature_df.values
