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
common_dir = os.path.join(current_dir, "simple_trader", "projects", "common")
pengu_ema_dir = os.path.join(current_dir, "simple_trader", "projects", "pengu_ema")

# Add directories to Python path
if common_dir not in sys.path:
    sys.path.insert(0, common_dir)
if pengu_ema_dir not in sys.path:
    sys.path.insert(0, pengu_ema_dir)

# Import modules
try:
    # Import from common directory
    from order_client import IdempotentOrderClient  # type: ignore
    
    # Import from pengu_ema directory
    from config_schema import load_and_validate_config, PenguEMAConfig  # type: ignore
    from symbol_mapping import SymbolMappingHelper  # type: ignore
    
except ImportError as e:
    print(f"❌ Import hatası: {e}")
    print(f"📁 Common dir: {common_dir}")
    print(f"📁 Pengu EMA dir: {pengu_ema_dir}")
    print(f"📁 Python path: {sys.path[:5]}...")  # Show first 5 paths
    print(f"📁 Files in common dir: {os.listdir(common_dir) if os.path.exists(common_dir) else 'Not found'}")
    print(f"📁 Files in pengu_ema dir: {os.listdir(pengu_ema_dir) if os.path.exists(pengu_ema_dir) else 'Not found'}")
    sys.exit(1)

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
            config_file = os.path.join(current_dir, 'pengu_ema_multi_config.json')
        
        # Config doğrulama ve yükleme
        try:
            self.cfg_obj = load_and_validate_config(config_file)
            self.cfg = self.cfg_obj.model_dump()  # Pydantic model'i dict'e çevir
            self.log = logging.getLogger(__name__)
            self.log.info("✅ Config doğrulaması başarılı - Pengu EMA Bot başlatılıyor")
            self.log.info(f"📊 Symbol: {self.cfg_obj.symbol}")
            self.log.info(f"💰 Trade Amount: {self.cfg_obj.trade_amount_usd} USDT")
            self.log.info(f"⚡ Leverage: {self.cfg_obj.leverage}x")
            self.log.info(f"🎯 Yüzde birimi standardı: 0.01 = %1")
            
        except Exception as e:
            print(f"❌ Config doğrulama hatası: {e}")
            print("🔧 Lütfen config dosyasını kontrol edin ve yüzde değerlerinin 0.01 = %1 standardında olduğundan emin olun")
            sys.exit(1)
        
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
            'enableRateLimit': True,
        })
        
        # Symbol mapping helper setup
        self.symbol_helper = SymbolMappingHelper(self.exchange, self.log)
        
        # Symbol validation and mapping
        try:
            self.symbol_mapping = self.symbol_helper.load_and_validate_markets(self.cfg_obj.symbol)
            self.log.info(f"🎯 Symbol mapping başarılı: {self.symbol_mapping.rest_symbol} / {self.symbol_mapping.order_symbol}")
        except SystemExit:
            self.log.error("❌ Symbol mapping başarısız - Bot durduruluyor")
            raise
        
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
        
        # QA Tracking sistemi
        self.qa_tracker = {
            'scenarios_passed': 0,
            'total_scenarios': 6,
            'anomalies': {
                'monotonic_sl': 0,
                'tp_rollback': 0,
                'dup_orders': 0,
                'stale_orders': 0
            },
            'logs': {
                'partial_fill': [],
                'micro_lot': [],
                'dynamic_tp': [],
                'reversal': [],
                'unknown_order': [],
                'idempotent': []
            }
        }
        
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
            symbol = self.symbol_helper.get_symbol_for_endpoint('fetch_ohlcv')
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
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
            symbol = self.symbol_helper.get_symbol_for_endpoint('fetch_positions')
            positions = self.exchange.fetch_positions()  # Tüm pozisyonları getir
            for position in positions:
                if position['symbol'] == symbol and position['contracts'] > 0:
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
            # Single position only kontrolü
            if self.single_position_only and self.active_position:
                self.log.info(f"🚫 Single position only aktif - Yeni pozisyon açılamaz")
                return False
            
            timeframe = signal_info['timeframe']
            signal = signal_info['signal']
            price = signal_info['price']
            
            # Ters sinyal kontrolü - ReduceOnly politikası
            if self.active_position:
                current_side = self.active_position['side']
                new_side = 'buy' if signal == 'long' else 'sell'
                
                # Ters yön kontrolü
                if (current_side == 'long' and new_side == 'sell') or (current_side == 'short' and new_side == 'buy'):
                    self.log.info(f"🔄 REVERSAL BLOCK new_entry_deferred=1 reason=open_position_exists")
                    self.log.info(f"⚠️ Ters sinyal tespit edildi - Önce mevcut pozisyonu kapat")
                    
                    # QA Tracking - S4 Reversal Flow
                    self.qa_track_log('reversal', f"REVERSAL BLOCK new_entry_deferred=1 reason=open_position_exists")
                    
                    # Mevcut pozisyonu kapat (reduceOnly=true)
                    self.close_position_with_reduce_only()
                    
                    # Bu döngüde yeni pozisyon açma - bir sonraki döngüde izin ver
                    return False
            
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
            symbol = self.symbol_helper.get_symbol_for_endpoint('create_order')
            order = self.order_client.place_entry_market(
                symbol=symbol,
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
                symbol=symbol,
                side=sl_side,
                stop_price=sl,
                position_side=position_side,
                intent="SL",
                extra=f"sl_{int(time.time())}"
            )
            
            tp_order = self.order_client.place_take_profit_market_close(
                symbol=symbol,
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
                    'intended_qty': size,  # Kısmi dolum takibi için
                    'amount': size,
                    'entry_price': price,
                    'time': datetime.now(),
                    'sl': sl,
                    'tp': tp,
                    'current_sl': sl,  # Trailing için mevcut SL
                    'current_tp': tp,  # Dynamic TP için mevcut TP
                    'hit_levels': set(),  # Dynamic TP hit levels
                    'trailing_active': False,  # Trailing aktif mi?
                    'trailing_mfe': 0,  # Most Favorable Exit
                    'sl_order_id': sl_order.get('id') if sl_order else None,
                    'tp_order_id': tp_order.get('id') if tp_order else None,
                    'timeframe': timeframe,
                    'take_profit_pct': tp_pct,
                    'stop_loss_pct': sl_pct,
                    'order_id': order['id'],
                    'entry_price': price,  # Break-even için entry price
                    'dynamic_tp_active': False,  # Dynamic TP aktif mi?
                    'break_even_reached': False,  # Break-even'e ulaşıldı mı?
                    'last_trailing_pnl': 0,  # Son trailing PnL
                    'last_tp_pnl': 0,  # Son TP PnL
                    'last_update_time': datetime.now()
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
    
    def handle_advanced_risk_management(self, position_data, current_price, pnl_pct, side, entry_price):
        """
        Gelişmiş risk yönetimi: Break-Even, Trailing Stop, Dynamic TP
        """
        try:
            risk_config = self.cfg['risk_management']
            trailing_enabled = risk_config.get('trailing_stop_enabled', False)
            dynamic_tp_enabled = risk_config.get('dynamic_tp_enabled', False)
            trailing_pct = risk_config.get('trailing_stop_percentage', 1.0)
            update_threshold = risk_config.get('trailing_update_threshold', 0.5)
            
            # Break-Even kontrolü
            if pnl_pct >= risk_config['break_even_percentage']:
                
                # Sadece ilk kez break-even'e ulaştığında log
                if not position_data.get('break_even_reached', False):
                    self.log.info(f"🛡️ Break-Even aktif - PnL: %{pnl_pct:.2f}")
                    position_data['break_even_reached'] = True
                
                # Trailing Stop Loss kontrolü - Threshold kontrolü ile
                if trailing_enabled:
                    last_pnl = position_data.get('last_trailing_pnl', 0)
                    if abs(pnl_pct - last_pnl) >= update_threshold:
                        self.update_trailing_stop_loss(position_data, current_price, side, trailing_pct)
                        position_data['last_trailing_pnl'] = pnl_pct
                    else:
                        self.log.info(f"📊 Trailing SL - PnL: %{pnl_pct:.2f} (Threshold altında)")
                
                # Dynamic Take Profit kontrolü - Threshold kontrolü ile
                if dynamic_tp_enabled:
                    last_tp_pnl = position_data.get('last_tp_pnl', 0)
                    if abs(pnl_pct - last_tp_pnl) >= update_threshold:
                        self.update_dynamic_take_profit(position_data, current_price, pnl_pct, side, entry_price)
                        position_data['last_tp_pnl'] = pnl_pct
                    else:
                        self.log.info(f"📊 Dynamic TP - PnL: %{pnl_pct:.2f} (Threshold altında)")
                
        except Exception as e:
            self.log.error(f"❌ Advanced risk management hatası: {e}")
    
    def update_trailing_stop_loss(self, position_data, current_price, side, trailing_pct):
        """
        Trailing Stop Loss güncelleme
        """
        try:
            current_sl = position_data.get('current_sl', position_data.get('sl'))
            entry_price = position_data['entry_price']
            
            # Yeni SL hesapla
            if side == 'buy':  # LONG
                new_sl = current_price * (1 - trailing_pct/100)
                # SL'i sadece yukarı doğru hareket ettir
                if new_sl > current_sl and new_sl > entry_price:
                    self.update_stop_loss_order(position_data, new_sl, "Trailing SL", current_price)
                    
            elif side == 'sell':  # SHORT
                new_sl = current_price * (1 + trailing_pct/100)
                # SL'i sadece aşağı doğru hareket ettir
                if new_sl < current_sl and new_sl < entry_price:
                    self.update_stop_loss_order(position_data, new_sl, "Trailing SL", current_price)
                    
        except Exception as e:
            self.log.error(f"❌ Trailing SL güncelleme hatası: {e}")
    
    def update_dynamic_take_profit(self, position_data, current_price, pnl_pct, side, entry_price):
        """
        Dynamic Take Profit güncelleme
        """
        try:
            risk_config = self.cfg['risk_management']
            tp_increment = risk_config.get('tp_increment_percentage', 0.3)
            max_tp = risk_config.get('max_tp_percentage', 2.0)
            update_threshold = risk_config.get('trailing_update_threshold', 0.5)
            
            current_tp = position_data.get('current_tp', position_data.get('tp'))
            
            # Yeni TP hesapla
            if side == 'buy':  # LONG
                new_tp = current_price * (1 + tp_increment/100)
                # Maksimum TP sınırı
                max_tp_price = entry_price * (1 + max_tp/100)
                new_tp = min(new_tp, max_tp_price)
                
                # TP'yi sadece yukarı doğru hareket ettir
                if new_tp > current_tp:
                    self.update_take_profit_order(position_data, new_tp, "Dynamic TP", current_price)
                    
            elif side == 'sell':  # SHORT
                new_tp = current_price * (1 - tp_increment/100)
                # Maksimum TP sınırı
                max_tp_price = entry_price * (1 - max_tp/100)
                new_tp = max(new_tp, max_tp_price)
                
                # TP'yi sadece aşağı doğru hareket ettir
                if new_tp < current_tp:
                    self.update_take_profit_order(position_data, new_tp, "Dynamic TP", current_price)
                    
        except Exception as e:
            self.log.error(f"❌ Dynamic TP güncelleme hatası: {e}")
    
    def update_stop_loss_order(self, position_data, new_sl, reason, current_price=None):
        """
        Stop Loss emrini güncelle
        """
        try:
            # Eski SL emrini iptal et
            old_sl_id = position_data.get('sl_order_id')
            if old_sl_id:
                try:
                    self.exchange.cancel_order(old_sl_id, f"{self.symbol.replace("/", "")}", params={"type": "future"})
                    self.log.info(f"✅ Eski SL emri iptal edildi: {old_sl_id}")
                except Exception as e:
                    self.log.warning(f"⚠️ SL emri iptal hatası: {e}")
            
            # Yeni SL emri yerleştir
            side = 'sell' if position_data['side'] == 'buy' else 'buy'
            futures_symbol = f"{self.symbol}:USDT"
            
            new_sl_order = self.order_client.place_stop_market_close(
                symbol=futures_symbol,
                side=side,
                stop_price=new_sl,
                position_side=position_data['side'].upper(),
                intent="SL",
                extra=f"{reason.lower().replace(' ', '_')}_{int(time.time())}",
                amount=position_data['size']
            )
            
            if new_sl_order and new_sl_order.get('id'):
                # State'i güncelle
                position_data['current_sl'] = new_sl
                position_data['sl_order_id'] = new_sl_order['id']
                position_data['trailing_active'] = True
                position_data['last_update_time'] = datetime.now()
                
                self.log.info(f"🛡️ {reason} güncellendi: ${new_sl:.4f}")
                self.log.info(f"📊 SL Order ID: {new_sl_order['id']}")
                
                # Telegram bildirimi
                if current_price:
                    self.send_telegram_message(f"""
🛡️ TRAILING STOP GÜNCELLENDİ

📊 Symbol: {self.symbol}
📈 Side: {position_data['side'].upper()}
💰 Entry: ${position_data['entry_price']:.4f}
📊 Current: ${current_price:.4f}
🛡️ New SL: ${new_sl:.4f}
📊 Reason: {reason}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}
""")
            else:
                self.log.error(f"❌ {reason} güncelleme başarısız!")
                
        except Exception as e:
            self.log.error(f"❌ SL order güncelleme hatası: {e}")
    
    def update_take_profit_order(self, position_data, new_tp, reason, current_price=None):
        """
        Take Profit emrini güncelle
        """
        try:
            # Eski TP emrini iptal et
            old_tp_id = position_data.get('tp_order_id')
            if old_tp_id:
                try:
                    self.exchange.cancel_order(old_tp_id, f"{self.symbol.replace("/", "")}", params={"type": "future"})
                    self.log.info(f"✅ Eski TP emri iptal edildi: {old_tp_id}")
                except Exception as e:
                    self.log.warning(f"⚠️ TP emri iptal hatası: {e}")
            
            # Yeni TP emri yerleştir
            side = 'sell' if position_data['side'] == 'buy' else 'buy'
            futures_symbol = f"{self.symbol}:USDT"
            
            new_tp_order = self.order_client.place_take_profit_market_close(
                symbol=futures_symbol,
                side=side,
                price=new_tp,
                position_side=position_data['side'].upper(),
                intent="TP",
                extra=f"{reason.lower().replace(' ', '_')}_{int(time.time())}",
                amount=position_data['size']
            )
            
            if new_tp_order and new_tp_order.get('id'):
                # State'i güncelle
                position_data['current_tp'] = new_tp
                position_data['tp_order_id'] = new_tp_order['id']
                position_data['dynamic_tp_active'] = True
                position_data['last_update_time'] = datetime.now()
                
                self.log.info(f"🎯 {reason} güncellendi: ${new_tp:.4f}")
                self.log.info(f"📊 TP Order ID: {new_tp_order['id']}")
                
                # Telegram bildirimi
                if current_price:
                    self.send_telegram_message(f"""
🎯 DYNAMIC TP GÜNCELLENDİ

📊 Symbol: {self.symbol}
📈 Side: {position_data['side'].upper()}
💰 Entry: ${position_data['entry_price']:.4f}
📊 Current: ${current_price:.4f}
🎯 New TP: ${new_tp:.4f}
📊 Reason: {reason}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}
""")
            else:
                self.log.error(f"❌ {reason} güncelleme başarısız!")
                
        except Exception as e:
            self.log.error(f"❌ TP order güncelleme hatası: {e}")
    
    def log_trailing_status(self, position_data, current_price, pnl_pct):
        """
        Trailing stop durumunu logla
        """
        try:
            if not position_data:
                return
            
            self.log.info("=" * 60)
            self.log.info("🛡️ TRAILING STOP STATUS")
            self.log.info("=" * 60)
            self.log.info(f"📊 Symbol: {position_data['symbol']}")
            self.log.info(f"📈 Side: {position_data['side'].upper()}")
            self.log.info(f"💰 Entry: ${position_data['entry_price']:.4f}")
            self.log.info(f"📊 Current: ${current_price:.4f}")
            self.log.info(f"📈 PnL: %{pnl_pct:.2f}")
            self.log.info(f"🛡️ Current SL: ${position_data.get('current_sl', 'N/A'):.4f}")
            self.log.info(f"🎯 Current TP: ${position_data.get('current_tp', 'N/A'):.4f}")
            self.log.info(f"🔄 Trailing Active: {position_data.get('trailing_active', False)}")
            self.log.info(f"🎯 Dynamic TP Active: {position_data.get('dynamic_tp_active', False)}")
            self.log.info(f"⏰ Last Update: {position_data.get('last_update_time', 'N/A')}")
            self.log.info("=" * 60)
            
        except Exception as e:
            self.log.error(f"❌ Trailing status log hatası: {e}")
    
    def test_trailing_calculations(self, entry_price, current_price, side):
        """
        Trailing stop hesaplamalarını test et
        """
        try:
            risk_config = self.cfg['risk_management']
            trailing_pct = risk_config.get('trailing_stop_percentage', 1.0)
            tp_increment = risk_config.get('tp_increment_percentage', 0.3)
            
            self.log.info("🧪 TRAILING CALCULATION TEST")
            self.log.info(f"Entry: ${entry_price:.4f}")
            self.log.info(f"Current: ${current_price:.4f}")
            self.log.info(f"Side: {side}")
            
            if side == 'buy':  # LONG
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                new_sl = current_price * (1 - trailing_pct/100)
                new_tp = current_price * (1 + tp_increment/100)
            else:  # SHORT
                pnl_pct = ((entry_price - current_price) / entry_price) * 100
                new_sl = current_price * (1 + trailing_pct/100)
                new_tp = current_price * (1 - tp_increment/100)
            
            self.log.info(f"PnL: %{pnl_pct:.2f}")
            self.log.info(f"New SL: ${new_sl:.4f}")
            self.log.info(f"New TP: ${new_tp:.4f}")
            self.log.info("=" * 40)
            
        except Exception as e:
            self.log.error(f"❌ Trailing test hatası: {e}")

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
                    symbol = self.symbol_helper.get_symbol_for_endpoint('cancel_order')
                    cancel_result = self.exchange.cancel_order(sl_order_id, symbol)
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
                    symbol = self.symbol_helper.get_symbol_for_endpoint('cancel_order')
                    cancel_result = self.exchange.cancel_order(tp_order_id, symbol)
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
    
    def close_position_with_reduce_only(self):
        """Pozisyonu ReduceOnly ile kapat"""
        try:
            if not self.active_position:
                self.log.warning("⚠️ Kapatılacak aktif pozisyon yok")
                return False
            
            side = self.active_position['side']
            amount = self.active_position['amount']
            
            # ReduceOnly ile pozisyon kapatma
            close_side = 'sell' if side == 'long' else 'buy'
            position_side = 'LONG' if side == 'long' else 'SHORT'
            
            self.log.info(f"🔄 EXIT INTENT reduceOnly=true qty={amount} reason=reversal_signal")
            
            # QA Tracking - S4 Reversal Flow
            self.qa_track_log('reversal', f"EXIT INTENT reduceOnly=true qty={amount} reason=reversal_signal")
            
            symbol = self.symbol_helper.get_symbol_for_endpoint('create_order')
            
            # Market order ile pozisyonu kapat (reduceOnly=true)
            order = self.order_client.place_entry_market(
                symbol=symbol,
                side=close_side,
                amount=amount,
                position_side=position_side,
                extra=f"exit_{int(time.time())}",
                reduce_only=True  # ReduceOnly politikası
            )
            
            if order and order.get('id'):
                self.log.info(f"✅ Pozisyon kapatma emri gönderildi: {order['id']}")
                
                # SL/TP emirlerini iptal et
                self.cancel_sl_tp_orders()
                
                # Pozisyonu temizle
                self.active_position = None
                self.last_exit_time = datetime.now()
                
                return True
            else:
                self.log.error("❌ Pozisyon kapatma emri başarısız")
                return False
                
        except Exception as e:
            self.log.error(f"❌ Pozisyon kapatma hatası: {e}")
            return False
    
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
            side = self.active_position['side']
            tp_pct = self.active_position['take_profit_pct']
            sl_pct = self.active_position['stop_loss_pct']
            
            # PnL hesapla
            if side == 'long':
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - current_price) / entry_price) * 100
            
            # Risk Management kontrolü
            risk_config = self.cfg['risk_management']
            break_even_enabled = risk_config['break_even_enabled']
            break_even_pct = risk_config['break_even_percentage']
            trailing_enabled = risk_config.get('trailing_stop_enabled', False)
            dynamic_tp_enabled = risk_config.get('dynamic_tp_enabled', False)
            
            # Dynamic TP ve Trailing SL kontrolleri
            self._check_dynamic_tp(current_price, pnl_pct, side, entry_price)
            self._check_trailing_stop(current_price, pnl_pct, side, entry_price)
            
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
                # Break Even veya Trailing Stop aktif
                self.handle_advanced_risk_management(
                    self.active_position, current_price, pnl_pct, side, entry_price
                )
                
                # Debug log - Trailing status
                if self.cfg['logging'].get('detailed_positions', False):
                    self.log_trailing_status(self.active_position, current_price, pnl_pct)
            
            if should_close:
                self.log.info(f"🎯 POZİSYON KAPATMA SEBEBİ: {close_reason}")
                self.log.info(f"📊 PnL: %{pnl_pct:.2f}")
                self.close_position()
            else:
                self.log.info(f"📊 Pozisyon izleniyor - PnL: %{pnl_pct:.2f}")
                
        except Exception as e:
            self.log.error(f"❌ Pozisyon izleme hatası: {e}")
    
    def reconcile(self):
        """Reconciliation mini-döngüsü - Borsa gerçeği ile lokal state eşitleme"""
        try:
            self.log.info("🔄 RECONCILE_START")
            
            # 1. Açık emirler snapshot
            symbol = self.symbol_helper.get_symbol_for_endpoint("fetch_open_orders")
            open_orders = self.exchange.fetch_open_orders(symbol)
            
            # 2. Mevcut pozisyon
            positions = self.exchange.fetch_positions()
            position = None
            for pos in positions:
                if pos["symbol"] == symbol and pos["contracts"] > 0:
                    position = pos
                    break
            
            # 3. Yeni gerçekleşen işlemler (son 5 dakika)
            since_ts = int((datetime.now() - timedelta(minutes=5)).timestamp() * 1000)
            trades = self.exchange.fetch_my_trades(symbol, since=since_ts)
            
            # 4. Kısmi dolum takibi ve VWAP hesaplama
            qty_adjust = 0
            if self.active_position and trades:
                qty_adjust = self._process_partial_fills(trades, position)
            
            # 5. Lokal state ile karşılaştır ve düzelt
            fixed_count = 0
            stale_orders = 0
            
            # Hayalet emirleri temizle
            if self.active_position:
                sl_order_id = self.active_position.get("sl_order_id")
                tp_order_id = self.active_position.get("tp_order_id")
                
                # SL order kontrolü
                if sl_order_id:
                    sl_exists = any(order["id"] == sl_order_id for order in open_orders)
                    if not sl_exists:
                        self.log.warning(f"⚠️ ORDER STALE REMOVED client_oid={sl_order_id} type=SL")
                        self.log.warning(f"⚠️ RECON WARN unknown_order client_oid={sl_order_id} action=state_cleanup")
                        
                        # QA Tracking - S5 Unknown Order Recovery
                        self.qa_track_log('unknown_order', f"ORDER STALE REMOVED client_oid={sl_order_id} type=SL")
                        self.qa_track_log('unknown_order', f"RECON WARN unknown_order client_oid={sl_order_id} action=state_cleanup")
                        
                        self.active_position["sl_order_id"] = None
                        stale_orders += 1
                        fixed_count += 1
                
                # TP order kontrolü
                if tp_order_id:
                    tp_exists = any(order["id"] == tp_order_id for order in open_orders)
                    if not tp_exists:
                        self.log.warning(f"⚠️ ORDER STALE REMOVED client_oid={tp_order_id} type=TP")
                        self.log.warning(f"⚠️ RECON WARN unknown_order client_oid={tp_order_id} action=state_cleanup")
                        
                        # QA Tracking - S5 Unknown Order Recovery
                        self.qa_track_log('unknown_order', f"ORDER STALE REMOVED client_oid={tp_order_id} type=TP")
                        self.qa_track_log('unknown_order', f"RECON WARN unknown_order client_oid={tp_order_id} action=state_cleanup")
                        
                        self.active_position["tp_order_id"] = None
                        stale_orders += 1
                        fixed_count += 1
            
            # Pozisyon durumu kontrolü
            if position:
                if not self.active_position:
                    # Exchange'de pozisyon var ama lokal state yok
                    self.log.info("ℹ️ RECON WARN position_exists_local_missing - Pozisyon bulundu")
                    self.active_position = {
                        "side": position["side"],
                        "entry_price": position["entryPrice"],
                        "amount": position["contracts"],
                        "timestamp": datetime.now()
                    }
                    fixed_count += 1
            else:
                if self.active_position:
                    # Lokal state'te pozisyon var ama exchange'de yok
                    self.log.info("ℹ️ RECON WARN position_missing_local_exists - Pozisyon temizlendi")
                    self.active_position = None
                    fixed_count += 1
            
            # Özet log
            pos_size = position["contracts"] if position else 0
            pos_side = position["side"] if position else "flat"
            trades_new = len(trades)
            
            self.log.info(f"✅ reconcile ok openOrders={len(open_orders)} pos_size={pos_size} side={pos_side} trades_new={trades_new} fixed={{stale_orders:{stale_orders}, qty_adjust:{qty_adjust}}}")
            
        except Exception as e:
            self.log.error(f"❌ Reconciliation hatası: {e}")
    
    def _process_partial_fills(self, trades, position):
        """Kısmi dolumları işle ve TP/SL'yi uyarla"""
        try:
            if not self.active_position or not trades:
                return 0
            
            # Pozisyon bilgilerini al
            intended_qty = self.active_position.get('intended_qty', self.active_position.get('amount', 0))
            current_qty = position['contracts'] if position else 0
            
            # Kısmi dolum kontrolü
            if current_qty < intended_qty:
                remaining_qty = current_qty
                cum_filled = intended_qty - current_qty
                
                # VWAP hesaplama (basit ortalama)
                total_cost = 0
                total_qty = 0
                for trade in trades:
                    if trade['side'] == self.active_position['side']:
                        total_cost += trade['amount'] * trade['price']
                        total_qty += trade['amount']
                
                avg_entry_price = total_cost / total_qty if total_qty > 0 else self.active_position['entry_price']
                
                self.log.info(f"🔄 PARTIAL FILL detected cum_filled={cum_filled:.4f} remaining={remaining_qty:.4f} vwap={avg_entry_price:.4f}")
                
                # QA Tracking - S1 Partial Fill
                self.qa_track_log('partial_fill', f"PARTIAL FILL detected cum_filled={cum_filled:.4f} remaining={remaining_qty:.4f} vwap={avg_entry_price:.4f}")
                
                # TP/SL'yi kalan miktara uyarla
                self._resize_protection_orders(remaining_qty)
                
                # Pozisyon bilgilerini güncelle
                self.active_position['amount'] = remaining_qty
                self.active_position['entry_price'] = avg_entry_price
                self.active_position['cum_filled'] = cum_filled
                self.active_position['remaining_qty'] = remaining_qty
                
                return 1  # qty_adjust sayacı
            
            return 0
            
        except Exception as e:
            self.log.error(f"❌ Kısmi dolum işleme hatası: {e}")
            return 0
    
    def _resize_protection_orders(self, new_qty):
        """TP/SL emirlerini yeni miktara uyarla"""
        try:
            if not self.active_position or new_qty <= 0:
                return
            
            # Lot adımı kontrolü
            symbol = self.symbol_helper.get_symbol_for_endpoint('fetch_open_orders')
            markets = self.exchange.load_markets()
            market = markets.get(symbol)
            
            if market:
                min_amount = market.get('limits', {}).get('amount', {}).get('min', 0.001)
                
                if new_qty < min_amount:
                    # Lot altı durum - tüm korumaları iptal et ve pozisyonu kapat
                    self.log.info(f"🔄 MICRO LOT EXIT used reduceOnly=true qty={new_qty:.6f} min_lot={min_amount}")
                    
                    # QA Tracking - S2 Micro Lot
                    self.qa_track_log('micro_lot', f"MICRO LOT EXIT used reduceOnly=true qty={new_qty:.6f} min_lot={min_amount}")
                    
                    self.cancel_sl_tp_orders()
                    self.close_position_with_reduce_only()
                    return
            
            # Mevcut TP/SL emirlerini iptal et
            old_sl_qty = self.active_position.get('sl_order_id')
            old_tp_qty = self.active_position.get('tp_order_id')
            
            if old_sl_qty or old_tp_qty:
                self.log.info(f"🔄 TP/SL RESIZE old_qty={self.active_position.get('amount', 0):.4f} new_qty={new_qty:.4f}")
                
                # QA Tracking - S1 Partial Fill
                self.qa_track_log('partial_fill', f"TP/SL RESIZE old_qty={self.active_position.get('amount', 0):.4f} new_qty={new_qty:.4f}")
                
                self.cancel_sl_tp_orders()
                
                # Yeni TP/SL emirleri oluştur
                self._create_protection_orders(new_qty)
            
        except Exception as e:
            self.log.error(f"❌ TP/SL resize hatası: {e}")
    
    def _create_protection_orders(self, qty):
        """Yeni TP/SL koruma emirleri oluştur"""
        try:
            if not self.active_position or qty <= 0:
                return
            
            side = self.active_position['side']
            entry_price = self.active_position['entry_price']
            timeframe = self.active_position.get('timeframe', '15m')
            
            # Timeframe konfigürasyonunu al
            tf_config = self.timeframes.get(timeframe, self.timeframes['15m'])
            tp_pct = tf_config['take_profit']
            sl_pct = tf_config['stop_loss']
            
            # TP/SL fiyatlarını hesapla
            if side == 'long':
                sl_price = entry_price * (1 - sl_pct)
                tp_price = entry_price * (1 + tp_pct)
                sl_side = 'sell'
                tp_side = 'sell'
            else:
                sl_price = entry_price * (1 + sl_pct)
                tp_price = entry_price * (1 - tp_pct)
                sl_side = 'buy'
                tp_side = 'buy'
            
            # Position side
            position_side = 'LONG' if side == 'long' else 'SHORT'
            symbol = self.symbol_helper.get_symbol_for_endpoint('create_order')
            
            # Yeni SL emri
            sl_order = self.order_client.place_stop_market_close(
                symbol=symbol,
                side=sl_side,
                stop_price=sl_price,
                position_side=position_side,
                intent="SL",
                extra=f"resize_{int(time.time())}",
                reduce_only=True
            )
            
            # Yeni TP emri
            tp_order = self.order_client.place_take_profit_market_close(
                symbol=symbol,
                side=tp_side,
                price=tp_price,
                position_side=position_side,
                intent="TP",
                extra=f"resize_{int(time.time())}",
                reduce_only=True
            )
            
            # Order ID'leri kaydet
            if sl_order and sl_order.get('id'):
                self.active_position['sl_order_id'] = sl_order['id']
            if tp_order and tp_order.get('id'):
                self.active_position['tp_order_id'] = tp_order['id']
            
            self.log.info(f"✅ PROTECTION RESEED side={side} sl={sl_price:.4f} tp={tp_price:.4f} reason=resize")
            
        except Exception as e:
            self.log.error(f"❌ Koruma emirleri oluşturma hatası: {e}")
    
    def qa_track_log(self, scenario: str, log_message: str):
        """QA için log mesajlarını takip et"""
        try:
            if scenario in self.qa_tracker['logs']:
                self.qa_tracker['logs'][scenario].append({
                    'timestamp': datetime.now(),
                    'message': log_message
                })
        except Exception as e:
            self.log.error(f"❌ QA tracking hatası: {e}")
    
    def qa_check_anomaly(self, anomaly_type: str, condition: bool, message: str = ""):
        """QA anomalilerini kontrol et"""
        try:
            if condition and anomaly_type in self.qa_tracker['anomalies']:
                self.qa_tracker['anomalies'][anomaly_type] += 1
                self.log.warning(f"⚠️ QA ANOMALY {anomaly_type}: {message}")
        except Exception as e:
            self.log.error(f"❌ QA anomaly check hatası: {e}")
    
    def qa_generate_summary(self):
        """QA özet raporu oluştur"""
        try:
            passed = self.qa_tracker['scenarios_passed']
            total = self.qa_tracker['total_scenarios']
            anomalies = self.qa_tracker['anomalies']
            
            summary = f"qa_summary passed={passed}/{total} anomalies={{monotonic_sl:{anomalies['monotonic_sl']}, tp_rollback:{anomalies['tp_rollback']}, dup_orders:{anomalies['dup_orders']}, stale_orders:{anomalies['stale_orders']}}}"
            
            self.log.info(f"📊 {summary}")
            return summary
            
        except Exception as e:
            self.log.error(f"❌ QA summary hatası: {e}")
            return "qa_summary error"
    
    def _check_dynamic_tp(self, current_price: float, pnl_pct: float, side: str, entry_price: float):
        """Dynamic TP merdiveni kontrolü"""
        try:
            if not self.active_position:
                return False
            
            timeframe = self.active_position.get('timeframe', '15m')
            tf_config = self.timeframes.get(timeframe, self.timeframes['15m'])
            
            if not tf_config.get('dynamic_tp', {}).get('enabled', False):
                return False
            
            dynamic_tp_config = tf_config['dynamic_tp']
            levels = dynamic_tp_config.get('levels', [])
            
            # Hit levels set'i (bir eşik tek kez tetiklensin)
            hit_levels = self.active_position.get('hit_levels', set())
            
            for level in levels:
                threshold_pct = level['threshold'] * 100  # 0.01 -> 1%
                tp_pct = level['tp_pct']
                
                # Eşik aşıldı mı ve daha önce tetiklenmedi mi?
                if pnl_pct >= threshold_pct and threshold_pct not in hit_levels:
                    # Yeni TP fiyatını hesapla
                    if side == 'long':
                        new_tp_price = entry_price * (1 + tp_pct)
                    else:  # short
                        new_tp_price = entry_price * (1 - tp_pct)
                    
                    # Geri gitmeme kuralı (non-decreasing)
                    current_tp_price = self.active_position.get('current_tp', 0)
                    
                    if side == 'long':
                        if new_tp_price < current_tp_price:
                            self.log.warning(f"⚠️ QA WARN tp_rollback_blocked: new_tp={new_tp_price:.4f} < current_tp={current_tp_price:.4f}")
                            self.qa_check_anomaly('tp_rollback', True, f"TP rollback blocked for LONG")
                            continue
                    else:  # short
                        if new_tp_price > current_tp_price:
                            self.log.warning(f"⚠️ QA WARN tp_rollback_blocked: new_tp={new_tp_price:.4f} > current_tp={current_tp_price:.4f}")
                            self.qa_check_anomaly('tp_rollback', True, f"TP rollback blocked for SHORT")
                            continue
                    
                    # TP güncelle
                    self._update_take_profit_order(new_tp_price, f"dynamic_tp_{threshold_pct:.0f}")
                    
                    # Hit level'ı kaydet
                    hit_levels.add(threshold_pct)
                    self.active_position['hit_levels'] = hit_levels
                    self.active_position['current_tp'] = new_tp_price
                    
                    # QA Tracking - S3 Dynamic TP
                    self.qa_track_log('dynamic_tp', f"TP SET/UPDATED price={new_tp_price:.4f} reason=dynamic_tp_{threshold_pct:.0f}")
                    
                    self.log.info(f"🎯 TP SET/UPDATED price={new_tp_price:.4f} reason=dynamic_tp_{threshold_pct:.0f}")
                    return True
            
            return False
            
        except Exception as e:
            self.log.error(f"❌ Dynamic TP kontrol hatası: {e}")
            return False
    
    def _check_trailing_stop(self, current_price: float, pnl_pct: float, side: str, entry_price: float):
        """Trailing Stop Loss kontrolü"""
        try:
            if not self.active_position:
                return False
            
            timeframe = self.active_position.get('timeframe', '15m')
            tf_config = self.timeframes.get(timeframe, self.timeframes['15m'])
            
            trailing_activation = tf_config.get('trailing_activation', 0.015) * 100  # 0.015 -> 1.5%
            trailing_step = tf_config.get('trailing_step', 0.005) * 100  # 0.005 -> 0.5%
            
            # Trailing aktivasyon kontrolü
            if pnl_pct >= trailing_activation:
                if not self.active_position.get('trailing_active', False):
                    # İlk kez trailing aktivasyon
                    self.active_position['trailing_active'] = True
                    self.active_position['trailing_mfe'] = pnl_pct  # Most Favorable Exit
                    
                    self.log.info(f"🛡️ SL SET reason=trailing_activate pnl={pnl_pct:.2f}%")
                    
                    # QA Tracking - S3 Trailing
                    self.qa_track_log('dynamic_tp', f"SL SET reason=trailing_activate pnl={pnl_pct:.2f}%")
                    
                    return True
                
                # Trailing step kontrolü
                current_mfe = self.active_position.get('trailing_mfe', trailing_activation)
                
                if pnl_pct >= current_mfe + trailing_step:
                    # Yeni SL fiyatını hesapla
                    if side == 'long':
                        new_sl_price = entry_price * (1 + (pnl_pct - trailing_step) / 100)
                    else:  # short
                        new_sl_price = entry_price * (1 - (pnl_pct - trailing_step) / 100)
                    
                    # Monotonik zorunluluk kontrolü
                    current_sl_price = self.active_position.get('current_sl', 0)
                    
                    if side == 'long':
                        if new_sl_price < current_sl_price:
                            self.log.warning(f"⚠️ QA WARN sl_monotonic_blocked: new_sl={new_sl_price:.4f} < current_sl={current_sl_price:.4f}")
                            self.qa_check_anomaly('monotonic_sl', True, f"SL monotonic blocked for LONG")
                            return False
                    else:  # short
                        if new_sl_price > current_sl_price:
                            self.log.warning(f"⚠️ QA WARN sl_monotonic_blocked: new_sl={new_sl_price:.4f} > current_sl={current_sl_price:.4f}")
                            self.qa_check_anomaly('monotonic_sl', True, f"SL monotonic blocked for SHORT")
                            return False
                    
                    # SL güncelle
                    self._update_stop_loss_order(new_sl_price, f"trailing_step")
                    
                    # MFE'yi güncelle
                    self.active_position['trailing_mfe'] = pnl_pct
                    self.active_position['current_sl'] = new_sl_price
                    
                    # QA Tracking - S3 Trailing
                    self.qa_track_log('dynamic_tp', f"SL UPDATED price={new_sl_price:.4f} reason=trailing_step")
                    
                    self.log.info(f"🛡️ SL UPDATED price={new_sl_price:.4f} reason=trailing_step")
                    return True
            
            return False
            
        except Exception as e:
            self.log.error(f"❌ Trailing stop kontrol hatası: {e}")
            return False
    
    def _update_take_profit_order(self, new_price: float, reason: str):
        """Take Profit emrini güncelle"""
        try:
            if not self.active_position:
                return False
            
            # Mevcut TP emrini iptal et
            tp_order_id = self.active_position.get('tp_order_id')
            if tp_order_id:
                symbol = self.symbol_helper.get_symbol_for_endpoint('cancel_order')
                self.exchange.cancel_order(tp_order_id, symbol)
            
            # Yeni TP emri oluştur
            side = self.active_position['side']
            position_side = 'LONG' if side == 'long' else 'SHORT'
            
            if side == 'long':
                tp_side = 'sell'
            else:
                tp_side = 'buy'
            
            symbol = self.symbol_helper.get_symbol_for_endpoint('create_order')
            
            tp_order = self.order_client.place_take_profit_market_close(
                symbol=symbol,
                side=tp_side,
                price=new_price,
                position_side=position_side,
                intent="TP",
                extra=f"update_{reason}_{int(time.time())}",
                reduce_only=True
            )
            
            if tp_order and tp_order.get('id'):
                self.active_position['tp_order_id'] = tp_order['id']
                return True
            
            return False
            
        except Exception as e:
            self.log.error(f"❌ TP güncelleme hatası: {e}")
            return False
    
    def _update_stop_loss_order(self, new_price: float, reason: str):
        """Stop Loss emrini güncelle"""
        try:
            if not self.active_position:
                return False
            
            # Mevcut SL emrini iptal et
            sl_order_id = self.active_position.get('sl_order_id')
            if sl_order_id:
                symbol = self.symbol_helper.get_symbol_for_endpoint('cancel_order')
                self.exchange.cancel_order(sl_order_id, symbol)
            
            # Yeni SL emri oluştur
            side = self.active_position['side']
            position_side = 'LONG' if side == 'long' else 'SHORT'
            
            if side == 'long':
                sl_side = 'sell'
            else:
                sl_side = 'buy'
            
            symbol = self.symbol_helper.get_symbol_for_endpoint('create_order')
            
            sl_order = self.order_client.place_stop_market_close(
                symbol=symbol,
                side=sl_side,
                stop_price=new_price,
                position_side=position_side,
                intent="SL",
                extra=f"update_{reason}_{int(time.time())}",
                reduce_only=True
            )
            
            if sl_order and sl_order.get('id'):
                self.active_position['sl_order_id'] = sl_order['id']
                return True
            
            return False
            
        except Exception as e:
            self.log.error(f"❌ SL güncelleme hatası: {e}")
            return False
    
    def run(self):
        """Ana döngü"""
        self.log.info("🚀 Multi-Timeframe EMA Crossover trading başlatıldı")
        
        while True:
            try:
                self.log.info(f"🔄 CYCLE_START: {datetime.now().strftime('%H:%M:%S')}")
                
                # Reconciliation mini-döngüsü - Her ana döngü başında
                self.reconcile()
                
                # Önce exchange'den pozisyon durumunu kontrol et
                position_status = self.check_position_status()
                
                # Aktif pozisyon varsa izle
                if self.active_position:
                    self.log.info("📊 Aktif pozisyon izleniyor...")
                    self.monitor_position()
                    time.sleep(60)
                    continue
                
                # Exchange'de pozisyon varsa ama active_position yoksa (sistem restart sonrası)
                if position_status['exists']:
                    self.log.info("ℹ️ Exchange'de aktif pozisyon bulundu, izleniyor...")
                    # Pozisyon bilgilerini güncelle - Config'den default timeframe değerlerini al
                    # 15m timeframe'i default olarak kullan (en sık kullanılan)
                    default_tf = '15m'
                    default_tf_config = self.timeframes[default_tf]
                    
                    self.active_position = {
                        'timeframe': 'unknown',
                        'side': position_status['side'],
                        'entry_price': position_status['entry_price'],
                        'amount': position_status['size'],
                        'take_profit_pct': default_tf_config['take_profit'],
                        'stop_loss_pct': default_tf_config['stop_loss'],
                        'order_id': 'unknown',
                        'timestamp': datetime.now()
                    }
                    self.log.info(f"📊 Default TP/SL kullanılıyor ({default_tf}): TP={default_tf_config['take_profit']*100:.1f}%, SL={default_tf_config['stop_loss']*100:.1f}%")
                    continue
                
                # Cooldown kontrolü
                if self.last_exit_time and self.cooldown_seconds > 0:
                    time_since_exit = (datetime.now() - self.last_exit_time).total_seconds()
                    if time_since_exit < self.cooldown_seconds:
                        remaining = self.cooldown_seconds - time_since_exit
                        self.log.info(f"⏰ Cooldown aktif - {remaining:.0f} saniye kaldı")
                        time.sleep(60)
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
