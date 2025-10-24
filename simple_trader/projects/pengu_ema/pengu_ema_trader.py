#!/usr/bin/env python3
"""
PENGU EMA Crossover Trader
Basit EMA crossover stratejisi - PENGU/USDT için
"""

import time
import json
import logging
import ccxt
from datetime import datetime
from typing import Dict, Any, Optional
import sys
import os

# Add common directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from order_client import IdempotentOrderClient

class PenguEmaTrader:
    def __init__(self, config_file: str = "pengu_ema_config.json"):
        """Initialize the PENGU EMA trader"""
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.setup_exchange()
        self.setup_order_client()
        
        # EMA parameters
        self.ema_fast = self.config.get('ema_fast', 10)
        self.ema_slow = self.config.get('ema_slow', 26)
        
        # Trading parameters
        self.symbol = self.config['symbol']
        self.trade_amount_usd = self.config['trade_amount_usd']
        self.leverage = self.config['leverage']
        self.take_profit_pct = self.config['take_profit_pct']
        self.stop_loss_pct = self.config['stop_loss_pct']
        
        # Telegram settings
        self.telegram_enabled = self.config.get('telegram', {}).get('enabled', False)
        if self.telegram_enabled:
            self.bot_token = self.config['telegram']['bot_token']
            self.chat_id = self.config['telegram']['chat_id']
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            self.log.info("📱 Telegram bildirimleri aktif")
        else:
            self.log.info("📱 Telegram bildirimleri pasif")
        
        self.log.info(f"🚀 PENGU EMA Trader başlatıldı")
        self.log.info(f"📊 Symbol: {self.symbol}")
        self.log.info(f"📈 EMA Fast: {self.ema_fast}, Slow: {self.ema_slow}")
        self.log.info(f"💰 Trade Amount: ${self.trade_amount_usd}")
        self.log.info(f"⚡ Leverage: {self.leverage}x")
        self.log.info(f"🎯 Take Profit: {self.take_profit_pct}%")
        self.log.info(f"🛡️ Stop Loss: {self.stop_loss_pct}%")

    def load_config(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Config yükleme hatası: {e}")
            sys.exit(1)

    def setup_logging(self):
        """Setup logging configuration"""
        log_level = self.config.get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('pengu_ema_trading.log'),
                logging.StreamHandler()
            ]
        )
        self.log = logging.getLogger('PenguEmaTrader')

    def setup_exchange(self):
        """Setup Binance exchange connection"""
        try:
            self.exchange = ccxt.binance({
                'apiKey': self.config['api_key'],
                'secret': self.config['secret'],
                'sandbox': self.config.get('sandbox', False),
                'options': {
                    'defaultType': 'future',
                }
            })
            self.log.info("✅ Binance Futures bağlantısı kuruldu")
        except Exception as e:
            self.log.error(f"❌ Exchange bağlantı hatası: {e}")
            sys.exit(1)

    def setup_order_client(self):
        """Setup order client for idempotent orders"""
        try:
            self.order_client = IdempotentOrderClient(
                exchange=self.exchange,
                config=self.config
            )
            self.log.info("✅ Order client hazır")
        except Exception as e:
            self.log.error(f"❌ Order client hatası: {e}")
            sys.exit(1)

    def calculate_heikin_ashi(self, klines: list) -> list:
        """Calculate Heikin Ashi candles"""
        ha_candles = []
        
        for i, kline in enumerate(klines):
            open_price = kline[1]
            high_price = kline[2]
            low_price = kline[3]
            close_price = kline[4]
            
            if i == 0:
                # İlk mum için normal OHLC kullan
                ha_open = open_price
                ha_close = close_price
                ha_high = high_price
                ha_low = low_price
            else:
                # Önceki Heikin Ashi değerleri
                prev_ha_open = ha_candles[-1][1]
                prev_ha_close = ha_candles[-1][4]
                
                # Heikin Ashi hesaplama
                ha_close = (open_price + high_price + low_price + close_price) / 4
                ha_open = (prev_ha_open + prev_ha_close) / 2
                ha_high = max(high_price, ha_open, ha_close)
                ha_low = min(low_price, ha_open, ha_close)
            
            ha_candles.append([kline[0], ha_open, ha_high, ha_low, ha_close])
        
        return ha_candles

    def send_telegram_message(self, message):
        """Telegram'a mesaj gönder"""
        if not self.telegram_enabled:
            return
        
        try:
            import requests
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

    def calculate_ema(self, prices: list, period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema

    def get_market_data(self) -> Optional[Dict]:
        """Get market data for PENGU/USDT"""
        try:
            # Get recent klines for EMA calculation
            klines = self.exchange.fetch_ohlcv(self.symbol, '1h', limit=100)
            
            if not klines:
                return None
            
            # Calculate Heikin Ashi candles
            ha_candles = self.calculate_heikin_ashi(klines)
            
            # Extract Heikin Ashi close prices
            ha_closes = [ha[4] for ha in ha_candles]
            
            # Calculate EMAs on Heikin Ashi closes
            ema_fast = self.calculate_ema(ha_closes, self.ema_fast)
            ema_slow = self.calculate_ema(ha_closes, self.ema_slow)
            
            if ema_fast is None or ema_slow is None:
                return None
            
            current_price = ha_closes[-1]
            
            return {
                'price': current_price,
                'ema_fast': ema_fast,
                'ema_slow': ema_slow,
                'timestamp': datetime.now(),
                'heikin_ashi': True
            }
            
        except Exception as e:
            self.log.error(f"❌ Market data hatası: {e}")
            return None

    def check_ema_crossover(self, data: Dict) -> Optional[str]:
        """Check for EMA crossover signals"""
        try:
            ema_fast = data['ema_fast']
            ema_slow = data['ema_slow']
            price = data['price']
            
            # Get previous EMAs for crossover detection
            klines = self.exchange.fetch_ohlcv(self.symbol, '1h', limit=101)
            
            # Calculate Heikin Ashi candles
            ha_candles = self.calculate_heikin_ashi(klines[:-1])  # Exclude current candle
            prev_ha_closes = [ha[4] for ha in ha_candles]
            
            prev_ema_fast = self.calculate_ema(prev_ha_closes, self.ema_fast)
            prev_ema_slow = self.calculate_ema(prev_ha_closes, self.ema_slow)
            
            if prev_ema_fast is None or prev_ema_slow is None:
                return None
            
            # Check for crossover
            if prev_ema_fast <= prev_ema_slow and ema_fast > ema_slow:
                return 'LONG'
            elif prev_ema_fast >= prev_ema_slow and ema_fast < ema_slow:
                return 'SHORT'
            
            return None
            
        except Exception as e:
            self.log.error(f"❌ EMA crossover kontrol hatası: {e}")
            return None

    def open_position(self, signal: str, data: Dict):
        """Open position based on signal"""
        try:
            price = data['price']
            ema_fast = data['ema_fast']
            ema_slow = data['ema_slow']
            
            # Calculate position size
            position_size = self.trade_amount_usd / price
            
            if signal == 'LONG':
                side = 'buy'
                tp_price = price * (1 + self.take_profit_pct / 100)
                # Minimum TP farkı ekle (Binance için)
                min_tp_diff = price * 0.005  # %0.5 minimum fark
                tp_price = max(tp_price, price + min_tp_diff)
                sl_price = price * (1 - self.stop_loss_pct / 100)
            else:  # SHORT
                side = 'sell'
                tp_price = price * (1 - self.take_profit_pct / 100)
                # Minimum TP farkı ekle (Binance için)
                min_tp_diff = price * 0.005  # %0.5 minimum fark
                tp_price = min(tp_price, price - min_tp_diff)
                sl_price = price * (1 + self.stop_loss_pct / 100)
            
            # Place entry order
            entry_order = self.order_client.place_entry_market(
                symbol=self.symbol,
                side=side,
                amount=position_size,
                extra=f"pengu_ema_{signal.lower()}"
            )
            
            if entry_order:
                self.log.info(f"✅ {signal} pozisyon açıldı: {price:.6f}")
                self.log.info(f"📊 EMA Fast: {ema_fast:.6f}, Slow: {ema_slow:.6f}")
                self.log.info(f"🎯 TP: {tp_price:.6f}, SL: {sl_price:.6f}")
                
                # Telegram bildirimi
                telegram_msg = f"""
🚀 <b>PENGU EMA - {signal} Pozisyon Açıldı</b>

📊 <b>Symbol:</b> {self.symbol}
💰 <b>Fiyat:</b> ${price:.6f}
📈 <b>EMA Fast:</b> {ema_fast:.6f}
📉 <b>EMA Slow:</b> {ema_slow:.6f}
🕯️ <b>Heikin Ashi:</b> Aktif

🎯 <b>Take Profit:</b> ${tp_price:.6f} ({self.take_profit_pct}%)
🛡️ <b>Stop Loss:</b> ${sl_price:.6f} ({self.stop_loss_pct}%)
⚡ <b>Leverage:</b> {self.leverage}x
💰 <b>Amount:</b> ${self.trade_amount_usd}

⏰ <b>Zaman:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                self.send_telegram_message(telegram_msg)
                
                # Place TP/SL orders
                self.place_tp_sl_orders(side, tp_price, sl_price, position_size)
                
                return True
            else:
                self.log.error(f"❌ {signal} pozisyon açılamadı")
                return False
                
        except Exception as e:
            self.log.error(f"❌ Pozisyon açma hatası: {e}")
            return False

    def place_tp_sl_orders(self, side: str, tp_price: float, sl_price: float, amount: float):
        """Place Take Profit and Stop Loss orders"""
        try:
            # Take Profit order
            tp_side = 'sell' if side == 'buy' else 'buy'
            tp_result = self.order_client.place_take_profit_market_close(
                symbol=self.symbol,
                side=tp_side,
                amount=amount,
                price=tp_price,
                intent='TP',
                extra=f"pengu_ema_tp_{int(time.time())}"
            )
            
            # Stop Loss order
            sl_side = 'sell' if side == 'buy' else 'buy'
            sl_result = self.order_client.place_stop_market_close(
                symbol=self.symbol,
                side=sl_side,
                amount=amount,
                stop_price=sl_price,
                intent='SL',
                extra=f"pengu_ema_sl_{int(time.time())}"
            )
            
            if tp_result and sl_result:
                self.log.info(f"✅ TP/SL emirleri yerleştirildi")
            else:
                self.log.warning(f"⚠️ TP/SL emirleri yerleştirilemedi")
            
        except Exception as e:
            self.log.error(f"❌ TP/SL emir hatası: {e}")

    def run(self):
        """Main trading loop"""
        self.log.info("🔄 PENGU EMA trading döngüsü başlatıldı")
        
        while True:
            try:
                # Get market data
                data = self.get_market_data()
                if not data:
                    self.log.warning("⚠️ Market data alınamadı")
                    time.sleep(300)
                    continue
                
                # Check for existing position first
                positions = self.exchange.fetch_positions([self.symbol])
                has_active_position = False
                for pos in positions:
                    position_size = pos.get('size', pos.get('contracts', pos.get('amount', 0)))
                    if pos['symbol'] == self.symbol and abs(float(position_size)) > 0:
                        has_active_position = True
                        self.log.info(f"📊 Aktif pozisyon var: {position_size} @ {pos['entryPrice']}")
                        break
                
                if has_active_position:
                    self.log.info("📊 Aktif pozisyon var - yeni sinyal bekleniyor")
                    time.sleep(300)
                    continue
                
                # Check for EMA crossover
                signal = self.check_ema_crossover(data)
                
                if signal:
                    self.log.info(f"🎯 EMA Crossover sinyali: {signal}")
                    self.log.info(f"💰 Fiyat: {data['price']:.6f}")
                    self.log.info(f"📊 EMA Fast: {data['ema_fast']:.6f}, Slow: {data['ema_slow']:.6f}")
                    self.log.info(f"🕯️ Heikin Ashi: Aktif")
                    
                    # Open position
                    success = self.open_position(signal, data)
                    if success:
                        self.log.info(f"✅ {signal} pozisyon başarıyla açıldı")
                    else:
                        self.log.error(f"❌ {signal} pozisyon açılamadı")
                else:
                    self.log.debug(f"📊 Sinyal yok - EMA Fast: {data['ema_fast']:.6f}, Slow: {data['ema_slow']:.6f}")
                
                # Wait before next check
                time.sleep(300)  # Check every 5 minutes (for 1h timeframe)
                
            except KeyboardInterrupt:
                self.log.info("🛑 Trading durduruldu")
                break
            except Exception as e:
                self.log.error(f"❌ Ana döngü hatası: {e}")
                time.sleep(60)

if __name__ == "__main__":
    trader = PenguEmaTrader()
    trader.run()
