#!/usr/bin/env python3
"""
SOL MACD Trend Trader
Volensy MACD Trend Strategy Implementation
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
                ha_data.iloc[i, ha_data.columns.get_loc('ha_open')] = (ha_data.iloc[i-1]['ha_open'] + ha_data.iloc[i-1]['ha_close']) / 2
        
        # Heikin Ashi High
        ha_data['ha_high'] = ha_data[['high', 'ha_open', 'ha_close']].max(axis=1)
        
        # Heikin Ashi Low
        ha_data['ha_low'] = ha_data[['low', 'ha_open', 'ha_close']].min(axis=1)
        
        return ha_data

class VolensyMacdStrategy:
    """Volensy MACD Trend Strategy Implementation"""
    
    def __init__(self, config):
        self.config = config
        self.ema_len = config.get('ema_len', 20)
        self.macd_fast = config.get('macd_fast', 12)
        self.macd_slow = config.get('macd_slow', 26)
        self.macd_signal = config.get('macd_signal', 9)
        self.rsi_len = config.get('rsi_len', 14)
        self.rsi_ob = config.get('rsi_ob', 70)
        self.rsi_os = config.get('rsi_os', 30)
        self.atr_len = config.get('atr_len', 14)
        
    def calculate_indicators(self, df):
        """Indicators hesapla - Pine Script'te normal close kullanılıyor, Heikin Ashi değil!"""
        # Pine Script: emaTrend = ta.ema(close, emaLen) - NORMAL close kullanıyor
        df['ema_trend'] = df['close'].ewm(span=self.ema_len, adjust=False).mean()
        
        # Pine Script: macd = ta.ema(close, macdFast) - ta.ema(close, macdSlow) - NORMAL close
        ema_fast = df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        df['macd'] = ema_fast - ema_slow
        # Pine Script: macdSig = ta.ema(macd, macdSignal)
        df['macd_signal'] = df['macd'].ewm(span=self.macd_signal, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Pine Script: rsi = ta.rsi(close, rsiLen) - NORMAL close
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_len).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_len).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Pine Script: atr = ta.atr(atrLen) - NORMAL high/low/close
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.rolling(window=self.atr_len).mean()
        
        return df
    
    def generate_signals(self, df):
        """Sinyaller üret - Pine Script'te normal close kullanılıyor"""
        # Pine Script: isBullTrend = close > emaTrend - NORMAL close
        df['is_bull_trend'] = df['close'] > df['ema_trend']
        # Pine Script: isBearTrend = close < emaTrend - NORMAL close
        df['is_bear_trend'] = df['close'] < df['ema_trend']
        # Pine: isBullMomentum = rsi > 50
        df['is_bull_momentum'] = df['rsi'] > 50
        # Pine: isBearMomentum = rsi < 50
        df['is_bear_momentum'] = df['rsi'] < 50
        # Pine: isBullPower = macd > macdSig
        df['is_bull_power'] = df['macd'] > df['macd_signal']
        # Pine: isBearPower = macd < macdSig
        df['is_bear_power'] = df['macd'] < df['macd_signal']
        
        # RSI filtreleri
        # Pine: notOverbought = rsi < rsiOB
        df['not_overbought'] = df['rsi'] < self.rsi_ob
        # Pine: notOversold = rsi > rsiOS
        df['not_oversold'] = df['rsi'] > self.rsi_os
        
        # Skorlar - Pine: bullScore = (isBullTrend ? 1 : 0) + (isBullMomentum ? 1 : 0) + (isBullPower ? 1 : 0)
        df['bull_score'] = (df['is_bull_trend'].astype(int) + 
                           df['is_bull_momentum'].astype(int) + 
                           df['is_bull_power'].astype(int))
        # Pine: bearScore = (isBearTrend ? 1 : 0) + (isBearMomentum ? 1 : 0) + (isBearPower ? 1 : 0)
        df['bear_score'] = (df['is_bear_trend'].astype(int) + 
                           df['is_bear_momentum'].astype(int) + 
                           df['is_bear_power'].astype(int))
        
        # Ham sinyaller - Pine: rawBuy = (bullScore == 3) and notOverbought
        df['raw_buy'] = (df['bull_score'] == 3) & df['not_overbought']
        # Pine: rawSell = (bearScore == 3) and notOversold
        df['raw_sell'] = (df['bear_score'] == 3) & df['not_oversold']
        
        # Sinyal filtreleme (yinelenen sinyalleri engelle) - Pine: buyOK = canSignal and rawBuy and (lastDir != 1)
        df['buy_signal'] = False
        df['sell_signal'] = False
        
        last_dir = 0
        for i in range(len(df)):
            if df.iloc[i]['raw_buy'] and last_dir != 1:
                df.iloc[i, df.columns.get_loc('buy_signal')] = True
                last_dir = 1
            elif df.iloc[i]['raw_sell'] and last_dir != -1:
                df.iloc[i, df.columns.get_loc('sell_signal')] = True
                last_dir = -1
        
        return df

class SolMacdTrader:
    """SOL MACD Trend Trader"""
    
    def __init__(self, config_file):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Exchange setup
        self.exchange = ccxt.binance({
            'apiKey': self.config['api_key'],
            'secret': self.config['secret'],
            'sandbox': self.config['sandbox'],
            'options': {
                'defaultType': 'future'
            }
        })
        
        # Order client
        self.order_client = IdempotentOrderClient(
            exchange=self.exchange,
            config=self.config
        )
        
        # Strategy
        self.strategy = VolensyMacdStrategy(self.config['volensy_macd'])
        
        # Logging
        self.setup_logging()
        
        # State
        self.current_position = None
        self.last_signal_time = None
        self._last_trade_candle = self._load_trade_candle()  # Son işlem açılan 4h periyodu
        
        # Signal confirmation settings
        self.confirmation_config = self.config.get('signal_confirmation', {})
        self.confirmation_enabled = self.confirmation_config.get('enabled', True)
        self.confirmation_duration = self.confirmation_config.get('confirmation_duration_seconds', 121)
        self.check_interval = self.confirmation_config.get('check_interval_seconds', 60)
        self.min_confirmation_count = self.confirmation_config.get('min_confirmation_count', 2)
        
        # Confirmation state
        self.signal_confirmation_start_time = None
        self.current_signal = None
        self.confirmation_count = 0
        self.last_confirmation_check = None
        
        if self.confirmation_enabled:
            self.logger.info(f"🔍 Signal confirmation aktif: {self.confirmation_duration}s süre, {self.check_interval}s aralık")
        else:
            self.logger.info("⚡ Signal confirmation pasif - anında pozisyon açılacak")
        
    def _get_state_file(self):
        """State dosyası path"""
        return os.path.join(os.path.dirname(__file__), "trade_state.json")
    
    def _load_trade_candle(self):
        """Son işlem periyodunu yükle"""
        state_file = self._get_state_file()
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    if 'last_trade_candle' in state:
                        from datetime import datetime
                        dt = datetime.fromisoformat(state['last_trade_candle'])
                        # Naive datetime olarak dön (UTC zamanı local gibi tut)
                        if dt.tzinfo is not None:
                            dt = dt.replace(tzinfo=None)
                        self.logger.info(f"📅 Son işlem periyodu yüklendi: {dt}")
                        return dt
            except:
                pass
        return None
    
    def _save_trade_candle(self, dt):
        """Son işlem periyodunu kaydet"""
        try:
            state_file = self._get_state_file()
            state = {'last_trade_candle': dt.isoformat()}
            with open(state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            self.logger.error(f"State kaydedilemedi: {e}")
    
    def setup_logging(self):
        """Logging ayarla"""
        log_config = self.config['logging']
        
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_config['file']),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('SolMacdTrader')
        
    def get_historical_data(self, symbol, timeframe, limit=100):
        """Geçmiş veri çek"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"Veri çekme hatası: {e}")
            return None
    
    def check_signals(self, symbol, timeframe):
        """Sinyalleri kontrol et"""
        try:
            # Veri çek
            df = self.get_historical_data(symbol, timeframe, limit=200)
            if df is None or len(df) < 50:
                self.logger.warning(f"⚠️ Veri yetersiz: df={df is not None}, len={len(df) if df is not None else 0}")
                return None
            
            # require_confirmed_candle kontrolü
            timeframe_validation = self.config.get('signal_management', {}).get('timeframe_validation', {})
            if timeframe_validation.get('require_confirmed_candle', False):
                from datetime import datetime, timezone, timedelta
                import pandas as pd
                
                last_candle_time = df.index[-1]
                # Pandas Timestamp'i datetime'a çevir
                if isinstance(last_candle_time, pd.Timestamp):
                    last_candle_time = last_candle_time.to_pydatetime()
                    if last_candle_time.tzinfo is None:
                        last_candle_time = last_candle_time.replace(tzinfo=timezone.utc)
                
                current_time_utc = datetime.now(timezone.utc)
                
                # Timeframe'e göre bir sonraki mumun başlangıç zamanını hesapla
                if timeframe == '4h':
                    # 4h mumlar 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC'de kapanır
                    # Son mumun başlangıç zamanını bul (4h boundary'ye yuvarla)
                    last_candle_start = last_candle_time.replace(minute=0, second=0, microsecond=0)
                    last_candle_start = last_candle_start.replace(hour=(last_candle_start.hour // 4) * 4)
                    
                    # Bir sonraki mumun başlangıcı = son mum + 4 saat
                    next_candle_start = last_candle_start + timedelta(hours=4)
                    
                    # Eğer son mum henüz kapanmamışsa (şu anki zaman < bir sonraki mumun başlangıcı)
                    if current_time_utc < next_candle_start:
                        self.logger.debug(f"⏸️ Son 4h mum henüz kapanmadı: {last_candle_start} → {next_candle_start}, şu an: {current_time_utc}")
                        return None
                    else:
                        self.logger.debug(f"✅ Son 4h mum kapanmış: {last_candle_start} → {next_candle_start}, şu an: {current_time_utc}")
            
            # Indicators hesapla
            df_with_indicators = self.strategy.calculate_indicators(df)
            
            # Sinyaller üret
            df_with_signals = self.strategy.generate_signals(df_with_indicators)
            
            # Son mumu kontrol et
            last_row = df_with_signals.iloc[-1]
            
            # Detaylı loglama
            self.logger.debug(f"📊 Sinyal kontrolü: {symbol} {timeframe}")
            self.logger.debug(f"   buy_signal: {last_row['buy_signal']}, sell_signal: {last_row['sell_signal']}")
            self.logger.debug(f"   raw_buy: {last_row['raw_buy']}, raw_sell: {last_row['raw_sell']}")
            self.logger.debug(f"   bull_score: {last_row['bull_score']}, bear_score: {last_row['bear_score']}")
            self.logger.debug(f"   RSI: {last_row['rsi']:.2f}, not_overbought: {last_row.get('not_overbought', 'N/A')}, not_oversold: {last_row.get('not_oversold', 'N/A')}")
            self.logger.debug(f"   is_bull_trend: {last_row.get('is_bull_trend', 'N/A')}, is_bull_momentum: {last_row.get('is_bull_momentum', 'N/A')}, is_bull_power: {last_row.get('is_bull_power', 'N/A')}")
            self.logger.debug(f"   is_bear_trend: {last_row.get('is_bear_trend', 'N/A')}, is_bear_momentum: {last_row.get('is_bear_momentum', 'N/A')}, is_bear_power: {last_row.get('is_bear_power', 'N/A')}")
            
            signal = None
            if last_row['buy_signal']:
                signal = {
                    'type': 'buy',
                    'price': last_row['close'],
                    'timestamp': last_row.name,
                    'timeframe': timeframe,
                    'indicators': {
                        'ema_trend': last_row['ema_trend'],
                        'macd': last_row['macd'],
                        'macd_signal': last_row['macd_signal'],
                        'rsi': last_row['rsi'],
                        'atr': last_row['atr'],
                        'bull_score': last_row['bull_score'],
                        'bear_score': last_row['bear_score']
                    }
                }
                self.logger.info(f"✅ BUY sinyali tespit edildi: {symbol} @ {signal['price']:.4f}")
            elif last_row['sell_signal']:
                signal = {
                    'type': 'sell',
                    'price': last_row['close'],
                    'timestamp': last_row.name,
                    'timeframe': timeframe,
                    'indicators': {
                        'ema_trend': last_row['ema_trend'],
                        'macd': last_row['macd'],
                        'macd_signal': last_row['macd_signal'],
                        'rsi': last_row['rsi'],
                        'atr': last_row['atr'],
                        'bull_score': last_row['bull_score'],
                        'bear_score': last_row['bear_score']
                    }
                }
                self.logger.info(f"✅ SELL sinyali tespit edildi: {symbol} @ {signal['price']:.4f}")
            else:
                # Sinyal yok ama neden yok, detaylı log
                if last_row.get('raw_buy', False) and not last_row['buy_signal']:
                    self.logger.debug(f"⚠️ raw_buy=True ama buy_signal=False (muhtemelen yinelenen sinyal engellendi)")
                elif last_row.get('raw_sell', False) and not last_row['sell_signal']:
                    self.logger.debug(f"⚠️ raw_sell=True ama sell_signal=False (muhtemelen yinelenen sinyal engellendi)")
                else:
                    self.logger.debug(f"ℹ️ Sinyal yok: bull_score={last_row['bull_score']}, bear_score={last_row['bear_score']}, RSI={last_row['rsi']:.2f}")
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Sinyal kontrol hatası: {e}", exc_info=True)
            return None
    
    def open_position(self, signal):
        """Pozisyon aç"""
        try:
            symbol = self.config['symbol']
            timeframe = signal['timeframe']
            tf_config = self.config['multi_timeframe']['timeframes'][timeframe]
            
            # Pozisyon boyutu
            trade_amount_usd = self.config['trade_amount_usd']
            leverage = self.config['leverage']
            
            # SL/TP hesapla (config'den al)
            stop_loss_pct = tf_config['stop_loss']
            take_profit_pct = tf_config['take_profit']
            
            if signal['type'] == 'buy':
                side = 'buy'
                stop_loss = signal['price'] * (1 - stop_loss_pct)  # %2 stop loss
                take_profit = signal['price'] * (1 + take_profit_pct)  # %1 take profit
            else:
                side = 'sell'
                stop_loss = signal['price'] * (1 + stop_loss_pct)  # %2 stop loss
                take_profit = signal['price'] * (1 - take_profit_pct)  # %1 take profit
            
            # Order gönder
            # Önce pozisyon aç
            entry_result = self.order_client.place_entry_market(
                symbol=symbol,
                side=side,
                amount=trade_amount_usd / signal['price'],  # USD'yi coin miktarına çevir
                extra=f"macd_trend_{timeframe}"
            )
            
            if not entry_result or 'id' not in entry_result:
                self.logger.error("Entry order başarısız")
                return False
            
            # Stop Loss order
            sl_result = self.order_client.place_stop_market_close(
                symbol=symbol,
                side='sell' if side == 'buy' else 'buy',
                stop_price=stop_loss,
                intent='SL',
                extra=f"macd_trend_{timeframe}"
            )
            
            # Take Profit order
            tp_result = self.order_client.place_take_profit_market_close(
                symbol=symbol,
                side='sell' if side == 'buy' else 'buy',
                price=take_profit,
                intent='TP',
                extra=f"macd_trend_{timeframe}"
            )
            
            order_result = {
                'success': True,
                'order_id': entry_result['id'],
                'sl_order_id': sl_result.get('id') if sl_result else None,
                'tp_order_id': tp_result.get('id') if tp_result else None
            }
            
            if order_result['success']:
                # Get current 4h candle timestamp (round down to 4h boundary) - UTC!
                from datetime import datetime, timezone
                current_time_utc = datetime.now(timezone.utc)
                # Round to 4h boundary
                current_4h = current_time_utc.replace(minute=0, second=0, microsecond=0)
                current_4h = current_4h.replace(hour=(current_4h.hour // 4) * 4)
                # Naive datetime olarak kaydet
                if current_4h.tzinfo is not None:
                    current_4h = current_4h.replace(tzinfo=None)
                
                self.current_position = {
                    'order_id': order_result['order_id'],
                    'side': side,
                    'entry_price': signal['price'],
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'timeframe': timeframe,
                    'timestamp': signal['timestamp'],
                    'sl_order_id': order_result['sl_order_id'],
                    'tp_order_id': order_result['tp_order_id'],
                    'candle_start_time': current_4h.isoformat()  # Hangi 4h periyodunda açıldı
                }
                
                # BU 4H PERİYODUNU KAYDET
                self._last_trade_candle = current_4h
                self._save_trade_candle(current_4h)
                self.logger.info(f"📅 4H periyodu kaydedildi: {current_4h}")
                
                self.logger.info(f"Pozisyon açıldı: {side} {symbol} @ {signal['price']:.4f}")
                self.logger.info(f"SL: {stop_loss:.4f}, TP: {take_profit:.4f}")
                
                # Telegram bildirimi
                self.send_telegram_message(
                    f"🚀 SOL MACD Trend - {side.upper()} Pozisyon Açıldı\n"
                    f"💰 Fiyat: ${signal['price']:.4f}\n"
                    f"🛑 SL: ${stop_loss:.4f}\n"
                    f"🎯 TP: ${take_profit:.4f}\n"
                    f"⏰ Timeframe: {timeframe}\n"
                    f"📊 Bull Score: {signal['indicators']['bull_score']}\n"
                    f"📈 RSI: {signal['indicators']['rsi']:.2f}"
                )
                
                return True
            else:
                self.logger.error(f"Order hatası: {order_result['error']}")
                return False
                
        except Exception as e:
            self.logger.error(f"Pozisyon açma hatası: {e}")
            return False
    
    def _symbol_match(self, pos_symbol: str, target_symbol: str) -> bool:
        """Symbol karşılaştırması: API 'SOL/USDT:USDT' dönebilir, 'SOL/USDT' ile eşleştir"""
        pos_clean = pos_symbol.replace(':USDT', '')
        return (pos_symbol == target_symbol or pos_clean == target_symbol or target_symbol in pos_symbol)
    
    def check_position_status(self):
        """Pozisyon durumunu kontrol et ve TP/SL gerçekleşmesi durumunda diğer emri cancel et"""
        if not self.current_position:
            return
        
        try:
            symbol = self.config['symbol']
            
            # Mevcut pozisyonları kontrol et
            positions = self.exchange.fetch_positions([symbol])
            current_pos = None
            for pos in positions:
                if self._symbol_match(pos['symbol'], symbol) and abs(float(pos['contracts'])) > 0:
                    current_pos = pos
                    break
            
            # Eğer pozisyon yoksa ama current_position varsa, pozisyon kapanmış demektir
            if not current_pos and self.current_position:
                self.logger.info("Pozisyon kapanmış - TP veya SL gerçekleşmiş olabilir")
                
                # Açık order'ları kontrol et ve cancel et
                self.cancel_remaining_orders(symbol)
                
                # Pozisyon bilgisini temizle
                self.current_position = None
                return True
            
            # Pozisyon varsa, açık order'ları kontrol et
            if current_pos:
                self.check_and_cancel_opposite_orders(symbol)
                
        except Exception as e:
            self.logger.error(f"Pozisyon durumu kontrol hatası: {e}")
    
    def cancel_remaining_orders(self, symbol):
        """Kalan tüm order'ları cancel et"""
        try:
            open_orders = self.exchange.fetch_open_orders(symbol)
            
            for order in open_orders:
                try:
                    self.exchange.cancel_order(order['id'], symbol)
                    self.logger.info(f"Kalan order cancel edildi: {order['id']} ({order['type']})")
                except Exception as e:
                    self.logger.warning(f"Order cancel hatası: {order['id']} - {e}")
                    
        except Exception as e:
            self.logger.error(f"Kalan order'ları cancel etme hatası: {e}")
    
    def check_and_cancel_opposite_orders(self, symbol):
        """Pozisyon açıkken karşıt order'ları kontrol et ve cancel et"""
        try:
            open_orders = self.exchange.fetch_open_orders(symbol)
            
            for order in open_orders:
                # Eğer pozisyon LONG ise ve order SELL ise, cancel et
                # Eğer pozisyon SHORT ise ve order BUY ise, cancel et
                if (self.current_position['side'] == 'buy' and order['side'] == 'sell') or \
                   (self.current_position['side'] == 'sell' and order['side'] == 'buy'):
                    try:
                        self.exchange.cancel_order(order['id'], symbol)
                        self.logger.info(f"Karşıt order cancel edildi: {order['id']} ({order['type']})")
                    except Exception as e:
                        self.logger.warning(f"Karşıt order cancel hatası: {order['id']} - {e}")
                        
        except Exception as e:
            self.logger.error(f"Karşıt order kontrol hatası: {e}")

    def check_exit_signals(self):
        """Çıkış sinyallerini kontrol et - Sadece warning için (opsiyonel TP/SL close)"""
        if not self.current_position:
            return
        
        try:
            symbol = self.config['symbol']
            timeframe = self.current_position.get('timeframe', '4h')
            
            # Sinyal kontrol et
            signal = self.check_signals(symbol, timeframe)
            
            if signal and signal['type'] != self.current_position['side']:
                # Karşı sinyal geldi
                auto_close_on_reversal = self.config.get('signal_management', {}).get('auto_close_on_reversal', False)
                
                if auto_close_on_reversal:
                    # Otomatik kapat
                    self.logger.warning(f"⚠️ Karşı sinyal tespit edildi: Position={self.current_position['side']}, Signal={signal['type']}")
                    self.logger.warning(f"    Pozisyon otomatik kapatılıyor (reversal)")
                    self.close_position("signal_reversal")
                else:
                    # Sadece log
                    self.logger.warning(f"⚠️ Karşı sinyal tespit edildi: Position={self.current_position['side']}, Signal={signal['type']}")
                    self.logger.warning(f"    Pozisyon açık kalıyor - TP/SL bekleniyor")
                
        except Exception as e:
            self.logger.error(f"Çıkış sinyal kontrol hatası: {e}")
    
    def close_position(self, reason="manual"):
        """Pozisyonu kapat"""
        if not self.current_position:
            return
        
        try:
            symbol = self.config['symbol']
            side = self.current_position['side']
            
            # Mevcut pozisyonu al
            positions = self.exchange.fetch_positions([symbol])
            current_pos = None
            for pos in positions:
                if self._symbol_match(pos['symbol'], symbol) and abs(float(pos['contracts'])) > 0:
                    current_pos = pos
                    break
            
            if not current_pos:
                self.logger.warning("Aktif pozisyon bulunamadı")
                self.current_position = None
                return True
            
            # Önce SL ve TP order'larını cancel et
            self.cancel_sl_tp_orders(symbol)
            
            # Pozisyonu kapat
            close_side = 'sell' if side == 'buy' else 'buy'
            close_result = self.order_client.place_entry_market(
                symbol=symbol,
                side=close_side,
                amount=abs(current_pos['contracts']),
                reduce_only=True,
                extra=f"close_{reason}"
            )
            
            if close_result and 'id' in close_result:
                self.logger.info(f"Pozisyon kapatıldı: {reason}")
                
                # Telegram bildirimi
                self.send_telegram_message(
                    f"🔒 SOL MACD Trend - Pozisyon Kapatıldı\n"
                    f"📝 Sebep: {reason}\n"
                    f"⏰ Timeframe: {self.current_position['timeframe']}"
                )
                
                self.current_position = None
                return True
            else:
                self.logger.error("Pozisyon kapatma order'ı başarısız")
                return False
                
        except Exception as e:
            self.logger.error(f"Pozisyon kapatma hatası: {e}")
            return False
    
    def cancel_sl_tp_orders(self, symbol):
        """SL ve TP order'larını cancel et"""
        try:
            # Eğer pozisyon bilgilerinde SL/TP order ID'leri varsa, onları kullan
            if (self.current_position and 
                (self.current_position.get('sl_order_id') or self.current_position.get('tp_order_id'))):
                
                # SL order'ı cancel et
                if self.current_position.get('sl_order_id'):
                    try:
                        self.exchange.cancel_order(self.current_position['sl_order_id'], symbol)
                        self.logger.info(f"SL order cancel edildi: {self.current_position['sl_order_id']}")
                    except Exception as e:
                        self.logger.warning(f"SL order cancel hatası: {e}")
                
                # TP order'ı cancel et
                if self.current_position.get('tp_order_id'):
                    try:
                        self.exchange.cancel_order(self.current_position['tp_order_id'], symbol)
                        self.logger.info(f"TP order cancel edildi: {self.current_position['tp_order_id']}")
                    except Exception as e:
                        self.logger.warning(f"TP order cancel hatası: {e}")
            else:
                # Fallback: Tüm açık order'ları kontrol et
                open_orders = self.exchange.fetch_open_orders(symbol)
                
                for order in open_orders:
                    # SL veya TP order'ı mı kontrol et
                    if (order.get('type') == 'stop_market' or 
                        order.get('type') == 'take_profit_market' or
                        'SL' in str(order.get('info', {})) or
                        'TP' in str(order.get('info', {}))):
                        
                        try:
                            self.exchange.cancel_order(order['id'], symbol)
                            self.logger.info(f"Order cancel edildi: {order['id']} ({order.get('type', 'unknown')})")
                        except Exception as e:
                            self.logger.warning(f"Order cancel hatası: {order['id']} - {e}")
                        
        except Exception as e:
            self.logger.error(f"SL/TP order cancel hatası: {e}")
    
    def send_telegram_message(self, message):
        """Telegram mesajı gönder"""
        if not self.config['telegram']['enabled']:
            return
        
        try:
            bot_token = self.config['telegram']['bot_token']
            chat_id = self.config['telegram']['chat_id']
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code != 200:
                self.logger.error(f"Telegram mesaj hatası: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Telegram mesaj gönderme hatası: {e}")
    
    def start_signal_confirmation(self, signal: dict, data: dict = None):
        """Start signal confirmation process"""
        self.signal_confirmation_start_time = time.time()
        signal_type = signal.get('type', '').upper()  # 'buy' -> 'BUY', 'sell' -> 'SELL'
        self.current_signal = signal_type
        self.confirmation_count = 1
        self.last_confirmation_check = time.time()
        
        price = signal.get('price', 0)
        timeframe = signal.get('timeframe', '4h')
        indicators = signal.get('indicators', {})
        
        self.logger.info(f"🔍 CONFIRMATION BAŞLADI: {signal_type} sinyali")
        self.logger.info(f"💰 Fiyat: {price:.4f}")
        self.logger.info(f"⏰ Timeframe: {timeframe}")
        self.logger.info(f"📊 Bull Score: {indicators.get('bull_score', 0)}, Bear Score: {indicators.get('bear_score', 0)}")
        self.logger.info(f"⏰ Confirmation süresi: {self.confirmation_duration} saniye")
        self.logger.info(f"🔄 Kontrol aralığı: {self.check_interval} saniye")
        
        # Telegram bildirimi
        telegram_msg = f"""
🔍 <b>SOL MACD - Sinyal Confirmation Başladı</b>

📊 <b>Symbol:</b> {self.config['symbol']}
🎯 <b>Sinyal:</b> {signal_type}
💰 <b>Fiyat:</b> ${price:.4f}
⏰ <b>Timeframe:</b> {timeframe}

📈 <b>RSI:</b> {indicators.get('rsi', 0):.2f}
📊 <b>Bull Score:</b> {indicators.get('bull_score', 0)}
📉 <b>Bear Score:</b> {indicators.get('bear_score', 0)}

⏰ <b>Confirmation Süresi:</b> {self.confirmation_duration} saniye
🔄 <b>Kontrol Aralığı:</b> {self.check_interval} saniye
📊 <b>Min Confirmation:</b> {self.min_confirmation_count} kez

⏰ <b>Zaman:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        self.send_telegram_message(telegram_msg)
    
    def check_signal_confirmation(self, symbol: str, timeframe: str) -> bool:
        """Check if signal is still valid during confirmation"""
        current_time = time.time()
        elapsed_time = current_time - self.signal_confirmation_start_time
        
        # Check if it's time for next confirmation check
        if current_time - self.last_confirmation_check < self.check_interval:
            return False
        
        # Check current signal
        current_signal_data = self.check_signals(symbol, timeframe)
        
        if not current_signal_data:
            # Signal disappeared
            self.logger.warning(f"❌ CONFIRMATION İPTAL: Sinyal kayboldu!")
            self.logger.warning(f"⏰ Elapsed time: {elapsed_time:.0f} saniye")
            self.reset_confirmation_state()
            return False
        
        current_signal_type = current_signal_data.get('type', '').upper()
        
        if current_signal_type == self.current_signal:
            # Signal still valid
            self.confirmation_count += 1
            self.last_confirmation_check = current_time
            
            remaining_time = self.confirmation_duration - elapsed_time
            
            self.logger.info(f"✅ CONFIRMATION CHECK #{self.confirmation_count}: {self.current_signal} sinyali hala aktif")
            self.logger.info(f"💰 Fiyat: {current_signal_data.get('price', 0):.4f}")
            indicators = current_signal_data.get('indicators', {})
            self.logger.info(f"📊 Bull Score: {indicators.get('bull_score', 0)}, Bear Score: {indicators.get('bear_score', 0)}")
            self.logger.info(f"⏰ Kalan süre: {remaining_time:.0f} saniye")
            
            # Check if confirmation is complete
            if elapsed_time >= self.confirmation_duration and self.confirmation_count >= self.min_confirmation_count:
                self.logger.info(f"🎯 CONFIRMATION TAMAMLANDI: {self.current_signal} sinyali onaylandı!")
                self.logger.info(f"📊 Toplam confirmation sayısı: {self.confirmation_count}")
                return True
            else:
                self.logger.info(f"⏳ Confirmation devam ediyor... ({self.confirmation_count}/{self.min_confirmation_count} min)")
                return False
        else:
            # Signal changed or disappeared
            self.logger.warning(f"❌ CONFIRMATION İPTAL: Sinyal değişti!")
            self.logger.warning(f"📊 Beklenen: {self.current_signal}, Mevcut: {current_signal_type}")
            self.logger.warning(f"⏰ Elapsed time: {elapsed_time:.0f} saniye")
            
            # Reset confirmation state
            self.reset_confirmation_state()
            return False
    
    def reset_confirmation_state(self):
        """Reset confirmation state"""
        self.signal_confirmation_start_time = None
        self.current_signal = None
        self.confirmation_count = 0
        self.last_confirmation_check = None
        self.logger.info("🔄 Confirmation state sıfırlandı")
    
    def run(self):
        """Ana trading döngüsü"""
        self.logger.info("SOL MACD Trend Trader başlatıldı")
        
        symbol = self.config['symbol']
        timeframe = self.config['multi_timeframe']['timeframes']['4h']['enabled'] and '4h' or '1h'
        
        while True:
            try:
                # ÖNCE EXCHANGE'DEN GERÇEK POZİSYON DURUMUNU KONTROL ET
                positions = self.exchange.fetch_positions([symbol])
                has_active_position = False
                
                # DEBUG: Pozisyon durumunu logla
                if positions:
                    self.logger.debug(f"Exchange'den alınan pozisyon sayısı: {len(positions)}")
                
                for pos in positions:
                    # CCXT pozisyon field'ları: 'size', 'contracts', 'amount' olabilir
                    position_size = pos.get('size', pos.get('contracts', pos.get('amount', 0)))
                    
                    # INFO level ile logla
                    self.logger.info(f"📊 Pozisyon kontrol: symbol={pos.get('symbol')}, size={position_size}")
                    
                    # String veya number kontrolü
                    try:
                        pos_size_float = float(position_size) if position_size else 0.0
                    except (ValueError, TypeError):
                        pos_size_float = 0.0
                    
                    # Symbol karşılaştırması kullan
                    if self._symbol_match(pos['symbol'], symbol) and abs(pos_size_float) > 0:
                        has_active_position = True
                        self.logger.info(f"✅ AKTİF POZİSYON BULUNDU: {pos['side']} {pos_size_float} @ {pos.get('entryPrice')}")
                        
                        # Pozisyon varsa current_position'ı güncelle
                        if not self.current_position:
                            self.current_position = {
                                'side': pos['side'],
                                'entry_price': float(pos.get('entryPrice', 0)),
                                'size': abs(pos_size_float),
                                'timestamp': time.time(),
                                'timeframe': '4h'  # Default timeframe
                            }
                            self.logger.info(f"Internal state güncellendi: {self.current_position}")
                        break
                
                # Pozisyon yoksa ama current_position varsa temizle
                if not has_active_position and self.current_position:
                    self.logger.info("🚨 Pozisyon kapanmış - Exchange tarafından kapatıldı (TP/SL)")
                    # 4H periyodunu kaydet (bu periyotta işlem yapıldı, tekrar açma)
                    if 'candle_start_time' in self.current_position:
                        try:
                            from datetime import datetime
                            closed_candle = datetime.fromisoformat(self.current_position['candle_start_time'])
                            self._last_trade_candle = closed_candle
                            self._save_trade_candle(closed_candle)
                            self.logger.info(f"📅 Bu periyotta işlem yapıldı, artık YENİ PERİYOT bekleniyor")
                            self.logger.info(f"   Son işlem periyodu: {closed_candle}")
                        except Exception as e:
                            self.logger.error(f"Periyot kaydedilemedi: {e}")
                    else:
                        # TP/SL ile kapandı ama internal state'de candle_start_time yok
                        # _last_trade_candle'ı kullan (zaten dosyada kayıtlı)
                        if self._last_trade_candle is not None:
                            self.logger.info(f"📅 Bu periyotta işlem yapıldı, yeni periyot beklenecek")
                            self.logger.info(f"   Son işlem periyodu (dosyadan): {self._last_trade_candle}")
                            self._save_trade_candle(self._last_trade_candle)
                    self.current_position = None
                    time.sleep(60)  # Bu iterasyonda yeni işlem açma, bekle
                    continue
                
                # Pozisyon kontrolü: Hem internal state hem de exchange kontrolü
                if has_active_position or self.current_position:
                    if has_active_position:
                        self.logger.info(f"⚠️ Exchange'de aktif pozisyon var - Yeni pozisyon açılmayacak")
                        if self.current_position:
                            self.logger.info(f"  Internal state: {self.current_position['side']} @ {self.current_position.get('entry_price', 'N/A')}")
                    if self.current_position:
                        self.logger.debug(f"Internal state'de pozisyon var: {self.current_position['side']}")
                    # Çıkış sinyallerini kontrol et
                    self.check_exit_signals()
                else:
                    # Yeni sinyal kontrol et - SADECE POZİSYON YOKSA
                    
                    # 4H PERİYOT KONTROLÜ: Bu periyotta zaten işlem açılmış mı?
                    from datetime import datetime, timezone
                    # BINANCE UTC TIME KULLAN ama naive olarak tut
                    current_time_utc = datetime.now(timezone.utc)
                    current_4h = current_time_utc.replace(minute=0, second=0, microsecond=0)
                    current_4h = current_4h.replace(hour=(current_4h.hour // 4) * 4)
                    # Naive datetime olarak kaydet (timezone-aware karşılaştırmaları kaldır)
                    if current_4h.tzinfo is not None:
                        current_4h = current_4h.replace(tzinfo=None)
                    
                    # Son açılan işlemin periyodunu kontrol et
                    if self._last_trade_candle is not None:
                        # Son işlem bu 4h periyodunda mı? (NaN-safe datetime comparison)
                        last_candle_dt = self._last_trade_candle
                        if isinstance(last_candle_dt, str):
                            from datetime import datetime as dt
                            last_candle_dt = dt.fromisoformat(last_candle_dt.replace('Z', '+00:00')).replace(tzinfo=None)
                        
                        # BU PERİYOTTA İŞLEM AÇILDI MI?
                        # Son işlem periyodu == şu anki periyot ise engelle
                        if last_candle_dt == current_4h:
                            self.logger.info(f"⏸️ Bu 4h periyotunda ({current_4h}) zaten işlem açıldı. Yeni periyodu bekle...")
                            self.logger.info(f"   Son işlem periyodu: {last_candle_dt}")
                            time.sleep(60)
                            continue
                        else:
                            self.logger.info(f"✅ Farklı periyot: {last_candle_dt} → {current_4h}")
                    
                    self.logger.info(f"✅ Pozisyon yok - Sinyal kontrolüne geçiliyor (Periyot: {current_4h})")
                    
                    if self.signal_confirmation_start_time:
                        # Confirmation process is active
                        confirmation_complete = self.check_signal_confirmation(symbol, timeframe)
                        
                        if confirmation_complete:
                            # Confirmation completed - open position
                            # Get latest signal data for position opening
                            signal = self.check_signals(symbol, timeframe)
                            if signal and signal.get('type', '').upper() == self.current_signal:
                                self.logger.info(f"🎯 CONFIRMATION TAMAMLANDI - Pozisyon açılıyor: {self.current_signal}")
                                
                                # POZİSYON AÇMADAN ÖNCE TEKRAR KONTROL ET (GÜVENLİK)
                                final_check_positions = self.exchange.fetch_positions([symbol])
                                final_check_active = False
                                for pos in final_check_positions:
                                    pos_size = pos.get('size', pos.get('contracts', 0))
                                    try:
                                        if self._symbol_match(pos['symbol'], symbol) and abs(float(pos_size)) > 0:
                                            final_check_active = True
                                            self.logger.warning(f"⚠️ Güvenlik kontrolü: Son anda pozisyon tespit edildi! Yeni pozisyon açılmayacak.")
                                            break
                                    except (ValueError, TypeError):
                                        pass
                                
                                if not final_check_active:
                                    # Pozisyon aç (4H periyodu open_position içinde kaydedilecek)
                                    success = self.open_position(signal)
                                    if success:
                                        self.logger.info(f"✅ {self.current_signal} pozisyon başarıyla açıldı")
                                        self.last_signal_time = signal['timestamp']
                                    else:
                                        self.logger.error(f"❌ {self.current_signal} pozisyon açılamadı")
                                
                                # Reset confirmation state
                                self.reset_confirmation_state()
                    else:
                        # No confirmation active - check for new signals
                        signal = self.check_signals(symbol, timeframe)
                        
                        if signal:
                            self.logger.info(f"Yeni sinyal: {signal['type']} @ {signal['price']:.4f}")
                            
                            # Prevent processing the same signal multiple times
                            if self.last_signal_time and signal['timestamp'] == self.last_signal_time:
                                self.logger.debug(f"⏭️ Sinyal zaten işlendi: {signal['type']}")
                                time.sleep(60)
                                continue
                            
                            # Start confirmation if enabled
                            if self.confirmation_enabled:
                                self.start_signal_confirmation(signal)
                            else:
                                # Confirmation disabled - open position immediately
                                # POZİSYON AÇMADAN ÖNCE TEKRAR KONTROL ET (GÜVENLİK)
                                final_check_positions = self.exchange.fetch_positions([symbol])
                                final_check_active = False
                                for pos in final_check_positions:
                                    pos_size = pos.get('size', pos.get('contracts', 0))
                                    try:
                                        if self._symbol_match(pos['symbol'], symbol) and abs(float(pos_size)) > 0:
                                            final_check_active = True
                                            self.logger.warning(f"⚠️ Güvenlik kontrolü: Son anda pozisyon tespit edildi! Yeni pozisyon açılmayacak.")
                                            break
                                    except (ValueError, TypeError):
                                        pass
                                
                                if not final_check_active:
                                    # Pozisyon aç (4H periyodu open_position içinde kaydedilecek)
                                    if self.open_position(signal):
                                        self.last_signal_time = signal['timestamp']
                        else:
                            # Debug: Sinyal kontrol edildi ama sinyal yok
                            self.logger.debug(f"Sinyal kontrol edildi: {symbol} {timeframe} - Sinyal yok")
                
                # Bekle
                time.sleep(60)  # 1 dakika bekle
                
            except KeyboardInterrupt:
                self.logger.info("Trader durduruldu")
                break
            except Exception as e:
                self.logger.error(f"Ana döngü hatası: {e}")
                time.sleep(60)

if __name__ == "__main__":
    config_file = os.path.join(os.path.dirname(__file__), "sol_macd_config.json")
    trader = SolMacdTrader(config_file)
    trader.run()
