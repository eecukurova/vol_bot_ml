#!/usr/bin/env python3
"""
NASDAQ Dynamic Scanner - $5 altındaki tüm teknoloji firmalarını tarar
"""

import yfinance as yf
import pandas as pd
import json
import time
import logging
import requests
from datetime import datetime
import pytz
from typing import Dict, List, Optional

class NASDAQDynamicScanner:
    def __init__(self, config_file='nasdaq_dynamic_config.json'):
        # Logging setup
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('nasdaq_dynamic_signals.log')
            ]
        )
        self.log = logging.getLogger(__name__)

        # Load configuration
        with open(config_file, 'r') as f:
            self.cfg = json.load(f)
        
        # Telegram bot
        self.bot_token = self.cfg['telegram']['bot_token']
        self.chat_id = self.cfg['telegram']['chat_id']
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Scanner parameters
        self.max_price = self.cfg.get('max_price', 5.00)
        self.min_volume = self.cfg.get('min_volume', 100000)  # Minimum günlük volume
        self.min_market_cap = self.cfg.get('min_market_cap', 10000000)  # 10M minimum
        self.max_market_cap = self.cfg.get('max_market_cap', 1000000000)  # 1B maximum
        
        # Signal state
        self.last_signals = {}
        self.scanned_symbols = set()
        
        self.log.info(f"🚀 NASDAQ Dynamic Scanner başlatıldı")
        self.log.info(f"💰 Max fiyat: ${self.max_price}")
        self.log.info(f"📊 Min volume: {self.min_volume:,}")
        self.log.info(f"🏢 Market cap: ${self.min_market_cap:,} - ${self.max_market_cap:,}")

    def send_telegram_message(self, message: str):
        """Telegram'a mesaj gönder"""
        try:
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(self.base_url, data=data, timeout=10)
            if response.status_code == 200:
                self.log.info("📱 NASDAQ Dynamic Telegram mesajı gönderildi")
            else:
                self.log.error(f"❌ Telegram hatası: {response.status_code}")
        except Exception as e:
            self.log.error(f"❌ Telegram gönderme hatası: {e}")

    def is_working_hours(self) -> bool:
        """Çalışma saatleri kontrolü - UTC"""
        from datetime import datetime, timezone
        
        utc_tz = timezone.utc
        now = datetime.now(utc_tz)
        current_time = now.strftime("%H:%M")
        start_time = self.cfg['working_hours']['start']
        end_time = self.cfg['working_hours']['end']
        
        if now.weekday() >= 5:  # Hafta sonu
            return False
        
        return start_time <= current_time <= end_time

    def get_nasdaq_symbols(self) -> List[str]:
        """NASDAQ'tan teknoloji hisselerini çek"""
        try:
            # Bilinen teknoloji hisse listesi (genişletilmiş)
            tech_symbols = [
                # Büyük teknoloji firmaları
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'ADBE', 'CRM',
                'ORCL', 'INTC', 'AMD', 'CSCO', 'IBM', 'QCOM', 'TXN', 'AVGO', 'MU', 'AMAT',
                
                # Orta ölçekli teknoloji
                'SNOW', 'PLTR', 'CRWD', 'ZS', 'OKTA', 'NET', 'DDOG', 'MDB', 'TWLO', 'SQ',
                'PYPL', 'ROKU', 'SPOT', 'ZM', 'DOCU', 'WDAY', 'NOW', 'TEAM', 'SHOP', 'ABNB',
                
                # Küçük teknoloji hisseleri
                'KPLTW', 'MNYWW', 'EPWK', 'CYCU', 'AEVAW', 'YYAI', 'WCT', 'ZPTA', 'EGLXF', 'VEEA',
                'ILLR', 'SELX', 'TDTH', 'ZSPC', 'CLPS', 'CXAIW', 'CHR', 'FPAY', 'IOTR', 'AIRE',
                'OPTT', 'FEMY', 'SENS', 'ARBK', 'DKI', 'MYPS', 'ISPC', 'DDOG', 'SNOW', 'PLTR',
                
                # Ek teknoloji hisseleri
                'U', 'SOFI', 'HOOD', 'COIN', 'RBLX', 'PTON', 'PINS', 'SNAP', 'TWTR', 'UBER',
                'LYFT', 'DASH', 'GRAB', 'BABA', 'JD', 'PDD', 'BILI', 'IQ', 'VIPS', 'WB',
                
                # Fintech
                'SQ', 'PYPL', 'AFRM', 'UPST', 'LC', 'SOFI', 'HOOD', 'COIN', 'MSTR', 'RIOT',
                
                # SaaS/Cloud
                'SNOW', 'DDOG', 'NET', 'ZS', 'CRWD', 'OKTA', 'PLTR', 'MDB', 'TWLO', 'WDAY',
                'NOW', 'TEAM', 'SHOP', 'ABNB', 'DOCU', 'ZM', 'ROKU', 'SPOT', 'SQ', 'PYPL'
            ]
            
            self.log.info(f"📊 {len(tech_symbols)} teknoloji hissesi yüklendi")
            return tech_symbols
            
        except Exception as e:
            self.log.error(f"❌ NASDAQ sembol çekme hatası: {e}")
            return []

    def filter_tech_stocks(self, symbols: List[str]) -> List[Dict]:
        """Teknoloji hisselerini filtrele"""
        filtered_stocks = []
        
        self.log.info(f"🔍 {len(symbols)} hisse filtreleniyor...")
        
        for i, symbol in enumerate(symbols):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                # Temel bilgileri al
                current_price = info.get('currentPrice', 0)
                volume = info.get('volume', 0)
                market_cap = info.get('marketCap', 0)
                sector = info.get('sector', '').lower()
                industry = info.get('industry', '').lower()
                
                # Fiyat kontrolü
                if not current_price or current_price > self.max_price:
                    continue
                
                # Volume kontrolü
                if volume < self.min_volume:
                    continue
                
                # Market cap kontrolü
                if not market_cap or market_cap < self.min_market_cap or market_cap > self.max_market_cap:
                    continue
                
                # Sektör kontrolü
                is_tech = (
                    'technology' in sector or
                    'software' in industry or
                    'hardware' in industry or
                    'semiconductor' in industry or
                    'internet' in industry or
                    'telecommunications' in industry or
                    'communication services' in sector or
                    'consumer discretionary' in sector  # E-commerce, streaming vb.
                )
                
                if not is_tech:
                    continue
                
                filtered_stocks.append({
                    'symbol': symbol,
                    'name': info.get('longName', symbol),
                    'price': current_price,
                    'volume': volume,
                    'market_cap': market_cap,
                    'sector': sector,
                    'industry': industry
                })
                
                self.log.info(f"✅ {symbol}: ${current_price:.2f} | Vol: {volume:,} | Cap: ${market_cap:,}")
                
                # Rate limiting
                time.sleep(0.1)
                
                # Her 50 hisse için progress
                if (i + 1) % 50 == 0:
                    self.log.info(f"📊 {i + 1}/{len(symbols)} hisse kontrol edildi")
                
            except Exception as e:
                self.log.warning(f"⚠️ {symbol} için bilgi alınamadı: {e}")
                continue
        
        self.log.info(f"🎯 {len(filtered_stocks)} hisse filtrelendi")
        return filtered_stocks

    def get_stock_data(self, symbol: str, period: str = "5d") -> Optional[pd.DataFrame]:
        """Hisse verisi al"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval='15m')
            
            if df.empty or len(df) < 50:
                return None
            
            df.columns = [col.lower() for col in df.columns]
            return df
            
        except Exception as e:
            self.log.error(f"❌ {symbol} veri alma hatası: {e}")
            return None

    def calculate_atr_trailing_stop(self, df: pd.DataFrame) -> tuple:
        """ATR Trailing Stop hesapla"""
        try:
            # ATR hesapla
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            atr = tr.rolling(window=self.cfg['atr_period']).mean()
            n_loss = self.cfg['key_value'] * atr
            src = close
            
            # Trailing Stop hesaplama
            trailing_stop = pd.Series(index=df.index, dtype=float)
            trailing_stop.iloc[0] = src.iloc[0] - n_loss.iloc[0]
            
            for i in range(1, len(df)):
                prev_trailing = trailing_stop.iloc[i-1]
                current_src = src.iloc[i]
                prev_src = src.iloc[i-1]
                current_n_loss = n_loss.iloc[i]
                
                if current_src > prev_trailing and prev_src > prev_trailing:
                    trailing_stop.iloc[i] = max(prev_trailing, current_src - current_n_loss)
                elif current_src < prev_trailing and prev_src < prev_trailing:
                    trailing_stop.iloc[i] = min(prev_trailing, current_src + current_n_loss)
                elif current_src > prev_trailing:
                    trailing_stop.iloc[i] = current_src - current_n_loss
                else:
                    trailing_stop.iloc[i] = current_src + current_n_loss
            
            return trailing_stop, atr
            
        except Exception as e:
            self.log.error(f"❌ ATR Trailing Stop hesaplama hatası: {e}")
            return None, None

    def calculate_ema(self, df: pd.DataFrame, period: int = 1) -> pd.Series:
        """EMA hesapla"""
        return df['close'].ewm(span=period).mean()

    def generate_signals(self, symbol: str) -> Optional[Dict]:
        """Hisse için sinyal üret"""
        try:
            df = self.get_stock_data(symbol)
            if df is None:
                return None
            
            trailing_stop, atr = self.calculate_atr_trailing_stop(df)
            if trailing_stop is None:
                return None
            
            ema1 = self.calculate_ema(df, 1)
            
            current_price = df['close'].iloc[-1]
            current_trailing = trailing_stop.iloc[-1]
            current_ema1 = ema1.iloc[-1]
            prev_ema1 = ema1.iloc[-2]
            prev_trailing = trailing_stop.iloc[-2]
            
            above = current_ema1 > current_trailing and prev_ema1 <= prev_trailing
            below = current_ema1 < current_trailing and prev_ema1 >= prev_trailing
            
            buy_signal = current_price > current_trailing and above
            sell_signal = current_price < current_trailing and below
            
            return {
                'symbol': symbol,
                'price': current_price,
                'trailing_stop': current_trailing,
                'ema1': current_ema1,
                'atr': atr.iloc[-1],
                'timestamp': df.index[-1],
                'buy_signal': buy_signal,
                'sell_signal': sell_signal
            }
            
        except Exception as e:
            self.log.error(f"❌ {symbol} sinyal üretme hatası: {e}")
            return None

    def scan_and_process_signals(self):
        """Tüm hisseleri tara ve sinyal işle"""
        if not self.is_working_hours():
            self.log.info("⏰ Çalışma saatleri dışında, bekleniyor...")
            return
        
        # Hisse listesini al
        symbols = self.get_nasdaq_symbols()
        if not symbols:
            self.log.warning("⚠️ Hiç hisse bulunamadı")
            return
        
        # Hisse filtrele
        filtered_stocks = self.filter_tech_stocks(symbols)
        if not filtered_stocks:
            self.log.warning("⚠️ Filtrelenmiş hisse bulunamadı")
            return
        
        self.log.info(f"🔍 {len(filtered_stocks)} hisse için sinyal kontrolü başlatılıyor")
        
        signals_found = 0
        for stock in filtered_stocks:
            symbol = stock['symbol']
            try:
                signal_data = self.generate_signals(symbol)
                if signal_data is None:
                    continue
                
                current_time = datetime.now().strftime('%H:%M:%S')
                
                # Buy sinyal kontrolü
                if signal_data['buy_signal']:
                    if self.last_signals.get(symbol) != 'BUY':
                        self.log.info(f"🎯 {symbol} BUY sinyali!")
                        
                        telegram_msg = f"""
🇺🇸 <b>NASDAQ DYNAMIC BUY SİNYALİ</b>

📊 <b>Hisse:</b> {symbol}
🏢 <b>Şirket:</b> {stock['name'][:30]}
💰 <b>Fiyat:</b> ${signal_data['price']:.2f}
📈 <b>EMA(1):</b> ${signal_data['ema1']:.2f}
🛡️ <b>Trailing Stop:</b> ${signal_data['trailing_stop']:.2f}
📊 <b>ATR:</b> ${signal_data['atr']:.2f}
📊 <b>Volume:</b> {stock['volume']:,}
🏢 <b>Market Cap:</b> ${stock['market_cap']:,}
⏰ <b>Zaman:</b> {current_time} UTC

🚀 <b>ALIM SİNYALİ!</b>
"""
                        self.send_telegram_message(telegram_msg)
                        self.last_signals[symbol] = 'BUY'
                        signals_found += 1
                
                # Sell sinyal kontrolü
                elif signal_data['sell_signal']:
                    if self.last_signals.get(symbol) != 'SELL':
                        self.log.info(f"🎯 {symbol} SELL sinyali!")
                        
                        telegram_msg = f"""
🇺🇸 <b>NASDAQ DYNAMIC SELL SİNYALİ</b>

📊 <b>Hisse:</b> {symbol}
🏢 <b>Şirket:</b> {stock['name'][:30]}
💰 <b>Fiyat:</b> ${signal_data['price']:.2f}
📈 <b>EMA(1):</b> ${signal_data['ema1']:.2f}
🛡️ <b>Trailing Stop:</b> ${signal_data['trailing_stop']:.2f}
📊 <b>ATR:</b> ${signal_data['atr']:.2f}
📊 <b>Volume:</b> {stock['volume']:,}
🏢 <b>Market Cap:</b> ${stock['market_cap']:,}
⏰ <b>Zaman:</b> {current_time} UTC

🔻 <b>SATIM SİNYALİ!</b>
"""
                        self.send_telegram_message(telegram_msg)
                        self.last_signals[symbol] = 'SELL'
                        signals_found += 1
                
                # Sinyal yoksa state'i temizle
                else:
                    if self.last_signals.get(symbol):
                        self.last_signals[symbol] = None
                
            except Exception as e:
                self.log.error(f"❌ {symbol} işleme hatası: {e}")
        
        self.log.info(f"✅ Tarama tamamlandı - {signals_found} sinyal bulundu")

    def run(self):
        """Ana döngü"""
        self.log.info("🚀 NASDAQ Dynamic Scanner başlatıldı")
        
        while True:
            try:
                current_time = datetime.now()
                self.log.info(f"🔄 DYNAMIC_SCAN_START: {current_time.strftime('%H:%M:%S')}")
                
                # 15 dakikalık mum kapanışı için 1 dakika bekle
                current_minute = current_time.minute
                if current_minute % 15 == 1:  # 00:01, 00:16, 00:31, 00:46
                    self.log.info("⏰ 15 dakikalık mum kapanışı için 60 saniye bekleniyor...")
                    time.sleep(60)
                    current_time = datetime.now()
                    self.log.info(f"🔄 DYNAMIC_SCAN_CONTINUE: {current_time.strftime('%H:%M:%S')}")
                
                self.scan_and_process_signals()
                
                # Bir sonraki 15 dakikalık periyoda kadar bekle
                current_time = datetime.now()
                next_check_minute = ((current_time.minute // 15) + 1) * 15
                if next_check_minute >= 60:
                    next_check_minute = 0
                    next_check_hour = current_time.hour + 1
                else:
                    next_check_hour = current_time.hour
                
                next_check_time = current_time.replace(hour=next_check_hour, minute=next_check_minute, second=0, microsecond=0)
                wait_seconds = (next_check_time - current_time).total_seconds()
                
                self.log.info(f"⏰ Bir sonraki tarama: {next_check_time.strftime('%H:%M:%S')} ({wait_seconds:.0f} saniye sonra)")
                time.sleep(wait_seconds)
                
            except KeyboardInterrupt:
                self.log.info("🛑 NASDAQ Dynamic Scanner durduruluyor...")
                break
            except Exception as e:
                self.log.error(f"❌ Ana döngü hatası: {e}")
                time.sleep(60)

if __name__ == "__main__":
    scanner = NASDAQDynamicScanner()
    scanner.run()
