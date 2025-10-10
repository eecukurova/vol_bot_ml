#!/usr/bin/env python3
"""
Ultra Simple ATR + SuperTrend Trader + Trailing Stop
Tek dosya, maksimum 200 satır
"""

import ccxt
import pandas as pd
import numpy as np
import json
import time
import logging
from datetime import datetime

class UltraSimpleTrader:
    def __init__(self):
        # Konfigürasyon yükle
        with open('config.json', 'r') as f:
            self.cfg = json.load(f)
        
        # Exchange
        self.exchange = ccxt.binance({
            'apiKey': self.cfg['api_key'],
            'secret': self.cfg['secret'],
            'sandbox': self.cfg.get('sandbox', False)  # Canlı mod
        })
        
        # Durum
        self.position = None
        self.trades = []
        
        # Logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
        self.log = logging.getLogger(__name__)
    
    def get_data(self, symbol='SOL/USDT', timeframe='1h', limit=50):
        """Son veriyi al"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        return df
    
    def atr(self, df, period=14):
        """ATR hesapla"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        return tr.rolling(period).mean()
    
    def supertrend(self, df, period=14, multiplier=1.5):
        """SuperTrend hesapla"""
        atr_val = self.atr(df, period)
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
    
    def signal(self, df):
        """Sinyal üret"""
        st = self.supertrend(df)
        ema1 = df['close'].ewm(span=1).mean()
        
        close = df['close'].iloc[-1]
        st_val = st.iloc[-1]
        ema1_val = ema1.iloc[-1]
        prev_ema1 = ema1.iloc[-2]
        prev_st = st.iloc[-2]
        
        if close > st_val and ema1_val > st_val and prev_ema1 <= prev_st:
            return 'BUY'
        elif close < st_val and ema1_val < st_val and prev_ema1 >= prev_st:
            return 'SELL'
        return 'HOLD'
    
    def open_pos(self, symbol, side, price):
        """Pozisyon aç"""
        try:
            size = self.cfg['position_size'] * self.cfg['leverage'] / price
            
            if side == 'BUY':
                order = self.exchange.create_market_buy_order(symbol, size)
            else:
                order = self.exchange.create_market_sell_order(symbol, size)
            
            # Trailing stop için başlangıç değerleri
            if side == 'BUY':
                initial_sl = price * (1 - self.cfg['sl'])
                initial_tp = price * (1 + self.cfg['tp'])
                best_price = price
            else:
                initial_sl = price * (1 + self.cfg['sl'])
                initial_tp = price * (1 - self.cfg['tp'])
                best_price = price
            
            self.position = {
                'symbol': symbol,
                'side': side,
                'price': price,
                'size': size,
                'time': datetime.now(),
                'sl': initial_sl,
                'tp': initial_tp,
                'best_price': best_price,  # En iyi fiyat
                'trailing_active': False,  # Trailing başladı mı?
                'trailing_mult': self.cfg.get('trailing_mult', 8.0)  # Trailing çarpanı
            }
            
            self.log.info(f"✅ {side} {symbol} @ {price} | SL: {initial_sl:.4f} | TP: {initial_tp:.4f}")
            return True
        except Exception as e:
            self.log.error(f"❌ Open error: {e}")
            return False
    
    def update_trailing_stop(self, current_price):
        """Trailing stop güncelle"""
        if not self.position:
            return
        
        side = self.position['side']
        best_price = self.position['best_price']
        trailing_mult = self.position['trailing_mult']
        
        # En iyi fiyatı güncelle
        if side == 'BUY' and current_price > best_price:
            self.position['best_price'] = current_price
            best_price = current_price
        elif side == 'SELL' and current_price < best_price:
            self.position['best_price'] = current_price
            best_price = current_price
        
        # Trailing stop hesapla
        if side == 'BUY':
            # Long pozisyon için trailing
            profit_pct = (best_price - self.position['price']) / self.position['price'] * 100
            
            # Trailing başlat (5% profit'ten sonra)
            if profit_pct > 5.0 and not self.position['trailing_active']:
                self.position['trailing_active'] = True
                self.log.info(f"🎯 Trailing started! Profit: {profit_pct:.1f}%")
            
            if self.position['trailing_active']:
                # ATR tabanlı trailing stop
                df = self.get_data(self.position['symbol'])
                atr_val = self.atr(df).iloc[-1]
                
                # Yeni trailing stop
                new_sl = best_price - (atr_val * trailing_mult)
                new_tp = best_price + (atr_val * trailing_mult)
                
                # Sadece daha iyi ise güncelle
                if new_sl > self.position['sl']:
                    self.position['sl'] = new_sl
                    self.position['tp'] = new_tp
                    self.log.info(f"📈 Trailing updated! SL: {new_sl:.4f} | TP: {new_tp:.4f}")
        
        else:
            # Short pozisyon için trailing
            profit_pct = (self.position['price'] - best_price) / self.position['price'] * 100
            
            # Trailing başlat (5% profit'ten sonra)
            if profit_pct > 5.0 and not self.position['trailing_active']:
                self.position['trailing_active'] = True
                self.log.info(f"🎯 Trailing started! Profit: {profit_pct:.1f}%")
            
            if self.position['trailing_active']:
                # ATR tabanlı trailing stop
                df = self.get_data(self.position['symbol'])
                atr_val = self.atr(df).iloc[-1]
                
                # Yeni trailing stop
                new_sl = best_price + (atr_val * trailing_mult)
                new_tp = best_price - (atr_val * trailing_mult)
                
                # Sadece daha iyi ise güncelle
                if new_sl < self.position['sl']:
                    self.position['sl'] = new_sl
                    self.position['tp'] = new_tp
                    self.log.info(f"📉 Trailing updated! SL: {new_sl:.4f} | TP: {new_tp:.4f}")
    
    def close_pos(self, reason='MANUAL'):
        """Pozisyon kapat"""
        if not self.position:
            return False
        
        try:
            symbol = self.position['symbol']
            size = self.position['size']
            side = self.position['side']
            
            if side == 'BUY':
                order = self.exchange.create_market_sell_order(symbol, size)
            else:
                order = self.exchange.create_market_buy_order(symbol, size)
            
            pnl = self.pnl(order['price'])
            
            trade = {
                'time': self.position['time'],
                'exit': datetime.now(),
                'symbol': symbol,
                'side': side,
                'entry': self.position['price'],
                'exit': order['price'],
                'pnl': pnl,
                'reason': reason,
                'trailing_used': self.position['trailing_active']
            }
            
            self.trades.append(trade)
            self.save_trades()
            
            self.log.info(f"🔒 Closed {reason} | PnL: ${pnl:.2f} | Trailing: {self.position['trailing_active']}")
            self.position = None
            return True
        except Exception as e:
            self.log.error(f"❌ Close error: {e}")
            return False
    
    def pnl(self, exit_price):
        """PnL hesapla"""
        if not self.position:
            return 0
        
        entry = self.position['price']
        size = self.position['size']
        side = self.position['side']
        
        if side == 'BUY':
            return (exit_price - entry) * size
        else:
            return (entry - exit_price) * size
    
    def check_exit(self, price):
        """Çıkış kontrolü"""
        if not self.position:
            return False
        
        # Trailing stop güncelle
        self.update_trailing_stop(price)
        
        side = self.position['side']
        sl = self.position['sl']
        tp = self.position['tp']
        
        if side == 'BUY':
            if price <= sl:
                self.close_pos('STOP_LOSS')
                return True
            elif price >= tp:
                self.close_pos('TAKE_PROFIT')
                return True
        else:
            if price >= sl:
                self.close_pos('STOP_LOSS')
                return True
            elif price <= tp:
                self.close_pos('TAKE_PROFIT')
                return True
        
        return False
    
    def save_trades(self):
        """Trade'leri kaydet"""
        with open('trades.json', 'w') as f:
            json.dump(self.trades, f, indent=2, default=str)
    
    def stats(self):
        """İstatistikler"""
        if not self.trades:
            return "No trades yet"
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        wins = sum(1 for t in self.trades if t['pnl'] > 0)
        total_trades = len(self.trades)
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        trailing_trades = sum(1 for t in self.trades if t.get('trailing_used', False))
        
        return f"Trades: {total_trades} | Win Rate: {win_rate:.1f}% | Total PnL: ${total_pnl:.2f} | Trailing: {trailing_trades}"
    
    def run(self):
        """Ana döngü"""
        symbol = self.cfg['symbol']
        
        self.log.info(f"🚀 Starting trader for {symbol}")
        self.log.info(f"📊 Config: ${self.cfg['position_size']} | {self.cfg['leverage']}x | SL:{self.cfg['sl']*100:.1f}% | TP:{self.cfg['tp']*100:.1f}% | Trailing: {self.cfg.get('trailing_mult', 8.0)}x")
        
        while True:
            try:
                # Veri al
                df = self.get_data(symbol)
                price = df['close'].iloc[-1]
                
                # Çıkış kontrolü
                if self.position:
                    self.check_exit(price)
                
                # Sinyal kontrolü
                if not self.position:
                    sig = self.signal(df)
                    if sig in ['BUY', 'SELL']:
                        self.open_pos(symbol, sig, price)
                
                # İstatistikler
                if len(self.trades) % 10 == 0 and self.trades:
                    self.log.info(f"📈 {self.stats()}")
                
                # Bekle
                time.sleep(self.cfg['interval'])
                
            except KeyboardInterrupt:
                self.log.info("🛑 Stopping...")
                if self.position:
                    self.close_pos('MANUAL')
                break
            except Exception as e:
                self.log.error(f"❌ Error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    trader = UltraSimpleTrader()
    trader.run()
