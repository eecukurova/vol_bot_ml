"""
Multi-Timeframe EMA Crossover Trader – Production Hardening (Final)
Senior Python Engineer • CCXT/Trading • Reliability & Production Hardening

Production-ready EMA crossover trading bot with:
- Symbol consistency (USDⓈ-M Futures)
- EMA/RSI alignment with TradingView
- Intrabar/confirmed bar signal selection
- MTF filter + trigger logic
- Precision rules and error handling
- Persisted state management
- Dry-run mode
- Comprehensive logging
"""

import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
import ccxt
import requests

# Add common module to path
current_dir = os.path.dirname(os.path.abspath(__file__))
common_dir = os.path.join(os.path.dirname(current_dir), 'common')
sys.path.insert(0, common_dir)

from utils import (
    now_utc, format_utc_timestamp, quantize_amount, quantize_price,
    retry_with_backoff, safe_fetch_ticker, safe_fetch_ohlcv, safe_fetch_positions,
    safe_fetch_open_orders, safe_telegram_send, ema_tv, rsi_wilder,
    select_series_for_signal, detect_ema_crossover, validate_config,
    generate_signal_id, log_signal_details, log_position_details,
    calculate_pnl_percentage, format_pnl_message
)

# Import order client
from order_client import IdempotentOrderClient


class StateManager:
    """Persistent state management for runtime data"""
    
    def __init__(self, state_file: str):
        self.state_file = state_file
        self.state = self.load_state()
    
    def load_state(self) -> Dict[str, Any]:
        """Load state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load state: {e}")
        
        return {
            "active_position": None,
            "last_signal_times": {},
            "last_signal_bars": {},
            "break_even_applied": {},
            "cooldown_until": None,
            "last_update": None
        }
    
    def save_state(self):
        """Save state to file atomically"""
        try:
            self.state["last_update"] = format_utc_timestamp()
            temp_file = self.state_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            os.rename(temp_file, self.state_file)
        except Exception as e:
            logging.error(f"Failed to save state: {e}")
    
    def get(self, key: str, default=None):
        """Get state value"""
        return self.state.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set state value and save"""
        self.state[key] = value
        self.save_state()
    
    def update_position(self, position: Dict[str, Any]):
        """Update active position"""
        self.state["active_position"] = position
        self.save_state()
    
    def clear_position(self):
        """Clear active position"""
        self.state["active_position"] = None
        self.save_state()


class TechnicalIndicators:
    """TradingView-compatible technical indicators"""
    
    @staticmethod
    def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Heikin Ashi candles"""
        ha_df = df.copy()
        
        # First candle
        ha_df.iloc[0, 1] = (df.iloc[0, 1] + df.iloc[0, 4]) / 2  # HA Close
        ha_df.iloc[0, 0] = (df.iloc[0, 0] + ha_df.iloc[0, 1]) / 2  # HA Open
        
        # Subsequent candles
        for i in range(1, len(df)):
            # HA Close = (O + H + L + C) / 4
            ha_df.iloc[i, 4] = (df.iloc[i, 0] + df.iloc[i, 1] + df.iloc[i, 2] + df.iloc[i, 3]) / 4
            
            # HA Open = (Previous HA Open + Previous HA Close) / 2
            ha_df.iloc[i, 0] = (ha_df.iloc[i-1, 0] + ha_df.iloc[i-1, 4]) / 2
            
            # HA High = max(H, HA Open, HA Close)
            ha_df.iloc[i, 1] = max(df.iloc[i, 1], ha_df.iloc[i, 0], ha_df.iloc[i, 4])
            
            # HA Low = min(L, HA Open, HA Close)
            ha_df.iloc[i, 2] = min(df.iloc[i, 2], ha_df.iloc[i, 0], ha_df.iloc[i, 4])
        
        return ha_df


class MultiTimeframeEMATrader:
    """Production-ready Multi-Timeframe EMA Crossover Trader"""
    
    def __init__(self, config_file: Optional[str] = None):
        if config_file is None:
            config_file = os.path.join(current_dir, 'multiple_ema_crossover_config.json')
        
        # Load and validate configuration
        with open(config_file, 'r') as f:
            raw_config = json.load(f)
        self.cfg = validate_config(raw_config)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize exchange
        self._setup_exchange()
        
        # Initialize state manager
        state_file = os.path.join(current_dir, 'runtime', 'state.json')
        self.state_manager = StateManager(state_file)
        
        # Initialize order client
        self.order_client = IdempotentOrderClient(
            self.exchange,
            self.cfg
        )
        
        # Trading parameters
        self.symbol = self.cfg['symbol']
        self.futures_symbol = f"{self.symbol}{self.cfg['futures_suffix']}"
        self.trade_amount_usd = self.cfg['trade_amount_usd']
        self.leverage = self.cfg['leverage']
        self.dry_run = self.cfg['dry_run']
        
        # Multi-timeframe parameters
        self.timeframes = list(self.cfg['multi_timeframe']['timeframes'].keys())
        self.filter_tf = self.cfg['multi_timeframe']['filter_tf']
        self.trigger_tf = self.cfg['multi_timeframe']['trigger_tf']
        self.ema_fast = self.cfg['ema']['fast_period']
        self.ema_slow = self.cfg['ema']['slow_period']
        self.heikin_ashi_enabled = self.cfg['heikin_ashi']['enabled']
        
        # Signal management
        self.single_position_only = self.cfg['signal_management']['single_position_only']
        self.use_intrabar_signals = self.cfg['signal_management']['use_intrabar_signals']
        self.ema_cross_hysteresis = self.cfg['signal_management']['ema_cross_hysteresis']
        self.tf_cooldown_bars = self.cfg['signal_management']['tf_cooldown_bars']
        self.cooldown_after_exit = self.cfg['signal_management']['cooldown_after_exit']
        
        # Risk management
        self.break_even_enabled = self.cfg['risk_management']['break_even_enabled']
        self.break_even_pct = self.cfg['risk_management']['break_even_percentage']
        
        # Telegram settings
        self.telegram_enabled = self.cfg['telegram']['enabled']
        self.bot_token = self.cfg['telegram']['bot_token']
        self.chat_id = self.cfg['telegram']['chat_id']
        
        # Internal state
        self.active_position = self.state_manager.get('active_position')
        self.last_signal_times = self.state_manager.get('last_signal_times', {})
        self.last_signal_bars = self.state_manager.get('last_signal_bars', {})
        self.break_even_applied = self.state_manager.get('break_even_applied', {})
        
        # Cooldown management
        cooldown_until = self.state_manager.get('cooldown_until')
        self.cooldown_until = datetime.fromisoformat(cooldown_until) if cooldown_until else None
        
        self.log.info("🚀 Multi-Timeframe EMA Crossover Trader initialized")
        self.log.info(f"📊 Symbol: {self.futures_symbol}")
        self.log.info(f"📈 Timeframes: {self.timeframes}")
        self.log.info(f"📊 EMA: Fast={self.ema_fast}, Slow={self.ema_slow}")
        self.log.info(f"🕯️ Heikin Ashi: {'Enabled' if self.heikin_ashi_enabled else 'Disabled'}")
        self.log.info(f"🎯 Intrabar Signals: {'Enabled' if self.use_intrabar_signals else 'Disabled'}")
        self.log.info(f"🔧 Dry Run: {'Enabled' if self.dry_run else 'Disabled'}")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_file = os.path.join(current_dir, self.cfg['logging']['file'])
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, self.cfg['logging']['level']),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file)
            ]
        )
        self.log = logging.getLogger(__name__)
    
    def _setup_exchange(self):
        """Setup exchange connection"""
        self.exchange = ccxt.binance({
            'apiKey': self.cfg['api_key'],
            'secret': self.cfg['secret'],
            'sandbox': self.cfg['sandbox'],
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future' if self.cfg['use_futures'] else 'spot'
            }
        })
        
        # Test connection
        try:
            self.exchange.fetch_status()
            self.log.info("✅ Exchange connection established")
        except Exception as e:
            self.log.error(f"❌ Exchange connection failed: {e}")
            raise
    
    def setup_trading_parameters(self):
        """Setup leverage, margin mode, and position mode"""
        try:
            # Set leverage
            self.exchange.set_leverage(self.leverage, self.futures_symbol)
            self.log.info(f"✅ Leverage set to {self.leverage}x for {self.futures_symbol}")
            
            # Set margin mode
            if self.cfg['margin_mode']:
                try:
                    self.exchange.set_margin_mode(self.cfg['margin_mode'], self.futures_symbol)
                    self.log.info(f"✅ Margin mode set to {self.cfg['margin_mode']}")
                except Exception as e:
                    self.log.warning(f"⚠️ Margin mode setting failed: {e}")
            
            # Set position mode (hedge/one-way)
            if self.cfg['hedge_mode']:
                try:
                    self.exchange.set_position_mode(True)  # Hedge mode
                    self.log.info("✅ Position mode set to hedge")
                except Exception as e:
                    self.log.warning(f"⚠️ Hedge mode setting failed: {e}")
            
        except Exception as e:
            self.log.error(f"❌ Trading parameters setup failed: {e}")
            raise
    
    def get_market_data(self, timeframe: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """Get market data with retry"""
        try:
            ohlcv = safe_fetch_ohlcv(self.exchange, self.futures_symbol, timeframe, limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Apply Heikin Ashi if enabled
            if self.heikin_ashi_enabled:
                df = TechnicalIndicators.calculate_heikin_ashi(df)
            
            return df
        except Exception as e:
            self.log.error(f"❌ Market data fetch failed ({timeframe}): {e}")
            return None
    
    def calculate_indicators(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calculate EMA indicators"""
        close_prices = df['close']
        fast_ema = ema_tv(close_prices, self.ema_fast)
        slow_ema = ema_tv(close_prices, self.ema_slow)
        return fast_ema, slow_ema
    
    def detect_signal(self, timeframe: str) -> Optional[Dict[str, Any]]:
        """Detect EMA crossover signal for given timeframe"""
        try:
            # Get market data
            df = self.get_market_data(timeframe, limit=200)
            if df is None or len(df) < self.cfg['signal_management']['timeframe_validation']['min_candles_for_signal']:
                return None
            
            # Calculate indicators
            fast_ema, slow_ema = self.calculate_indicators(df)
            
            # Select series for signal generation
            fast_ema_signal = select_series_for_signal(fast_ema, self.use_intrabar_signals)
            slow_ema_signal = select_series_for_signal(slow_ema, self.use_intrabar_signals)
            
            # Detect crossover
            crossover = detect_ema_crossover(fast_ema_signal, slow_ema_signal, self.ema_cross_hysteresis)
            
            # Get latest signal
            latest_signal = crossover.iloc[-1]
            if latest_signal == 'none':
                return None
            
            # Check timeframe cooldown
            if self._is_timeframe_in_cooldown(timeframe, df.index[-1]):
                return None
            
            # Get current price
            current_price = df['close'].iloc[-1]
            
            # Create signal info
            signal_info = {
                'timeframe': timeframe,
                'signal_type': f'EMA_CROSS_{latest_signal.upper()}',
                'side': latest_signal,
                'price': current_price,
                'ema_fast': fast_ema.iloc[-1],
                'ema_slow': slow_ema.iloc[-1],
                'timestamp': df.index[-1],
                'signal_id': generate_signal_id()
            }
            
            # Log signal details
            log_signal_details(
                self.log, signal_info['signal_id'], self.futures_symbol,
                timeframe, latest_signal, current_price,
                fast_ema.iloc[-1], slow_ema.iloc[-1]
            )
            
            # Update signal tracking
            self.last_signal_times[timeframe] = format_utc_timestamp()
            self.last_signal_bars[timeframe] = df.index[-1].timestamp()
            self.state_manager.set('last_signal_times', self.last_signal_times)
            self.state_manager.set('last_signal_bars', self.last_signal_bars)
            
            return signal_info
            
        except Exception as e:
            self.log.error(f"❌ Signal detection failed ({timeframe}): {e}")
            return None
    
    def _is_timeframe_in_cooldown(self, timeframe: str, current_bar_timestamp) -> bool:
        """Check if timeframe is in cooldown"""
        if timeframe not in self.tf_cooldown_bars:
            return False
        
        last_bar_timestamp = self.last_signal_bars.get(timeframe)
        if last_bar_timestamp is None:
            return False
        
        cooldown_bars = self.tf_cooldown_bars[timeframe]
        # Simple bar count check (in production, you'd want more sophisticated logic)
        return (current_bar_timestamp.timestamp() - last_bar_timestamp) < (cooldown_bars * 60 * 60)  # Simplified
    
    def check_mtf_filter(self) -> Optional[str]:
        """Check multi-timeframe filter"""
        try:
            # Get filter timeframe data
            df = self.get_market_data(self.filter_tf, limit=200)
            if df is None:
                return None
            
            # Calculate indicators
            fast_ema, slow_ema = self.calculate_indicators(df)
            
            # Select series for filter
            fast_ema_filter = select_series_for_signal(fast_ema, self.use_intrabar_signals)
            slow_ema_filter = select_series_for_signal(slow_ema, self.use_intrabar_signals)
            
            # Determine trend direction
            latest_fast = fast_ema_filter.iloc[-1]
            latest_slow = slow_ema_filter.iloc[-1]
            
            diff_pct = abs(latest_fast - latest_slow) / latest_slow
            
            if diff_pct < 0.001:  # Less than 0.1% difference
                return 'none'  # No clear trend
            elif latest_fast > latest_slow:
                return 'long'
            else:
                return 'short'
                
        except Exception as e:
            self.log.error(f"❌ MTF filter check failed: {e}")
            return None
    
    def validate_signal_with_filter(self, signal_info: Dict[str, Any]) -> bool:
        """Validate signal against MTF filter"""
        filter_direction = self.check_mtf_filter()
        if filter_direction is None:
            return True  # If filter fails, allow signal
        
        signal_direction = signal_info['side']
        
        # Check if signal aligns with filter
        if filter_direction == 'none':
            return True  # No clear filter direction, allow signal
        elif filter_direction == signal_direction:
            return True  # Signal aligns with filter
        else:
            self.log.info(f"🚫 Signal filtered out: {signal_direction} signal vs {filter_direction} filter")
            return False
    
    def calculate_position_size(self, price: float) -> float:
        """Calculate position size based on USD amount"""
        try:
            size = self.trade_amount_usd / price
            return quantize_amount(self.exchange, self.futures_symbol, size)
        except Exception as e:
            self.log.error(f"❌ Position size calculation failed: {e}")
            return 0.0
    
    def open_position(self, signal_info: Dict[str, Any]) -> bool:
        """Open position based on signal"""
        try:
            if self.dry_run:
                self.log.info(f"[DRY-RUN] Would open {signal_info['side']} position")
                return True
            
            # Validate signal with MTF filter
            if not self.validate_signal_with_filter(signal_info):
                return False
            
            # Check single position only
            if self.single_position_only and self.active_position:
                self.log.info("🚫 Single position only - position already active")
                return False
            
            # Check cooldown
            if self._is_in_cooldown():
                return False
            
            # Calculate position size
            price = signal_info['price']
            size = self.calculate_position_size(price)
            
            if size <= 0:
                self.log.error("❌ Invalid position size")
                return False
            
            # Get timeframe-specific TP/SL
            timeframe = signal_info['timeframe']
            tp_pct = self.cfg['multi_timeframe']['timeframes'][timeframe]['take_profit']
            sl_pct = self.cfg['multi_timeframe']['timeframes'][timeframe]['stop_loss']
            
            # Calculate TP/SL prices
            side = signal_info['side']
            if side == 'long':
                tp_price = quantize_price(self.exchange, self.futures_symbol, price * (1 + tp_pct))
                sl_price = quantize_price(self.exchange, self.futures_symbol, price * (1 - sl_pct))
            else:
                tp_price = quantize_price(self.exchange, self.futures_symbol, price * (1 - tp_pct))
                sl_price = quantize_price(self.exchange, self.futures_symbol, price * (1 + sl_pct))
            
            # Place entry order
            self.log.info(f"🚀 {side.upper()} position opening: {size:.4f} @ ${price:.4f}")
            
            entry_order = self.order_client.place_entry_market(
                symbol=self.futures_symbol,
                side=side,
                amount=size,
                extra=f"entry_{int(time.time())}"
            )
            
            if not entry_order:
                self.log.error("❌ Entry order failed")
                return False
            
            # Get actual entry price
            actual_entry_price = entry_order.get('average') or entry_order.get('price') or price
            
            # Place SL order
            sl_order = self.order_client.create_stop_loss_order(
                symbol=self.futures_symbol,
                side='sell' if side == 'long' else 'buy',
                price=sl_price,
                extra=f"sl_{int(time.time())}"
            )
            
            # Place TP order
            tp_order = self.order_client.create_take_profit_order(
                symbol=self.futures_symbol,
                side='sell' if side == 'long' else 'buy',
                price=tp_price,
                extra=f"tp_{int(time.time())}"
            )
            
            # Create position record
            position = {
                'symbol': self.futures_symbol,
                    'side': side,
                'entry_price': float(actual_entry_price),
                    'size': size,
                    'timeframe': timeframe,
                    'take_profit_pct': tp_pct,
                    'stop_loss_pct': sl_pct,
                'sl_order_id': sl_order.get('id') if sl_order else None,
                'tp_order_id': tp_order.get('id') if tp_order else None,
                'signal_id': signal_info['signal_id'],
                'timestamp': format_utc_timestamp(),
                'break_even_applied': False
            }
            
            # Update state
            self.active_position = position
            self.state_manager.update_position(position)
            
            # Send Telegram notification
            self._send_position_open_notification(position, signal_info)
            
            self.log.info(f"✅ {side.upper()} position opened @ ${actual_entry_price:.4f}")
            return True
            
        except Exception as e:
            self.log.error(f"❌ Position opening failed: {e}")
            self.log.error(traceback.format_exc())
            return False
    
    def _send_position_open_notification(self, position: Dict[str, Any], signal_info: Dict[str, Any]):
        """Send position open notification"""
        if not self.telegram_enabled:
            return
        
        side = position['side']
        entry_price = position['entry_price']
        size = position['size']
        timeframe = position['timeframe']
        
        # Calculate TP/SL prices
        tp_pct = position['take_profit_pct']
        sl_pct = position['stop_loss_pct']
        
        if side == 'long':
            tp_price = entry_price * (1 + tp_pct)
            sl_price = entry_price * (1 - sl_pct)
        else:
            tp_price = entry_price * (1 - tp_pct)
            sl_price = entry_price * (1 + sl_pct)
        
        message = f"""
🚀 <b>PENGU POZİSYON AÇILDI</b>

📊 <b>Timeframe:</b> {timeframe}
📈 <b>Yön:</b> {side.upper()}
🎯 <b>Sinyal:</b> {signal_info['signal_type']}
💰 <b>Entry Fiyatı:</b> ${entry_price:.4f}
📦 <b>Miktar:</b> {size:.4f} PENGU
💵 <b>Değer:</b> ${self.trade_amount_usd:.2f} USDT
⚡ <b>Kaldıraç:</b> {self.leverage}x

📈 <b>EMA:</b> Fast=${signal_info['ema_fast']:.4f}, Slow=${signal_info['ema_slow']:.4f}

🛡️ <b>Stop Loss:</b> ${sl_price:.4f} ({sl_pct*100:.1f}%)
🎯 <b>Take Profit:</b> ${tp_price:.4f} ({tp_pct*100:.1f}%)
⏰ <b>Zaman:</b> {format_utc_timestamp()}

{'📈 LONG pozisyon açıldı!' if side == 'long' else '📉 SHORT pozisyon açıldı!'}

<i>PnL kaldıraç ve komisyonları içermez; bilgilendirme amaçlıdır.</i>
        """
        
        safe_telegram_send(self.bot_token, self.chat_id, message)
        self.log.info("📱 Position open notification sent")
    
    def _is_in_cooldown(self) -> bool:
        """Check if in cooldown period"""
        if self.cooldown_until is None:
            return False
        
        now = now_utc()
        if now < self.cooldown_until:
            remaining = (self.cooldown_until - now).total_seconds()
            self.log.info(f"⏰ Cooldown active - {remaining:.0f} seconds remaining")
            return True
        
        return False
                
    def _set_cooldown(self):
        """Set cooldown period"""
        self.cooldown_until = now_utc() + timedelta(seconds=self.cooldown_after_exit)
        self.state_manager.set('cooldown_until', self.cooldown_until.isoformat())
    
    def check_position_status(self) -> Dict[str, Any]:
        """Check current position status"""
        try:
            positions = safe_fetch_positions(self.exchange, [self.futures_symbol])
            active_positions = [p for p in positions if p['contracts'] > 0]
            
            if not active_positions:
                return {'exists': False}
            
            position = active_positions[0]
            return {
                'exists': True,
                'side': position['side'],
                'size': position['contracts'],
                'entry_price': position['entryPrice'],
                'mark_price': position['markPrice'],
                'unrealized_pnl': position['unrealizedPnl']
            }
        except Exception as e:
            self.log.error(f"❌ Position status check failed: {e}")
            return {'exists': False}
    
    def monitor_position(self):
        """Monitor active position"""
        try:
            if not self.active_position:
                return
            
            # Check if position still exists
            position_info = self.check_position_status()
            if not position_info['exists']:
                self.log.info("ℹ️ Position automatically closed")
                self._send_position_close_notification()
                self._cancel_sl_tp_orders()
                self.active_position = None
                self.state_manager.clear_position()
                self._set_cooldown()
                return
            
            # Get current price
            ticker = safe_fetch_ticker(self.exchange, self.futures_symbol)
            current_price = ticker['last']
            
            # Calculate PnL
            entry_price = self.active_position['entry_price']
            side = self.active_position['side']
            pnl_pct = calculate_pnl_percentage(entry_price, current_price, side)
            
            # Check break-even
            if (self.break_even_enabled and 
                not self.active_position.get('break_even_applied', False) and
                pnl_pct >= self.break_even_pct * 100):
                self._apply_break_even()
            
            # Log position status
            self.log.info(f"📊 Position monitoring - PnL: {format_pnl_message(pnl_pct)}")
            
        except Exception as e:
            self.log.error(f"❌ Position monitoring failed: {e}")
    
    def _apply_break_even(self):
        """Apply break-even by updating SL to entry price"""
        try:
            if self.dry_run:
                self.log.info("[DRY-RUN] Would apply break-even")
                return
            
            # Cancel current SL order
            sl_order_id = self.active_position.get('sl_order_id')
            if sl_order_id:
                try:
                    self.exchange.cancel_order(sl_order_id, self.futures_symbol)
                    self.log.info(f"✅ SL order cancelled for break-even: {sl_order_id}")
                except Exception as e:
                    self.log.warning(f"⚠️ SL order cancellation failed: {e}")
            
            # Create new SL order at entry price
            entry_price = self.active_position['entry_price']
            side = self.active_position['side']
            
            # Add small buffer to entry price
            if side == 'long':
                new_sl_price = quantize_price(self.exchange, self.futures_symbol, entry_price * 0.9999)
            else:
                new_sl_price = quantize_price(self.exchange, self.futures_symbol, entry_price * 1.0001)
            
            # Create new SL order
            new_sl_order = self.order_client.create_stop_loss_order(
                symbol=self.futures_symbol,
                side='sell' if side == 'long' else 'buy',
                price=new_sl_price,
                extra=f"be_{int(time.time())}"
            )
            
            if new_sl_order:
                # Update position
                self.active_position['sl_order_id'] = new_sl_order.get('id')
                self.active_position['break_even_applied'] = True
                self.state_manager.update_position(self.active_position)
                
                self.log.info(f"✅ Break-even applied - SL moved to ${new_sl_price:.4f}")
                
        except Exception as e:
            self.log.error(f"❌ Break-even application failed: {e}")
    
    def _cancel_sl_tp_orders(self):
        """Cancel SL/TP orders"""
        try:
            cancelled_count = 0
            
            # Get order IDs from active position
            sl_order_id = self.active_position.get('sl_order_id') if self.active_position else None
            tp_order_id = self.active_position.get('tp_order_id') if self.active_position else None
            
            # If no order IDs, try to find from open orders
            if not sl_order_id and not tp_order_id:
                try:
                    open_orders = safe_fetch_open_orders(self.exchange, self.futures_symbol)
                    for order in open_orders:
                        if order['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
                            if order['type'] == 'STOP_MARKET':
                                sl_order_id = order['id']
                            elif order['type'] == 'TAKE_PROFIT_MARKET':
                                tp_order_id = order['id']
                except Exception as e:
                    self.log.warning(f"⚠️ Failed to fetch open orders: {e}")
            
            # Cancel SL order
            if sl_order_id:
                try:
                    self.exchange.cancel_order(sl_order_id, self.futures_symbol)
                    self.log.info(f"✅ SL order cancelled: {sl_order_id}")
                    cancelled_count += 1
                except Exception as e:
                    self.log.warning(f"⚠️ SL order cancellation failed: {e}")
            
            # Cancel TP order
            if tp_order_id:
                try:
                    self.exchange.cancel_order(tp_order_id, self.futures_symbol)
                    self.log.info(f"✅ TP order cancelled: {tp_order_id}")
                    cancelled_count += 1
                except Exception as e:
                    self.log.warning(f"⚠️ TP order cancellation failed: {e}")
            
            if cancelled_count > 0:
                self.log.info(f"🔄 Total {cancelled_count} SL/TP orders cancelled")
            else:
                self.log.info("ℹ️ No SL/TP orders to cancel")
                
        except Exception as e:
            self.log.error(f"❌ SL/TP order cancellation failed: {e}")
    
    def _send_position_close_notification(self):
        """Send position close notification"""
        if not self.active_position or not self.telegram_enabled:
            return
        
        try:
            # Get position details
            entry_price = self.active_position['entry_price']
            side = self.active_position['side']
            timeframe = self.active_position['timeframe']
            signal_type = self.active_position.get('signal_type', 'unknown')
            
            # Get current price
            ticker = safe_fetch_ticker(self.exchange, self.futures_symbol)
            current_price = ticker['last']
            
            # Calculate PnL
            pnl_pct = calculate_pnl_percentage(entry_price, current_price, side)
            
            # PnL emoji
            pnl_emoji = "📈" if pnl_pct > 0 else "📉" if pnl_pct < 0 else "➡️"
            
            message = f"""
🔚 <b>PENGU POZİSYON KAPANDI</b>

📊 <b>Timeframe:</b> {timeframe}
📈 <b>Yön:</b> {side.upper()}
🎯 <b>Sinyal:</b> {signal_type}

💰 <b>Entry Fiyatı:</b> ${entry_price:.4f}
💵 <b>Kapanış Fiyatı:</b> ${current_price:.4f}

{pnl_emoji} <b>PnL:</b> {pnl_pct:+.2f}%
⏰ <b>Zaman:</b> {format_utc_timestamp()}

{'🎉 Pozisyon karlı kapatıldı!' if pnl_pct > 0 else '😔 Pozisyon zararla kapatıldı!' if pnl_pct < 0 else '➡️ Pozisyon başabaş kapatıldı!'}
            """
            
            safe_telegram_send(self.bot_token, self.chat_id, message)
            self.log.info("📱 Position close notification sent")
                
        except Exception as e:
            self.log.error(f"❌ Position close notification failed: {e}")
    
    def run(self):
        """Main trading loop"""
        self.log.info("🚀 Multi-Timeframe EMA Crossover trading started")
        
        # Setup trading parameters
        self.setup_trading_parameters()
        
        while True:
            try:
                self.log.info(f"🔄 CYCLE_START: {format_utc_timestamp()}")
                
                # Cleanup old orders
                self.order_client.cleanup_old_orders(1)  # 1 hour
                # Sync with exchange to remove stale orders
                self.order_client.sync_with_exchange(self.futures_symbol)
                
                # Monitor active position
                if self.active_position:
                    self.log.info("📊 Monitoring active position...")
                    self.monitor_position()
                    time.sleep(60)
                    continue
                
                # Check cooldown
                if self._is_in_cooldown():
                    time.sleep(60)
                    continue
                
                # Check for signals on trigger timeframe
                signal_info = self.detect_signal(self.trigger_tf)
                
                if signal_info:
                    self.log.info(f"🎯 Signal detected: {signal_info['signal_type']}")
                    
                    # Open position
                    if self.open_position(signal_info):
                        self.log.info("✅ Position opened successfully")
                    else:
                        self.log.info("❌ Position opening failed")
                else:
                    self.log.info("📊 No signal found - waiting for EMA crossover")
                
                # Wait before next cycle
                time.sleep(60)
                
            except KeyboardInterrupt:
                self.log.info("🛑 Trading stopped by user")
                break
            except Exception as e:
                self.log.error(f"❌ Trading loop error: {e}")
                self.log.error(traceback.format_exc())
                time.sleep(60)


if __name__ == "__main__":
    trader = MultiTimeframeEMATrader()
    trader.run()