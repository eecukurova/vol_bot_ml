"""
ATR SuperTrend Strategy for NASDAQ Stocks
Pine Script'ten Python'a çevrilmiş ATR SuperTrend stratejisi
NASDAQ hisseleri için optimize edilmiş parametreler
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ATRSuperTrendConfig:
    """ATR SuperTrend stratejisi konfigürasyonu"""
    key_value: float = 3.0          # Key Value (sensitivity)
    atr_period: int = 10            # ATR Period
    use_heikin_ashi: bool = False   # Heikin Ashi candles
    multiplier: float = 1.5         # SuperTrend multiplier
    symbol: str = "AAPL"            # NASDAQ symbol
    timeframe: str = "1d"           # Timeframe

class ATRSuperTrendStrategy:
    """
    ATR SuperTrend Strategy for NASDAQ Stocks
    
    Pine Script'ten çevrilmiş:
    - ATR hesaplaması
    - Trailing Stop hesaplaması  
    - SuperTrend çizgisi
    - Buy/Sell sinyalleri
    """
    
    def __init__(self, config: ATRSuperTrendConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.symbol}")
        
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """ATR hesaplama"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range hesaplama
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR hesaplama (EMA ile)
        atr = true_range.ewm(span=self.config.atr_period).mean()
        
        return atr
    
    def calculate_heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Heikin Ashi mumları hesaplama"""
        ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_open = pd.Series(index=df.index, dtype=float)
        ha_open.iloc[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
        
        for i in range(1, len(df)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        
        ha_high = pd.concat([df['high'], ha_open, ha_close], axis=1).max(axis=1)
        ha_low = pd.concat([df['low'], ha_open, ha_close], axis=1).min(axis=1)
        
        return pd.DataFrame({
            'open': ha_open,
            'high': ha_high,
            'low': ha_low,
            'close': ha_close
        })
    
    def calculate_trailing_stop(self, df: pd.DataFrame, atr: pd.Series) -> pd.Series:
        """ATR Trailing Stop hesaplama"""
        src = df['close']
        if self.config.use_heikin_ashi:
            ha_df = self.calculate_heikin_ashi(df)
            src = ha_df['close']
        
        n_loss = self.config.key_value * atr
        
        x_atr_trailing_stop = pd.Series(index=df.index, dtype=float)
        x_atr_trailing_stop.iloc[0] = src.iloc[0] - n_loss.iloc[0]
        
        for i in range(1, len(df)):
            prev_stop = x_atr_trailing_stop.iloc[i-1]
            current_src = src.iloc[i]
            prev_src = src.iloc[i-1]
            current_n_loss = n_loss.iloc[i]
            
            if current_src > prev_stop and prev_src > prev_stop:
                x_atr_trailing_stop.iloc[i] = max(prev_stop, current_src - current_n_loss)
            elif current_src < prev_stop and prev_src < prev_stop:
                x_atr_trailing_stop.iloc[i] = min(prev_stop, current_src + current_n_loss)
            elif current_src > prev_stop:
                x_atr_trailing_stop.iloc[i] = current_src - current_n_loss
            else:
                x_atr_trailing_stop.iloc[i] = current_src + current_n_loss
        
        return x_atr_trailing_stop
    
    def calculate_position(self, df: pd.DataFrame, trailing_stop: pd.Series) -> pd.Series:
        """Pozisyon hesaplama"""
        src = df['close']
        if self.config.use_heikin_ashi:
            ha_df = self.calculate_heikin_ashi(df)
            src = ha_df['close']
        
        pos = pd.Series(index=df.index, dtype=int)
        pos.iloc[0] = 0
        
        for i in range(1, len(df)):
            prev_src = src.iloc[i-1]
            current_src = src.iloc[i]
            prev_stop = trailing_stop.iloc[i-1]
            current_stop = trailing_stop.iloc[i]
            
            if prev_src < prev_stop and current_src > current_stop:
                pos.iloc[i] = 1
            elif prev_src > prev_stop and current_src < current_stop:
                pos.iloc[i] = -1
            else:
                pos.iloc[i] = pos.iloc[i-1]
        
        return pos
    
    def calculate_supertrend(self, df: pd.DataFrame, atr: pd.Series) -> pd.Series:
        """SuperTrend çizgisi hesaplama"""
        super_trend = atr * self.config.multiplier
        trend_up = (df['high'] + df['low']) / 2 - super_trend
        trend_down = (df['high'] + df['low']) / 2 + super_trend
        
        super_trend_line = pd.Series(index=df.index, dtype=float)
        super_trend_line.iloc[0] = trend_down.iloc[0]
        
        for i in range(1, len(df)):
            prev_line = super_trend_line.iloc[i-1]
            current_close = df['close'].iloc[i]
            
            if pd.isna(prev_line):
                super_trend_line.iloc[i] = trend_down.iloc[i]
            elif current_close > prev_line:
                super_trend_line.iloc[i] = max(trend_up.iloc[i], prev_line)
            else:
                super_trend_line.iloc[i] = min(trend_down.iloc[i], prev_line)
        
        return super_trend_line
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sinyal üretimi"""
        # ATR hesaplama
        atr = self.calculate_atr(df)
        
        # Trailing Stop hesaplama
        trailing_stop = self.calculate_trailing_stop(df, atr)
        
        # Pozisyon hesaplama
        position = self.calculate_position(df, trailing_stop)
        
        # SuperTrend hesaplama
        super_trend_line = self.calculate_supertrend(df, atr)
        
        # Sinyal üretimi
        src = df['close']
        if self.config.use_heikin_ashi:
            ha_df = self.calculate_heikin_ashi(df)
            src = ha_df['close']
        
        # EMA(1) hesaplama
        ema_1 = src.ewm(span=1).mean()
        
        # Crossover sinyalleri
        above = (ema_1 > trailing_stop) & (ema_1.shift(1) <= trailing_stop.shift(1))
        below = (trailing_stop > ema_1) & (trailing_stop.shift(1) <= ema_1.shift(1))
        
        # Buy/Sell sinyalleri
        buy_signal = (src > trailing_stop) & above
        sell_signal = (src < trailing_stop) & below
        
        # SuperTrend sinyalleri
        buy_supertrend = (df['close'] > super_trend_line) & (df['close'].shift(1) <= super_trend_line.shift(1))
        sell_supertrend = (df['close'] < super_trend_line) & (df['close'].shift(1) >= super_trend_line.shift(1))
        
        # Sonuç DataFrame'i
        result = df.copy()
        result['atr'] = atr
        result['trailing_stop'] = trailing_stop
        result['position'] = position
        result['super_trend_line'] = super_trend_line
        result['buy_signal'] = buy_signal
        result['sell_signal'] = sell_signal
        result['buy_supertrend'] = buy_supertrend
        result['sell_supertrend'] = sell_supertrend
        
        return result
    
    def get_strategy_info(self) -> Dict:
        """Strateji bilgileri"""
        return {
            'name': 'ATR SuperTrend NASDAQ',
            'symbol': self.config.symbol,
            'timeframe': self.config.timeframe,
            'parameters': {
                'key_value': self.config.key_value,
                'atr_period': self.config.atr_period,
                'use_heikin_ashi': self.config.use_heikin_ashi,
                'multiplier': self.config.multiplier
            }
        }

# NASDAQ hisseleri için optimize edilmiş parametreler
NASDAQ_OPTIMIZED_PARAMS = {
    'AAPL': ATRSuperTrendConfig(key_value=2.5, atr_period=14, multiplier=1.8),
    'AMD': ATRSuperTrendConfig(key_value=3.0, atr_period=10, multiplier=1.5),
    'AMZN': ATRSuperTrendConfig(key_value=2.8, atr_period=12, multiplier=1.6),
    'MSFT': ATRSuperTrendConfig(key_value=2.7, atr_period=11, multiplier=1.7),
    'GOOGL': ATRSuperTrendConfig(key_value=2.6, atr_period=13, multiplier=1.6),
    'TSLA': ATRSuperTrendConfig(key_value=3.2, atr_period=9, multiplier=1.4),
    'NVDA': ATRSuperTrendConfig(key_value=2.9, atr_period=10, multiplier=1.5),
    'META': ATRSuperTrendConfig(key_value=2.8, atr_period=12, multiplier=1.6),
    'NFLX': ATRSuperTrendConfig(key_value=3.1, atr_period=9, multiplier=1.4),
    'CRM': ATRSuperTrendConfig(key_value=2.7, atr_period=11, multiplier=1.7)
}
