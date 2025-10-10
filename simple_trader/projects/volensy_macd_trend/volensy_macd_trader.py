#!/usr/bin/env python3
"""
Volensy MACD Trend Trading Sistemi
MACD tabanlı trend takibi ve otomatik işlem
"""

import ccxt
import pandas as pd
import numpy as np
import json
import time
import logging
import requests
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../common')))
from order_client import IdempotentOrderClient

class VolensyMacdTrader:
    def __init__(self, config_file='/root/simple_trader/projects/volensy_macd_trend/volensy_macd_config.json'):
        # Konfigürasyon yükle
        with open(config_file, 'r') as f:
            self.cfg = json.load(f)
        
        # Exchange (Futures) - EIGEN EMA'dan temiz yapı
        self.exchange = ccxt.binance({
            'apiKey': self.cfg['api_key'],
            'secret': self.cfg['secret'],
            'sandbox': self.cfg.get('sandbox', False),
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # Durum
        self.position = None
        self.trades = []
        self.signal_cooldown = 60  # 1 dakika cooldown
        
        # Logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('trading.log')
            ]
        )
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
        
        # Signal state'i IdempotentOrderClient'tan al
        self.last_signal = self.order_client.get_last_signal()
        self.last_signal_time = self.order_client.get_last_signal_time()
        
        # Volensy MACD parametreleri
        self.macd_params = self.cfg.get('volensy_macd', {})
        self.ema_trend_period = self.macd_params.get('ema_trend_period', 55)
        self.macd_fast = self.macd_params.get('macd_fast', 12)
        self.macd_slow = self.macd_params.get('macd_slow', 26)
        self.macd_signal = self.macd_params.get('macd_signal', 9)
        self.rsi_period = self.macd_params.get('rsi_period', 14)
        self.rsi_overbought = self.macd_params.get('rsi_overbought', 70)
        self.rsi_oversold = self.macd_params.get('rsi_oversold', 30)
        self.atr_period = self.macd_params.get('atr_period', 14)
        
        # Signal filters
        self.signal_filters = self.cfg.get('signal_filters', {})
        self.min_signal_strength = self.signal_filters.get('min_signal_strength', 0.2)
        self.min_volume_ratio = self.signal_filters.get('min_volume_ratio', 1.2)
        self.trend_confirmation_bars = self.signal_filters.get('trend_confirmation_bars', 3)
        
        self.log.info(f"🚀 Volensy MACD Trader başlatıldı - {self.cfg['symbol']}")
        self.log.info(f"📊 Last signal: {self.last_signal}")
        self.log.info(f"🎯 Volensy MACD: EMA={self.ema_trend_period}, MACD={self.macd_fast}/{self.macd_slow}/{self.macd_signal}, RSI={self.rsi_period}")
        
        # Detaylı sistem bilgileri
        trade_amount = self.cfg.get('trade_amount_usd', 100)
        self.log.info(f"⚙️ SYSTEM_CONFIG: trade_amount=${trade_amount}, leverage={self.cfg['leverage']}, sl={self.cfg['sl']}, tp={self.cfg['tp']}")
        self.log.info(f"🛡️ SAFETY_FEATURES: idempotent_orders=True, binance_auto_sl_tp=True, position_check=True")
        
        # Pozisyon takip değişkenleri
        self.last_position_state = None  # Son pozisyon durumu
        self.position_close_detected = False  # Pozisyon kapanma algılandı mı
    
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
        
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def calculate_atr(self, df, period=14):
        """ATR hesapla"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        return tr.rolling(period).mean()
    
    def calculate_supertrend(self, df, period=14, multiplier=1.5):
        """SuperTrend hesapla"""
        atr_val = self.calculate_atr(df, period)
        hl2 = (df['high'] + df['low']) / 2
        upper = hl2 + (atr_val * multiplier)
        lower = hl2 - (atr_val * multiplier)
        
        st = pd.Series(index=df.index, dtype=float)
        for i in range(len(df)):
            if i == 0:
                st.iloc[i] = lower.iloc[i]
            else:
                if df['close'].iloc[i] > st.iloc[i-1]:
                    st.iloc[i] = max(lower.iloc[i], st.iloc[i-1])
                else:
                    st.iloc[i] = min(upper.iloc[i], st.iloc[i-1])
        return st
    
    def calculate_volensy_macd(self, df):
        """Volensy MACD stratejisi hesapla"""
        try:
            close = df['close']
            
            # EMA Trend (55 periyot)
            ema_trend = close.ewm(span=self.ema_trend_period).mean()
            
            # MACD hesapla
            ema_fast = close.ewm(span=self.macd_fast).mean()
            ema_slow = close.ewm(span=self.macd_slow).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=self.macd_signal).mean()
            macd_histogram = macd - macd_signal
            
            # RSI hesapla
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # ATR hesapla (bilgi amaçlı)
            high = df['high']
            low = df['low']
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=self.atr_period).mean()
            
            return {
                'ema_trend': ema_trend,
                'macd': macd,
                'macd_signal': macd_signal,
                'macd_histogram': macd_histogram,
                'rsi': rsi,
                'atr': atr
            }
            
        except Exception as e:
            self.log.error(f"❌ Volensy MACD hesaplama hatası: {e}")
            return None
    
    def generate_signal(self, df):
        """Volensy MACD stratejisi ile sinyal üret"""
        try:
            if len(df) < max(self.ema_trend_period, self.macd_slow, self.rsi_period, self.atr_period):
                return {'signal': 'HOLD', 'strength': 0, 'price': df['close'].iloc[-1]}
            
            # Volensy MACD hesapla
            indicators = self.calculate_volensy_macd(df)
            if indicators is None:
                return {'signal': 'HOLD', 'strength': 0, 'price': df['close'].iloc[-1]}
            
            close = df['close'].iloc[-1]
            ema_trend = indicators['ema_trend'].iloc[-1]
            macd = indicators['macd'].iloc[-1]
            macd_signal = indicators['macd_signal'].iloc[-1]
            rsi = indicators['rsi'].iloc[-1]
            atr = indicators['atr'].iloc[-1]
            
            # Pine Script'teki koşulları implement et
            # 1. Trend koşulları
            is_bull_trend = close > ema_trend
            is_bear_trend = close < ema_trend
            
            # 2. Momentum koşulları (RSI)
            is_bull_momentum = rsi > 50
            is_bear_momentum = rsi < 50
            
            # 3. Power koşulları (MACD)
            is_bull_power = macd > macd_signal
            is_bear_power = macd < macd_signal
            
            # 4. RSI aşırı alım/satım kontrolü
            not_overbought = rsi < self.rsi_overbought
            not_oversold = rsi > self.rsi_oversold
            
            # 5. Skor hesapla (Pine Script'teki gibi)
            bull_score = (1 if is_bull_trend else 0) + (1 if is_bull_momentum else 0) + (1 if is_bull_power else 0)
            bear_score = (1 if is_bear_trend else 0) + (1 if is_bear_momentum else 0) + (1 if is_bear_power else 0)
            
            # 6. Raw sinyaller
            raw_buy = (bull_score == 3) and not_overbought
            raw_sell = (bear_score == 3) and not_oversold
            
            signal = 'HOLD'
            signal_strength = 0
            
            # 7. Final sinyal
            if raw_buy:
                signal = 'BUY'
                signal_strength = abs(close - ema_trend) / close * 100
                self.log.info(f"🎯 VOLENSY MACD LONG! Skor: {bull_score}/3, RSI: {rsi:.1f}, MACD: {macd:.4f}")
            elif raw_sell:
                signal = 'SELL'
                signal_strength = abs(close - ema_trend) / close * 100
                self.log.info(f"🎯 VOLENSY MACD SHORT! Skor: {bear_score}/3, RSI: {rsi:.1f}, MACD: {macd:.4f}")
            
            # Debug bilgileri
            self.log.debug(f"📊 Volensy MACD Debug:")
            self.log.debug(f"   Close: {close:.4f}, EMA Trend: {ema_trend:.4f}")
            self.log.debug(f"   MACD: {macd:.4f}, Signal: {macd_signal:.4f}")
            self.log.debug(f"   RSI: {rsi:.1f}, ATR: {atr:.4f}")
            self.log.debug(f"   Bull Score: {bull_score}/3, Bear Score: {bear_score}/3")
            self.log.debug(f"   Trend: {'BULL' if is_bull_trend else 'BEAR'}, Momentum: {'BULL' if is_bull_momentum else 'BEAR'}, Power: {'BULL' if is_bull_power else 'BEAR'}")
            
            return {
                'signal': signal,
                'strength': signal_strength,
                'price': close,
                'ema_trend': ema_trend,
                'macd': macd,
                'macd_signal': macd_signal,
                'rsi': rsi,
                'atr': atr,
                'bull_score': bull_score,
                'bear_score': bear_score,
                'timestamp': df.index[-1]
            }
            
        except Exception as e:
            self.log.error(f"❌ Volensy MACD sinyal hatası: {e}")
            return {'signal': 'HOLD', 'strength': 0, 'price': df['close'].iloc[-1]}
    
    def open_position(self, signal_data):
        """Pozisyon aç - IdempotentOrderClient ile"""
        try:
            symbol = self.cfg['symbol']
            price = signal_data['price']
            side = signal_data['signal']
            
            # Son kontrol: Pozisyon var mı?
            positions = self.exchange.fetch_positions()
            target_symbol = f"{symbol}:USDT"  # Binance Futures format
            for pos in positions:
                if float(pos['contracts']) > 0 and (pos['symbol'] == symbol or pos['symbol'] == target_symbol):
                    self.log.warning(f"⚠️ Pozisyon açma iptal: Zaten {pos['side']} pozisyon var")
                    return False
            
            # Leverage ayarla
            self.exchange.set_leverage(self.cfg['leverage'], symbol)
            
            # Trade amount mantığı: USD cinsinden sabit pozisyon değeri
            trade_amount_usd = self.cfg.get('trade_amount_usd', 100)  # Default $100
            size = trade_amount_usd / price  # USD / Price = Token miktarı
            
            self.log.info(f"💰 TRADE_AMOUNT: ${trade_amount_usd} ÷ ${price:.4f} = {size:.6f} token")
            
            self.log.info(f"🚀 {side} pozisyon açılıyor: {size:.6f} @ ${price:.4f}")
            
            # Idempotent market order
            side_lower = 'buy' if side == 'BUY' else 'sell'
            order = self.order_client.place_entry_market(
                symbol=symbol,
                side=side_lower,
                amount=size,
                extra=f"signal_{int(time.time())}"
            )
            
            # SL/TP hesapla
            if side == 'BUY':  # LONG pozisyon
                sl = price * (1 - self.cfg['sl'])  # SL: Entry'den düşük
                tp = price * (1 + self.cfg['tp'])  # TP: Entry'den yüksek
                sl_side = 'sell'
                tp_side = 'sell'
            else:  # SHORT pozisyon
                sl = price * (1 + self.cfg['sl'])  # SL: Entry'den yüksek (zarar)
                tp = price * (1 - self.cfg['tp'])  # TP: Entry'den düşük (kar)
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
            
            # Order başarı kontrolü
            if not sl_order or not sl_order.get('id'):
                self.log.error("❌ SL order başarısız!")
            if not tp_order or not tp_order.get('id'):
                self.log.error("❌ TP order başarısız!")
            
            self.position = {
                'symbol': symbol,
                'side': side,
                'price': price,
                'size': size,
                'time': datetime.now(),
                'sl': sl,
                'tp': tp,
                'order_id': order.get('id', 'unknown'),
                'sl_order_id': sl_order.get('id', 'unknown'),
                'tp_order_id': tp_order.get('id', 'unknown')
            }
            
            self.log.info(f"✅ {side} pozisyon açıldı @ ${price:.4f}")
            self.log.info(f"📊 SL: ${sl:.4f} | TP: ${tp:.4f}")
            self.log.info(f"🛡️ SL Order ID: {sl_order.get('id', 'unknown')}")
            self.log.info(f"🎯 TP Order ID: {tp_order.get('id', 'unknown')}")
            
            # SL/TP detaylı bilgi
            sl_percent = abs(sl - price) / price * 100
            tp_percent = abs(tp - price) / price * 100
            self.log.info(f"📈 SL: {sl_percent:.2f}% | TP: {tp_percent:.2f}%")
            
            # Telegram bildirimi
            telegram_msg = f"""
🚀 <b>VOLENSY MACD POZİSYON AÇILDI</b>

📊 <b>Symbol:</b> {symbol}
📈 <b>Yön:</b> {'LONG' if side == 'BUY' else 'SHORT'}
💰 <b>Fiyat:</b> ${price:.4f}
🛡️ <b>Stop Loss:</b> ${sl:.4f}
🎯 <b>Take Profit:</b> ${tp:.4f}
📦 <b>Miktar:</b> {size:.6f}
⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S UTC')}

💪 <b>Güç:</b> {signal_data.get('strength', 0):.2f}%
"""
            self.send_telegram_message(telegram_msg)
            
            # Binance Futures otomatik SL/TP kullanıyor, monitor gerekmiyor
            self.log.info("✅ Binance Futures otomatik SL/TP aktif")
            
            return True
            
        except Exception as e:
            self.log.error(f"❌ Pozisyon açma hatası: {e}")
            return False
    
    def close_position(self, reason='MANUAL'):
        """Pozisyon kapat"""
        if not self.position:
            return False
        
        try:
            symbol = self.position['symbol']
            size = self.position['size']
            side = self.position['side']
            
            # Futures trading için pozisyon kapatma
            if side == 'BUY':
                order = self.exchange.create_market_sell_order(symbol, size)
            else:
                order = self.exchange.create_market_buy_order(symbol, size)
            
            # PnL hesapla
            exit_price = order['price']
            entry_price = self.position['price']
            
            if side == 'BUY':
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size
            
            # Trade kaydet
            trade = {
                'time': self.position['time'],
                'exit': datetime.now(),
                'symbol': symbol,
                'side': side,
                'entry': entry_price,
                'exit': exit_price,
                'pnl': pnl,
                'reason': reason
            }
            
            self.trades.append(trade)
            self.save_trades()
            
            self.log.info(f"🔒 Pozisyon kapatıldı ({reason})")
            self.log.info(f"💰 PnL: ${pnl:.2f}")
            
            # Telegram bildirimi
            telegram_msg = f"""
🔒 <b>VOLENSY MACD POZİSYON KAPATILDI</b>

📊 <b>Symbol:</b> {symbol}
📈 <b>Yön:</b> {'LONG' if side == 'BUY' else 'SHORT'}
💰 <b>Giriş:</b> ${entry_price:.4f}
💸 <b>Çıkış:</b> ${exit_price:.4f}
💵 <b>PnL:</b> ${pnl:.2f}
📝 <b>Sebep:</b> {reason}
⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S UTC')}

{'🟢' if pnl > 0 else '🔴'} <b>Sonuç:</b> {'KAR' if pnl > 0 else 'ZARAR'}
"""
            self.send_telegram_message(telegram_msg)
            
            # State temizleme - pozisyon kapandıktan sonra sinyal state'ini sıfırla
            self.position = None
            self.last_signal = None
            self.last_signal_time = None
            
            # IdempotentOrderClient state'ini de temizle
            self.order_client.set_last_signal('HOLD')
            
            self.log.info("🔄 State temizlendi: Pozisyon kapatıldı, sinyal state sıfırlandı")
            return True
            
        except Exception as e:
            self.log.error(f"❌ Pozisyon kapatma hatası: {e}")
            return False
    
    # SL/TP Monitor kaldırıldı - Binance Futures otomatik SL/TP kullanıyor
    def check_exit_conditions(self, current_price):
        """Çıkış koşullarını kontrol et"""
        if not self.position:
            return False
        
        side = self.position['side']
        sl = self.position['sl']
        tp = self.position['tp']
        
        if side == 'BUY':
            if current_price <= sl:
                self.close_position('STOP_LOSS')
                return True
            elif current_price >= tp:
                self.close_position('TAKE_PROFIT')
                return True
        else:
            if current_price >= sl:
                self.close_position('STOP_LOSS')
                return True
            elif current_price <= tp:
                self.close_position('TAKE_PROFIT')
                return True
        
        return False
    
    def save_trades(self):
        """Trade'leri kaydet"""
        with open('trades.json', 'w') as f:
            json.dump(self.trades, f, indent=2, default=str)
    
    def get_stats(self):
        """İstatistikleri al"""
        if not self.trades:
            return "Henüz işlem yok"
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        wins = sum(1 for t in self.trades if t['pnl'] > 0)
        total_trades = len(self.trades)
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        return f"İşlemler: {total_trades} | Win Rate: {win_rate:.1f}% | Toplam PnL: ${total_pnl:.2f}"
    
    def run(self):
        """Ana döngü"""
        symbol = self.cfg['symbol']
        interval = self.cfg.get('interval', 60)
        
        self.log.info(f"🚀 Otomatik trading başlatıldı")
        self.log.info(f"📊 Symbol: {symbol}")
        self.log.info(f"⏰ Kontrol aralığı: {interval} saniye")
        
        while True:
            try:
                cycle_start = datetime.now()
                self.log.info(f"🔄 CYCLE_START: {cycle_start.strftime('%H:%M:%S')} - Veri alınıyor...")
                
                # Veri al
                df = self.get_latest_data()
                current_price = df['close'].iloc[-1]
                self.log.info(f"📊 MARKET_DATA: price=${current_price:.4f}, volume={df['volume'].iloc[-1]:.2f}")
                
                # Çıkış koşulları Binance SL/TP order'ları ile otomatik çalışıyor
                # Manuel kontrol gerekmiyor
                
                # Pozisyon kontrolü
                self.log.info("🔍 POSITION_CHECK: Başlatılıyor...")
                try:
                    positions = self.exchange.fetch_positions()
                    has_position = False
                    target_symbol = f"{symbol}:USDT"  # Binance Futures format
                    
                    self.log.info(f"🔍 POSITION_CHECK: {len(positions)} pozisyon kontrol ediliyor, target={target_symbol}")
                    
                    for pos in positions:
                        if float(pos['contracts']) > 0:
                            # Symbol karşılaştırması - hem :USDT hem de normal format
                            if pos['symbol'] == target_symbol or pos['symbol'] == symbol:
                                has_position = True
                                notional_value = float(pos['contracts']) * float(pos['entryPrice']) * self.cfg['leverage']
                                unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                                self.log.info(f"📊 POSITION_FOUND: {pos['symbol']} {pos['side']} {pos['contracts']} @ {pos['entryPrice']}")
                                self.log.info(f"💰 POSITION_VALUE: ${notional_value:.2f} (leverage: {self.cfg['leverage']}x)")
                                self.log.info(f"💵 POSITION_PNL: ${unrealized_pnl:.2f}")
                                
                                # Pozisyon durumunu güncelle
                                self.last_position_state = True
                                self.position_close_detected = False
                                break
                    
                    if has_position:
                        self.log.info("⏭️ Aktif pozisyon var, sinyal kontrolü atlanıyor")
                        self.log.info(f"⏰ {interval} saniye bekleniyor...")
                        time.sleep(interval)
                        continue
                    else:
                        # Pozisyon kapanma algılama
                        if self.last_position_state == True and not self.position_close_detected:
                            self.log.info("🚨 POZİSYON KAPANDI! Telegram bildirimi gönderiliyor...")
                            
                            # Son işlemleri kontrol et (TP/SL hangisi tetiklendi?)
                            try:
                                trades = self.exchange.fetch_my_trades(symbol, limit=5)
                                if trades:
                                    last_trade = trades[0]
                                    trade_price = float(last_trade['price'])
                                    trade_side = last_trade['side']
                                    pnl = float(last_trade.get('info', {}).get('realizedPnl', 0))
                                    
                                    # TP/SL hangisi tetiklendi?
                                    if pnl > 0:
                                        close_reason = "TAKE PROFIT"
                                        emoji = "🎯"
                                    else:
                                        close_reason = "STOP LOSS"
                                        emoji = "🛡️"
                                    
                                    # Telegram mesajı
                                    telegram_msg = f"""
{emoji} <b>EIGEN POZİSYON KAPANDI</b>

📊 <b>Kapanma Sebebi:</b> {close_reason}
💰 <b>Kapanma Fiyatı:</b> ${trade_price:.4f}
💵 <b>PnL:</b> ${pnl:.4f} USDT
📈 <b>İşlem:</b> {trade_side.upper()}
⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S')} UTC

{'✅ Kar ile kapandı!' if pnl > 0 else '❌ Zarar ile kapandı!'}
                                    """
                                    
                                    self.send_telegram_message(telegram_msg)
                                    self.log.info(f"📱 Pozisyon kapanma bildirimi gönderildi: {close_reason}")
                                    
                            except Exception as e:
                                self.log.error(f"❌ Pozisyon kapanma bildirimi hatası: {e}")
                            
                            self.position_close_detected = True
                        
                        # Pozisyon yok ama açık SL/TP emirleri olabilir - temizle
                        self.log.info("🧹 Pozisyon yok, açık emirleri kontrol ediliyor...")
                        try:
                            open_orders = self.exchange.fetch_open_orders(symbol)
                            if open_orders:
                                self.log.info(f"🗑️ {len(open_orders)} açık emir bulundu, iptal ediliyor...")
                                for order in open_orders:
                                    try:
                                        self.exchange.cancel_order(order['id'], symbol)
                                        self.log.info(f"✅ Emir iptal edildi: {order['id']}")
                                    except Exception as e:
                                        self.log.error(f"❌ Emir iptal hatası {order['id']}: {e}")
                            else:
                                self.log.info("✅ Açık emir yok")
                        except Exception as e:
                            self.log.error(f"❌ Açık emir kontrol hatası: {e}")
                        
                        # Pozisyon durumunu güncelle
                        self.last_position_state = False
                        
                except Exception as e:
                    self.log.error(f"❌ Pozisyon kontrol hatası: {e}")
                    self.log.info(f"⏰ {interval} saniye bekleniyor...")
                    time.sleep(interval)
                    continue
                
                # Sinyal kontrolü
                self.log.info("🔍 SIGNAL_CHECK: Başlatılıyor...")
                signal_data = self.generate_signal(df)
                self.log.info(f"📈 SIGNAL_RESULT: {signal_data['signal']} (strength: {signal_data['strength']:.2f}%)")
                
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
                            target_symbol = f"{symbol}:USDT"  # Binance Futures format
                            
                            for pos in positions:
                                if float(pos['contracts']) > 0:
                                    # Symbol karşılaştırması - hem :USDT hem de normal format
                                    if pos['symbol'] == target_symbol or pos['symbol'] == symbol:
                                        has_position = True
                                        notional_value = float(pos['contracts']) * float(pos['entryPrice']) * self.cfg['leverage']
                                        self.log.warning(f"⚠️ Son kontrol: Zaten aktif pozisyon var: {pos['symbol']} {pos['side']} {pos['contracts']} @ {pos['entryPrice']}")
                                        self.log.warning(f"💰 Pozisyon değeri: ${notional_value:.2f}")
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
                                    self.order_client.set_last_signal(signal_data['signal'], current_time)
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
                    # HOLD sinyali - state'i temizle
                    if self.last_signal:
                        self.order_client.set_last_signal('HOLD')
                        self.last_signal = None
                        self.last_signal_time = None
                
                # İstatistikler
                if len(self.trades) % 5 == 0 and self.trades:
                    self.log.info(f"📈 {self.get_stats()}")
                
                self.log.info(f"⏰ {interval} saniye bekleniyor...")
                # Bekle
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.log.info("🛑 Trading durduruluyor...")
                if self.position:
                    self.close_position('MANUAL')
                break
            except Exception as e:
                self.log.error(f"❌ Ana döngü hatası: {e}")
                import traceback
                self.log.error(f"❌ Traceback: {traceback.format_exc()}")
                time.sleep(60)

if __name__ == "__main__":
    trader = VolensyMacdTrader()
    trader.run()
