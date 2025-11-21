"""
NASDAQ Data Provider for Strategy Optimizer
NASDAQ hisseleri için veri sağlayıcı modülü
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import yfinance as yf
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NASDAQSymbol:
    """NASDAQ sembol bilgileri"""
    symbol: str
    name: str
    sector: str
    market_cap: str
    volume_avg: int
    price_range: Tuple[float, float]

# NASDAQ-100 ve büyük hacimli hisseler
NASDAQ_SYMBOLS = {
    'AAPL': NASDAQSymbol('AAPL', 'Apple Inc.', 'Technology', '3.2T', 50000000, (150, 200)),
    'AMD': NASDAQSymbol('AMD', 'Advanced Micro Devices', 'Technology', '200B', 40000000, (100, 150)),
    'AMZN': NASDAQSymbol('AMZN', 'Amazon.com Inc.', 'Consumer Discretionary', '1.5T', 30000000, (120, 180)),
    'MSFT': NASDAQSymbol('MSFT', 'Microsoft Corporation', 'Technology', '2.8T', 25000000, (300, 400)),
    'GOOGL': NASDAQSymbol('GOOGL', 'Alphabet Inc.', 'Technology', '1.7T', 20000000, (120, 150)),
    'TSLA': NASDAQSymbol('TSLA', 'Tesla Inc.', 'Consumer Discretionary', '800B', 80000000, (200, 300)),
    'NVDA': NASDAQSymbol('NVDA', 'NVIDIA Corporation', 'Technology', '1.2T', 35000000, (400, 600)),
    'META': NASDAQSymbol('META', 'Meta Platforms Inc.', 'Technology', '800B', 15000000, (300, 400)),
    'NFLX': NASDAQSymbol('NFLX', 'Netflix Inc.', 'Communication Services', '200B', 3000000, (400, 500)),
    'CRM': NASDAQSymbol('CRM', 'Salesforce Inc.', 'Technology', '200B', 5000000, (200, 250)),
    'ADBE': NASDAQSymbol('ADBE', 'Adobe Inc.', 'Technology', '250B', 2000000, (500, 600)),
    'PYPL': NASDAQSymbol('PYPL', 'PayPal Holdings Inc.', 'Financial Services', '60B', 8000000, (50, 80)),
    'INTC': NASDAQSymbol('INTC', 'Intel Corporation', 'Technology', '200B', 25000000, (30, 50)),
    'CSCO': NASDAQSymbol('CSCO', 'Cisco Systems Inc.', 'Technology', '200B', 15000000, (45, 60)),
    'ORCL': NASDAQSymbol('ORCL', 'Oracle Corporation', 'Technology', '300B', 10000000, (100, 130))
}

class NASDAQDataProvider:
    """
    NASDAQ hisseleri için veri sağlayıcı
    Yahoo Finance API kullanarak veri çekme
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cache = {}
        
    def get_symbol_info(self, symbol: str) -> Optional[NASDAQSymbol]:
        """Sembol bilgilerini getir"""
        return NASDAQ_SYMBOLS.get(symbol.upper())
    
    def get_available_symbols(self) -> List[str]:
        """Mevcut sembolleri listele"""
        return list(NASDAQ_SYMBOLS.keys())
    
    def get_symbols_by_sector(self, sector: str) -> List[str]:
        """Sektöre göre sembolleri getir"""
        return [symbol for symbol, info in NASDAQ_SYMBOLS.items() 
                if info.sector.lower() == sector.lower()]
    
    def get_high_volume_symbols(self, min_volume: int = 10000000) -> List[str]:
        """Yüksek hacimli sembolleri getir"""
        return [symbol for symbol, info in NASDAQ_SYMBOLS.items() 
                if info.volume_avg >= min_volume]
    
    def fetch_data(self, 
                   symbol: str, 
                   period: str = "2y",
                   interval: str = "1d",
                   use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Yahoo Finance'den veri çek
        
        Args:
            symbol: Hisse senedi sembolü
            period: Veri periyodu (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Veri aralığı (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
            use_cache: Cache kullan
        """
        symbol = symbol.upper()
        
        # Cache kontrolü
        cache_key = f"{symbol}_{period}_{interval}"
        if use_cache and cache_key in self.cache:
            self.logger.info(f"Cache'den veri getiriliyor: {symbol}")
            return self.cache[cache_key].copy()
        
        try:
            self.logger.info(f"Veri çekiliyor: {symbol} ({period}, {interval})")
            
            # Yahoo Finance'den veri çek
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                self.logger.warning(f"Veri bulunamadı: {symbol}")
                return None
            
            # Veri temizleme
            df = self._clean_data(df)
            
            # Cache'e kaydet
            if use_cache:
                self.cache[cache_key] = df.copy()
            
            self.logger.info(f"Veri başarıyla çekildi: {symbol} ({len(df)} kayıt)")
            return df
            
        except Exception as e:
            self.logger.error(f"Veri çekme hatası {symbol}: {e}")
            return None
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Veri temizleme"""
        # NaN değerleri temizle
        df = df.dropna()
        
        # Sıfır hacimli günleri temizle
        df = df[df['Volume'] > 0]
        
        # Tarih indeksini sıfırla
        df = df.reset_index()
        
        # Kolon isimlerini küçük harfe çevir
        df.columns = df.columns.str.lower()
        
        # Gerekli kolonları kontrol et
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            self.logger.warning(f"Eksik kolonlar: {missing_columns}")
        
        return df
    
    def get_multiple_symbols_data(self, 
                                 symbols: List[str],
                                 period: str = "2y",
                                 interval: str = "1d") -> Dict[str, pd.DataFrame]:
        """Birden fazla sembol için veri çek"""
        data = {}
        
        for symbol in symbols:
            df = self.fetch_data(symbol, period, interval)
            if df is not None:
                data[symbol] = df
            else:
                self.logger.warning(f"Veri çekilemedi: {symbol}")
        
        return data
    
    def get_sector_data(self, 
                       sector: str,
                       period: str = "2y",
                       interval: str = "1d") -> Dict[str, pd.DataFrame]:
        """Sektör verilerini getir"""
        symbols = self.get_symbols_by_sector(sector)
        return self.get_multiple_symbols_data(symbols, period, interval)
    
    def get_high_volume_data(self, 
                            min_volume: int = 10000000,
                            period: str = "2y",
                            interval: str = "1d") -> Dict[str, pd.DataFrame]:
        """Yüksek hacimli hisselerin verilerini getir"""
        symbols = self.get_high_volume_symbols(min_volume)
        return self.get_multiple_symbols_data(symbols, period, interval)
    
    def clear_cache(self):
        """Cache'i temizle"""
        self.cache.clear()
        self.logger.info("Cache temizlendi")
    
    def get_cache_info(self) -> Dict:
        """Cache bilgilerini getir"""
        return {
            'cache_size': len(self.cache),
            'cached_symbols': list(self.cache.keys()),
            'memory_usage': sum(df.memory_usage(deep=True).sum() for df in self.cache.values())
        }

# Global instance
nasdaq_provider = NASDAQDataProvider()

def get_nasdaq_data(symbol: str, **kwargs) -> Optional[pd.DataFrame]:
    """Hızlı veri çekme fonksiyonu"""
    return nasdaq_provider.fetch_data(symbol, **kwargs)

def get_nasdaq_symbols() -> List[str]:
    """Mevcut NASDAQ sembollerini getir"""
    return nasdaq_provider.get_available_symbols()

def get_high_volume_symbols(min_volume: int = 10000000) -> List[str]:
    """Yüksek hacimli sembolleri getir"""
    return nasdaq_provider.get_high_volume_symbols(min_volume)
