#!/usr/bin/env python3
"""
Binance Public API Test - API Key gerektirmez
"""

import ccxt
import pandas as pd
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

def test_binance_public_api():
    """Binance public API'yi test et"""
    
    try:
        log.info("🔍 Binance Public API test başlatılıyor...")
        
        # Exchange setup (API key olmadan)
        exchange = ccxt.binance({
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        log.info("📊 Exchange oluşturuldu (Public)")
        
        # Test symbols
        test_symbols = ['PENGU/USDT', 'EIGEN/USDT', 'BTC/USDT']
        
        for symbol in test_symbols:
            try:
                log.info(f"🔍 {symbol} test ediliyor...")
                
                # Ticker al (public)
                ticker = exchange.fetch_ticker(symbol)
                log.info(f"✅ {symbol} ticker: ${ticker['last']:.6f}")
                log.info(f"📊 Volume: {ticker['baseVolume']:.0f}")
                log.info(f"📈 Change: {ticker['percentage']:.2f}%")
                
                # OHLCV al (public)
                ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=10)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                log.info(f"✅ {symbol} OHLCV: {len(df)} mum")
                log.info(f"📅 Son mum: {df['timestamp'].iloc[-1]}")
                log.info(f"💰 Son fiyat: ${df['close'].iloc[-1]:.6f}")
                log.info(f"📊 Son volume: {df['volume'].iloc[-1]:.0f}")
                
                # Son 3 mumun fiyatları
                log.info("📈 Son 3 mum:")
                for i in range(-3, 0):
                    log.info(f"  {df['timestamp'].iloc[i]}: ${df['close'].iloc[i]:.6f}")
                
                log.info("")
                
            except Exception as e:
                log.error(f"❌ {symbol} hatası: {e}")
        
        log.info("✅ Binance Public API test tamamlandı")
        
    except Exception as e:
        log.error(f"❌ API test hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_binance_public_api()
