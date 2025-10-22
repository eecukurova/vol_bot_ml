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
        """Indicators hesapla"""
        # Heikin Ashi kullan
        ha_data = HeikinAshiCalculator.calculate_heikin_ashi(df)
        
        # EMA Trend
        ha_data['ema_trend'] = ha_data['ha_close'].ewm(span=self.ema_len).mean()
        
        # MACD
        ema_fast = ha_data['ha_close'].ewm(span=self.macd_fast).mean()
        ema_slow = ha_data['ha_close'].ewm(span=self.macd_slow).mean()
        ha_data['macd'] = ema_fast - ema_slow
        ha_data['macd_signal'] = ha_data['macd'].ewm(span=self.macd_signal).mean()
        ha_data['macd_hist'] = ha_data['macd'] - ha_data['macd_signal']
        
        # RSI
        delta = ha_data['ha_close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_len).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_len).mean()
        rs = gain / loss
        ha_data['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR
        high_low = ha_data['high'] - ha_data['low']
        high_close = np.abs(ha_data['high'] - ha_data['close'].shift())
        low_close = np.abs(ha_data['low'] - ha_data['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        ha_data['atr'] = true_range.rolling(window=self.atr_len).mean()
        
        return ha_data
    
    def generate_signals(self, df):
        """Sinyaller üret"""
        # Bileşen koşulları
        df['is_bull_trend'] = df['ha_close'] > df['ema_trend']
        df['is_bear_trend'] = df['ha_close'] < df['ema_trend']
        df['is_bull_momentum'] = df['rsi'] > 50
        df['is_bear_momentum'] = df['rsi'] < 50
        df['is_bull_power'] = df['macd'] > df['macd_signal']
        df['is_bear_power'] = df['macd'] < df['macd_signal']
        
        # RSI filtreleri
        df['not_overbought'] = df['rsi'] < self.rsi_ob
        df['not_oversold'] = df['rsi'] > self.rsi_os
        
        # Skorlar
        df['bull_score'] = (df['is_bull_trend'].astype(int) + 
                           df['is_bull_momentum'].astype(int) + 
                           df['is_bull_power'].astype(int))
        df['bear_score'] = (df['is_bear_trend'].astype(int) + 
                           df['is_bear_momentum'].astype(int) + 
                           df['is_bear_power'].astype(int))
        
        # Ham sinyaller
        df['raw_buy'] = (df['bull_score'] == 3) & df['not_overbought']
        df['raw_sell'] = (df['bear_score'] == 3) & df['not_oversold']
        
        # Sinyal filtreleme (yinelenen sinyalleri engelle)
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
                return None
            
            # Indicators hesapla
            df_with_indicators = self.strategy.calculate_indicators(df)
            
            # Sinyaller üret
            df_with_signals = self.strategy.generate_signals(df_with_indicators)
            
            # Son mumu kontrol et
            last_row = df_with_signals.iloc[-1]
            
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
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Sinyal kontrol hatası: {e}")
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
                self.current_position = {
                    'order_id': order_result['order_id'],
                    'side': side,
                    'entry_price': signal['price'],
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'timeframe': timeframe,
                    'timestamp': signal['timestamp'],
                    'sl_order_id': order_result['sl_order_id'],
                    'tp_order_id': order_result['tp_order_id']
                }
                
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
                if pos['symbol'] == symbol and pos['contracts'] > 0:
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
        """Çıkış sinyallerini kontrol et"""
        if not self.current_position:
            return
        
        try:
            symbol = self.config['symbol']
            timeframe = self.current_position['timeframe']
            
            # Sinyal kontrol et
            signal = self.check_signals(symbol, timeframe)
            
            if signal and signal['type'] != self.current_position['side']:
                # Karşı sinyal geldi, pozisyonu kapat
                self.close_position("signal_reversal")
                
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
                if pos['symbol'] == symbol and pos['contracts'] > 0:
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
    
    def run(self):
        """Ana trading döngüsü"""
        self.logger.info("SOL MACD Trend Trader başlatıldı")
        
        symbol = self.config['symbol']
        timeframe = self.config['multi_timeframe']['timeframes']['4h']['enabled'] and '4h' or '1h'
        
        while True:
            try:
                # Mevcut pozisyon kontrol et
                if self.current_position:
                    # Pozisyon durumunu kontrol et (TP/SL gerçekleşmesi)
                    self.check_position_status()
                    
                    # Çıkış sinyallerini kontrol et
                    self.check_exit_signals()
                else:
                    # Yeni sinyal kontrol et
                    signal = self.check_signals(symbol, timeframe)
                    
                    if signal:
                        self.logger.info(f"Yeni sinyal: {signal['type']} @ {signal['price']:.4f}")
                        
                        # Pozisyon aç
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
