"""
TWMA (Time Weighted Moving Average) Trend Strategy - Enhanced Version
4H Zaman Ağırlıklı Trend Stratejisi - Filtrelerle Geliştirilmiş
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class TWMATrendEnhancedStrategy:
    """TWMA Trend Strategy - Enhanced with Filters"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        Initialize Enhanced TWMA Trend Strategy
        
        Args:
            params: Strategy parameters
                - twma_len: TWMA period (default: 20)
                - atr_len: ATR period (default: 14)
                - sl_atr_mult: Stop Loss ATR multiplier (default: 0.5)
                - tp_atr_mult: Take Profit ATR multiplier (default: 1.0)
                - pivot_len: Pivot left/right bar count (default: 5)
                
                # Filters
                - use_rsi_filter: Enable RSI filter (default: True)
                - rsi_length: RSI period (default: 14)
                - rsi_oversold: RSI oversold level (default: 30)
                - rsi_overbought: RSI overbought level (default: 70)
                
                - use_macd_filter: Enable MACD filter (default: True)
                - macd_fast: MACD fast period (default: 12)
                - macd_slow: MACD slow period (default: 26)
                - macd_signal: MACD signal period (default: 9)
                
                - use_volume_filter: Enable volume filter (default: True)
                - volume_ma_length: Volume MA length (default: 20)
                - volume_multiplier: Volume multiplier threshold (default: 1.2)
                
                - use_ema_filter: Enable EMA trend filter (default: True)
                - ema_fast: Fast EMA period (default: 12)
                - ema_slow: Slow EMA period (default: 26)
                
                - use_adx_filter: Enable ADX trend strength filter (default: True)
                - adx_length: ADX period (default: 14)
                - adx_threshold: Minimum ADX value (default: 20)
                
                - leverage: Leverage multiplier (default: 5.0)
                - commission: Commission rate (default: 0.0005)
                - slippage: Slippage percentage (default: 0.0002)
        """
        # TWMA Parameters
        self.twma_len = params.get('twma_len', 20)
        self.atr_len = params.get('atr_len', 14)
        self.sl_atr_mult = params.get('sl_atr_mult', 0.5)
        self.tp_atr_mult = params.get('tp_atr_mult', 1.0)
        self.pivot_len = params.get('pivot_len', 5)
        
        # RSI Filter
        self.use_rsi_filter = params.get('use_rsi_filter', True)
        self.rsi_length = params.get('rsi_length', 14)
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_overbought = params.get('rsi_overbought', 70)
        
        # MACD Filter
        self.use_macd_filter = params.get('use_macd_filter', True)
        self.macd_fast = params.get('macd_fast', 12)
        self.macd_slow = params.get('macd_slow', 26)
        self.macd_signal = params.get('macd_signal', 9)
        
        # Volume Filter
        self.use_volume_filter = params.get('use_volume_filter', True)
        self.volume_ma_length = params.get('volume_ma_length', 20)
        self.volume_multiplier = params.get('volume_multiplier', 1.2)
        
        # EMA Trend Filter
        self.use_ema_filter = params.get('use_ema_filter', True)
        self.ema_fast = params.get('ema_fast', 12)
        self.ema_slow = params.get('ema_slow', 26)
        
        # ADX Trend Strength Filter
        self.use_adx_filter = params.get('use_adx_filter', True)
        self.adx_length = params.get('adx_length', 14)
        self.adx_threshold = params.get('adx_threshold', 20)
        
        # Trading Parameters
        self.leverage = params.get('leverage', 5.0)
        self.commission = params.get('commission', 0.0005)
        self.slippage = params.get('slippage', 0.0002)
    
    def calculate_twma(self, src: pd.Series, length: int) -> pd.Series:
        """Calculate Time Weighted Moving Average"""
        twma = pd.Series(index=src.index, dtype=float)
        
        for i in range(len(src)):
            if i < length - 1:
                twma.iloc[i] = np.nan
                continue
            
            num = 0.0
            den = 0.0
            
            for j in range(length):
                w = length - j
                num += src.iloc[i - j] * w
                den += w
            
            twma.iloc[i] = num / den if den > 0 else np.nan
        
        return twma
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_len).mean()
        return atr
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        ema_fast = df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd - signal
        return macd, signal, histogram
    
    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index"""
        # Calculate True Range
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Calculate +DM and -DM
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        # Smooth TR, +DM, -DM
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # Calculate ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    def calculate_pivot_high_low(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calculate pivot high and pivot low"""
        pivot_high = pd.Series(index=df.index, dtype=float)
        pivot_low = pd.Series(index=df.index, dtype=float)
        
        for i in range(self.pivot_len, len(df) - self.pivot_len):
            # Check pivot high
            high_val = df['high'].iloc[i]
            is_pivot_high = True
            for j in range(1, self.pivot_len + 1):
                if df['high'].iloc[i - j] >= high_val or df['high'].iloc[i + j] >= high_val:
                    is_pivot_high = False
                    break
            if is_pivot_high:
                pivot_high.iloc[i] = high_val
            
            # Check pivot low
            low_val = df['low'].iloc[i]
            is_pivot_low = True
            for j in range(1, self.pivot_len + 1):
                if df['low'].iloc[i - j] <= low_val or df['low'].iloc[i + j] <= low_val:
                    is_pivot_low = False
                    break
            if is_pivot_low:
                pivot_low.iloc[i] = low_val
        
        return pivot_high, pivot_low
    
    def check_filters_long(self, df: pd.DataFrame, i: int, rsi: pd.Series, macd: pd.Series, 
                          macd_signal: pd.Series, macd_hist: pd.Series, volume_ma: pd.Series,
                          ema_fast: pd.Series, ema_slow: pd.Series, adx: pd.Series) -> bool:
        """Check all filters for LONG entry"""
        filters_passed = 0
        total_filters = 0
        
        # RSI Filter - Long için: RSI aşırı alımda olmamalı
        if self.use_rsi_filter:
            total_filters += 1
            if not pd.isna(rsi.iloc[i]):
                if rsi.iloc[i] < self.rsi_overbought:  # Overbought'tan kaçın
                    filters_passed += 1
        
        # MACD Filter - Long için: MACD > Signal ve histogram pozitif
        if self.use_macd_filter:
            total_filters += 1
            if not pd.isna(macd.iloc[i]) and not pd.isna(macd_signal.iloc[i]):
                if macd.iloc[i] > macd_signal.iloc[i] and macd_hist.iloc[i] > 0:
                    filters_passed += 1
        
        # Volume Filter - Long için: Volume ortalamanın üzerinde olmalı
        if self.use_volume_filter:
            total_filters += 1
            if not pd.isna(volume_ma.iloc[i]):
                if df['volume'].iloc[i] > volume_ma.iloc[i] * self.volume_multiplier:
                    filters_passed += 1
        
        # EMA Trend Filter - Long için: Fast EMA > Slow EMA (yukarı trend)
        if self.use_ema_filter:
            total_filters += 1
            if not pd.isna(ema_fast.iloc[i]) and not pd.isna(ema_slow.iloc[i]):
                if ema_fast.iloc[i] > ema_slow.iloc[i]:
                    filters_passed += 1
        
        # ADX Filter - Trend gücü yeterli olmalı
        if self.use_adx_filter:
            total_filters += 1
            if not pd.isna(adx.iloc[i]):
                if adx.iloc[i] >= self.adx_threshold:
                    filters_passed += 1
        
        # En az %60 filtre geçmeli (veya tüm filtreler aktif değilse)
        if total_filters == 0:
            return True
        
        return filters_passed >= (total_filters * 0.6)  # En az %60 onay
    
    def check_filters_short(self, df: pd.DataFrame, i: int, rsi: pd.Series, macd: pd.Series,
                           macd_signal: pd.Series, macd_hist: pd.Series, volume_ma: pd.Series,
                           ema_fast: pd.Series, ema_slow: pd.Series, adx: pd.Series) -> bool:
        """Check all filters for SHORT entry"""
        filters_passed = 0
        total_filters = 0
        
        # RSI Filter - Short için: RSI aşırı satımda olmamalı
        if self.use_rsi_filter:
            total_filters += 1
            if not pd.isna(rsi.iloc[i]):
                if rsi.iloc[i] > self.rsi_oversold:  # Oversold'tan kaçın
                    filters_passed += 1
        
        # MACD Filter - Short için: MACD < Signal ve histogram negatif
        if self.use_macd_filter:
            total_filters += 1
            if not pd.isna(macd.iloc[i]) and not pd.isna(macd_signal.iloc[i]):
                if macd.iloc[i] < macd_signal.iloc[i] and macd_hist.iloc[i] < 0:
                    filters_passed += 1
        
        # Volume Filter - Short için: Volume ortalamanın üzerinde olmalı
        if self.use_volume_filter:
            total_filters += 1
            if not pd.isna(volume_ma.iloc[i]):
                if df['volume'].iloc[i] > volume_ma.iloc[i] * self.volume_multiplier:
                    filters_passed += 1
        
        # EMA Trend Filter - Short için: Fast EMA < Slow EMA (aşağı trend)
        if self.use_ema_filter:
            total_filters += 1
            if not pd.isna(ema_fast.iloc[i]) and not pd.isna(ema_slow.iloc[i]):
                if ema_fast.iloc[i] < ema_slow.iloc[i]:
                    filters_passed += 1
        
        # ADX Filter - Trend gücü yeterli olmalı
        if self.use_adx_filter:
            total_filters += 1
            if not pd.isna(adx.iloc[i]):
                if adx.iloc[i] >= self.adx_threshold:
                    filters_passed += 1
        
        # En az %60 filtre geçmeli
        if total_filters == 0:
            return True
        
        return filters_passed >= (total_filters * 0.6)  # En az %60 onay
    
    def run_backtest(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run backtest with filters"""
        # Calculate indicators
        twma = self.calculate_twma(df['close'], self.twma_len)
        atr = self.calculate_atr(df)
        pivot_high, pivot_low = self.calculate_pivot_high_low(df)
        
        # Calculate filter indicators
        rsi = self.calculate_rsi(df, self.rsi_length) if self.use_rsi_filter else pd.Series(index=df.index, dtype=float)
        macd, macd_signal, macd_hist = self.calculate_macd(df) if self.use_macd_filter else (pd.Series(index=df.index), pd.Series(index=df.index), pd.Series(index=df.index))
        volume_ma = df['volume'].rolling(window=self.volume_ma_length).mean() if self.use_volume_filter else pd.Series(index=df.index, dtype=float)
        ema_fast = df['close'].ewm(span=self.ema_fast, adjust=False).mean() if self.use_ema_filter else pd.Series(index=df.index, dtype=float)
        ema_slow = df['close'].ewm(span=self.ema_slow, adjust=False).mean() if self.use_ema_filter else pd.Series(index=df.index, dtype=float)
        adx = self.calculate_adx(df, self.adx_length) if self.use_adx_filter else pd.Series(index=df.index, dtype=float)
        
        # Track last swing high/low
        last_swing_high = None
        last_swing_low = None
        
        # Track position
        position = None
        entry_price = None
        stop_loss = None
        take_profit = None
        
        # Track trades
        trades = []
        equity = 100000.0
        equity_curve = [equity]
        
        # Track state
        long_sl = None
        long_tp = None
        short_sl = None
        short_tp = None
        
        # Track filtered signals
        filtered_signals = 0
        total_signals = 0
        
        for i in range(1, len(df)):
            if pd.isna(twma.iloc[i]) or pd.isna(twma.iloc[i-1]) or pd.isna(atr.iloc[i]):
                equity_curve.append(equity)
                continue
            
            # Update last swing high/low
            if not pd.isna(pivot_high.iloc[i]):
                last_swing_high = pivot_high.iloc[i]
            if not pd.isna(pivot_low.iloc[i]):
                last_swing_low = pivot_low.iloc[i]
            
            # TWMA direction
            twma_up = twma.iloc[i] > twma.iloc[i-1]
            twma_down = twma.iloc[i] < twma.iloc[i-1]
            
            # Current bar values
            curr_close = df['close'].iloc[i]
            curr_high = df['high'].iloc[i]
            curr_low = df['low'].iloc[i]
            curr_twma = twma.iloc[i]
            curr_atr = atr.iloc[i]
            
            # Previous bar values
            prev_close = df['close'].iloc[i-1]
            prev_low = df['low'].iloc[i-1]
            prev_high = df['high'].iloc[i-1]
            prev_twma = twma.iloc[i-1]
            
            # Entry conditions - Pine: longEntryCond = setupLongBar[1] and touchLongNow[1] and noPos
            no_pos = position is None
            
            # Check if setup was 2 bars ago and touch was 1 bar ago
            if i >= 3:
                # Setup bar (2 bars ago): close > twma and twmaUp
                setup_bar_close = df['close'].iloc[i-2]
                setup_bar_twma = twma.iloc[i-2]
                setup_bar_twma_prev = twma.iloc[i-3]
                setup_twma_up = setup_bar_twma > setup_bar_twma_prev
                
                prev_setup_long = setup_bar_close > setup_bar_twma and setup_twma_up
                prev_setup_short = setup_bar_close < setup_bar_twma and (setup_bar_twma < setup_bar_twma_prev)
                
                # Touch bar (1 bar ago): low <= twma and close >= twma (for long)
                prev_touch_long = prev_low <= prev_twma and prev_close >= prev_twma
                prev_touch_short = prev_high >= prev_twma and prev_close <= prev_twma
                
                # Base entry conditions
                base_long_entry = prev_setup_long and prev_touch_long and no_pos
                base_short_entry = prev_setup_short and prev_touch_short and no_pos
                
                # Apply filters
                if base_long_entry:
                    total_signals += 1
                    if self.check_filters_long(df, i, rsi, macd, macd_signal, macd_hist, volume_ma, ema_fast, ema_slow, adx):
                        long_entry_cond = True
                    else:
                        long_entry_cond = False
                        filtered_signals += 1
                else:
                    long_entry_cond = False
                
                if base_short_entry:
                    total_signals += 1
                    if self.check_filters_short(df, i, rsi, macd, macd_signal, macd_hist, volume_ma, ema_fast, ema_slow, adx):
                        short_entry_cond = True
                    else:
                        short_entry_cond = False
                        filtered_signals += 1
                else:
                    short_entry_cond = False
            else:
                long_entry_cond = False
                short_entry_cond = False
            
            # LONG ENTRY
            if long_entry_cond:
                base_twma = prev_twma
                prev_atr_val = atr.iloc[i-1] if not pd.isna(atr.iloc[i-1]) else atr.iloc[i]
                sl_price = base_twma - self.sl_atr_mult * prev_atr_val if not pd.isna(prev_atr_val) else base_twma * 0.98
                tp_base = last_swing_high if last_swing_high is not None else base_twma
                tp_price = tp_base + self.tp_atr_mult * prev_atr_val if not pd.isna(prev_atr_val) else base_twma * 1.02
                
                position = 'long'
                entry_price = curr_close * (1 + self.slippage)
                
                # Stop Loss'u maksimum %1.5 ile sınırla (leverage etkisi: 5x)
                # %1.5 kayıp için fiyat hareketi: %1.5 / 5 = %0.3
                max_sl_price = entry_price * (1 - 0.003)  # Maksimum %0.3 fiyat hareketi = %1.5 kayıp (5x leverage)
                long_sl = max(sl_price, max_sl_price)  # Hesaplanan SL ile max SL'den daha yakın olanı seç
                stop_loss = long_sl
                take_profit = tp_price
                
                position_value = equity * 0.10 * self.leverage
                quantity = position_value / entry_price
                commission_cost = position_value * self.commission
                equity -= commission_cost
            
            # SHORT ENTRY
            elif short_entry_cond:
                base_twma_s = prev_twma
                prev_atr_val_s = atr.iloc[i-1] if not pd.isna(atr.iloc[i-1]) else atr.iloc[i]
                sl_price_s = base_twma_s + self.sl_atr_mult * prev_atr_val_s if not pd.isna(prev_atr_val_s) else base_twma_s * 1.02
                tp_base_s = last_swing_low if last_swing_low is not None else base_twma_s
                tp_price_s = tp_base_s - self.tp_atr_mult * prev_atr_val_s if not pd.isna(prev_atr_val_s) else base_twma_s * 0.98
                
                position = 'short'
                entry_price = curr_close * (1 - self.slippage)
                
                # Stop Loss'u maksimum %1.5 ile sınırla (leverage etkisi: 5x)
                # %1.5 kayıp için fiyat hareketi: %1.5 / 5 = %0.3
                max_sl_price = entry_price * (1 + 0.003)  # Maksimum %0.3 fiyat hareketi = %1.5 kayıp (5x leverage)
                short_sl = min(sl_price_s, max_sl_price)  # Hesaplanan SL ile max SL'den daha yakın olanı seç
                stop_loss = short_sl
                take_profit = tp_price_s
                
                position_value = equity * 0.10 * self.leverage
                quantity = position_value / entry_price
                commission_cost = position_value * self.commission
                equity -= commission_cost
            
            # Check exit conditions (same as before)
            if position == 'long' and entry_price is not None:
                if curr_low <= stop_loss:
                    exit_price = stop_loss * (1 - self.slippage)
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * self.leverage
                    pnl = equity * 0.10 * (pnl_pct / 100)
                    equity += pnl
                    commission_cost = equity * 0.10 * self.commission
                    equity -= commission_cost
                    
                    trades.append({
                        'entry_time': df.index[i-1] if i > 0 else df.index[i],
                        'exit_time': df.index[i],
                        'side': 'long',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'sl'
                    })
                    
                    position = None
                    entry_price = None
                    stop_loss = None
                    take_profit = None
                
                elif curr_high >= take_profit:
                    exit_price = take_profit * (1 + self.slippage)
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * self.leverage
                    pnl = equity * 0.10 * (pnl_pct / 100)
                    equity += pnl
                    commission_cost = equity * 0.10 * self.commission
                    equity -= commission_cost
                    
                    trades.append({
                        'entry_time': df.index[i-1] if i > 0 else df.index[i],
                        'exit_time': df.index[i],
                        'side': 'long',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'tp'
                    })
                    
                    position = None
                    entry_price = None
                    stop_loss = None
                    take_profit = None
            
            elif position == 'short' and entry_price is not None:
                if curr_high >= stop_loss:
                    exit_price = stop_loss * (1 + self.slippage)
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * self.leverage
                    pnl = equity * 0.10 * (pnl_pct / 100)
                    equity += pnl
                    commission_cost = equity * 0.10 * self.commission
                    equity -= commission_cost
                    
                    trades.append({
                        'entry_time': df.index[i-1] if i > 0 else df.index[i],
                        'exit_time': df.index[i],
                        'side': 'short',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'sl'
                    })
                    
                    position = None
                    entry_price = None
                    stop_loss = None
                    take_profit = None
                
                elif curr_low <= take_profit:
                    exit_price = take_profit * (1 - self.slippage)
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * self.leverage
                    pnl = equity * 0.10 * (pnl_pct / 100)
                    equity += pnl
                    commission_cost = equity * 0.10 * self.commission
                    equity -= commission_cost
                    
                    trades.append({
                        'entry_time': df.index[i-1] if i > 0 else df.index[i],
                        'exit_time': df.index[i],
                        'side': 'short',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'tp'
                    })
                    
                    position = None
                    entry_price = None
                    stop_loss = None
                    take_profit = None
            
            equity_curve.append(equity)
        
        # Close any open position at the end
        if position is not None and entry_price is not None:
            exit_price = df['close'].iloc[-1]
            if position == 'long':
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * self.leverage
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * self.leverage
            
            pnl = equity * 0.10 * (pnl_pct / 100)
            equity += pnl
            commission_cost = equity * 0.10 * self.commission
            equity -= commission_cost
            
            trades.append({
                'entry_time': df.index[-2] if len(df) > 1 else df.index[-1],
                'exit_time': df.index[-1],
                'side': position,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_pct': pnl_pct,
                'exit_reason': 'end'
            })
        
        # Calculate metrics
        if len(trades) == 0:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'total_return_pct': 0.0,
                'max_drawdown_pct': 0.0,
                'avg_win_pct': 0.0,
                'avg_loss_pct': 0.0,
                'gross_profit': 0.0,
                'gross_loss': 0.0,
                'final_equity': equity,
                'trades': [],
                'filtered_signals': filtered_signals,
                'total_signals': total_signals
            }
        
        winning_trades = [t for t in trades if t['pnl_pct'] > 0]
        losing_trades = [t for t in trades if t['pnl_pct'] < 0]
        
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0.0
        
        gross_profit = sum(t['pnl_pct'] for t in winning_trades) if winning_trades else 0.0
        gross_loss = abs(sum(t['pnl_pct'] for t in losing_trades)) if losing_trades else 0.0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        avg_win = np.mean([t['pnl_pct'] for t in winning_trades]) if winning_trades else 0.0
        avg_loss = np.mean([t['pnl_pct'] for t in losing_trades]) if losing_trades else 0.0
        
        total_return_pct = ((equity - 100000.0) / 100000.0) * 100
        
        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown_pct = abs(drawdown.min()) if len(drawdown) > 0 else 0.0
        
        return {
            'total_trades': len(trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return_pct': total_return_pct,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'final_equity': equity,
            'trades': trades,
            'filtered_signals': filtered_signals,
            'total_signals': total_signals,
            'filter_rate': (filtered_signals / total_signals * 100) if total_signals > 0 else 0.0
        }

