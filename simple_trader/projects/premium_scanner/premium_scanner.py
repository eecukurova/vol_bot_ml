#!/usr/bin/env python3
"""
Premium Stock Scanner
AMD, NVDA, TSLA gibi premium teknoloji hisselerini tarar
4H Heikin Ashi ile ATR SuperTrend stratejisi kullanır
"""

import json
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np

class PremiumStockScanner:
    def __init__(self, config_file: str = "premium_scanner_config.json"):
        """Premium Stock Scanner başlat"""
        self.cfg = self.load_config(config_file)
        
        # Logging setup
        logging.basicConfig(
            level=getattr(logging, self.cfg['logging']['level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.cfg['logging']['file']),
                logging.StreamHandler()
            ]
        )
        self.log = logging.getLogger('PremiumScanner')
        
        # Premium hisse listesi
        self.premium_stocks = self.cfg['premium_stocks']
        
        # Timeframe listesi
        self.timeframes = self.cfg.get('timeframes', ['4h'])
        
        # ATR SuperTrend parametreleri
        self.atr_period = self.cfg['atr_period']
        self.key_value = self.cfg['key_value']
        self.factor = self.cfg['factor']
        
        # Telegram settings
        self.telegram_enabled = self.cfg['telegram']['enabled']
        if self.telegram_enabled:
            self.bot_token = self.cfg['telegram']['bot_token']
            self.chat_id = self.cfg['telegram']['chat_id']
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            self.log.info("📱 Telegram bildirimleri aktif")
        
        self.log.info("🚀 Premium Stock Scanner başlatıldı")
        self.log.info(f"📊 Premium hisseler: {len(self.premium_stocks)}")
        self.log.info(f"⏰ Tarama aralığı: {self.cfg['check_interval']} saniye")
        self.log.info(f"🕯️ Heikin Ashi: Aktif")
        self.log.info(f"📈 Timeframes: {', '.join(self.timeframes)}")

    def load_config(self, config_file: str) -> Dict:
        """Konfigürasyon dosyasını yükle"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Konfigürasyon yükleme hatası: {e}")
            return self.get_default_config()

    def get_default_config(self) -> Dict:
        """Varsayılan konfigürasyon"""
        return {
            "timeframes": ["4h", "1h"],
            "atr_period": 10,
            "key_value": 3,
            "factor": 1.5,
            "check_interval": 1800,  # 30 dakika
            "premium_stocks": [
                "AMD", "NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "META", "AMZN",
                "NFLX", "CRM", "ADBE", "INTC", "QCOM", "AVGO", "TXN", "MU",
                "AMAT", "LRCX", "KLAC", "MRVL", "SNPS", "CDNS", "ANSS", "FTNT"
            ],
            "telegram": {
                "enabled": True,
                "bot_token": "YOUR_BOT_TOKEN",
                "chat_id": "YOUR_CHAT_ID"
            },
            "logging": {
                "level": "INFO",
                "file": "premium_scanner.log"
            }
        }

    def calculate_heikin_ashi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Heikin Ashi mumları hesapla - Basit versiyon"""
        ha_df = df.copy()
        
        # Heikin Ashi kolonlarını ekle
        ha_df['ha_close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
        ha_df['ha_open'] = 0.0
        ha_df['ha_high'] = 0.0
        ha_df['ha_low'] = 0.0
        
        # İlk Heikin Ashi Open
        ha_df.iloc[0, ha_df.columns.get_loc('ha_open')] = (df.iloc[0]['Open'] + df.iloc[0]['Close']) / 2
        
        # Sonraki Heikin Ashi değerleri
        for i in range(1, len(df)):
            # Heikin Ashi Open
            ha_df.iloc[i, ha_df.columns.get_loc('ha_open')] = (
                ha_df.iloc[i-1]['ha_open'] + ha_df.iloc[i-1]['ha_close']
            ) / 2
            
            # Heikin Ashi High
            ha_df.iloc[i, ha_df.columns.get_loc('ha_high')] = max(
                df.iloc[i]['High'], ha_df.iloc[i]['ha_open'], ha_df.iloc[i]['ha_close']
            )
            
            # Heikin Ashi Low
            ha_df.iloc[i, ha_df.columns.get_loc('ha_low')] = min(
                df.iloc[i]['Low'], ha_df.iloc[i]['ha_open'], ha_df.iloc[i]['ha_close']
            )
        
        return ha_df

    def calculate_atr_supertrend(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """ATR SuperTrend hesapla - Pandas ile basit versiyon"""
        try:
            # Heikin Ashi verilerini kullan
            ha_df = self.calculate_heikin_ashi(df)
            
            # Pandas DataFrame'e çevir
            high = ha_df['ha_high']
            low = ha_df['ha_low']
            close = ha_df['ha_close']
            
            # True Range hesapla - Pandas ile
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # ATR hesapla - basit moving average
            atr = tr.rolling(window=self.atr_period, min_periods=1).mean()
            
            # SuperTrend hesapla
            hl2 = (high + low) / 2
            super_trend = atr * self.factor
            
            trend_up = hl2 - super_trend
            trend_down = hl2 + super_trend
            
            # SuperTrend line
            super_trend_line = pd.Series(index=df.index, dtype=float)
            
            if len(df) > 0:
                super_trend_line.iloc[0] = trend_down.iloc[0]
                
                for i in range(1, len(df)):
                    if close.iloc[i] > super_trend_line.iloc[i-1]:
                        super_trend_line.iloc[i] = max(trend_up.iloc[i], super_trend_line.iloc[i-1])
                    else:
                        super_trend_line.iloc[i] = min(trend_down.iloc[i], super_trend_line.iloc[i-1])
            
            return super_trend_line, atr
            
        except Exception as e:
            self.log.error(f"❌ ATR SuperTrend hesaplama hatası: {e}")
            import traceback
            self.log.error(f"Traceback: {traceback.format_exc()}")
            return None, None

    def get_stock_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Hisse verisi al (belirtilen timeframe)"""
        try:
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)  # 30 günlük veri
            
            data = ticker.history(start=start_date, end=end_date, interval=timeframe)
            
            if data.empty:
                self.log.warning(f"⚠️ {symbol} ({timeframe}) için veri bulunamadı")
                return None
            
            # Kolon isimlerini düzenle
            data.columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
            
            return data
            
        except Exception as e:
            self.log.error(f"❌ {symbol} ({timeframe}) veri alma hatası: {e}")
            return None

    def generate_signals(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Hisse için sinyal üret (belirtilen timeframe)"""
        try:
            df = self.get_stock_data(symbol, timeframe)
            if df is None or len(df) < 20:
                return None
            
            super_trend_line, atr = self.calculate_atr_supertrend(df)
            if super_trend_line is None:
                return None
            
            # Heikin Ashi verilerini al
            ha_df = self.calculate_heikin_ashi(df)
            
            current_price = ha_df['ha_close'].iloc[-1]
            current_super_trend = super_trend_line.iloc[-1]
            prev_price = ha_df['ha_close'].iloc[-2]
            prev_super_trend = super_trend_line.iloc[-2]
            
            # Sinyal koşulları
            buy_signal = prev_price <= prev_super_trend and current_price > current_super_trend
            sell_signal = prev_price >= prev_super_trend and current_price < current_super_trend
            
            # Trend durumu
            trend = "BULLISH" if current_price > current_super_trend else "BEARISH"
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'price': current_price,
                'super_trend': current_super_trend,
                'atr': atr.iloc[-1],
                'trend': trend,
                'buy_signal': buy_signal,
                'sell_signal': sell_signal,
                'timestamp': datetime.now(),
                'heikin_ashi': True
            }
            
        except Exception as e:
            self.log.error(f"❌ {symbol} ({timeframe}) sinyal üretme hatası: {e}")
            return None

    def send_telegram_message(self, message: str):
        """Telegram'a mesaj gönder"""
        if not self.telegram_enabled:
            return
        
        try:
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(self.base_url, data=data, timeout=10)
            if response.status_code == 200:
                self.log.info("📱 Telegram mesajı gönderildi")
            else:
                self.log.error(f"❌ Telegram hatası: {response.status_code}")
        except Exception as e:
            self.log.error(f"❌ Telegram gönderme hatası: {e}")

    def scan_premium_stocks(self):
        """Premium hisseleri tara (çoklu timeframe)"""
        self.log.info("🔍 Premium hisseler taranıyor...")
        
        signals_found = []
        
        for symbol in self.premium_stocks:
            for timeframe in self.timeframes:
                try:
                    signal_data = self.generate_signals(symbol, timeframe)
                    if signal_data:
                        if signal_data['buy_signal'] or signal_data['sell_signal']:
                            signals_found.append(signal_data)
                            self.log.info(f"📈 {symbol} ({timeframe}): {signal_data['trend']} - "
                                        f"Fiyat: ${signal_data['price']:.2f} - "
                                        f"SuperTrend: ${signal_data['super_trend']:.2f}")
                    
                    # Rate limiting
                    time.sleep(0.2)
                    
                except Exception as e:
                    self.log.error(f"❌ {symbol} ({timeframe}) tarama hatası: {e}")
                    continue
        
        # Sinyal bildirimi
        if signals_found:
            self.send_signal_notification(signals_found)
        
        self.log.info(f"✅ Tarama tamamlandı. {len(signals_found)} sinyal bulundu.")

    def send_signal_notification(self, signals: List[Dict]):
        """Sinyal bildirimi gönder"""
        if not signals:
            return
        
        message = "🚀 <b>Premium Stock Scanner - Sinyaller</b>\n\n"
        
        for signal in signals:
            signal_type = "🟢 LONG" if signal['buy_signal'] else "🔴 SHORT"
            message += f"{signal_type} <b>{signal['symbol']}</b> ({signal['timeframe']})\n"
            message += f"💰 Fiyat: ${signal['price']:.2f}\n"
            message += f"📊 SuperTrend: ${signal['super_trend']:.2f}\n"
            message += f"📈 Trend: {signal['trend']}\n"
            message += f"🕯️ Heikin Ashi: Aktif\n\n"
        
        message += f"⏰ Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.send_telegram_message(message)

    def run(self):
        """Ana döngü"""
        self.log.info("🔄 Premium Stock Scanner döngüsü başlatıldı")
        
        while True:
            try:
                self.scan_premium_stocks()
                self.log.info(f"⏳ {self.cfg['check_interval']} saniye bekleniyor...")
                time.sleep(self.cfg['check_interval'])
                
            except KeyboardInterrupt:
                self.log.info("🛑 Scanner durduruldu")
                break
            except Exception as e:
                self.log.error(f"❌ Döngü hatası: {e}")
                time.sleep(60)  # Hata durumunda 1 dakika bekle

if __name__ == "__main__":
    scanner = PremiumStockScanner()
    scanner.run()
