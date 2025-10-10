import yfinance as yf
import pandas as pd
import json
import time
from datetime import datetime
import logging

class NASDAQStockScanner:
    def __init__(self):
        # Logging setup
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('nasdaq_scanner.log')
            ]
        )
        self.log = logging.getLogger(__name__)
        
        self.log.info("🔍 NASDAQ Stock Scanner başlatıldı")
        
    def get_nasdaq_symbols(self):
        """NASDAQ sembollerini çek - Sadece $1 altındaki teknoloji hisseleri"""
        try:
            # Sadece $1 altındaki teknoloji hisseleri (resimdeki hisseler)
            nasdaq_symbols = [
                # Resimdeki hisseler ($1 altında)
                'KPLTW', 'CXAIW', 'MNYWW', 'EPWK', 'CHR', 'CYCU', 'AEVAW', 'YYAI', 'FPAY', 'IOTR', 'WCT',
                'ZPTA', 'AIRE', 'EGLXF', 'OPTT', 'VEEA', 'FEMY', 'SENS', 'ARBK',
                
                # Ek küçük teknoloji hisseleri
                'DKI', 'ILLR', 'SELX', 'TDTH', 'MYPS', 'ZSPC', 'ISPC', 'CLPS'
            ]
            
            self.log.info(f"📊 {len(nasdaq_symbols)} küçük teknoloji hissesi yüklendi")
            return nasdaq_symbols
            
        except Exception as e:
            self.log.error(f"❌ NASDAQ sembol çekme hatası: {e}")
            return []
    
    def scan_technology_stocks(self, max_price=1.00):
        """Teknoloji hisselerini tara"""
        nasdaq_symbols = self.get_nasdaq_symbols()
        tech_stocks = []
        
        self.log.info(f"🔍 Teknoloji hisseleri taranıyor (max fiyat: ${max_price})")
        
        for symbol in nasdaq_symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                # Sektör kontrolü
                sector = info.get('sector', '').lower()
                industry = info.get('industry', '').lower()
                
                # Teknoloji sektörü kontrolü
                is_tech = (
                    'technology' in sector or
                    'software' in industry or
                    'hardware' in industry or
                    'semiconductor' in industry or
                    'internet' in industry or
                    'telecommunications' in industry
                )
                
                if not is_tech:
                    continue
                
                # Fiyat kontrolü
                current_price = info.get('currentPrice', 0)
                if current_price and current_price < max_price:
                    tech_stocks.append({
                        'symbol': symbol,
                        'name': info.get('longName', symbol),
                        'price': current_price,
                        'sector': sector,
                        'industry': industry,
                        'market_cap': info.get('marketCap', 0),
                        'volume': info.get('volume', 0)
                    })
                    
                    self.log.info(f"✅ Teknoloji hissesi bulundu: {symbol} - ${current_price:.2f}")
                elif is_tech and current_price:
                    self.log.info(f"🔍 Teknoloji ama fiyat yüksek: {symbol} - ${current_price:.2f} ({sector})")
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                self.log.warning(f"⚠️ {symbol} için bilgi alınamadı: {e}")
                continue
        
        self.log.info(f"🎯 Toplam {len(tech_stocks)} teknoloji hissesi bulundu")
        return tech_stocks
    
    def save_tech_stocks(self, tech_stocks, filename='nasdaq_tech_stocks.json'):
        """Teknoloji hisselerini dosyaya kaydet"""
        try:
            with open(filename, 'w') as f:
                json.dump(tech_stocks, f, indent=2)
            
            self.log.info(f"💾 {len(tech_stocks)} teknoloji hissesi {filename} dosyasına kaydedildi")
            
        except Exception as e:
            self.log.error(f"❌ Dosya kaydetme hatası: {e}")
    
    def run_scan(self):
        """Ana tarama işlemi"""
        self.log.info("🚀 NASDAQ teknoloji hisse taraması başlatılıyor...")
        
        tech_stocks = self.scan_technology_stocks(max_price=1.00)
        
        if tech_stocks:
            self.save_tech_stocks(tech_stocks)
            
            # Sonuçları göster
            print("\n" + "="*60)
            print("🎯 BULUNAN TEKNOLOJİ HİSSELERİ ($1 ALTINDA)")
            print("="*60)
            
            for stock in tech_stocks:
                print(f"📊 {stock['symbol']:6} | ${stock['price']:6.2f} | {stock['name'][:30]}")
            
            print(f"\n✅ Toplam {len(tech_stocks)} hisse bulundu")
            
        else:
            self.log.warning("⚠️ Hiç teknoloji hissesi bulunamadı")

if __name__ == "__main__":
    scanner = NASDAQStockScanner()
    scanner.run_scan()
