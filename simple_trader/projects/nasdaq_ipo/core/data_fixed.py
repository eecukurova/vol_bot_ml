    @staticmethod
    def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Calculate ADX (Average Directional Index)"""
        if len(high) < period + 1:
            return 0.0
        
        try:
            # Calculate True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Calculate Directional Movement
            dm_plus = high.diff()
            dm_minus = -low.diff()
            
            dm_plus = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0)
            dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0)
            
            # Smooth the values
            tr_smooth = tr.rolling(window=period).mean()
            dm_plus_smooth = dm_plus.rolling(window=period).mean()
            dm_minus_smooth = dm_minus.rolling(window=period).mean()
            
            # Calculate DI+ and DI-
            di_plus = 100 * safe_divide(dm_plus_smooth.iloc[-1], tr_smooth.iloc[-1])
            di_minus = 100 * safe_divide(dm_minus_smooth.iloc[-1], tr_smooth.iloc[-1])
            
            # Calculate DX
            dx = 100 * safe_divide(abs(di_plus - di_minus), (di_plus + di_minus))
            
            # Calculate ADX (smoothed DX)
            adx = dx.rolling(window=period).mean().iloc[-1]
            
            return adx if not pd.isna(adx) else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating ADX: {e}")
            return 0.0
