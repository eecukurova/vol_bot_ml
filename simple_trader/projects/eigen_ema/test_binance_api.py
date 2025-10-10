#!/usr/bin/env python3
"""
Binance API Test - Gerçek verilerle
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

def test_binance_api():
    """Binance API'yi test et"""
    
    try:
        log.info("🔍 Binance API test başlatılıyor...")
        
        # Exchange setup
        exchange = ccxt.binance({
            'apiKey': '3qWqvsKBb2h127SPOv9RVRsJYRHpvwtBDE3zVc20cBjS1lwWDCn3IY5azWjUSP0e',
            'secret': 'HZRMeUvbKkbONjXsbZrD2WFuPPXARPTM2oM0TnTOaRsIBKoNdLUsCLVCQLnpZB3u',
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        log.info("📊 Exchange oluşturuldu")
        
        # Test symbols
        test_symbols = ['PENGU/USDT', 'EIGEN/USDT', 'BTC/USDT']
        
        for symbol in test_symbols:
            try:
                log.info(f"🔍 {symbol} test ediliyor...")
                
                # Ticker al
                ticker = exchange.fetch_ticker(symbol)
                log.info(f"✅ {symbol} ticker: ${ticker['last']:.6f}")
                
                # OHLCV al
                ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=5)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                log.info(f"✅ {symbol} OHLCV: {len(df)} mum")
                log.info(f"📅 Son mum: {df['timestamp'].iloc[-1]}")
                log.info(f"💰 Son fiyat: ${df['close'].iloc[-1]:.6f}")
                
            except Exception as e:
                log.error(f"❌ {symbol} hatası: {e}")
        
        # Account bilgileri
        try:
            log.info("🔍 Account bilgileri alınıyor...")
            balance = exchange.fetch_balance()
            log.info(f"✅ Account bilgileri alındı")
            log.info(f"💰 USDT Balance: {balance.get('USDT', {}).get('free', 0):.2f}")
        except Exception as e:
            log.error(f"❌ Account bilgileri hatası: {e}")
        
        log.info("✅ Binance API test tamamlandı")
        
    except Exception as e:
        log.error(f"❌ API test hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_binance_api()
