#!/usr/bin/env python3
"""ENA ATR Live Signal Generator - ATR + Super Trend Strategy."""
import time
import ccxt
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.atr_supertrend import get_atr_supertrend_signals, calculate_heikin_ashi
from src.live_loop import init_order_client, init_telegram, send_order, send_telegram_alert, get_order_client

def tp_sl_from_pct(last_price: float, tp_pct: float, sl_pct: float, side: str) -> tuple:
    """Calculate TP/SL from percentages."""
    if side == "LONG":
        tp = last_price * (1 + tp_pct)
        sl = last_price * (1 - sl_pct)
    elif side == "SHORT":
        tp = last_price * (1 - tp_pct)
        sl = last_price * (1 + sl_pct)
    else:  # FLAT
        tp = last_price
        sl = last_price
    return tp, sl
from src.trend_following_exit import init_trend_following_exit, get_trend_following_exit
import logging
from pathlib import Path

# Configure logging with file handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("runs/ena_atr_live.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def fetch_latest_bars(symbol="ENAUSDT", timeframe="15m", limit=200):
    """Fetch latest bars from Binance."""
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'timeout': 30000,  # 30 seconds timeout
        'enableRateLimit': True,
        'rateLimit': 1200,
    })
    # Retry logic for timeout errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('time', inplace=True)
            return df
        except (ccxt.RequestTimeout, ccxt.ExchangeNotAvailable, ccxt.NetworkError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Fetch attempt {attempt + 1} failed, retrying... Error: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"❌ Failed to fetch bars after {max_retries} attempts: {e}")
                raise

def fetch_trend_bars(symbol="ENAUSDT", timeframe="1h", limit=200):
    """Fetch bars for trend analysis (longer timeframe)."""
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'timeout': 30000,  # 30 seconds timeout
        'enableRateLimit': True,
        'rateLimit': 1200,
    })
    # Retry logic for timeout errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('time', inplace=True)
            return df
        except (ccxt.RequestTimeout, ccxt.ExchangeNotAvailable, ccxt.NetworkError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Fetch attempt {attempt + 1} failed, retrying... Error: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"❌ Failed to fetch bars after {max_retries} attempts: {e}")
                raise

def main():
    logger.info("🚀 Starting ENA ATR Live Signal Generator (ATR + Super Trend Strategy)")
    
    # Load config
    with open("configs/llm_config.json", "r") as f:
        llm_cfg = json.load(f)
    
    # Initialize API & Telegram
    init_order_client(
        api_key=llm_cfg["api_key"],
        api_secret=llm_cfg["secret"],
        sandbox=False
    )
    
    if llm_cfg["telegram"]["enabled"]:
        init_telegram(
            bot_token=llm_cfg["telegram"]["bot_token"],
            chat_id=llm_cfg["telegram"]["chat_id"]
        )
    
    # Initialize shadow mode from config
    from src.shadow_mode import ShadowMode
    shadow_config = llm_cfg.get("shadow_mode", {})
    shadow_mode = ShadowMode(
        enabled=shadow_config.get("enabled", True),
        duration_days=shadow_config.get("duration_days", 7),
        state_file=shadow_config.get("state_file", "runs/shadow_mode_state.json")
    )
    # Set global instance
    import src.shadow_mode as shadow_module
    shadow_module._shadow_mode = shadow_mode
    
    # Initialize trend following exit
    init_trend_following_exit(llm_cfg)
    
    # Trading params from config
    trading_params = llm_cfg.get("trading_params", {})
    tp_pct = trading_params.get("tp_pct", 0.005)
    sl_pct = trading_params.get("sl_pct", 0.012)
    
    # ATR + Super Trend params from config
    atr_config = llm_cfg.get("atr_supertrend", {})
    atr_period = atr_config.get("atr_period", 10)
    key_value = atr_config.get("key_value", 3.0)
    super_trend_factor = atr_config.get("super_trend_factor", 1.5)
    use_heikin_ashi = atr_config.get("use_heikin_ashi", False)
    timeframe = atr_config.get("timeframe", "15m")
    
    # Get leverage and trade amount from config
    leverage = llm_cfg.get("leverage", 5)
    trade_amount_usd = llm_cfg.get("trade_amount_usd", 100)
    
    symbol = llm_cfg.get("symbol", "ENAUSDT")
    
    # Get trend following exit config
    trend_config = llm_cfg.get("trend_following_exit", {})
    trend_exit_enabled = trend_config.get("enabled", False)
    
    # Get multi-timeframe config
    multi_tf_config = llm_cfg.get("multi_timeframe", {})
    multi_tf_enabled = multi_tf_config.get("enabled", False)
    signal_tf = multi_tf_config.get("signal_timeframe", "15m")
    trend_tf = multi_tf_config.get("trend_timeframe", "1h")
    require_both = multi_tf_config.get("require_both_timeframes", True)
    
    # Get intra-bar signal config
    intra_bar_config = llm_cfg.get("intra_bar_signal", {})
    intra_bar_enabled = intra_bar_config.get("enabled", True)
    confirmation_delay = intra_bar_config.get("confirmation_delay_seconds", 60)
    
    logger.info("✅ All systems ready. Starting live loop...")
    logger.info(f"📊 Monitoring: {symbol} {timeframe}")
    logger.info(f"🎯 TP: {tp_pct*100}%, SL: {sl_pct*100}%")
    logger.info(f"📈 ATR Period: {atr_period}, Key Value: {key_value}")
    logger.info(f"📊 Super Trend Factor: {super_trend_factor}")
    logger.info(f"🕯️  Use Heikin Ashi: {use_heikin_ashi}")
    logger.info(f"💰 Trade Amount: ${trade_amount_usd}, Leverage: {leverage}x")
    logger.info(f"🎯 Trend Following Exit: {'ENABLED' if trend_exit_enabled else 'DISABLED'}")
    logger.info(f"📊 Multi-Timeframe: {'ENABLED' if multi_tf_enabled else 'DISABLED'}")
    if multi_tf_enabled:
        logger.info(f"   Signal TF: {signal_tf}, Trend TF: {trend_tf}, Require Both: {require_both}")
    logger.info(f"🔄 Intra-Bar Signal: {'ENABLED' if intra_bar_enabled else 'DISABLED'}")
    if intra_bar_enabled:
        logger.info(f"   Confirmation Delay: {confirmation_delay} seconds")
    if shadow_mode.is_active():
        logger.info(f"👻 Shadow mode ACTIVE (will not place real orders for {shadow_config.get('duration_days', 7)} days)")
    else:
        logger.info(f"✅ Shadow mode INACTIVE (real orders will be placed)")
    
    last_bar_time = None
    # Pending signal state for intra-bar signal confirmation
    pending_signal = {
        'side': None,
        'detected_time': None,
        'signal_info': None,
        'last_price': None
    }
    
    # Calculate timeframe in seconds for precise timing
    timeframe_seconds = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600}.get(timeframe, 900)
    # Check more frequently (every 5-10 seconds) to catch bar close immediately
    check_interval = min(5, max(1, timeframe_seconds // 20))  # Check every 5 seconds or 1/20 of timeframe (minimum 1 second)
    
    logger.info(f"⏱️ Bar check interval: {check_interval} seconds (timeframe: {timeframe})")
    
    while True:
        try:
            # Fetch latest data
            df = fetch_latest_bars(symbol=symbol, timeframe=timeframe, limit=200)
            
            # Check if new bar
            current_bar_time = df.index[-1]
            
            # Check if new bar started - clear pending signal if bar changed
            if last_bar_time is not None and current_bar_time != last_bar_time:
                if pending_signal['side']:
                    logger.info(f"🔄 New bar started: {current_bar_time}, clearing pending signal: {pending_signal['side']}")
                    pending_signal = {'side': None, 'detected_time': None, 'signal_info': None, 'last_price': None}
                logger.info(f"\n🔄 BAR CLOSED: {last_bar_time} -> New bar started: {current_bar_time}")
                last_bar_time = current_bar_time
            elif last_bar_time is None:
                logger.info(f"\n🔄 Initial bar: {current_bar_time}")
                last_bar_time = current_bar_time
            
            # Check trend following exit for existing positions (ALWAYS check, not just on bar close)
            if trend_exit_enabled:
                if last_bar_time is not None:
                    # Previous bar just closed - this is the moment signal should be generated
                    logger.info(f"\n🔄 BAR CLOSED: {last_bar_time} -> New bar started: {current_bar_time}")
                    logger.info(f"⏰ Signal check triggered at bar close (immediate processing)")
                else:
                    logger.info(f"\n🔄 Initial bar: {current_bar_time}")
                
                # Check trend following exit for existing positions (BEFORE checking new signals)
                if trend_exit_enabled:
                    trend_exit = get_trend_following_exit()
                    
                    if symbol in trend_exit.positions:
                        # First, verify that position actually exists on exchange
                        from src.live_loop import check_active_position
                        real_position = check_active_position(symbol)
                        pos = trend_exit.positions[symbol]
                        tracked_side = pos['side']
                        
                        logger.info(f"🔍 Position check: Tracked={tracked_side}, Real={real_position}")
                        
                        # If real position doesn't exist or doesn't match tracked position, clean up state
                        if real_position is None:
                            logger.warning(f"⚠️ Position mismatch: Tracked={tracked_side}, Real=None (position closed)")
                            logger.warning(f"🧹 Cleaning up trend following exit state for {symbol}")
                            trend_exit.close_position(symbol)
                            continue  # Skip exit checks if position doesn't exist
                        elif real_position != tracked_side:
                            logger.warning(f"⚠️ Position side mismatch: Tracked={tracked_side}, Real={real_position}")
                            logger.warning(f"🧹 Cleaning up trend following exit state for {symbol}")
                            trend_exit.close_position(symbol)
                            continue
                        
                        # Get current bar data for exit checks
                        current_bar = df.iloc[-1]
                        current_price = float(current_bar["close"])
                        high = float(current_bar["high"])
                        low = float(current_bar["low"])
                        
                        # Calculate EMA12 and EMA26
                        df["ema12"] = df["close"].ewm(span=12, adjust=False).mean()
                        df["ema26"] = df["close"].ewm(span=26, adjust=False).mean()
                        
                        ema_fast = float(df["ema12"].iloc[-1])
                        ema_slow = float(df["ema26"].iloc[-1])
                        
                        # Volume ratio calculation (simple)
                        if len(df) > 20:
                            vol_mean = df["volume"].rolling(20).mean().iloc[-1]
                            current_vol = df["volume"].iloc[-1]
                            volume_ratio = current_vol / vol_mean if vol_mean > 0 else 1.0
                        else:
                            volume_ratio = 1.0
                        
                        # Heikin Ashi calculation for volume exit
                        # HA close = (O + H + L + C) / 4
                        ha_close = (current_bar["open"] + current_bar["high"] + current_bar["low"] + current_bar["close"]) / 4
                        # HA open = (previous HA open + previous HA close) / 2
                        if len(df) > 1:
                            prev_ha_close = (df["open"].iloc[-2] + df["high"].iloc[-2] + 
                                           df["low"].iloc[-2] + df["close"].iloc[-2]) / 4
                            prev_ha_open = (df["open"].iloc[-2] + df["close"].iloc[-2]) / 2 if len(df) == 2 else (
                                (df["open"].iloc[-3] + df["close"].iloc[-3]) / 2 if len(df) > 2 else current_bar["open"]
                            )
                            ha_open = (prev_ha_open + prev_ha_close) / 2
                        else:
                            ha_open = current_bar["open"]
                        
                        ha_up = ha_close > ha_open
                        ha_down = ha_close < ha_open
                        
                        # Check exit signals
                        exit_reason, exit_price, action = trend_exit.check_exit_signals(
                            symbol=symbol,
                            current_price=current_price,
                            high=high,
                            low=low,
                            ema_fast=ema_fast,
                            ema_slow=ema_slow,
                            volume_ratio=volume_ratio,
                            ha_up=ha_up,
                            ha_down=ha_down
                        )
                        
                        # Update trailing stop on exchange if activated
                        pos = trend_exit.positions[symbol]
                        if pos.get('trailing_activated') and pos.get('trailing_stop_price'):
                            trailing_stop_price = pos['trailing_stop_price']
                            
                            # Check if trailing stop price has changed (need to update SL order)
                            last_trailing_price = pos.get('last_exchange_sl_price')
                            if last_trailing_price != trailing_stop_price:
                                # Update SL order on exchange
                                order_client = get_order_client()
                                if order_client:
                                    try:
                                        close_order_side = "sell" if pos['side'] == "LONG" else "buy"
                                        sl_result = order_client.update_sl_order(
                                            symbol=symbol,
                                            new_sl_price=trailing_stop_price,
                                            side=close_order_side,
                                            position_side=pos['side'],
                                            extra="TREND_FOLLOWING",
                                            reason="TRAILING_STOP_UPDATE"
                                        )
                                        # Store the updated SL price
                                        pos['last_exchange_sl_price'] = trailing_stop_price
                                        trend_exit._save_state()
                                        logger.info(f"📈 Trailing stop updated on exchange: ${trailing_stop_price:.2f}")
                                    except Exception as e:
                                        logger.error(f"❌ Failed to update trailing stop on exchange: {e}")
                        
                        if exit_reason:
                            logger.info(f"🛑 Trend Following Exit: {exit_reason} @ ${exit_price:.2f}, Action: {action}")
                            
                            # Get position info
                            pos = trend_exit.positions[symbol]
                            pos_side = pos['side']
                            
                            # Close position (partial or full)
                            if action == "CLOSE_PARTIAL":
                                # Partial exit - close specified percentage
                                partial_pct = trend_config.get("partial_exit_pct", 75.0)
                                logger.info(f"💰 Partial exit: Closing {partial_pct}% of position")
                                
                                # Determine order side (opposite of position side)
                                if pos_side == "LONG":
                                    close_side = "sell"
                                else:
                                    close_side = "buy"
                                
                                # Place partial close order
                                order_client = get_order_client()
                                if order_client:
                                    try:
                                        close_result = order_client.partial_close_position(
                                            symbol=symbol,
                                            side=close_side,
                                            close_pct=partial_pct,
                                            position_side=pos_side,
                                            extra="TREND_FOLLOWING",
                                            reason=exit_reason
                                        )
                                        logger.info(f"✅ Partial close order placed: {close_result.get('id')}")
                                    except Exception as e:
                                        logger.error(f"❌ Failed to place partial close order: {e}")
                                else:
                                    logger.warning("⚠️ Order client not available - cannot place partial close order")
                            else:
                                # Full exit - close entire position
                                logger.info(f"🔚 Full exit: Closing position")
                                
                                # Determine order side (opposite of position side)
                                if pos_side == "LONG":
                                    close_side = "sell"
                                else:
                                    close_side = "buy"
                                
                                # Place full close order
                                order_client = get_order_client()
                                if order_client:
                                    try:
                                        close_result = order_client.close_position_market(
                                            symbol=symbol,
                                            side=close_side,
                                            position_side=pos_side,
                                            extra="TREND_FOLLOWING",
                                            reason=exit_reason
                                        )
                                        logger.info(f"✅ Full close order placed: {close_result.get('id')}")
                                        
                                        # Remove from tracking after successful order
                                        trend_exit.close_position(symbol)
                                    except Exception as e:
                                        logger.error(f"❌ Failed to place full close order: {e}")
                                else:
                                    logger.warning("⚠️ Order client not available - cannot place close order")
                                    # Remove from tracking anyway
                                    trend_exit.close_position(symbol)
            
            # INTRABAR SIGNAL LOGIC: Check for signals during bar formation
            if intra_bar_enabled:
                # Check if we have a pending signal waiting for confirmation
                if pending_signal['side']:
                    elapsed = (datetime.now() - pending_signal['detected_time']).total_seconds()
                    
                    if elapsed >= confirmation_delay:
                        # 1 minute passed - re-check signal
                        logger.info(f"⏰ Confirmation delay elapsed ({elapsed:.0f}s), re-checking signal...")
                        
                        if len(df) >= max(atr_period, 2):
                            # Re-check signal with current bar data
                            side, signal_info = get_atr_supertrend_signals(
                                df=df,
                                atr_period=atr_period,
                                key_value=key_value,
                                super_trend_factor=super_trend_factor,
                                use_heikin_ashi=use_heikin_ashi,
                                use_previous_bar=False  # Check current bar
                            )
                            
                            # Get current price
                            if use_heikin_ashi:
                                ha_df = calculate_heikin_ashi(df)
                                current_price = float(ha_df['ha_close'].iloc[-1])
                            else:
                                current_price = float(df["close"].iloc[-1])
                            
                            # Multi-timeframe check (if enabled)
                            if side and multi_tf_enabled:
                                try:
                                    trend_df = fetch_trend_bars(symbol=symbol, timeframe=trend_tf, limit=200)
                                    trend_side, trend_signal_info = get_atr_supertrend_signals(
                                        df=trend_df,
                                        atr_period=atr_period,
                                        key_value=key_value,
                                        super_trend_factor=super_trend_factor,
                                        use_heikin_ashi=use_heikin_ashi
                                    )
                                    
                                    if require_both:
                                        if trend_side != side:
                                            logger.warning(f"🚫 MULTI-TIMEFRAME FILTER: Signal rejected after confirmation")
                                            side = None
                                except Exception as e:
                                    logger.error(f"❌ Multi-timeframe check failed: {e}")
                                    if require_both:
                                        side = None
                            
                            if side == pending_signal['side']:
                                # Signal still valid - proceed with order
                                logger.info(f"✅ Signal confirmed after {confirmation_delay}s: {side}")
                                last_price = current_price
                                
                                # Clear pending signal
                                confirmed_side = pending_signal['side']
                                confirmed_signal_info = pending_signal['signal_info']
                                pending_signal = {'side': None, 'detected_time': None, 'signal_info': None, 'last_price': None}
                                
                                # Proceed with order placement (use existing logic below)
                                # This will be handled by the signal processing code below
                                side = confirmed_side
                                signal_info = confirmed_signal_info
                            else:
                                # Signal no longer valid
                                logger.info(f"❌ Signal invalidated after {confirmation_delay}s: {pending_signal['side']} -> {side if side else 'FLAT'}")
                                pending_signal = {'side': None, 'detected_time': None, 'signal_info': None, 'last_price': None}
                                side = None
                    else:
                        # Still waiting for confirmation
                        remaining = confirmation_delay - elapsed
                        logger.debug(f"⏳ Waiting for signal confirmation: {remaining:.0f}s remaining ({pending_signal['side']})")
                        side = None  # Don't process signal yet
                else:
                    # No pending signal - check for new signals during bar formation
                    if len(df) >= max(atr_period, 2):
                        side, signal_info = get_atr_supertrend_signals(
                            df=df,
                            atr_period=atr_period,
                            key_value=key_value,
                            super_trend_factor=super_trend_factor,
                            use_heikin_ashi=use_heikin_ashi,
                            use_previous_bar=False  # Check current bar (intra-bar)
                        )
                        
                        # Get current price
                        if use_heikin_ashi:
                            ha_df = calculate_heikin_ashi(df)
                            current_price = float(ha_df['ha_close'].iloc[-1])
                        else:
                            current_price = float(df["close"].iloc[-1])
                        
                        # Multi-timeframe check (if enabled)
                        if side and multi_tf_enabled:
                            try:
                                trend_df = fetch_trend_bars(symbol=symbol, timeframe=trend_tf, limit=200)
                                trend_side, trend_signal_info = get_atr_supertrend_signals(
                                    df=trend_df,
                                    atr_period=atr_period,
                                    key_value=key_value,
                                    super_trend_factor=super_trend_factor,
                                    use_heikin_ashi=use_heikin_ashi
                                )
                                
                                if require_both:
                                    if trend_side != side:
                                        logger.warning(f"🚫 MULTI-TIMEFRAME FILTER: Signal rejected")
                                        side = None
                            except Exception as e:
                                logger.error(f"❌ Multi-timeframe check failed: {e}")
                                if require_both:
                                    side = None
                        
                        if side:
                            # New signal detected - store in pending state
                            logger.info(f"🎯 Signal detected during bar: {side} @ ${current_price:.4f}")
                            logger.info(f"⏳ Waiting {confirmation_delay} seconds for confirmation...")
                            pending_signal = {
                                'side': side,
                                'detected_time': datetime.now(),
                                'signal_info': signal_info,
                                'last_price': current_price
                            }
                            side = None  # Don't process yet, wait for confirmation
            else:
                # OLD LOGIC: Bar close only (intra_bar_enabled = False)
                # Get ATR + Super Trend signals
                # Pine Script: onlyOnClose = true -> signal generated at bar close
                # We check the PREVIOUS bar (that just closed) for signals, not the current forming bar
                if len(df) >= max(atr_period, 2):
                    side, signal_info = get_atr_supertrend_signals(
                        df=df,
                        atr_period=atr_period,
                        key_value=key_value,
                        super_trend_factor=super_trend_factor,
                        use_heikin_ashi=use_heikin_ashi,
                        use_previous_bar=True  # Pine Script onlyOnClose = true logic
                    )
                    
                    # IMPORTANT: Signal is generated from previous bar (use_previous_bar=True)
                    # So we must use previous bar's close price for entry, not current bar
                    # This ensures position is opened at the same price as TradingView (bar close price)
                    if len(df) >= 2:
                        if use_heikin_ashi:
                            ha_df = calculate_heikin_ashi(df)
                            # Use previous bar's Heikin Ashi close (the bar that just closed and generated the signal)
                            last_price = float(ha_df['ha_close'].iloc[-2])
                        else:
                            # Use previous bar's close (the bar that just closed and generated the signal)
                            last_price = float(df["close"].iloc[-2])
                    else:
                        # Fallback: if only one bar, use current bar
                        if use_heikin_ashi:
                            ha_df = calculate_heikin_ashi(df)
                            last_price = float(ha_df['ha_close'].iloc[-1])
                        else:
                            last_price = float(df["close"].iloc[-1])
                    
                    # Multi-timeframe check (if enabled)
                    if side and multi_tf_enabled:
                        try:
                            # Fetch trend timeframe data
                            trend_df = fetch_trend_bars(symbol=symbol, timeframe=trend_tf, limit=200)
                            
                            # Get trend signal from higher timeframe
                            trend_side, trend_signal_info = get_atr_supertrend_signals(
                                df=trend_df,
                                atr_period=atr_period,
                                key_value=key_value,
                                super_trend_factor=super_trend_factor,
                                use_heikin_ashi=use_heikin_ashi
                            )
                            
                            logger.info(f"📊 Multi-Timeframe Check:")
                            logger.info(f"   Signal TF ({signal_tf}): {side}")
                            logger.info(f"   Trend TF ({trend_tf}): {trend_side if trend_side else 'FLAT'}")
                            
                            # Check if both timeframes agree
                            if require_both:
                                if trend_side != side:
                                    logger.warning(f"🚫 MULTI-TIMEFRAME FILTER: Signal TF ({signal_tf}) = {side}, but Trend TF ({trend_tf}) = {trend_side if trend_side else 'FLAT'} - Signal REJECTED")
                                    side = None  # Reject signal
                                else:
                                    logger.info(f"✅ Multi-Timeframe: Both timeframes agree ({side})")
                            else:
                                # If not requiring both, just log the trend
                                if trend_side:
                                    logger.info(f"📊 Trend TF ({trend_tf}): {trend_side} (not required, but noted)")
                        except Exception as e:
                            logger.error(f"❌ Multi-timeframe check failed: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                            # If multi-timeframe check fails and require_both is True, reject signal
                            if require_both:
                                logger.warning(f"🚫 MULTI-TIMEFRAME FILTER: Check failed, rejecting signal (require_both=True)")
                                side = None
            
            # Process signal if we have one (either from intra-bar confirmation or bar-close logic)
            if side:
                        # Log ATR + Super Trend signal
                        logger.info(f"📊 ATR + Super Trend Signal: {side}")
                        logger.info(f"   ATR Trailing Stop: ${signal_info.get('atr_trailing_stop', 0):.4f}")
                        logger.info(f"   Current Price: ${last_price:.4f}")
                        logger.info(f"   Super Trend: ${signal_info.get('super_trend', 0):.4f}")
                        logger.info(f"   Position: {signal_info.get('position', 0)}")
                        logger.info(f"   Buy Signal (ATR): {signal_info.get('buy_signal', False)}")
                        logger.info(f"   Sell Signal (ATR): {signal_info.get('sell_signal', False)}")
                        logger.info(f"   Buy Super Trend (Alert): {signal_info.get('buy_super_trend', False)}")
                        logger.info(f"   Sell Super Trend (Alert): {signal_info.get('sell_super_trend', False)}")
                        logger.info(f"   📌 Note: SuperTrend sadece alert için, sinyal üretiminde kullanılmıyor")
                        
                        # MINIMUM BAR KONTROLÜ - Hızlı ardışık sinyalleri engelle
                        min_bars_after_entry = 2  # 15m timeframe için 2 bar ≈ 30 dakika
                        try:
                            from datetime import datetime
                            entry_times_file = Path("runs/entry_times.json")
                            if entry_times_file.exists():
                                with open(entry_times_file, 'r') as f:
                                    entry_times = json.load(f)
                                
                                # Aktif pozisyon var mı kontrol et
                                active_position_side = entry_times.get(side)
                                if active_position_side:
                                    # Entry zamanından bu yana kaç bar geçti?
                                    entry_dt = datetime.fromisoformat(active_position_side)
                                    current_dt = datetime.now()
                                    
                                    # Timeframe'e göre bar süresi hesapla
                                    timeframe_seconds = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "1h": 3600}.get(timeframe, 900)
                                    bars_passed = int((current_dt - entry_dt).total_seconds() / timeframe_seconds)
                                    
                                    if bars_passed < min_bars_after_entry:
                                        logger.warning(f"🚫 MINIMUM BAR FİLTER: {side} pozisyonu {bars_passed} bar önce açıldı (< {min_bars_after_entry} bar) - Çok hızlı yeni sinyal, reddedildi")
                                        logger.warning(f"   Entry: {entry_dt.strftime('%Y-%m-%d %H:%M:%S')}, Şimdi: {current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                                        continue
                        except Exception as e:
                            logger.debug(f"Minimum bar check error: {e}")
                        
                        # TP/SL hesapla (mevcut yapı korunuyor)
                        tp, sl = tp_sl_from_pct(last_price, tp_pct, sl_pct, side)
                        
                        # Log signal
                        logger.info(f"🎯 SIGNAL: {side} @ ${last_price:.4f}")
                        logger.info(f"   TP: ${tp:.4f}, SL: ${sl:.4f}")
                        logger.info(f"   ATR Trailing Stop: ${signal_info.get('atr_trailing_stop', 0):.4f}")
                        logger.info(f"   Super Trend: ${signal_info.get('super_trend', 0):.4f}")
                        
                        # Shadow mode check
                        if shadow_mode.is_active():
                            logger.info("👻 Shadow mode: Signal recorded (order not placed)")
                            
                            # Telegram alert with shadow mode indicator
                            payload = {
                                "symbol": symbol,
                                "side": side,
                                "entry": last_price,
                                "tp": tp,
                                "sl": sl,
                                "confidence": 1.0,  # ATR strategy doesn't use confidence
                                "leverage": leverage,
                                "qty_usd": trade_amount_usd,
                                "shadow_mode": True,
                                "strategy": "ATR + Super Trend",
                                "atr_trailing_stop": signal_info.get('atr_trailing_stop', 0),
                                "super_trend": signal_info.get('super_trend', 0),
                            }
                            send_telegram_alert(payload)
                        else:
                            # Production mode: send real orders (use config values)
                            order_result = send_order(
                                side=side,
                                entry=last_price,
                                tp=tp,
                                sl=sl,
                                leverage=leverage,
                                qty=trade_amount_usd,
                                symbol=symbol,
                                trend_following_exit_enabled=trend_exit_enabled
                            )
                            
                            # Log order result for debugging
                            logger.info(f"📊 Order result: {order_result} (type: {type(order_result).__name__})")
                            
                            # Determine if position was opened
                            # order_result is dict with "status": "success" if position opened successfully
                            # order_result is dict with "status": "skipped" if position was skipped (already exists)
                            # order_result is None if there was an error
                            position_opened = False
                            active_position = None
                            
                            if order_result and isinstance(order_result, dict):
                                if order_result.get("status") == "success":
                                    position_opened = True
                                    
                                    # Entry time kaydet (minimum bar kontrolü için)
                                    try:
                                        from datetime import datetime
                                        entry_time = datetime.now().isoformat()
                                        entry_times_file = Path("runs/entry_times.json")
                                        entry_times_file.parent.mkdir(parents=True, exist_ok=True)
                                        
                                        # Load existing entry times
                                        entry_times = {}
                                        if entry_times_file.exists():
                                            try:
                                                with open(entry_times_file, 'r') as f:
                                                    entry_times = json.load(f)
                                            except:
                                                entry_times = {}
                                        
                                        # Save entry time for this position
                                        entry_times[side] = entry_time
                                        
                                        # Save
                                        with open(entry_times_file, 'w') as f:
                                            json.dump(entry_times, f, indent=2)
                                        
                                        logger.info(f"💾 Entry time saved: {side} @ {entry_time}")
                                    except Exception as e:
                                        logger.debug(f"Entry time save error: {e}")
                                    
                                    # Register position for trend following exit tracking
                                    if trend_exit_enabled:
                                        trend_exit = get_trend_following_exit()
                                        position_id = order_result.get("order_id", "unknown")
                                        trend_exit.register_position(
                                            symbol=symbol,
                                            side=side,
                                            entry_price=last_price,
                                            position_id=position_id
                                        )
                                        logger.info(f"📝 Position registered for trend following exit tracking")
                                elif order_result.get("status") == "skipped":
                                    position_opened = False
                                    active_position = order_result.get("active_position")
                                    logger.info(f"⏸️ Position skipped: {active_position} position already exists")
                            elif order_result is None:
                                logger.warning("⚠️ Order result is None - order may have failed")
                                position_opened = False
                            
                            logger.info(f"📊 Position opened: {position_opened}, Active position: {active_position}")
                            
                            # Telegram alert
                            payload = {
                                "symbol": symbol,
                                "side": side,
                                "entry": last_price,
                                "tp": tp,
                                "sl": sl,
                                "confidence": 1.0,  # ATR strategy doesn't use confidence
                                "leverage": leverage,
                                "qty_usd": trade_amount_usd,
                                "shadow_mode": False,
                                "position_opened": position_opened,
                                "active_position": active_position if active_position and not position_opened else None,
                                "strategy": "ATR + Super Trend",
                                "atr_trailing_stop": signal_info.get('atr_trailing_stop', 0),
                                "super_trend": signal_info.get('super_trend', 0),
                            }
                            send_telegram_alert(payload)
            else:
                # No signal to process
                if not intra_bar_enabled or not pending_signal['side']:
                    logger.debug(f"⚪ No signal (ATR + Super Trend)")
            
            # CRITICAL FIX: Sleep for shorter intervals to catch bar close immediately
            # Instead of sleeping for entire bar duration, check frequently
            # This ensures we detect bar close within 5-10 seconds instead of waiting full bar duration
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("Stopping live loop...")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(60)

if __name__ == "__main__":
    main()
