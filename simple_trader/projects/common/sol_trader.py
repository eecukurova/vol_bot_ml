#!/usr/bin/env python3
"""
SOL/USDT Otomatik Trading Sistemi
Gerçek zamanlı sinyal takibi ve otomatik işlem
"""

import ccxt
import pandas as pd
import numpy as np
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from order_client import IdempotentOrderClient

class AutoTrader:
    def __init__(self, config_file='sol_config.json'):
        # Konfigürasyon yükle
        with open(config_file, 'r') as f:
            self.cfg = json.load(f)
        
        # Exchange (Futures)
        self.exchange = ccxt.binance({
            'apiKey': self.cfg['api_key'],
            'secret': self.cfg['secret'],
            'sandbox': self.cfg.get('sandbox', False),
            'options': {'defaultType': 'future'}
        })
        
        # Durum
        self.position = None
        self.trades = []
        self.last_signal = None
        self.last_signal_time = None
        self.signal_cooldown = 300  # 5 dakika cooldown
        
        # Logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
        self.log = logging.getLogger(__name__)
        
        # Telegram bot
        self.bot_token = '7956697051:AAErScGMFGVxOyt3dGiw0jrFoakBELRdtm4'
        self.chat_id = '-1002699769366'
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Idempotent Order Client
        self.order_client = IdempotentOrderClient(self.exchange, self.cfg)
        
        # Servis başlangıcında reconcile yap
        reconciled = self.order_client.reconcile_pending(self.cfg['symbol'])
        if reconciled > 0:
            self.log.info(f"🔄 Servis başlangıcında {reconciled} emir uzlaştırıldı")
        
        self.log.info(f"🚀 AutoTrader başlatıldı - {self.cfg['symbol']}")
    
    def send_telegram_message(self, message):
        """Telegram'a mesaj gönder"""
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
    
    def get_latest_data(self, symbol=None, timeframe='1h', limit=50):
        """Son veriyi al"""
        if symbol is None:
            symbol = self.cfg['symbol']
        
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            self.log.error(f"❌ Veri alma hatası: {e}")
            return None
    
    def calculate_atr(self, df, period=14):
        """ATR hesapla"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def calculate_supertrend(self, df, period=14, multiplier=1.5):
        """SuperTrend hesapla"""
        atr = self.calculate_atr(df, period)
        hl2 = (df['high'] + df['low']) / 2
        
        upper_band = hl2 + (atr * multiplier)
        lower_band = hl2 - (atr * multiplier)
        
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(1, len(df)):
            if df['close'].iloc[i] > upper_band.iloc[i-1]:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            elif df['close'].iloc[i] < lower_band.iloc[i-1]:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = supertrend.iloc[i-1]
                direction.iloc[i] = direction.iloc[i-1]
        
        return supertrend, direction
    
    def calculate_ema(self, df, period=1):
        """EMA hesapla"""
        return df['close'].ewm(span=period).mean()
    
    def generate_signal(self, df):
        """Sinyal üret"""
        try:
            # İndikatörleri hesapla
            supertrend, direction = self.calculate_supertrend(df)
            ema1 = self.calculate_ema(df, 1)
            
            # Son değerler
            close = df['close'].iloc[-1]
            st_val = supertrend.iloc[-1]
            ema1_val = ema1.iloc[-1]
            
            # Önceki değerler
            prev_ema1 = ema1.iloc[-2] if len(ema1) > 1 else ema1_val
            prev_st = supertrend.iloc[-2] if len(supertrend) > 1 else st_val
            
            # Debug: Sinyal kurallarını detaylı logla
            self.log.info(f"🔍 DEBUG - Close: ${close:.4f} | SuperTrend: ${st_val:.4f} | EMA(1): ${ema1_val:.4f}")
            self.log.info(f"🔍 DEBUG - Prev EMA(1): ${prev_ema1:.4f} | Prev SuperTrend: ${prev_st:.4f}")
            
            # LONG koşulları kontrol et
            long_cond1 = close > st_val
            long_cond2 = ema1_val > st_val
            long_cond3 = prev_ema1 <= prev_st
            
            # SHORT koşulları kontrol et
            short_cond1 = close < st_val
            short_cond2 = ema1_val < st_val
            short_cond3 = prev_ema1 >= prev_st
            
            self.log.info(f"🔍 LONG: C1={long_cond1} C2={long_cond2} C3={long_cond3}")
            self.log.info(f"🔍 SHORT: C1={short_cond1} C2={short_cond2} C3={short_cond3}")
            
            # Sinyal belirleme
            if long_cond1 and long_cond2 and long_cond3:
                signal = 'BUY'
                strength = abs(close - st_val) / st_val * 100
                self.log.info(f"🎯 LONG SİNYALİ! Güç: {strength:.2f}%")
            elif short_cond1 and short_cond2 and short_cond3:
                signal = 'SELL'
                strength = abs(close - st_val) / st_val * 100
                self.log.info(f"🎯 SHORT SİNYALİ! Güç: {strength:.2f}%")
            else:
                signal = 'HOLD'
                strength = 0
            
            return {
                'signal': signal,
                'price': close,
                'strength': strength,
                'supertrend': st_val,
                'ema1': ema1_val
            }
            
        except Exception as e:
            self.log.error(f"❌ Sinyal üretme hatası: {e}")
            return {'signal': 'HOLD', 'price': 0, 'strength': 0, 'supertrend': 0, 'ema1': 0}
    
    def open_position(self, signal_data):
        """Pozisyon aç - IdempotentOrderClient ile"""
        try:
            symbol = self.cfg['symbol']
            side = signal_data['signal']
            price = signal_data['price']
            
            # Pozisyon büyüklüğü hesapla
            position_value = self.cfg['position_size'] * self.cfg['leverage']
            size = position_value / price
            
            self.log.info(f"🚀 {side} pozisyon açılıyor: {size:.6f} @ ${price:.4f}")
            
            # Leverage ayarla
            self.exchange.set_leverage(self.cfg['leverage'], symbol)
            
            # Idempotent market order
            side_lower = 'buy' if side == 'BUY' else 'sell'
            order = self.order_client.place_entry_market(
                symbol=symbol,
                side=side_lower,
                amount=size,
                extra=f"signal_{int(time.time())}"
            )
            
            self.log.info(f"✅ {side} pozisyon açıldı @ ${price:.4f}")
            
            # Pozisyon bilgilerini kaydet
            self.position = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'entry_price': price,
                'timestamp': datetime.now(),
                'order_id': order.get('id', 'unknown')
            }
            
            # SL/TP hesapla
            if side == 'BUY':
                sl = price * (1 - self.cfg['sl'])
                tp = price * (1 + self.cfg['tp'])
                sl_side = 'sell'
                tp_side = 'sell'
            else:
                sl = price * (1 + self.cfg['sl'])
                tp = price * (1 - self.cfg['tp'])
                sl_side = 'buy'
                tp_side = 'buy'
            
            # Idempotent SL/TP orders
            sl_order = self.order_client.place_stop_market_close(
                symbol=symbol,
                side=sl_side,
                stop_price=sl,
                intent="SL",
                extra=f"sl_{int(time.time())}"
            )
            
            tp_order = self.order_client.place_stop_market_close(
                symbol=symbol,
                side=tp_side,
                stop_price=tp,
                intent="TP",
                extra=f"tp_{int(time.time())}"
            )
            
            self.position['sl_order_id'] = sl_order.get('id', 'unknown')
            self.position['tp_order_id'] = tp_order.get('id', 'unknown')
            
            self.log.info(f"📊 SL: ${sl:.4f} | TP: ${tp:.4f}")
            self.log.info(f"🛡️ SL Order ID: {sl_order.get('id', 'unknown')}")
            self.log.info(f"🎯 TP Order ID: {tp_order.get('id', 'unknown')}")
            
            # Telegram bildirimi
            position_msg = f"""
🚀 <b>YENİ POZİSYON AÇILDI</b>

📊 <b>Symbol:</b> {symbol}
📈 <b>Yön:</b> {'LONG' if side == 'BUY' else 'SHORT'}
💰 <b>Fiyat:</b> ${price:.4f}
🛡️ <b>Stop Loss:</b> ${sl:.4f}
🎯 <b>Take Profit:</b> ${tp:.4f}
📦 <b>Miktar:</b> {size:.6f}
⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S UTC')}
💪 <b>Güç:</b> {signal_data['strength']:.2f}%
"""
            self.send_telegram_message(position_msg)
            
            return True
            
        except Exception as e:
            self.log.error(f"❌ Pozisyon açma hatası: {e}")
            return False
    
    def check_exit_conditions(self, current_price):
        """Çıkış koşullarını kontrol et"""
        if not self.position:
            return
        
        try:
            # Pozisyon durumunu kontrol et
            positions = self.exchange.fetch_positions()
            position_closed = True
            
            for pos in positions:
                if pos['symbol'] == self.position['symbol'] and float(pos['contracts']) > 0:
                    position_closed = False
                    break
            
            if position_closed:
                self.log.info("📊 Pozisyon kapatıldı")
                self.position = None
                
        except Exception as e:
            self.log.error(f"❌ Pozisyon kontrol hatası: {e}")
    
    def get_stats(self):
        """İstatistikleri al"""
        if not self.trades:
            return "Henüz işlem yok"
        
        total_trades = len(self.trades)
        winning_trades = sum(1 for trade in self.trades if trade['pnl'] > 0)
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        return f"İşlemler: {total_trades} | Kazanma: {winning_trades} | Oran: {win_rate:.1f}%"
    
    def run(self):
        """Ana döngü"""
        symbol = self.cfg['symbol']
        interval = self.cfg.get('interval', 60)
        
        self.log.info("🚀 Otomatik trading başlatıldı")
        self.log.info(f"📊 Symbol: {symbol}")
        self.log.info(f"⏰ Kontrol aralığı: {interval} saniye")
        
        while True:
            try:
                # Veri al
                self.log.info("🔄 Veri alınıyor...")
                df = self.get_latest_data()
                
                if df is None or len(df) < 50:
                    self.log.error("❌ Yetersiz veri")
                    time.sleep(interval)
                    continue
                
                current_price = df['close'].iloc[-1]
                self.log.info(f"📊 Güncel fiyat: ${current_price:.4f}")
                
                # Çıkış koşullarını kontrol et
                if self.position:
                    self.check_exit_conditions(current_price)
                
                # Pozisyon kontrolü
                self.log.info("🔍 Pozisyon kontrol ediliyor...")
                try:
                    positions = self.exchange.fetch_positions()
                    has_position = False
                    for pos in positions:
                        if float(pos['contracts']) > 0 and pos['symbol'] == symbol:
                            has_position = True
                            self.log.info(f"📊 Aktif pozisyon bulundu: {pos['side']} {pos['contracts']} @ {pos['entryPrice']}")
                            break
                    
                    if has_position:
                        self.log.info("⏭️ Aktif pozisyon var, sinyal kontrolü atlanıyor")
                        self.log.info(f"⏰ {interval} saniye bekleniyor...")
                        time.sleep(interval)
                        continue
                        
                except Exception as e:
                    self.log.error(f"❌ Pozisyon kontrol hatası: {e}")
                    self.log.info(f"⏰ {interval} saniye bekleniyor...")
                    time.sleep(interval)
                    continue
                
                # Sinyal kontrolü
                self.log.info("🔍 Sinyal kontrol ediliyor...")
                signal_data = self.generate_signal(df)
                self.log.info(f"📈 Sinyal: {signal_data['signal']}")
                
                # Sinyal işleme
                if signal_data['signal'] != 'HOLD':
                    current_time = datetime.now()
                    
                    # Cooldown kontrolü
                    if self.last_signal_time and (current_time - self.last_signal_time).seconds < self.signal_cooldown:
                        self.log.info(f"⏰ Sinyal cooldown aktif: {(self.signal_cooldown - (current_time - self.last_signal_time).seconds)} saniye kaldı")
                        self.log.info(f"⏰ {interval} saniye bekleniyor...")
                        time.sleep(interval)
                        continue
                    
                    # Yeni sinyal kontrolü
                    if self.last_signal != signal_data['signal']:
                        self.log.info(f"🎯 Yeni {signal_data['signal']} sinyali!")
                        self.log.info(f"💪 Güç: {signal_data['strength']:.2f}%")
                        
                        # Son pozisyon kontrolü
                        try:
                            positions = self.exchange.fetch_positions()
                            has_position = False
                            for pos in positions:
                                if float(pos['contracts']) > 0 and pos['symbol'] == symbol:
                                    has_position = True
                                    self.log.warning(f"⚠️ Son kontrol: Zaten aktif pozisyon var: {pos['side']} {pos['contracts']}")
                                    break
                            
                            if not has_position:
                                # Telegram sinyal bildirimi
                                signal_msg = f"""
🎯 <b>YENİ SİNYAL!</b>

📊 <b>Symbol:</b> {symbol}
📈 <b>Sinyal:</b> {'LONG' if signal_data['signal'] == 'BUY' else 'SHORT' if signal_data['signal'] == 'SELL' else 'HOLD'}
💰 <b>Fiyat:</b> ${signal_data['price']:.4f}
💪 <b>Güç:</b> {signal_data['strength']:.2f}%
📊 <b>SuperTrend:</b> ${signal_data['supertrend']:.4f}
📈 <b>EMA(1):</b> ${signal_data['ema1']:.4f}
⏰ <b>Zaman:</b> {current_time.strftime('%H:%M:%S UTC')}

🚀 <b>Pozisyon açılıyor...</b>
"""
                                self.send_telegram_message(signal_msg)
                                
                                # Pozisyon aç
                                if self.open_position(signal_data):
                                    self.last_signal = signal_data['signal']
                                    self.last_signal_time = current_time
                                    self.log.info(f"✅ Pozisyon açıldı, cooldown başladı: {self.signal_cooldown} saniye")
                                else:
                                    self.log.error("❌ Pozisyon açılamadı")
                            else:
                                self.log.info("⏭️ Pozisyon zaten var, sinyal atlanıyor")
                                
                        except Exception as e:
                            self.log.error(f"❌ Pozisyon kontrol hatası: {e}")
                    else:
                        self.log.info("🔄 Aynı sinyal devam ediyor, pozisyon açılmıyor")
                else:
                    self.last_signal = None
                    self.last_signal_time = None
                
                # İstatistikler
                if len(self.trades) % 5 == 0 and self.trades:
                    self.log.info(f"📈 {self.get_stats()}")
                
                # Bekle
                self.log.info(f"⏰ {interval} saniye bekleniyor...")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.log.info("🛑 Kullanıcı tarafından durduruldu")
                break
            except Exception as e:
                self.log.error(f"❌ Ana döngü hatası: {e}")
                time.sleep(interval)

if __name__ == "__main__":
    trader = AutoTrader()
    trader.run()
