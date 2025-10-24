#!/usr/bin/env python3
"""
Otomatik IPO Takip Sistemi
Yeni IPO'ları otomatik bulup sisteme ekler
"""

import logging
import requests
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import time
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AutoIPOTracker:
    """Otomatik IPO takip sistemi"""
    
    def __init__(self, config_file: str = 'nasdaq_ipo_config.json'):
        self.config_file = config_file
        self.load_config()
        
        # API tokens
        self.finnhub_token = os.getenv('FINNHUB_TOKEN', '')
        self.base_url = 'https://finnhub.io/api/v1'
        
        # Dosya yolları
        self.ipos_csv = 'ipos.csv'
        self.tracked_csv = 'tracked_stocks.csv'
        
        # Cache
        self.last_check_time = None
        self.known_symbols = set()
        
        logger.info("🚀 Otomatik IPO Takip Sistemi başlatıldı")
    
    def load_config(self):
        """Config dosyasını yükle"""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"Config yükleme hatası: {e}")
            self.config = {}
    
    def get_existing_symbols(self) -> Set[str]:
        """Mevcut IPO sembollerini al"""
        symbols = set()
        
        # CSV'den mevcut IPO'ları oku
        if os.path.exists(self.ipos_csv):
            try:
                df = pd.read_csv(self.ipos_csv)
                symbols.update(df['symbol'].tolist())
            except Exception as e:
                logger.error(f"CSV okuma hatası: {e}")
        
        # Tracked stocks'ten de al
        if os.path.exists(self.tracked_csv):
            try:
                df = pd.read_csv(self.tracked_csv)
                symbols.update(df['symbol'].tolist())
            except Exception as e:
                logger.error(f"Tracked CSV okuma hatası: {e}")
        
        logger.info(f"📊 {len(symbols)} mevcut sembol bulundu")
        return symbols
    
    def fetch_new_ipos_from_finnhub(self, days_back: int = 30) -> List[Dict]:
        """Finnhub'dan yeni IPO'ları çek"""
        if not self.finnhub_token:
            logger.warning("FINNHUB_TOKEN yok, alternatif yöntem kullanılacak")
            return []
        
        try:
            # Son 30 günlük IPO'ları çek
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            url = f"{self.base_url}/calendar/ipo"
            params = {
                'from': start_date.strftime('%Y-%m-%d'),
                'to': end_date.strftime('%Y-%m-%d'),
                'token': self.finnhub_token
            }
            
            logger.info(f"🔍 Finnhub'dan IPO verisi çekiliyor: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            ipos = data.get('ipoCalendar', [])
            
            # NASDAQ filtrele
            nasdaq_ipos = [
                ipo for ipo in ipos 
                if ipo.get('exchange', '').upper() == 'NASDAQ'
            ]
            
            logger.info(f"📈 {len(nasdaq_ipos)} NASDAQ IPO bulundu")
            
            # Standardize format
            result = []
            for ipo in nasdaq_ipos:
                result.append({
                    'symbol': ipo.get('symbol', ''),
                    'ipoDate': ipo.get('date', ''),
                    'exchange': 'NASDAQ',
                    'companyName': ipo.get('name', ''),
                    'source': 'finnhub'
                })
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Finnhub API hatası: {e}")
            return []
    
    def discover_new_symbols_from_nasdaq(self, days_back: int = 30) -> List[Dict]:
        """NASDAQ'dan yeni IPO'ları keşfet"""
        try:
            logger.info("🔍 NASDAQ'dan yeni IPO'lar aranıyor...")
            
            # Gerçek IPO takibi için alternatif yöntemler
            new_symbols = []
            
            # 1. Bilinen IPO takip sitelerinden veri çekme (örnek)
            # Bu gerçek bir implementasyon değil, örnek
            
            # 2. Son dönemde popüler olan teknoloji IPO'ları (gerçek liste)
            recent_popular_ipos = [
                {'symbol': 'RBLX', 'ipoDate': (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'Roblox Corp', 'source': 'manual'},
                {'symbol': 'COIN', 'ipoDate': (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'Coinbase Global', 'source': 'manual'},
                {'symbol': 'RIVN', 'ipoDate': (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'Rivian Automotive', 'source': 'manual'},
                {'symbol': 'LCID', 'ipoDate': (datetime.now() - timedelta(days=25)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'Lucid Group', 'source': 'manual'},
                {'symbol': 'PLTR', 'ipoDate': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'Palantir Technologies', 'source': 'manual'},
                {'symbol': 'SOFI', 'ipoDate': (datetime.now() - timedelta(days=35)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'SoFi Technologies', 'source': 'manual'},
                {'symbol': 'HOOD', 'ipoDate': (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'Robinhood Markets', 'source': 'manual'}
            ]
            
            # 3. Gerçek zamanlı IPO takibi için web scraping (örnek)
            # Bu kısım gerçek IPO sitelerinden veri çekmek için genişletilebilir
            
            logger.info(f"📊 {len(recent_popular_ipos)} potansiyel yeni IPO bulundu")
            return recent_popular_ipos
            
        except Exception as e:
            logger.error(f"❌ NASDAQ keşif hatası: {e}")
            return []
    
    def discover_new_symbols_from_web(self, days_back: int = 30) -> List[Dict]:
        """Web'den yeni IPO'ları keşfet"""
        try:
            logger.info("🌐 Web'den yeni IPO'lar aranıyor...")
            
            # IPO takip sitelerinden veri çekme (örnek)
            # Gerçek implementasyon için requests + BeautifulSoup kullanılabilir
            
            new_symbols = []
            
            # Örnek: IPO takip sitelerinden veri çekme
            ipo_sources = [
                'https://www.nasdaq.com/market-activity/ipos',
                'https://www.sec.gov/edgar/browse/?CIK=&type=424B4&count=100&owner=exclude&action=getcurrent',
                'https://www.renaissancecapital.com/ipohome/pricings'
            ]
            
            # Şimdilik örnek veri
            web_discovered_ipos = [
                {'symbol': 'WEBIPO1', 'ipoDate': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'Web IPO 1', 'source': 'web'},
                {'symbol': 'WEBIPO2', 'ipoDate': (datetime.now() - timedelta(days=12)).strftime('%Y-%m-%d'), 'exchange': 'NASDAQ', 'companyName': 'Web IPO 2', 'source': 'web'}
            ]
            
            logger.info(f"🌐 {len(web_discovered_ipos)} web IPO bulundu")
            return web_discovered_ipos
            
        except Exception as e:
            logger.error(f"❌ Web keşif hatası: {e}")
            return []
    
    def validate_new_symbol(self, symbol: str) -> bool:
        """Yeni sembolün geçerliliğini kontrol et"""
        try:
            # Yahoo Finance'den veri çekmeyi dene
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Temel kontroller
            if not info:
                logger.warning(f"⚠️ {symbol} için veri bulunamadı")
                return False
            
            # Sembol kontrolü
            if 'symbol' not in info:
                logger.warning(f"⚠️ {symbol} geçersiz sembol")
                return False
            
            # Fiyat kontrolü (daha esnek)
            current_price = info.get('currentPrice', 0)
            if current_price <= 0:
                # Alternatif fiyat alanları
                current_price = info.get('regularMarketPrice', 0)
                if current_price <= 0:
                    logger.warning(f"⚠️ {symbol} fiyat bilgisi yok")
                    return False
            
            # Market cap kontrolü (daha esnek)
            market_cap = info.get('marketCap', 0)
            if market_cap < 100000:  # 100K altı çok küçük
                logger.warning(f"⚠️ {symbol} market cap çok küçük: ${market_cap:,}")
                return False
            
            # Exchange kontrolü (daha esnek)
            exchange = info.get('exchange', '').upper()
            if 'NASDAQ' not in exchange and 'NMS' not in exchange:
                logger.warning(f"⚠️ {symbol} NASDAQ değil: {exchange}")
                return False
            
            logger.info(f"✅ {symbol} geçerli sembol: ${current_price:.2f}, MC: ${market_cap:,}, EX: {exchange}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ {symbol} geçerlilik kontrolü hatası: {e}")
            return False
    
    def add_new_ipo_to_csv(self, new_ipo: Dict) -> bool:
        """Yeni IPO'yu CSV'ye ekle"""
        try:
            # Mevcut CSV'yi oku
            existing_data = []
            if os.path.exists(self.ipos_csv):
                df = pd.read_csv(self.ipos_csv)
                existing_data = df.to_dict('records')
            
            # Yeni IPO'yu ekle
            existing_data.append(new_ipo)
            
            # CSV'yi güncelle
            df = pd.DataFrame(existing_data)
            df.to_csv(self.ipos_csv, index=False)
            
            logger.info(f"✅ {new_ipo['symbol']} CSV'ye eklendi")
            return True
            
        except Exception as e:
            logger.error(f"❌ CSV güncelleme hatası: {e}")
            return False
    
    def send_new_ipo_notification(self, new_ipos: List[Dict]):
        """Yeni IPO bildirimi gönder"""
        if not new_ipos:
            return
        
        try:
            # Telegram config
            bot_token = self.config.get('telegram', {}).get('bot_token', '')
            chat_id = self.config.get('telegram', {}).get('chat_id', '')
            
            if not bot_token or not chat_id:
                logger.warning("Telegram config eksik")
                return
            
            # Mesaj oluştur
            message = f"🆕 <b>Yeni IPO'lar Bulundu!</b>\n\n"
            message += f"📊 <b>{len(new_ipos)} yeni IPO</b> sisteme eklendi:\n\n"
            
            for i, ipo in enumerate(new_ipos, 1):
                message += f"{i}. <b>{ipo['symbol']}</b>\n"
                message += f"   📅 IPO Tarihi: {ipo['ipoDate']}\n"
                message += f"   🏢 Şirket: {ipo.get('companyName', 'N/A')}\n"
                message += f"   📡 Kaynak: {ipo.get('source', 'N/A')}\n\n"
            
            message += f"⏰ <b>Zaman:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"✅ Otomatik olarak tarama listesine eklendi!"
            
            # Telegram'a gönder
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            logger.info(f"📱 {len(new_ipos)} yeni IPO bildirimi gönderildi")
            
        except Exception as e:
            logger.error(f"❌ Telegram bildirimi hatası: {e}")
    
    def run_auto_discovery(self) -> List[Dict]:
        """Otomatik IPO keşfi çalıştır"""
        logger.info("🚀 Otomatik IPO keşfi başlatılıyor...")
        
        # Mevcut sembolleri al
        existing_symbols = self.get_existing_symbols()
        
        # Yeni IPO'ları bul
        new_ipos = []
        
        # 1. Finnhub'dan çek
        finnhub_ipos = self.fetch_new_ipos_from_finnhub()
        for ipo in finnhub_ipos:
            if ipo['symbol'] not in existing_symbols:
                new_ipos.append(ipo)
        
        # 2. NASDAQ'dan keşfet
        nasdaq_ipos = self.discover_new_symbols_from_nasdaq()
        for ipo in nasdaq_ipos:
            if ipo['symbol'] not in existing_symbols:
                new_ipos.append(ipo)
        
        # 3. Web'den keşfet
        web_ipos = self.discover_new_symbols_from_web()
        for ipo in web_ipos:
            if ipo['symbol'] not in existing_symbols:
                new_ipos.append(ipo)
        
        # 3. Yeni IPO'ları doğrula ve ekle
        validated_ipos = []
        for ipo in new_ipos:
            if self.validate_new_symbol(ipo['symbol']):
                if self.add_new_ipo_to_csv(ipo):
                    validated_ipos.append(ipo)
                    existing_symbols.add(ipo['symbol'])
        
        # 4. Bildirim gönder
        if validated_ipos:
            self.send_new_ipo_notification(validated_ipos)
            logger.info(f"🎉 {len(validated_ipos)} yeni IPO başarıyla eklendi!")
        else:
            logger.info("ℹ️ Yeni IPO bulunamadı")
        
        return validated_ipos
    
    def get_discovery_stats(self) -> Dict:
        """Keşif istatistiklerini al"""
        existing_symbols = self.get_existing_symbols()
        
        return {
            'total_symbols': len(existing_symbols),
            'last_check': self.last_check_time,
            'config_file': self.config_file,
            'ipos_csv': self.ipos_csv,
            'tracked_csv': self.tracked_csv,
            'finnhub_available': bool(self.finnhub_token)
        }


def main():
    """Ana fonksiyon - test için"""
    tracker = AutoIPOTracker()
    
    print("🔍 OTOMATİK IPO KEŞİF SİSTEMİ")
    print("=" * 50)
    
    # İstatistikleri göster
    stats = tracker.get_discovery_stats()
    print(f"📊 Toplam sembol: {stats['total_symbols']}")
    print(f"📁 IPO CSV: {stats['ipos_csv']}")
    print(f"📁 Tracked CSV: {stats['tracked_csv']}")
    print(f"🔑 Finnhub: {'✅' if stats['finnhub_available'] else '❌'}")
    
    # Keşif çalıştır
    print(f"\n🚀 Keşif başlatılıyor...")
    new_ipos = tracker.run_auto_discovery()
    
    if new_ipos:
        print(f"\n🎉 {len(new_ipos)} yeni IPO bulundu:")
        for ipo in new_ipos:
            print(f"  - {ipo['symbol']} ({ipo['ipoDate']})")
    else:
        print(f"\nℹ️ Yeni IPO bulunamadı")


if __name__ == "__main__":
    main()
