#!/usr/bin/env python3
"""
Multi-Timeframe EMA Crossover Trader
Heikin Ashi + EMA Crossover Strategy
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

# Path'leri dinamik olarak ayarla
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
common_dir = os.path.join(parent_dir, "common")

sys.path.append(common_dir)

from order_client import IdempotentOrderClient

class HeikinAshiCalculator:
    """Heikin Ashi candle hesaplama sınıfı"""
    
    @staticmethod
    def calculate_heikin_ashi(df):
        """
        Heikin Ashi mumları hesapla
        
        Pine Script'teki formül:
        ha_close = (open + high + low + close) / 4
        ha_open = na(ha_open[1]) ? (open + close) / 2 : (ha_open[1] + ha_close[1]) / 2
        ha_high = max(high, max(ha_open, ha_close))
        ha_low = min(low, min(ha_open, ha_close))
        """
        ha_data = df.copy()
        
        # Heikin Ashi Close
        ha_data['ha_close'] = (ha_data['open'] + ha_data['high'] + ha_data['low'] + ha_data['close']) / 4
        
        # Heikin Ashi Open
        ha_data['ha_open'] = 0.0
        for i in range(len(ha_data)):
            if i == 0:
                ha_data.iloc[i, ha_data.columns.get_loc('ha_open')] = (ha_data.iloc[i]['open'] + ha_data.iloc[i]['close']) / 2
            else:
                prev_ha_open = ha_data.iloc[i-1]['ha_open']
                prev_ha_close = ha_data.iloc[i-1]['ha_close']
                ha_data.iloc[i, ha_data.columns.get_loc('ha_open')] = (prev_ha_open + prev_ha_close) / 2
        
        # Heikin Ashi High
        ha_data['ha_high'] = np.maximum(ha_data['high'], np.maximum(ha_data['ha_open'], ha_data['ha_close']))
        
        # Heikin Ashi Low
        ha_data['ha_low'] = np.minimum(ha_data['low'], np.minimum(ha_data['ha_open'], ha_data['ha_close']))
        
        return ha_data

class TechnicalIndicators:
    """Teknik indikatörler sınıfı - Pine Script stratejisine göre"""
    
    @staticmethod
    def calculate_ema(data, period):
        """EMA hesapla"""
        return data.ewm(span=period).mean()
    
    @staticmethod
    def calculate_rsi(data, period):
        """RSI hesapla"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_bollinger_bands(data, period, std_dev):
        """Bollinger Bands hesapla"""
        sma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower
    
    @staticmethod
    def calculate_volume_ratio(volume, period):
        """Volume ratio hesapla"""
        volume_ma = volume.rolling(window=period).mean()
        return volume / volume_ma
    
    @staticmethod
    def calculate_price_momentum(data, period):
        """Price momentum hesapla"""
        return ((data - data.shift(period)) / data.shift(period)) * 100
    
    @staticmethod
    def detect_ema_crossover(fast_ema, slow_ema):
        """
        Pine Script'teki EMA crossover/crossunder tespit et
        
        Returns:
        - 'long': Fast EMA yukarı doğru Slow EMA'yı keser (ta.crossover)
        - 'short': Fast EMA aşağı doğru Slow EMA'yı keser (ta.crossunder)
        - 'none': Crossover yok
        """
        if len(fast_ema) < 2 or len(slow_ema) < 2:
            return 'none'
        
        # Son 2 değeri al
        fast_current = fast_ema.iloc[-1]
        fast_previous = fast_ema.iloc[-2]
        slow_current = slow_ema.iloc[-1]
        slow_previous = slow_ema.iloc[-2]
        
        # Pine Script ta.crossover ve ta.crossunder mantığı
        if fast_previous <= slow_previous and fast_current > slow_current:
            return 'long'  # ta.crossover(ema_fast_ln, ema_slow_ln)
        elif fast_previous >= slow_previous and fast_current < slow_current:
            return 'short'  # ta.crossunder(ema_fast_ln, ema_slow_ln)
        else:
            return 'none'

class MultiTimeframeEMATrader:
    """Multi-Timeframe EMA Crossover Trader"""
    
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = os.path.join(current_dir, 'eigen_ema_multi_config.json')
        # Konfigürasyon yükle
        with open(config_file, 'r') as f:
            self.cfg = json.load(f)
        
        # Logging setup
        logging.basicConfig(
            level=getattr(logging, self.cfg['logging']['level']),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.cfg['logging']['file'])
            ]
        )
        self.log = logging.getLogger(__name__)
        
        # Exchange setup
        self.exchange = ccxt.binance({
            'apiKey': self.cfg['api_key'],
            'secret': self.cfg['secret'],
            'sandbox': self.cfg['sandbox'],
            'enableRateLimit': True,
        })
        
        # Order client
        self.order_client = IdempotentOrderClient(
            self.exchange,
            self.cfg
        )
        
        # Trading parameters
        self.symbol = self.cfg['symbol']
        self.trade_amount_usd = self.cfg['trade_amount_usd']
        self.leverage = self.cfg['leverage']
        
        # Multi-timeframe parameters
        self.timeframes = self.cfg['multi_timeframe']['timeframes']
        self.ema_fast = self.cfg['ema']['fast_period']
        self.ema_slow = self.cfg['ema']['slow_period']
        self.heikin_ashi_enabled = self.cfg['heikin_ashi']['enabled']
        
        # Signal management
        self.single_position_only = self.cfg['signal_management']['single_position_only']
        self.priority_order = self.cfg['signal_management']['priority_order']
        
        # Telegram settings
        self.telegram_enabled = self.cfg['telegram']['enabled']
        self.bot_token = self.cfg['telegram']['bot_token']
        self.chat_id = self.cfg['telegram']['chat_id']
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # State tracking
        self.active_position = None
        self.last_signals = {}
        self.last_exit_time = None
        self.cooldown_seconds = self.cfg['signal_management']['cooldown_after_exit']
        
        self.log.info("🚀 Multi-Timeframe EMA Crossover Trader başlatıldı")
        self.log.info(f"📊 Symbol: {self.symbol}")
        self.log.info(f"📈 Timeframes: {list(self.timeframes.keys())}")
        self.log.info(f"📊 EMA: Fast={self.ema_fast}, Slow={self.ema_slow}")
        self.log.info(f"🕯️ Heikin Ashi: {'Enabled' if self.heikin_ashi_enabled else 'Disabled'}")
    
    def send_telegram_message(self, message):
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
    
    def get_market_data(self, timeframe, limit=100):
        """Market verisi al"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            self.log.error(f"❌ Market data alma hatası ({timeframe}): {e}")
            return None
    
    def validate_timeframe_data(self, df, timeframe):
        """Timeframe verisini validate et"""
        try:
            validation_config = self.cfg.get('signal_management', {}).get('timeframe_validation', {})
            if not validation_config.get('enabled', True):
                return True, "Validation disabled"
            
            min_candles = validation_config.get('min_candles_for_signal', 50)
            require_confirmed = validation_config.get('require_confirmed_candle', True)
            
            # Yeterli mum sayısı kontrolü
            if len(df) < min_candles:
                return False, f"Insufficient candles: {len(df)} < {min_candles}"
            
            # Son mumun confirmed olup olmadığı kontrolü
            if require_confirmed:
                # Son mumun timestamp'ini kontrol et
                last_timestamp = df.index[-1]
                current_time = datetime.now()
                
                # Timeframe'e göre beklenen mum süresi
                timeframe_minutes = {
                    '15m': 15,
                    '30m': 30,
                    '1h': 60,
                    '4h': 240,
                    '1d': 1440
                }
                
                expected_minutes = timeframe_minutes.get(timeframe, 60)
                time_diff = (current_time - last_timestamp).total_seconds() / 60
                
                # Eğer son mum çok yakın zamanda ise henüz confirmed değil
                if time_diff < expected_minutes * 0.8:  # %80'i geçmiş olmalı
                    return False, f"Candle not confirmed: {time_diff:.1f}min < {expected_minutes * 0.8:.1f}min"
            
            return True, "Validation passed"
            
        except Exception as e:
            self.log.error(f"❌ Timeframe validation hatası: {e}")
            return False, f"Validation error: {e}"
    
    def calculate_signals(self, df, timeframe):
        """Sadece EMA crossover sinyalleri - Pine Script stratejisine göre"""
        try:
            # Timeframe validasyonu
            is_valid, validation_msg = self.validate_timeframe_data(df, timeframe)
            if not is_valid:
                self.log.warning(f"⚠️ {timeframe} validation failed: {validation_msg}")
                return None
            
            # Heikin Ashi hesapla
            if self.heikin_ashi_enabled:
                df = HeikinAshiCalculator.calculate_heikin_ashi(df)
                close_data = df['ha_close']
            else:
                close_data = df['close']
            
            # Sadece EMA hesapla
            ema_fast = TechnicalIndicators.calculate_ema(close_data, self.ema_fast)
            ema_slow = TechnicalIndicators.calculate_ema(close_data, self.ema_slow)
            
            # Pine Script'teki EMA crossover/crossunder
            ema_cross_long = TechnicalIndicators.detect_ema_crossover(ema_fast, ema_slow) == 'long'
            ema_cross_short = TechnicalIndicators.detect_ema_crossover(ema_fast, ema_slow) == 'short'
            
            # Sadece EMA crossover sinyalleri
            if ema_cross_long:
                signal = 'long'
                signal_type = 'EMA_CROSS_LONG'
            elif ema_cross_short:
                signal = 'short'
                signal_type = 'EMA_CROSS_SHORT'
            else:
                signal = 'none'
                signal_type = 'NONE'
            
            # Sinyal bilgileri
            signal_info = {
                'timeframe': timeframe,
                'signal': signal,
                'signal_type': signal_type,
                'price': close_data.iloc[-1],
                'ema_fast': ema_fast.iloc[-1],
                'ema_slow': ema_slow.iloc[-1],
                'timestamp': datetime.now()
            }
            
            return signal_info
            
        except Exception as e:
            self.log.error(f"❌ Sinyal hesaplama hatası ({timeframe}): {e}")
            return None
    
    def check_all_timeframes(self):
        """Tüm timeframe'leri kontrol et"""
        signals = {}
        
        for tf_name, tf_config in self.timeframes.items():
            if not tf_config['enabled']:
                continue
                
            self.log.info(f"🔍 {tf_name} timeframe kontrol ediliyor...")
            
            # Market verisi al
            df = self.get_market_data(tf_name)
            if df is None:
                continue
            
            # Sinyal hesapla
            signal_info = self.calculate_signals(df, tf_name)
            if signal_info is None:
                continue
            
            signals[tf_name] = signal_info
            
            # Detaylı log - Sadece EMA crossover
            if self.cfg['logging']['detailed_timeframes']:
                self.log.info(f"📊 {tf_name}: {signal_info['signal_type']} | Price=${signal_info['price']:.4f}")
                self.log.info(f"📈 EMA: Fast=${signal_info['ema_fast']:.4f}, Slow=${signal_info['ema_slow']:.4f}")
            else:
                self.log.info(f"📊 {tf_name}: {signal_info['signal_type']} | Price=${signal_info['price']:.4f}")
        
        return signals
    
    def select_best_signal(self, signals):
        """En iyi sinyali seç (öncelik sırasına göre)"""
        if not signals:
            return None
        
        # Öncelik sırasına göre kontrol et
        for priority_tf in self.priority_order:
            if priority_tf in signals and signals[priority_tf]['signal'] != 'none':
                return signals[priority_tf]
        
        return None
    
    def check_position_status(self):
        """Mevcut pozisyon durumunu kontrol et"""
        try:
            futures_symbol = f"{self.symbol}:USDT"  # Futures format
            positions = self.exchange.fetch_positions([futures_symbol])
            for position in positions:
                if position['symbol'] == futures_symbol and position['contracts'] > 0:
                    return {
                        'exists': True,
                        'side': position['side'],
                        'size': position['contracts'],
                        'entry_price': position['entryPrice'],
                        'unrealized_pnl': position['unrealizedPnl'],
                        'percentage': position['percentage']
                    }
            return {'exists': False}
        except Exception as e:
            self.log.error(f"❌ Pozisyon kontrol hatası: {e}")
            return {'exists': False}
    
    def open_position(self, signal_info):
        """Pozisyon aç"""
        try:
            timeframe = signal_info['timeframe']
            signal = signal_info['signal']
            price = signal_info['price']
            
            # Timeframe parametrelerini al
            tf_config = self.timeframes[timeframe]
            tp_pct = tf_config['take_profit']
            sl_pct = tf_config['stop_loss']
            
            # Hem LONG hem SHORT sinyallerini işle (manuel olarak açabiliyorsan sistemde de açılabilir)
            side = 'buy' if signal == 'long' else 'sell'
            
            # Trade amount mantığı: USD cinsinden sabit pozisyon değeri (EIGEN ile aynı)
            trade_amount_usd = self.trade_amount_usd
            size = trade_amount_usd / price  # USD / Price = Token miktarı
            
            self.log.info(f"💰 TRADE_AMOUNT: ${trade_amount_usd} ÷ ${price:.4f} = {size:.6f} token")
            self.log.info(f"🎯 POZİSYON AÇILIYOR: {timeframe} - {side.upper()}")
            self.log.info(f"🚀 {side.upper()} pozisyon açılıyor: {size:.6f} @ ${price:.4f}")
            
            # Idempotent market order (hem LONG hem SHORT)
            side_lower = side
            position_side = 'LONG' if side == 'buy' else 'SHORT'
            futures_symbol = f"{self.symbol}:USDT"  # Futures format
            order = self.order_client.place_entry_market(
                symbol=futures_symbol,
                side=side_lower,
                amount=size,
                position_side=position_side,
                extra=f"signal_{int(time.time())}"
            )
            
            # SL/TP hesapla (hem LONG hem SHORT)
            if side == 'buy':  # LONG pozisyon
                sl = price * (1 - sl_pct)  # SL: Entry'den düşük
                tp = price * (1 + tp_pct)  # TP: Entry'den yüksek
                # TP fiyatını minimum %0.1 daha uzak yap (immediately trigger önlemek için)
                tp = max(tp, price * 1.001)
                sl_side = 'sell'
                tp_side = 'sell'
            else:  # SHORT pozisyon
                sl = price * (1 + sl_pct)  # SL: Entry'den yüksek (zarar)
                tp = price * (1 - tp_pct)  # TP: Entry'den düşük (kar)
                # TP fiyatını minimum %0.1 daha uzak yap (immediately trigger önlemek için)
                tp = min(tp, price * 0.999)
                sl_side = 'buy'
                tp_side = 'buy'
            
            # Idempotent SL/TP orders (hem LONG hem SHORT)
            sl_order = self.order_client.place_stop_market_close(
                symbol=futures_symbol,
                side=sl_side,
                stop_price=sl,
                position_side=position_side,
                intent="SL",
                extra=f"sl_{int(time.time())}"
            )
            
            tp_order = self.order_client.place_take_profit_market_close(
                symbol=futures_symbol,
                side=tp_side,
                price=tp,
                position_side=position_side,
                intent="TP",
                extra=f"tp_{int(time.time())}"
            )
            
            # Order başarı kontrolü (EIGEN ile aynı)
            if not sl_order or not sl_order.get('id'):
                self.log.error("❌ SL order başarısız!")
            if not tp_order or not tp_order.get('id'):
                self.log.error("❌ TP order başarısız!")
            
            if order:
                # Pozisyon bilgilerini kaydet (hem LONG hem SHORT)
                self.active_position = {
                    'symbol': self.symbol,
                    'side': side,
                    'price': price,
                    'size': size,
                    'time': datetime.now(),
                    'sl': sl,
                    'tp': tp,
                    'sl_order_id': sl_order.get('id') if sl_order else None,
                    'tp_order_id': tp_order.get('id') if tp_order else None,
                    'timeframe': timeframe,
                    'take_profit_pct': tp_pct,
                    'stop_loss_pct': sl_pct,
                    'order_id': order['id']
                }
                
                # Başarılı pozisyon açma logları (hem LONG hem SHORT)
                self.log.info(f"✅ {side.upper()} pozisyon açıldı @ ${price:.4f}")
                self.log.info(f"📊 SL: ${sl:.4f} | TP: ${tp:.4f}")
                self.log.info(f"🛡️ SL Order ID: {sl_order.get('id') if sl_order else 'N/A'}")
                self.log.info(f"🎯 TP Order ID: {tp_order.get('id') if tp_order else 'N/A'}")
                
                # Telegram bildirimi gönder
                telegram_msg = f"""
🚀 EMA CROSSOVER POZİSYON AÇILDI

📊 Symbol: {self.symbol}
📈 Side: {side.upper()}
💰 Entry: ${price:.4f}
📊 Timeframe: {timeframe}
📈 EMA Fast: {signal_info['ema_fast']:.4f}
📉 EMA Slow: {signal_info['ema_slow']:.4f}

🛡️ Stop Loss: ${sl:.4f} ({sl_pct*100:.1f}%)
🎯 Take Profit: ${tp:.4f} ({tp_pct*100:.1f}%)
⚡ Leverage: {self.leverage}x
💰 Amount: ${self.trade_amount_usd}

⏰ Zaman: {datetime.now().strftime('%H:%M:%S')} UTC
"""
                self.send_telegram_message(telegram_msg)
                self.log.info(f"📈 SL: {sl_pct*100:.2f}% | TP: {tp_pct*100:.2f}%")
                
                # Telegram bildirimi - Sadece EMA crossover
                signal_type = signal_info.get('signal_type', 'UNKNOWN')
                telegram_msg = f"""
🚀 <b>PENGU POZİSYON AÇILDI</b>

📊 <b>Timeframe:</b> {timeframe}
📈 <b>Yön:</b> {side.upper()}
🎯 <b>Sinyal:</b> {signal_type}
💰 <b>Entry Fiyatı:</b> ${price:.4f}
📦 <b>Miktar:</b> {size:.4f} PENGU
💵 <b>Değer:</b> ${trade_amount_usd:.2f} USDT

📈 <b>EMA:</b> Fast=${signal_info.get('ema_fast', 0):.4f}, Slow=${signal_info.get('ema_slow', 0):.4f}

🛡️ <b>Stop Loss:</b> ${sl:.4f} ({sl_pct:.1f}%)
🎯 <b>Take Profit:</b> ${tp:.4f} ({tp_pct:.1f}%)
⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S')} UTC

{'📈 LONG pozisyon açıldı!' if side == 'buy' else '📉 SHORT pozisyon açıldı!'}
                """
                
                self.send_telegram_message(telegram_msg)
                self.log.info("📱 Telegram mesajı gönderildi")
                
                return True
            else:
                self.log.error("❌ Pozisyon açılamadı")
                return False
                
        except Exception as e:
            self.log.error(f"❌ Pozisyon açma hatası: {e}")
            return False
    
    def close_position(self):
        """Mevcut pozisyonu kapat"""
        try:
            if not self.active_position:
                return False
            
            position_info = self.check_position_status()
            if not position_info['exists']:
                self.log.info("ℹ️ Pozisyon zaten kapalı")
                # SL/TP emirlerini iptal et
                self.cancel_sl_tp_orders()
                self.active_position = None
                return True
            
            # Pozisyon bilgilerini al
            side = position_info['side']
            size = position_info['size']
            
            # Ters yönde market order
            close_side = 'sell' if side == 'long' else 'buy'
            
            self.log.info(f"🔄 POZİSYON KAPATILIYOR: {side.upper()} -> {close_side.upper()}")
            
            # Market order ile kapat
            order = self.order_client.place_entry_market(
                symbol=f"{self.symbol}:USDT",
                side=close_side,
                amount=size,
                extra=f"close_{int(time.time())}"
            )
            
            if order:
                self.log.info(f"✅ Pozisyon kapatıldı: {order['id']}")
                
                # SL/TP emirlerini iptal et
                self.cancel_sl_tp_orders()
                
                self.active_position = None
                self.last_exit_time = datetime.now()  # Cooldown için zaman kaydet
                return True
            else:
                self.log.error("❌ Pozisyon kapatılamadı")
                return False
                
        except Exception as e:
            self.log.error(f"❌ Pozisyon kapatma hatası: {e}")
            return False
    
    def cancel_sl_tp_orders(self):
        """SL/TP emirlerini iptal et"""
        try:
            if not self.active_position:
                return
            
            sl_order_id = self.active_position.get('sl_order_id')
            tp_order_id = self.active_position.get('tp_order_id')
            
            cancelled_count = 0
            
            # Stop Loss emrini iptal et
            if sl_order_id:
                try:
                    cancel_result = self.exchange.cancel_order(sl_order_id, self.symbol)
                    if cancel_result:
                        self.log.info(f"✅ SL emri iptal edildi: {sl_order_id}")
                        cancelled_count += 1
                    else:
                        self.log.warning(f"⚠️ SL emri iptal edilemedi: {sl_order_id}")
                except Exception as e:
                    self.log.warning(f"⚠️ SL emri iptal hatası: {e}")
            
            # Take Profit emrini iptal et
            if tp_order_id:
                try:
                    cancel_result = self.exchange.cancel_order(tp_order_id, self.symbol)
                    if cancel_result:
                        self.log.info(f"✅ TP emri iptal edildi: {tp_order_id}")
                        cancelled_count += 1
                    else:
                        self.log.warning(f"⚠️ TP emri iptal edilemedi: {tp_order_id}")
                except Exception as e:
                    self.log.warning(f"⚠️ TP emri iptal hatası: {e}")
            
            if cancelled_count > 0:
                self.log.info(f"🔄 Toplam {cancelled_count} SL/TP emri iptal edildi")
            else:
                self.log.info("ℹ️ İptal edilecek SL/TP emri bulunamadı")
                
        except Exception as e:
            self.log.error(f"❌ SL/TP emir iptal hatası: {e}")
    
    def monitor_position(self):
        """Aktif pozisyonu izle"""
        try:
            if not self.active_position:
                return
            
            position_info = self.check_position_status()
            if not position_info['exists']:
                self.log.info("ℹ️ Pozisyon otomatik olarak kapatılmış")
                # SL/TP emirlerini iptal et
                self.cancel_sl_tp_orders()
                self.active_position = None
                return
            
            # Mevcut fiyat
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            # Pozisyon bilgileri
            entry_price = self.active_position['entry_price']
            # Debug: Pozisyon bilgilerini kontrol et
            if not self.active_position or "entry_price" not in self.active_position:
                self.log.error(f"❌ Pozisyon izleme hatası: active_position eksik veya entry_price field yok: {self.active_position}")
                return
            side = self.active_position['side']
            tp_pct = self.active_position['take_profit_pct']
            sl_pct = self.active_position['stop_loss_pct']
            
            # PnL hesapla
            if side == 'long':
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - current_price) / entry_price) * 100
            
            # Break Even kontrolü
            break_even_enabled = self.cfg['risk_management']['break_even_enabled']
            break_even_pct = self.cfg['risk_management']['break_even_percentage']
            
            # TP/SL kontrolü
            should_close = False
            close_reason = ""
            
            if pnl_pct >= tp_pct:
                should_close = True
                close_reason = f"Take Profit (%{tp_pct})"
            elif pnl_pct <= -sl_pct:
                should_close = True
                close_reason = f"Stop Loss (%{sl_pct})"
            elif break_even_enabled and pnl_pct >= break_even_pct:
                # Break Even'e ulaştıysa SL'i entry price'a çek
                if side == 'long' and current_price >= entry_price:
                    should_close = False  # Pozisyonu kapatma, sadece SL'i güncelle
                    self.log.info(f"🛡️ Break Even aktif - SL entry price'a çekildi")
                elif side == 'short' and current_price <= entry_price:
                    should_close = False  # Pozisyonu kapatma, sadece SL'i güncelle
                    self.log.info(f"🛡️ Break Even aktif - SL entry price'a çekildi")
            
            if should_close:
                self.log.info(f"🎯 POZİSYON KAPATMA SEBEBİ: {close_reason}")
                self.log.info(f"📊 PnL: %{pnl_pct:.2f}")
                self.close_position()
            else:
                self.log.info(f"📊 Pozisyon izleniyor - PnL: %{pnl_pct:.2f}")
                
        except Exception as e:
            self.log.error(f"❌ Pozisyon izleme hatası: {e}")
    
    def run(self):
        """Ana döngü"""
        self.log.info("🚀 Multi-Timeframe EMA Crossover trading başlatıldı")
        
        while True:
            try:
                # Cleanup old orders
                self.order_client.cleanup_old_orders(1)  # 1 hour
                # Sync with exchange to remove stale orders
                self.order_client.sync_with_exchange(self.symbol)
                self.log.info(f"🔄 CYCLE_START: {datetime.now().strftime('%H:%M:%S')}")
                
                # Aktif pozisyon varsa izle
                if self.active_position:
                    self.log.info("📊 Aktif pozisyon izleniyor...")
                    self.monitor_position()
                    time.sleep(60)
                    continue
                
                # Cooldown kontrolü
                if self.last_exit_time and self.cooldown_seconds > 0:
                    time_since_exit = (datetime.now() - self.last_exit_time).total_seconds()
                    if time_since_exit < self.cooldown_seconds:
                        remaining = self.cooldown_seconds - time_since_exit
                        self.log.info(f"⏰ Cooldown aktif - {remaining:.0f} saniye kaldı")
                        time.sleep(60)
                        continue
                
                # Pozisyon kontrolü (exchange'den)
                position_status = self.check_position_status()
                if position_status['exists']:
                    self.log.info("ℹ️ Exchange'de aktif pozisyon bulundu, izleniyor...")
                    # Pozisyon bilgilerini güncelle
                    self.active_position = {
                        'timeframe': 'unknown',
                        'side': position_status['side'],
                        'entry_price': position_status['entry_price'],
                        'amount': position_status['size'],
                        'take_profit_pct': 0.5,  # Default
                        'stop_loss_pct': 1.5,    # Default
                        'order_id': 'unknown',
                        'timestamp': datetime.now()
                    }
                    continue
                
                # Tüm timeframe'leri kontrol et
                signals = self.check_all_timeframes()
                
                # En iyi sinyali seç
                best_signal = self.select_best_signal(signals)
                
                if best_signal and best_signal['signal'] != 'none':
                    signal_type = best_signal.get('signal_type', 'UNKNOWN')
                    self.log.info(f"🎯 SİNYAL BULUNDU: {best_signal['timeframe']} - {signal_type}")
                    self.log.info(f"📊 Sinyal Detayı: {best_signal['signal'].upper()} @ ${best_signal['price']:.4f}")
                    
                    # Pozisyon aç
                    success = self.open_position(best_signal)
                    if success:
                        self.log.info(f"✅ Pozisyon açıldı: {best_signal['timeframe']} - {signal_type}")
                    else:
                        self.log.error("❌ Pozisyon açılamadı")
                else:
                    self.log.info("📊 Sinyal bulunamadı - EMA crossover bekleniyor")
                
                # 60 saniye bekle
                time.sleep(60)
                
            except KeyboardInterrupt:
                self.log.info("🛑 Trading durduruluyor...")
                break
            except Exception as e:
                self.log.error(f"❌ Ana döngü hatası: {e}")
                time.sleep(60)

if __name__ == "__main__":
    trader = MultiTimeframeEMATrader()
    trader.run()
