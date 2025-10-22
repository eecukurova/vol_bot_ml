#!/usr/bin/env python3
"""
SOL Supertrend RSI Strategy - Optimized Version
Adapted from DEEP strategy for SOL/USDT
"""

import ccxt
import pandas as pd
import pandas_ta as pta
import json
import time
import logging
import requests
from datetime import datetime
from typing import Dict, Optional, Tuple

class SolSupertrendStrategy:
    """SOL Supertrend RSI Strategy Implementation"""
    
    def __init__(self, config_file: str):
        """Initialize strategy with config"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Setup logging
        self.setup_logging()
        
        # Exchange setup
        self.exchange = ccxt.binance({
            'apiKey': self.config['api_key'],
            'secret': self.config['secret'],
            'sandbox': self.config['sandbox'],
            'options': {'defaultType': 'future'},
            'enableRateLimit': True
        })
        
        # Strategy parameters
        self.symbol = self.config['symbol']
        self.trade_amount_usd = self.config['trade_amount_usd']
        self.leverage = self.config['leverage']
        
        # Strategy config
        self.strategy_config = self.config['strategy']
        self.rsi_length = self.strategy_config['rsi_length']
        self.rsi_oversold = self.strategy_config['rsi_oversold']
        self.rsi_overbought = self.strategy_config['rsi_overbought']
        self.rsi_long_exit = self.strategy_config['rsi_long_exit']
        self.rsi_short_exit = self.strategy_config['rsi_short_exit']
        self.supertrend_length = self.strategy_config['supertrend_length']
        self.supertrend_multiplier = self.strategy_config['supertrend_multiplier']
        self.support_resistance_period = self.strategy_config['support_resistance_period']
        self.max_bars = self.strategy_config['max_bars']
        
        # State variables
        self.long_status = 0
        self.short_status = 0
        self.long_position = 0
        self.short_position = 0
        self.long_amount = 0
        self.short_amount = 0
        self.dip_level = 0.0
        self.tepe_level = 0.0
        self.long_boyun = 0.0
        self.short_boyun = 0.0
        
        self.logger.info("🚀 SOL Supertrend RSI Strategy initialized")
        self.logger.info(f"📊 Symbol: {self.symbol}")
        self.logger.info(f"💰 Trade Amount: ${self.trade_amount_usd}")
        self.logger.info(f"📈 RSI: {self.rsi_length} period, OS={self.rsi_oversold}, OB={self.rsi_overbought}")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config['logging']
        
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_config['file']),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('SolSupertrendStrategy')
    
    def send_telegram_message(self, message: str):
        """Send Telegram notification"""
        if not self.config['telegram']['enabled']:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.config['telegram']['bot_token']}/sendMessage"
            data = {
                'chat_id': self.config['telegram']['chat_id'],
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.logger.info("📱 Telegram message sent")
            else:
                self.logger.warning(f"⚠️ Telegram send failed: {response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ Telegram error: {e}")
    
    def get_market_data(self) -> Optional[pd.DataFrame]:
        """Get market data for analysis"""
        try:
            # Get OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(
                self.symbol, 
                '1m', 
                limit=self.max_bars
            )
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
        except Exception as e:
            self.logger.error(f"❌ Market data error: {e}")
            return None
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators"""
        try:
            # Get latest values
            latest_close = float(df['close'].iloc[-1])
            latest_high = float(df['high'].iloc[-1])
            latest_low = float(df['low'].iloc[-1])
            
            # RSI calculation
            rsi_values = pta.rsi(df['close'], length=self.rsi_length)
            current_rsi = float(rsi_values.iloc[-1])
            
            # Supertrend calculation
            supertrend_data = pta.supertrend(
                df['high'], 
                df['low'], 
                df['close'], 
                length=self.supertrend_length,
                multiplier=self.supertrend_multiplier
            )
            current_supertrend = float(supertrend_data[f'SUPERT_{self.supertrend_length}_{self.supertrend_multiplier}'].iloc[-1])
            
            # Support/Resistance levels (last 22 bars)
            recent_df = df.tail(self.support_resistance_period)
            max_level = float(recent_df['high'].max())
            min_level = float(recent_df['low'].min())
            
            return {
                'current_price': latest_close,
                'current_high': latest_high,
                'current_low': latest_low,
                'rsi': current_rsi,
                'supertrend': current_supertrend,
                'max_level': max_level,
                'min_level': min_level
            }
        except Exception as e:
            self.logger.error(f"❌ Indicator calculation error: {e}")
            return None
    
    def update_long_signals(self, indicators: Dict):
        """Update LONG signal logic"""
        current_price = indicators['current_price']
        current_high = indicators['current_high']
        current_low = indicators['current_low']
        rsi = indicators['rsi']
        supertrend = indicators['supertrend']
        min_level = indicators['min_level']
        
        # LONG Signal Logic (5 stages)
        if self.long_status == 0 and rsi < self.rsi_oversold:
            if self.long_position == 0 and self.short_position == 0:
                self.long_status = 1
                self.dip_level = min_level
                self.logger.info(f"🟢 LONG Signal Stage 1: RSI={rsi:.2f} < {self.rsi_oversold}")
        
        elif self.long_status == 1 and supertrend < current_price:
            self.long_status = 2
            self.long_boyun = current_high
            self.logger.info(f"🟢 LONG Signal Stage 2: Supertrend < Price, Boyun={self.long_boyun:.4f}")
        
        elif self.long_status == 2:
            if current_high > self.long_boyun:
                self.long_boyun = current_high
                self.logger.info(f"🟢 LONG Boyun updated: {self.long_boyun:.4f}")
            
            if supertrend > current_price and current_price < self.long_boyun:
                self.long_status = 3
                self.logger.info(f"🟢 LONG Signal Stage 3: Supertrend > Price")
        
        elif self.long_status == 3 and supertrend < current_price and current_price > self.long_boyun:
            self.long_status = 4
            self.logger.info(f"🟢 LONG Signal Stage 4: Supertrend < Price, Price > Boyun")
        
        elif self.long_status == 4 and supertrend > current_price and current_price < self.long_boyun:
            self.long_status = 5
            self.logger.info(f"🟢 LONG Signal Stage 5: READY TO BUY!")
        
        # Reset conditions
        if self.long_status in [2, 4] and rsi > self.rsi_long_exit:
            self.long_status = 0
            self.logger.info(f"🔄 LONG Reset: RSI={rsi:.2f} > {self.rsi_long_exit}")
        
        if self.long_status in [2, 3, 4, 5] and rsi < self.rsi_oversold:
            self.long_status = 1
            self.dip_level = min_level
            self.logger.info(f"🔄 LONG Reset to Stage 1: RSI={rsi:.2f} < {self.rsi_oversold}")
    
    def update_short_signals(self, indicators: Dict):
        """Update SHORT signal logic"""
        current_price = indicators['current_price']
        current_high = indicators['current_high']
        current_low = indicators['current_low']
        rsi = indicators['rsi']
        supertrend = indicators['supertrend']
        max_level = indicators['max_level']
        
        # SHORT Signal Logic (5 stages)
        if self.short_status == 0 and rsi > self.rsi_overbought:
            if self.long_position == 0 and self.short_position == 0:
                self.short_status = 1
                self.tepe_level = max_level
                self.logger.info(f"🔴 SHORT Signal Stage 1: RSI={rsi:.2f} > {self.rsi_overbought}")
        
        elif self.short_status == 1 and supertrend > current_price:
            self.short_status = 2
            self.short_boyun = current_low
            self.logger.info(f"🔴 SHORT Signal Stage 2: Supertrend > Price, Boyun={self.short_boyun:.4f}")
        
        elif self.short_status == 2:
            if current_low < self.short_boyun:
                self.short_boyun = current_low
                self.logger.info(f"🔴 SHORT Boyun updated: {self.short_boyun:.4f}")
            
            if supertrend < current_price and current_price > self.short_boyun:
                self.short_status = 3
                self.logger.info(f"🔴 SHORT Signal Stage 3: Supertrend < Price")
        
        elif self.short_status == 3 and supertrend > current_price and current_price < self.short_boyun:
            self.short_status = 4
            self.logger.info(f"🔴 SHORT Signal Stage 4: Supertrend > Price, Price < Boyun")
        
        elif self.short_status == 4 and supertrend < current_price and current_price > self.short_boyun:
            self.short_status = 5
            self.logger.info(f"🔴 SHORT Signal Stage 5: READY TO SELL!")
        
        # Reset conditions
        if self.short_status in [2, 4] and rsi < self.rsi_short_exit:
            self.short_status = 0
            self.logger.info(f"🔄 SHORT Reset: RSI={rsi:.2f} < {self.rsi_short_exit}")
        
        if self.short_status in [2, 3, 4, 5] and rsi > self.rsi_overbought:
            self.short_status = 1
            self.tepe_level = max_level
            self.logger.info(f"🔄 SHORT Reset to Stage 1: RSI={rsi:.2f} > {self.rsi_overbought}")
    
    def execute_trades(self, indicators: Dict):
        """Execute buy/sell orders"""
        current_price = indicators['current_price']
        
        # Calculate position size
        size = self.trade_amount_usd / current_price
        amount = round(size, 6)
        
        # LONG Entry
        if (self.long_position == 0 and self.short_position == 0 and 
            self.long_status == 5 and current_price > self.long_boyun):
            
            try:
                order = self.exchange.create_market_buy_order(self.symbol, amount)
                self.long_position = 1
                self.long_amount = amount
                
                self.logger.info(f"🟢 LONG POSITION OPENED: {amount} @ {current_price:.4f}")
                self.send_telegram_message(
                    f"🟢 SOL LONG Position Opened\n"
                    f"💰 Amount: {amount}\n"
                    f"💵 Price: ${current_price:.4f}\n"
                    f"📊 RSI: {indicators['rsi']:.2f}\n"
                    f"🎯 Boyun: ${self.long_boyun:.4f}"
                )
            except Exception as e:
                self.logger.error(f"❌ LONG order error: {e}")
        
        # SHORT Entry
        if (self.long_position == 0 and self.short_position == 0 and 
            self.short_status == 5 and current_price < self.short_boyun):
            
            try:
                order = self.exchange.create_market_sell_order(self.symbol, amount)
                self.short_position = 1
                self.short_amount = amount
                
                self.logger.info(f"🔴 SHORT POSITION OPENED: {amount} @ {current_price:.4f}")
                self.send_telegram_message(
                    f"🔴 SOL SHORT Position Opened\n"
                    f"💰 Amount: {amount}\n"
                    f"💵 Price: ${current_price:.4f}\n"
                    f"📊 RSI: {indicators['rsi']:.2f}\n"
                    f"🎯 Boyun: ${self.short_boyun:.4f}"
                )
            except Exception as e:
                self.logger.error(f"❌ SHORT order error: {e}")
        
        # LONG Exit
        if self.long_position == 1 and current_price < indicators['min_level']:
            try:
                order = self.exchange.create_market_sell_order(self.symbol, self.long_amount)
                self.long_position = 0
                self.long_status = 0
                self.short_status = 0
                
                self.logger.info(f"🟢 LONG POSITION CLOSED: {self.long_amount} @ {current_price:.4f}")
                self.send_telegram_message(
                    f"🟢 SOL LONG Position Closed\n"
                    f"💰 Amount: {self.long_amount}\n"
                    f"💵 Price: ${current_price:.4f}\n"
                    f"📊 Exit Level: ${indicators['min_level']:.4f}"
                )
            except Exception as e:
                self.logger.error(f"❌ LONG exit error: {e}")
        
        # SHORT Exit
        if self.short_position == 1 and current_price > indicators['max_level']:
            try:
                order = self.exchange.create_market_buy_order(self.symbol, self.short_amount)
                self.short_position = 0
                self.long_status = 0
                self.short_status = 0
                
                self.logger.info(f"🔴 SHORT POSITION CLOSED: {self.short_amount} @ {current_price:.4f}")
                self.send_telegram_message(
                    f"🔴 SOL SHORT Position Closed\n"
                    f"💰 Amount: {self.short_amount}\n"
                    f"💵 Price: ${current_price:.4f}\n"
                    f"📊 Exit Level: ${indicators['max_level']:.4f}"
                )
            except Exception as e:
                self.logger.error(f"❌ SHORT exit error: {e}")
    
    def run(self):
        """Main trading loop"""
        self.logger.info("🚀 SOL Supertrend RSI Strategy started")
        
        while True:
            try:
                # Get market data
                df = self.get_market_data()
                if df is None:
                    time.sleep(60)
                    continue
                
                # Calculate indicators
                indicators = self.calculate_indicators(df)
                if indicators is None:
                    time.sleep(60)
                    continue
                
                # Update signals
                self.update_long_signals(indicators)
                self.update_short_signals(indicators)
                
                # Execute trades
                self.execute_trades(indicators)
                
                # Log status
                self.logger.info(
                    f"📊 Status - LONG: {self.long_status}, SHORT: {self.short_status}, "
                    f"Price: ${indicators['current_price']:.4f}, RSI: {indicators['rsi']:.2f}, "
                    f"Supertrend: ${indicators['supertrend']:.4f}"
                )
                
                # Wait before next iteration
                time.sleep(60)  # 1 minute intervals
                
            except KeyboardInterrupt:
                self.logger.info("🛑 Strategy stopped by user")
                break
            except Exception as e:
                self.logger.error(f"❌ Main loop error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    strategy = SolSupertrendStrategy("sol_supertrend_config.json")
    strategy.run()
