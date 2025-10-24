#!/usr/bin/env python3
"""
Gerçek IPO sembolleri test
"""

import yfinance as yf

def test_real_ipos():
    """Gerçek IPO'ları test et"""
    
    # Gerçek IPO'ları test et
    test_symbols = ['RBLX', 'COIN', 'RIVN', 'LCID', 'PLTR', 'SOFI', 'HOOD']
    
    print('🔍 GERÇEK IPO SEMBOLLERİ TEST')
    print('=' * 40)
    
    for symbol in test_symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if info and 'symbol' in info:
                price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                market_cap = info.get('marketCap', 0)
                exchange = info.get('exchange', 'N/A')
                
                print(f'✅ {symbol}: ${price:.2f}, MC: ${market_cap:,}, EX: {exchange}')
            else:
                print(f'❌ {symbol}: Veri yok')
        except Exception as e:
            print(f'❌ {symbol}: Hata - {e}')

if __name__ == "__main__":
    test_real_ipos()
