#!/usr/bin/env python3
"""
ATR SuperTrend Strategy
Pine Script'teki "ATR with Super Trend" stratejisinin Python implementasyonu
Hem ATR Trailing Stop hem de SuperTrend kombinasyonu kullanır
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional

class ATRSuperTrendStrategy:
    def __init__(self, params: Dict[str, Any]):
        """
        ATR SuperTrend stratejisi başlat
        
        Args:
            params: Strateji parametreleri
                - a: Key Value (sensitivity) - default: 3
                - c: ATR Period - default: 10
                - h: Heikin Ashi enabled - default: False
                - factor: SuperTrend multiplier - default: 1.5
        """
        self.a = params.get('a', 3)  # Key Value
        self.c = params.get('c', 10)  # ATR Period
        self.h = params.get('h', False)  # Heikin Ashi
        self.factor = params.get('factor', 1.5)  # SuperTrend multiplier
        
        self.validate_params()
    
    def validate_params(self):
        """Parametreleri doğrula"""
        if self.a <= 0:
            raise ValueError("Key Value (a) must be positive")
        if self.c <= 0:
            raise ValueError("ATR Period (c) must be positive")
        if self.factor <= 0:
            raise ValueError("SuperTrend factor must be positive")
    
    def calculate_heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Heikin Ashi mumları hesapla"""
        ha_df = df.copy()
        
        # İlk Heikin Ashi değerleri
        first_idx = ha_df.index[0]
        ha_df.loc[first_idx, 'ha_close'] = (df.loc[first_idx, 'Open'] + df.loc[first_idx, 'High'] + 
                                           df.loc[first_idx, 'Low'] + df.loc[first_idx, 'Close']) / 4
        ha_df.loc[first_idx, 'ha_open'] = (df.loc[first_idx, 'Open'] + df.loc[first_idx, 'Close']) / 2
        
        # Sonraki Heikin Ashi değerleri
        for i in range(1, len(df)):
            current_idx = ha_df.index[i]
            prev_idx = ha_df.index[i-1]
            
            # Heikin Ashi Close
            ha_df.loc[current_idx, 'ha_close'] = (df.loc[current_idx, 'Open'] + df.loc[current_idx, 'High'] + 
                                                df.loc[current_idx, 'Low'] + df.loc[current_idx, 'Close']) / 4
            
            # Heikin Ashi Open
            ha_df.loc[current_idx, 'ha_open'] = (ha_df.loc[prev_idx, 'ha_open'] + ha_df.loc[prev_idx, 'ha_close']) / 2
            
            # Heikin Ashi High
            ha_df.loc[current_idx, 'ha_high'] = max(df.loc[current_idx, 'High'], ha_df.loc[current_idx, 'ha_open'], ha_df.loc[current_idx, 'ha_close'])
            
            # Heikin Ashi Low
            ha_df.loc[current_idx, 'ha_low'] = min(df.loc[current_idx, 'Low'], ha_df.loc[current_idx, 'ha_open'], ha_df.loc[current_idx, 'ha_close'])
        
        return ha_df
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """ATR hesapla"""
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=self.c).mean()
        return atr
    
    def calculate_atr_trailing_stop(self, df: pd.DataFrame) -> pd.Series:
        """ATR Trailing Stop hesapla"""
        atr = self.calculate_atr(df)
        n_loss = self.a * atr
        
        # Source: Heikin Ashi veya normal close
        if self.h:
            ha_df = self.calculate_heikin_ashi(df)
            src = ha_df['ha_close']
        else:
            src = df['Close']
        
        # ATR Trailing Stop hesaplama
        trailing_stop = pd.Series(index=df.index, dtype=float)
        trailing_stop.iloc[0] = src.iloc[0] - n_loss.iloc[0]
        
        for i in range(1, len(df)):
            prev_trailing = trailing_stop.iloc[i-1]
            current_src = src.iloc[i]
            prev_src = src.iloc[i-1]
            current_n_loss = n_loss.iloc[i]
            
            if current_src > prev_trailing and prev_src > prev_trailing:
                # Uptrend - trailing stop'u yukarı çek
                trailing_stop.iloc[i] = max(prev_trailing, current_src - current_n_loss)
            elif current_src < prev_trailing and prev_src < prev_trailing:
                # Downtrend - trailing stop'u aşağı çek
                trailing_stop.iloc[i] = min(prev_trailing, current_src + current_n_loss)
            elif current_src > prev_trailing:
                # Trend değişimi: bearish -> bullish
                trailing_stop.iloc[i] = current_src - current_n_loss
            else:
                # Trend değişimi: bullish -> bearish
                trailing_stop.iloc[i] = current_src + current_n_loss
        
        return trailing_stop
    
    def calculate_supertrend(self, df: pd.DataFrame) -> pd.Series:
        """SuperTrend hesapla"""
        atr = self.calculate_atr(df)
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        # SuperTrend hesaplama
        hl2 = (high + low) / 2
        super_trend = atr * self.factor
        
        trend_up = hl2 - super_trend
        trend_down = hl2 + super_trend
        
        # SuperTrend line
        super_trend_line = pd.Series(index=df.index, dtype=float)
        super_trend_line.iloc[0] = trend_down.iloc[0]
        
        for i in range(1, len(df)):
            if close.iloc[i] > super_trend_line.iloc[i-1]:
                super_trend_line.iloc[i] = max(trend_up.iloc[i], super_trend_line.iloc[i-1])
            else:
                super_trend_line.iloc[i] = min(trend_down.iloc[i], super_trend_line.iloc[i-1])
        
        return super_trend_line
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tüm indikatörleri hesapla"""
        df = df.copy()
        
        # ATR Trailing Stop
        df['atr_trailing_stop'] = self.calculate_atr_trailing_stop(df)
        
        # SuperTrend
        df['supertrend'] = self.calculate_supertrend(df)
        
        # ATR
        df['atr'] = self.calculate_atr(df)
        
        # EMA(1) - Pine Script'teki ema(src, 1)
        if self.h:
            ha_df = self.calculate_heikin_ashi(df)
            src = ha_df['ha_close']
        else:
            src = df['Close']
        
        df['ema1'] = src.ewm(span=1).mean()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sinyalleri üret"""
        df = df.copy()
        
        # Source price
        if self.h:
            ha_df = self.calculate_heikin_ashi(df)
            src = ha_df['ha_close']
        else:
            src = df['Close']
        
        # ATR Trailing Stop sinyalleri
        df['above'] = (df['ema1'] > df['atr_trailing_stop']) & (df['ema1'].shift(1) <= df['atr_trailing_stop'].shift(1))
        df['below'] = (df['ema1'] < df['atr_trailing_stop']) & (df['ema1'].shift(1) >= df['atr_trailing_stop'].shift(1))
        
        df['buy_atr'] = (src > df['atr_trailing_stop']) & df['above']
        df['sell_atr'] = (src < df['atr_trailing_stop']) & df['below']
        
        # SuperTrend sinyalleri
        df['buy_supertrend'] = (src > df['supertrend']) & (src.shift(1) <= df['supertrend'].shift(1))
        df['sell_supertrend'] = (src < df['supertrend']) & (src.shift(1) >= df['supertrend'].shift(1))
        
        # Kombine sinyaller (her iki strateji de aynı yönde sinyal verirse)
        df['buy_signal'] = df['buy_atr'] & df['buy_supertrend']
        df['sell_signal'] = df['sell_atr'] & df['sell_supertrend']
        
        # Alternatif: ATR Trailing Stop sinyallerini kullan (daha hassas)
        # df['buy_signal'] = df['buy_atr']
        # df['sell_signal'] = df['sell_atr']
        
        # Backtester için gerekli kolonlar
        df['buy_final'] = df['buy_signal']
        df['sell_final'] = df['sell_signal']
        
        return df
    
    def run_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Stratejiyi çalıştır
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with signals
        """
        # İndikatörleri hesapla
        df_with_indicators = self.calculate_indicators(df)
        
        # Sinyalleri üret
        df_with_signals = self.generate_signals(df_with_indicators)
        
        return df_with_signals

def create_strategy(params: Dict[str, Any]) -> ATRSuperTrendStrategy:
    """Strateji factory fonksiyonu"""
    return ATRSuperTrendStrategy(params)

def validate_strategy_params(params: Dict[str, Any]) -> bool:
    """Parametreleri doğrula"""
    try:
        # Gerekli parametreleri kontrol et
        required_params = ['a', 'c', 'factor']
        for param in required_params:
            if param not in params:
                return False
            if not isinstance(params[param], (int, float)):
                return False
            if params[param] <= 0:
                return False
        
        # Heikin Ashi parametresi opsiyonel
        if 'h' in params:
            if not isinstance(params['h'], bool):
                return False
        
        return True
    except Exception:
        return False
