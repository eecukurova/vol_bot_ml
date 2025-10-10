#!/usr/bin/env python3
"""
BIST Sinyal Generator
ATR Trailing Stop + EMA(1) crossover/crossunder sinyalleri
"""

import json
import time
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
from typing import Dict, List, Optional, Tuple

class BISTSignalGenerator:
    def __init__(self, config_file='bist_config.json'):
        """BIST Sinyal Generator başlat"""
        # Konfigürasyon yükle
        with open(config_file, 'r') as f:
            self.cfg = json.load(f)
        
        # Logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('bist_signals.log')
            ]
        )
        self.log = logging.getLogger(__name__)
        
        # Telegram bot
        self.bot_token = self.cfg['telegram']['bot_token']
        self.chat_id = self.cfg['telegram']['chat_id']
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Sinyal state
        self.last_signals = {}
        self.symbols = self.cfg['symbols']
        
        self.log.info(f"🚀 BIST Signal Generator başlatıldı")
        self.log.info(f"📊 {len(self.symbols)} hisse takip ediliyor")
        self.log.info(f"⏰ Çalışma saatleri: {self.cfg['working_hours']['start']}-{self.cfg['working_hours']['end']}")
        self.log.info(f"📈 Timeframe: {self.cfg['timeframe']}")
    
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
                self.log.info("📱 BIST Telegram mesajı gönderildi")
            else:
                self.log.error(f"❌ Telegram hatası: {response.status_code}")
        except Exception as e:
            self.log.error(f"❌ Telegram gönderme hatası: {e}")
    
    def is_working_hours(self) -> bool:
        """Çalışma saatleri kontrolü"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        start_time = self.cfg['working_hours']['start']
        end_time = self.cfg['working_hours']['end']
        
        # Hafta sonu kontrolü
        if now.weekday() >= 5:  # Cumartesi=5, Pazar=6
            return False
        
        return start_time <= current_time <= end_time
    
    def get_bist_data(self, symbol: str, period: str = "5d") -> Optional[pd.DataFrame]:
        """BIST hisse verisi al"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=self.cfg['timeframe'])
            
            if df.empty:
                self.log.warning(f"⚠️ {symbol} için veri bulunamadı")
                return None
            
            # Sütun isimlerini küçük harfe çevir
            df.columns = [col.lower() for col in df.columns]
            
            return df
            
        except Exception as e:
            self.log.error(f"❌ {symbol} veri alma hatası: {e}")
            return None
    
    def calculate_atr_trailing_stop(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """ATR Trailing Stop hesapla"""
        try:
            # ATR hesapla
            high = df['high']
            low = df['low']
            close = df['close']
            
            # True Range hesapla
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # ATR hesapla
            atr = tr.rolling(window=self.cfg['atr_period']).mean()
            
            # ATR Trailing Stop hesapla
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
            df = self.get_bist_data(symbol)
            if df is None or len(df) < 50:
                return None
            
            # ATR Trailing Stop hesapla
            trailing_stop, atr = self.calculate_atr_trailing_stop(df)
            if trailing_stop is None:
                return None
            
            # EMA(1) hesapla
            ema1 = self.calculate_ema(df, 1)
            
            # Son değerleri al
            current_price = df['close'].iloc[-1]
            current_trailing = trailing_stop.iloc[-1]
            current_ema1 = ema1.iloc[-1]
            prev_ema1 = ema1.iloc[-2]
            prev_trailing = trailing_stop.iloc[-2]
            
            # Sinyal koşulları
            above = current_ema1 > current_trailing and prev_ema1 <= prev_trailing
            below = current_ema1 < current_trailing and prev_ema1 >= prev_trailing
            
            buy_signal = current_price > current_trailing and above
            sell_signal = current_price < current_trailing and below
            
            signal_data = {
                'symbol': symbol,
                'price': current_price,
                'trailing_stop': current_trailing,
                'ema1': current_ema1,
                'atr': atr.iloc[-1],
                'timestamp': df.index[-1],
                'buy_signal': buy_signal,
                'sell_signal': sell_signal
            }
            
            return signal_data
            
        except Exception as e:
            self.log.error(f"❌ {symbol} sinyal üretme hatası: {e}")
            return None
    
    def process_signals(self):
        """Tüm hisseler için sinyal işle"""
        if not self.is_working_hours():
            self.log.info("⏰ Çalışma saatleri dışında, bekleniyor...")
            return
        
        self.log.info(f"🔍 BIST sinyal kontrolü başlatılıyor - {len(self.symbols)} hisse")
        
        for symbol in self.symbols:
            try:
                signal_data = self.generate_signals(symbol)
                if signal_data is None:
                    continue
                
                symbol_name = symbol.replace('.IS', '')
                current_time = datetime.now().strftime('%H:%M:%S')
                
                # Buy sinyal kontrolü
                if signal_data['buy_signal']:
                    if self.last_signals.get(symbol) != 'BUY':
                        self.log.info(f"🎯 {symbol_name} BUY sinyali!")
                        
                        telegram_msg = f"""
🎯 <b>BIST BUY SİNYALİ</b>

📊 <b>Hisse:</b> {symbol_name}
💰 <b>Fiyat:</b> ₺{signal_data['price']:.2f}
📈 <b>EMA(1):</b> ₺{signal_data['ema1']:.2f}
🛡️ <b>Trailing Stop:</b> ₺{signal_data['trailing_stop']:.2f}
📊 <b>ATR:</b> ₺{signal_data['atr']:.2f}
⏰ <b>Zaman:</b> {current_time}

🚀 <b>ALIM SİNYALİ!</b>
"""
                        self.send_telegram_message(telegram_msg)
                        self.last_signals[symbol] = 'BUY'
                
                # Sell sinyal kontrolü
                elif signal_data['sell_signal']:
                    if self.last_signals.get(symbol) != 'SELL':
                        self.log.info(f"🎯 {symbol_name} SELL sinyali!")
                        
                        telegram_msg = f"""
🎯 <b>BIST SELL SİNYALİ</b>

📊 <b>Hisse:</b> {symbol_name}
💰 <b>Fiyat:</b> ₺{signal_data['price']:.2f}
📈 <b>EMA(1):</b> ₺{signal_data['ema1']:.2f}
🛡️ <b>Trailing Stop:</b> ₺{signal_data['trailing_stop']:.2f}
📊 <b>ATR:</b> ₺{signal_data['atr']:.2f}
⏰ <b>Zaman:</b> {current_time}

🔻 <b>SATIM SİNYALİ!</b>
"""
                        self.send_telegram_message(telegram_msg)
                        self.last_signals[symbol] = 'SELL'
                
                # Sinyal yoksa state'i temizle
                else:
                    if self.last_signals.get(symbol):
                        self.last_signals[symbol] = None
                
            except Exception as e:
                self.log.error(f"❌ {symbol} işleme hatası: {e}")
        
        self.log.info("✅ BIST sinyal kontrolü tamamlandı")
    
    def run(self):
        """Ana döngü"""
        self.log.info("🚀 BIST Signal Generator başlatıldı")
        
        while True:
            try:
                current_time = datetime.now()
                self.log.info(f"🔄 BIST_CYCLE_START: {current_time.strftime('%H:%M:%S')}")
                
                # 15 dakikalık mum kapanışı için 1 dakika bekle
                current_minute = current_time.minute
                if current_minute % 15 == 0:  # 00:00, 00:15, 00:30, 00:45
                    self.log.info("⏰ 15 dakikalık mum kapanışı için 60 saniye bekleniyor...")
                    time.sleep(60)  # 1 dakika bekle
                    current_time = datetime.now()
                    self.log.info(f"🔄 BIST_CYCLE_CONTINUE: {current_time.strftime('%H:%M:%S')}")
                
                self.process_signals()
                
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
                
                self.log.info(f"⏰ Bir sonraki kontrol: {next_check_time.strftime('%H:%M:%S')} ({wait_seconds:.0f} saniye sonra)")
                time.sleep(wait_seconds)
                
            except KeyboardInterrupt:
                self.log.info("🛑 BIST Signal Generator durduruluyor...")
                break
            except Exception as e:
                self.log.error(f"❌ Ana döngü hatası: {e}")
                time.sleep(60)  # Hata durumunda 1 dakika bekle

if __name__ == "__main__":
    generator = BISTSignalGenerator()
    generator.run()
