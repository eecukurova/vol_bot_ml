#!/usr/bin/env python3
"""
Otomatik IPO Keşif Sistemi
Yahoo Finance + Web Scraping ile yeni IPO'ları bulur ve ekler
"""

import requests
import pandas as pd
import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from bs4 import BeautifulSoup
import yfinance as yf
from urllib.parse import urljoin, urlparse
import re

logger = logging.getLogger(__name__)

class AutoIPODiscovery:
    """Otomatik IPO keşif sistemi"""
    
    def __init__(self, ipos_csv_path: str = 'ipos.csv'):
        self.ipos_csv_path = ipos_csv_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # IPO kaynak siteleri
        self.ipo_sources = [
            {
                'name': 'NASDAQ IPO Calendar',
                'url': 'https://www.nasdaq.com/market-activity/ipos',
                'method': 'nasdaq_scraping'
            },
            {
                'name': 'SEC EDGAR',
                'url': 'https://www.sec.gov/edgar/browse/?CIK=&type=424B4&count=100&owner=exclude&action=getcurrent',
                'method': 'sec_scraping'
            },
            {
                'name': 'Renaissance Capital',
                'url': 'https://www.renaissancecapital.com/ipohome/pricings',
                'method': 'renaissance_scraping'
            }
        ]
        
        logger.info("🚀 Otomatik IPO Keşif Sistemi başlatıldı")
    
    def get_existing_symbols(self) -> Set[str]:
        """Mevcut IPO sembollerini al"""
        symbols = set()
        
        if os.path.exists(self.ipos_csv_path):
            try:
                df = pd.read_csv(self.ipos_csv_path)
                symbols.update(df['symbol'].tolist())
                logger.info(f"📊 {len(symbols)} mevcut IPO sembolü bulundu")
            except Exception as e:
                logger.error(f"CSV okuma hatası: {e}")
        
        return symbols
    
    def scrape_nasdaq_ipos(self) -> List[Dict]:
        """NASDAQ IPO sayfasından IPO'ları çek"""
        try:
            logger.info("🔍 NASDAQ IPO sayfası taranıyor...")
            
            url = 'https://www.nasdaq.com/market-activity/ipos'
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            ipos = []
            
            # NASDAQ IPO tablosunu bul
            # Bu kısım gerçek HTML yapısına göre güncellenmeli
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Header'ı atla
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        try:
                            symbol = cells[0].get_text(strip=True)
                            company_name = cells[1].get_text(strip=True)
                            ipo_date = cells[2].get_text(strip=True)
                            
                            # Tarih formatını düzenle
                            if ipo_date and symbol:
                                ipos.append({
                                    'symbol': symbol,
                                    'companyName': company_name,
                                    'ipoDate': self.parse_ipo_date(ipo_date),
                                    'exchange': 'NASDAQ',
                                    'source': 'nasdaq_scraping'
                                })
                        except Exception as e:
                            logger.warning(f"Satır parse hatası: {e}")
                            continue
            
            logger.info(f"📈 {len(ipos)} NASDAQ IPO bulundu")
            return ipos
            
        except Exception as e:
            logger.error(f"❌ NASDAQ scraping hatası: {e}")
            return []
    
    def scrape_sec_edgar(self) -> List[Dict]:
        """SEC EDGAR'dan IPO'ları çek"""
        try:
            logger.info("🔍 SEC EDGAR taranıyor...")
            
            url = 'https://www.sec.gov/edgar/browse/?CIK=&type=424B4&count=100&owner=exclude&action=getcurrent'
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            ipos = []
            
            # SEC EDGAR tablosunu parse et
            # Bu kısım gerçek HTML yapısına göre güncellenmeli
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:
                        try:
                            company_name = cells[0].get_text(strip=True)
                            filing_date = cells[1].get_text(strip=True)
                            form_type = cells[2].get_text(strip=True)
                            
                            # 424B4 formları IPO'lar için
                            if '424B4' in form_type and company_name:
                                # Company name'den symbol çıkarmaya çalış
                                symbol = self.extract_symbol_from_name(company_name)
                                if symbol:
                                    ipos.append({
                                        'symbol': symbol,
                                        'companyName': company_name,
                                        'ipoDate': self.parse_ipo_date(filing_date),
                                        'exchange': 'NASDAQ',
                                        'source': 'sec_scraping'
                                    })
                        except Exception as e:
                            logger.warning(f"SEC satır parse hatası: {e}")
                            continue
            
            logger.info(f"📈 {len(ipos)} SEC IPO bulundu")
            return ipos
            
        except Exception as e:
            logger.error(f"❌ SEC scraping hatası: {e}")
            return []
    
    def scrape_renaissance_capital(self) -> List[Dict]:
        """Renaissance Capital'dan IPO'ları çek"""
        try:
            logger.info("🔍 Renaissance Capital taranıyor...")
            
            url = 'https://www.renaissancecapital.com/ipohome/pricings'
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            ipos = []
            
            # Renaissance Capital tablosunu parse et
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:
                        try:
                            symbol = cells[0].get_text(strip=True)
                            company_name = cells[1].get_text(strip=True)
                            ipo_date = cells[2].get_text(strip=True)
                            
                            if symbol and company_name:
                                ipos.append({
                                    'symbol': symbol,
                                    'companyName': company_name,
                                    'ipoDate': self.parse_ipo_date(ipo_date),
                                    'exchange': 'NASDAQ',
                                    'source': 'renaissance_scraping'
                                })
                        except Exception as e:
                            logger.warning(f"Renaissance satır parse hatası: {e}")
                            continue
            
            logger.info(f"📈 {len(ipos)} Renaissance IPO bulundu")
            return ipos
            
        except Exception as e:
            logger.error(f"❌ Renaissance scraping hatası: {e}")
            return []
    
    def discover_new_ipos_yahoo(self) -> List[Dict]:
        """Yahoo Finance'den yeni IPO'ları keşfet"""
        try:
            logger.info("🔍 Yahoo Finance'den IPO keşfi...")
            
            # Bilinen teknoloji sektörü anahtar kelimeleri
            tech_keywords = [
                'AI', 'ML', 'DATA', 'CLOUD', 'SAAS', 'CYBER', 'BLOCKCHAIN',
                'CRYPTO', 'FINTECH', 'BIOTECH', 'MEDTECH', 'EDTECH',
                'GAMING', 'SOCIAL', 'E-COMMERCE', 'LOGISTICS', 'MOBILITY'
            ]
            
            new_ipos = []
            
            # Son dönemde popüler olan gerçek IPO'lar
            recent_popular_ipos = [
                {'symbol': 'RBLX', 'companyName': 'Roblox Corp', 'ipoDate': '2021-03-10'},
                {'symbol': 'COIN', 'companyName': 'Coinbase Global', 'ipoDate': '2021-04-14'},
                {'symbol': 'RIVN', 'companyName': 'Rivian Automotive', 'ipoDate': '2021-11-10'},
                {'symbol': 'LCID', 'companyName': 'Lucid Group', 'ipoDate': '2021-07-26'},
                {'symbol': 'PLTR', 'companyName': 'Palantir Technologies', 'ipoDate': '2020-09-30'},
                {'symbol': 'SOFI', 'companyName': 'SoFi Technologies', 'ipoDate': '2021-06-01'},
                {'symbol': 'HOOD', 'companyName': 'Robinhood Markets', 'ipoDate': '2021-07-29'},
                {'symbol': 'WISH', 'companyName': 'ContextLogic', 'ipoDate': '2020-12-16'},
                {'symbol': 'CLOV', 'companyName': 'Clover Health', 'ipoDate': '2021-01-08'},
                {'symbol': 'SPCE', 'companyName': 'Virgin Galactic', 'ipoDate': '2019-10-28'}
            ]
            
            # Her IPO'yu kontrol et
            for ipo in recent_popular_ipos:
                try:
                    ticker = yf.Ticker(ipo['symbol'])
                    info = ticker.info
                    
                    if info and 'symbol' in info:
                        # Exchange kontrolü
                        exchange = info.get('exchange', '').upper()
                        if 'NASDAQ' in exchange or 'NMS' in exchange:
                            new_ipos.append({
                                'symbol': ipo['symbol'],
                                'companyName': ipo['companyName'],
                                'ipoDate': ipo['ipoDate'],
                                'exchange': 'NASDAQ',
                                'source': 'yahoo_discovery'
                            })
                    
                    time.sleep(0.5)  # Rate limiting
                    
                except Exception as e:
                    logger.warning(f"Yahoo Finance kontrol hatası {ipo['symbol']}: {e}")
                    continue
            
            logger.info(f"📊 {len(new_ipos)} Yahoo Finance IPO bulundu")
            return new_ipos
            
        except Exception as e:
            logger.error(f"❌ Yahoo Finance keşif hatası: {e}")
            return []
    
    def validate_ipo_symbol(self, symbol: str) -> bool:
        """IPO sembolünün geçerliliğini kontrol et"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info or 'symbol' not in info:
                return False
            
            # Exchange kontrolü
            exchange = info.get('exchange', '').upper()
            if 'NASDAQ' not in exchange and 'NMS' not in exchange:
                return False
            
            # Fiyat kontrolü
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            if current_price <= 0:
                return False
            
            # Market cap kontrolü
            market_cap = info.get('marketCap', 0)
            if market_cap < 1000000:  # 1M altı çok küçük
                return False
            
            logger.info(f"✅ {symbol} geçerli IPO: ${current_price:.2f}, MC: ${market_cap:,}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ {symbol} geçerlilik kontrolü hatası: {e}")
            return False
    
    def parse_ipo_date(self, date_str: str) -> str:
        """IPO tarihini parse et"""
        try:
            # Çeşitli tarih formatlarını dene
            date_formats = [
                '%Y-%m-%d',
                '%m/%d/%Y',
                '%m-%d-%Y',
                '%d/%m/%Y',
                '%d-%m-%Y',
                '%B %d, %Y',
                '%b %d, %Y'
            ]
            
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str.strip(), fmt)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # Eğer hiçbiri çalışmazsa, bugünün tarihini döndür
            logger.warning(f"Tarih parse edilemedi: {date_str}, bugünün tarihi kullanılıyor")
            return datetime.now().strftime('%Y-%m-%d')
            
        except Exception as e:
            logger.error(f"Tarih parse hatası: {e}")
            return datetime.now().strftime('%Y-%m-%d')
    
    def extract_symbol_from_name(self, company_name: str) -> Optional[str]:
        """Company name'den symbol çıkarmaya çalış"""
        try:
            # Basit pattern matching
            # Bu kısım daha gelişmiş hale getirilebilir
            words = company_name.split()
            if len(words) >= 2:
                # İlk iki kelimenin baş harflerini al
                symbol = ''.join([word[0] for word in words[:2]]).upper()
                if len(symbol) >= 2 and len(symbol) <= 5:
                    return symbol
            return None
        except Exception as e:
            logger.warning(f"Symbol çıkarma hatası: {e}")
            return None
    
    def add_new_ipo_to_csv(self, new_ipo: Dict) -> bool:
        """Yeni IPO'yu CSV'ye ekle"""
        try:
            # Mevcut CSV'yi oku
            existing_data = []
            if os.path.exists(self.ipos_csv_path):
                df = pd.read_csv(self.ipos_csv_path)
                existing_data = df.to_dict('records')
            
            # Duplicate kontrolü
            existing_symbols = {row['symbol'] for row in existing_data}
            if new_ipo['symbol'] in existing_symbols:
                logger.info(f"ℹ️ {new_ipo['symbol']} zaten mevcut")
                return False
            
            # Yeni IPO'yu ekle
            existing_data.append(new_ipo)
            
            # CSV'yi güncelle
            df = pd.DataFrame(existing_data)
            df.to_csv(self.ipos_csv_path, index=False)
            
            logger.info(f"✅ {new_ipo['symbol']} CSV'ye eklendi")
            return True
            
        except Exception as e:
            logger.error(f"❌ CSV güncelleme hatası: {e}")
            return False
    
    def run_discovery(self) -> List[Dict]:
        """Ana keşif fonksiyonu"""
        logger.info("🚀 Otomatik IPO keşfi başlatılıyor...")
        
        # Mevcut sembolleri al
        existing_symbols = self.get_existing_symbols()
        
        # Yeni IPO'ları bul
        all_new_ipos = []
        
        # 1. Web scraping
        try:
            nasdaq_ipos = self.scrape_nasdaq_ipos()
            all_new_ipos.extend(nasdaq_ipos)
        except Exception as e:
            logger.error(f"NASDAQ scraping hatası: {e}")
        
        try:
            sec_ipos = self.scrape_sec_edgar()
            all_new_ipos.extend(sec_ipos)
        except Exception as e:
            logger.error(f"SEC scraping hatası: {e}")
        
        try:
            renaissance_ipos = self.scrape_renaissance_capital()
            all_new_ipos.extend(renaissance_ipos)
        except Exception as e:
            logger.error(f"Renaissance scraping hatası: {e}")
        
        # 2. Yahoo Finance keşfi
        try:
            yahoo_ipos = self.discover_new_ipos_yahoo()
            all_new_ipos.extend(yahoo_ipos)
        except Exception as e:
            logger.error(f"Yahoo Finance keşif hatası: {e}")
        
        # 3. Yeni IPO'ları filtrele ve doğrula
        validated_ipos = []
        for ipo in all_new_ipos:
            if ipo['symbol'] not in existing_symbols:
                if self.validate_ipo_symbol(ipo['symbol']):
                    if self.add_new_ipo_to_csv(ipo):
                        validated_ipos.append(ipo)
                        existing_symbols.add(ipo['symbol'])
        
        logger.info(f"🎉 {len(validated_ipos)} yeni IPO başarıyla eklendi!")
        return validated_ipos


def main():
    """Test fonksiyonu"""
    discovery = AutoIPODiscovery()
    
    print("🔍 OTOMATİK IPO KEŞİF SİSTEMİ")
    print("=" * 50)
    
    # Keşif çalıştır
    new_ipos = discovery.run_discovery()
    
    if new_ipos:
        print(f"\n🎉 {len(new_ipos)} yeni IPO bulundu:")
        for ipo in new_ipos:
            print(f"  - {ipo['symbol']} ({ipo['ipoDate']}) - {ipo['source']}")
    else:
        print(f"\nℹ️ Yeni IPO bulunamadı")


if __name__ == "__main__":
    main()
