#!/usr/bin/env python3
"""
DEEP Supertrend RSI Strategy for Strategy Optimizer
Orijinal DEEP stratejisinin optimize edilmiş versiyonu
"""

import pandas as pd
import numpy as np
import pandas_ta as pta
from typing import Dict, Any, Tuple, Optional

class DeepSupertrendRSIStrategy:
    def __init__(self, params: Dict[str, Any]):
        """
        DEEP Supertrend RSI stratejisi başlat
        
        Args:
            params: Strateji parametreleri
                - rsi_length: RSI periyodu - default: 14
                - rsi_oversold: RSI oversold seviyesi - default: 30
                - rsi_overbought: RSI overbought seviyesi - default: 70
                - rsi_long_exit: RSI long exit seviyesi - default: 65
                - rsi_short_exit: RSI short exit seviyesi - default: 35
                - supertrend_length: Supertrend periyodu - default: 1
                - supertrend_multiplier: Supertrend çarpanı - default: 3.0
                - support_resistance_period: Support/Resistance periyodu - default: 22
        """
        self.rsi_length = params.get('rsi_length', 14)
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_overbought = params.get('rsi_overbought', 70)
        self.rsi_long_exit = params.get('rsi_long_exit', 65)
        self.rsi_short_exit = params.get('rsi_short_exit', 35)
        self.supertrend_length = params.get('supertrend_length', 1)
        self.supertrend_multiplier = params.get('supertrend_multiplier', 3.0)
        self.support_resistance_period = params.get('support_resistance_period', 22)
        
        self.validate_params()
    
    def validate_params(self):
        """Parametreleri doğrula"""
        if self.rsi_length <= 0:
            raise ValueError("RSI length must be positive")
        if not (0 < self.rsi_oversold < 100):
            raise ValueError("RSI oversold must be between 0 and 100")
        if not (0 < self.rsi_overbought < 100):
            raise ValueError("RSI overbought must be between 0 and 100")
        if self.supertrend_length <= 0:
            raise ValueError("Supertrend length must be positive")
        if self.supertrend_multiplier <= 0:
            raise ValueError("Supertrend multiplier must be positive")
        if self.support_resistance_period <= 0:
            raise ValueError("Support/Resistance period must be positive")
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Teknik indikatörleri hesapla"""
        result_df = df.copy()
        
        # RSI hesaplama
        result_df['rsi'] = pta.rsi(df['Close'], length=self.rsi_length)
        
        # Supertrend hesaplama
        supertrend_data = pta.supertrend(
            df['High'], 
            df['Low'], 
            df['Close'], 
            length=self.supertrend_length,
            multiplier=self.supertrend_multiplier
        )
        result_df['supertrend'] = supertrend_data[f'SUPERT_{self.supertrend_length}_{self.supertrend_multiplier}']
        
        # Support/Resistance seviyeleri (rolling window)
        result_df['max_level'] = df['High'].rolling(window=self.support_resistance_period).max()
        result_df['min_level'] = df['Low'].rolling(window=self.support_resistance_period).min()
        
        return result_df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Trading sinyalleri üret"""
        result_df = df.copy()
        
        # State variables initialization
        result_df['long_status'] = 0
        result_df['short_status'] = 0
        result_df['long_position'] = 0
        result_df['short_position'] = 0
        result_df['dip_level'] = 0.0
        result_df['tepe_level'] = 0.0
        result_df['long_boyun'] = 0.0
        result_df['short_boyun'] = 0.0
        
        # Initialize state variables
        long_status = 0
        short_status = 0
        long_position = 0
        short_position = 0
        dip_level = 0.0
        tepe_level = 0.0
        long_boyun = 0.0
        short_boyun = 0.0
        
        # Signal generation logic
        for i in range(len(result_df)):
            current_price = result_df.iloc[i]['Close']
            current_high = result_df.iloc[i]['High']
            current_low = result_df.iloc[i]['Low']
            rsi = result_df.iloc[i]['rsi']
            supertrend = result_df.iloc[i]['supertrend']
            min_level = result_df.iloc[i]['min_level']
            max_level = result_df.iloc[i]['max_level']
            
            # Skip if indicators are NaN
            if pd.isna(rsi) or pd.isna(supertrend) or pd.isna(min_level) or pd.isna(max_level):
                continue
            
            # LONG Signal Logic (5 stages)
            if long_status == 0 and rsi < self.rsi_oversold:
                if long_position == 0 and short_position == 0:
                    long_status = 1
                    dip_level = min_level
            
            elif long_status == 1 and supertrend < current_price:
                long_status = 2
                long_boyun = current_high
            
            elif long_status == 2:
                if current_high > long_boyun:
                    long_boyun = current_high
                
                if supertrend > current_price and current_price < long_boyun:
                    long_status = 3
            
            elif long_status == 3 and supertrend < current_price and current_price > long_boyun:
                long_status = 4
            
            elif long_status == 4 and supertrend > current_price and current_price < long_boyun:
                long_status = 5
            
            # SHORT Signal Logic (5 stages)
            if short_status == 0 and rsi > self.rsi_overbought:
                if long_position == 0 and short_position == 0:
                    short_status = 1
                    tepe_level = max_level
            
            elif short_status == 1 and supertrend > current_price:
                short_status = 2
                short_boyun = current_low
            
            elif short_status == 2:
                if current_low < short_boyun:
                    short_boyun = current_low
                
                if supertrend < current_price and current_price > short_boyun:
                    short_status = 3
            
            elif short_status == 3 and supertrend > current_price and current_price < short_boyun:
                short_status = 4
            
            elif short_status == 4 and supertrend < current_price and current_price > short_boyun:
                short_status = 5
            
            # Reset conditions
            if long_status in [2, 4] and rsi > self.rsi_long_exit:
                long_status = 0
            
            if long_status in [2, 3, 4, 5] and rsi < self.rsi_oversold:
                long_status = 1
                dip_level = min_level
            
            if short_status in [2, 4] and rsi < self.rsi_short_exit:
                short_status = 0
            
            if short_status in [2, 3, 4, 5] and rsi > self.rsi_overbought:
                short_status = 1
                tepe_level = max_level
            
            # Position management
            if long_position == 0 and short_position == 0:
                if long_status == 5 and current_price > long_boyun:
                    long_position = 1
                elif short_status == 5 and current_price < short_boyun:
                    short_position = 1
            
            if long_position == 1 and current_price < min_level:
                long_position = 0
                long_status = 0
                short_status = 0
            
            if short_position == 1 and current_price > max_level:
                short_position = 0
                long_status = 0
                short_status = 0
            
            # Store state
            result_df.iloc[i, result_df.columns.get_loc('long_status')] = long_status
            result_df.iloc[i, result_df.columns.get_loc('short_status')] = short_status
            result_df.iloc[i, result_df.columns.get_loc('long_position')] = long_position
            result_df.iloc[i, result_df.columns.get_loc('short_position')] = short_position
            result_df.iloc[i, result_df.columns.get_loc('dip_level')] = dip_level
            result_df.iloc[i, result_df.columns.get_loc('tepe_level')] = tepe_level
            result_df.iloc[i, result_df.columns.get_loc('long_boyun')] = long_boyun
            result_df.iloc[i, result_df.columns.get_loc('short_boyun')] = short_boyun
        
        # Generate buy/sell signals
        result_df['buy_signal'] = (result_df['long_position'] == 1) & (result_df['long_position'].shift(1) == 0)
        result_df['sell_signal'] = (result_df['short_position'] == 1) & (result_df['short_position'].shift(1) == 0)
        result_df['close_long'] = (result_df['long_position'] == 0) & (result_df['long_position'].shift(1) == 1)
        result_df['close_short'] = (result_df['short_position'] == 0) & (result_df['short_position'].shift(1) == 1)
        
        return result_df
    
    def get_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ana sinyal üretme fonksiyonu"""
        # Calculate indicators
        df_with_indicators = self.calculate_indicators(df)
        
        # Generate signals
        df_with_signals = self.generate_signals(df_with_indicators)
        
        return df_with_signals
