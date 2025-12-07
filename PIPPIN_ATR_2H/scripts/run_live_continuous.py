#!/usr/bin/env python3
"""PIPPIN ATR Live Signal Generator - ATR + Super Trend Strategy."""
import time
import ccxt
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime

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
        logging.FileHandler("runs/pippin_atr_live.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def fetch_latest_bars(symbol="PIPPINUSDT", timeframe="2h", limit=200):
    """Fetch latest bars from Binance."""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    return df

def fetch_trend_bars(symbol="PIPPINUSDT", timeframe="6h", limit=200):
    """Fetch bars for trend analysis (longer timeframe)."""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    return df

def main():
    logger.info("🚀 Starting PIPPIN ATR Live Signal Generator (ATR + Super Trend Strategy)")
    
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
    timeframe = atr_config.get("timeframe", "2h")
    
    # Get leverage and trade amount from config
    leverage = llm_cfg.get("leverage", 5)
    trade_amount_usd = llm_cfg.get("trade_amount_usd", 100)
    
    symbol = llm_cfg.get("symbol", "PIPPINUSDT")
    
    # Get trend following exit config
    trend_config = llm_cfg.get("trend_following_exit", {})
    trend_exit_enabled = trend_config.get("enabled", False)
    
    # Get multi-timeframe config
    multi_tf_config = llm_cfg.get("multi_timeframe", {})
    multi_tf_enabled = multi_tf_config.get("enabled", False)
    signal_tf = multi_tf_config.get("signal_timeframe", "2h")
    trend_tf = multi_tf_config.get("trend_timeframe", "6h")
    require_both = multi_tf_config.get("require_both_timeframes", True)
    
    # Get intra-bar signal config
    intra_bar_config = llm_cfg.get("intra_bar_signal", {})
    intra_bar_enabled = intra_bar_config.get("enabled", True)
    confirmation_delay = intra_bar_config.get("confirmation_delay_seconds", 300)
    
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
    last_partial_exit_check = None  # Track last partial exit check time
    # Pending signal state for intra-bar signal confirmation
    pending_signal = {
        'side': None,
        'detected_time': None,
        'signal_info': None,
        'last_price': None
    }
    
    # Calculate timeframe in seconds for precise timing
    timeframe_seconds = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600
    }.get(timeframe, 7200)
    # Check more frequently (every 5-10 seconds) to catch bar close immediately
    check_interval = min(10, max(5, timeframe_seconds // 20))  # Check every 10 seconds or 1/20 of timeframe (minimum 5 seconds)
    
    logger.info(f"⏱️ Bar check interval: {check_interval} seconds (timeframe: {timeframe})")
    
    while True:
        try:
            # Fetch latest data
            df = fetch_latest_bars(symbol=symbol, timeframe=timeframe, limit=200)
            
            # Check trend following exit for partial exit (check every 5 minutes)
            # This allows partial exit to trigger within 5 minutes when profit threshold is reached
            current_time = time.time()
            if trend_exit_enabled:
                # Check if 5 minutes (300 seconds) have passed since last partial exit check
                if last_partial_exit_check is None or (current_time - last_partial_exit_check) >= 300:
                    last_partial_exit_check = current_time
                    trend_exit = get_trend_following_exit()
                    
                    if symbol in trend_exit.positions:
                        # First, verify that position actually exists on exchange
                        from src.live_loop import check_active_position
                        real_position = check_active_position(symbol)
                        pos = trend_exit.positions[symbol]
                        tracked_side = pos['side']
                        
                        # If real position doesn't exist or doesn't match tracked position, clean up state
                        if real_position is None:
                            logger.warning(f"⚠️ Position mismatch: Tracked={tracked_side}, Real=None (position closed)")
                            logger.warning(f"🧹 Cleaning up trend following exit state for {symbol}")
                            trend_exit.close_position(symbol)
                        elif real_position != tracked_side:
                            logger.warning(f"⚠️ Position side mismatch: Tracked={tracked_side}, Real={real_position}")
                            logger.warning(f"🧹 Cleaning up trend following exit state for {symbol}")
                            trend_exit.close_position(symbol)
                        else:
                            # Get current price for partial exit check (use latest price, not bar close)
                            current_bar = df.iloc[-1]
                            current_price = float(current_bar["close"])
                            
                            # Calculate current profit for partial exit check
                            entry_price = pos['entry_price']
                            if tracked_side == "LONG":
                                current_profit_pct = ((current_price - entry_price) / entry_price) * 100
                            else:
                                current_profit_pct = ((entry_price - current_price) / entry_price) * 100
                            
                            # Check if partial exit should trigger (only if not already done)
                            if not pos.get('partial_exit_done', False) and current_profit_pct >= trend_config.get("partial_exit_trigger_pct", 1.0):
                                # Trigger partial exit immediately
                                partial_pct = trend_config.get("partial_exit_pct", 75.0)
                                logger.info(f"💰 Partial exit triggered: {partial_pct}% @ ${current_price:.2f} (Profit: {current_profit_pct:.2f}%)")
                                
                                # Mark as done
                                pos['partial_exit_done'] = True
                                pos['partial_exit_price'] = current_price
                                pos['remaining_position_pct'] = 100.0 - partial_pct
                                trend_exit._save_state()
                                
                                # Place partial close order
                                if tracked_side == "LONG":
                                    close_side = "sell"
                                else:
                                    close_side = "buy"
                                
                                order_client = get_order_client()
                                if order_client:
                                    try:
                                        close_result = order_client.partial_close_position(
                                            symbol=symbol,
                                            side=close_side,
                                            close_pct=partial_pct,
                                            position_side=tracked_side,
                                            extra="TREND_FOLLOWING",
                                            reason="PARTIAL_EXIT"
                                        )
                                        logger.info(f"✅ Partial close order placed: {close_result.get('id')}")
                                    except Exception as e:
                                        logger.error(f"❌ Failed to place partial close order: {e}")
                                else:
                                    logger.warning("⚠️ Order client not available - cannot place partial close order")
            
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
                            # Skip partial exit here - it's handled in the main loop every iteration
                            # Only handle other exit types (trend reversal, volume exit, trailing stop)
                            if exit_reason == "PARTIAL_EXIT":
                                # Partial exit is already handled in main loop, skip here
                                pass
                            else:
                                logger.info(f"🛑 Trend Following Exit: {exit_reason} @ ${exit_price:.2f}, Action: {action}")
                                
                                # Get position info
                                pos = trend_exit.positions[symbol]
                                pos_side = pos['side']
                                
                                # Full exit - close entire position (trend reversal, volume exit, trailing stop)
                                logger.info(f"🔚 Full exit: Closing position ({exit_reason})")
                                
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
                
                # Initialize side variable
                side = None
                signal_info = {}
                last_price = None
                
                # INTRABAR SIGNAL LOGIC: Check for signals during bar formation
                if intra_bar_enabled:
                    # Check if we have a pending signal waiting for confirmation
                    if pending_signal['side']:
                        elapsed = (datetime.now() - pending_signal['detected_time']).total_seconds()
                        
                        if elapsed >= confirmation_delay:
                            # Confirmation delay elapsed - re-check signal
                            logger.info(f"⏰ Confirmation delay elapsed ({elapsed:.0f}s), re-checking signal...")
                            
                            if len(df) >= max(atr_period, 2):
                                # Re-check signal with current bar data
                                side, signal_info = get_atr_supertrend_signals(
                                    df=df,
                                    atr_period=atr_period,
                                    key_value=key_value,
                                    super_trend_factor=super_trend_factor,
                                    use_heikin_ashi=use_heikin_ashi
                                )
                                
                                # Get current price
                                if use_heikin_ashi:
                                    ha_df = calculate_heikin_ashi(df)
                                    current_price = float(ha_df['ha_close'].iloc[-1])
                                else:
                                    current_price = float(df["close"].iloc[-1])
                                
                                # After confirmation delay: Only check signal timeframe (2h), NOT trend timeframe (6h)
                                # Multi-timeframe check is only done at initial signal detection
                                # Here we just verify the signal is still valid on the signal timeframe
                                logger.info(f"✅ Confirmation check: Only verifying signal on {signal_tf} timeframe (trend timeframe {trend_tf} check skipped)")
                                
                                if side == pending_signal['side']:
                                    # Signal still valid - proceed with order
                                    logger.info(f"✅ Signal confirmed after {confirmation_delay}s: {side}")
                                    last_price = current_price
                                    
                                    # Clear pending signal
                                    confirmed_side = pending_signal['side']
                                    confirmed_signal_info = pending_signal['signal_info']
                                    pending_signal = {'side': None, 'detected_time': None, 'signal_info': None, 'last_price': None}
                                    
                                    # Proceed with order placement
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
                                use_heikin_ashi=use_heikin_ashi
                            )
                            
                            # Get current price
                            if use_heikin_ashi:
                                ha_df = calculate_heikin_ashi(df)
                                current_price = float(ha_df['ha_close'].iloc[-1])
                            else:
                                current_price = float(df["close"].iloc[-1])
                            
                            # No multi-timeframe check - only 2h timeframe is used
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
                    if len(df) >= max(atr_period, 2):
                        side, signal_info = get_atr_supertrend_signals(
                            df=df,
                            atr_period=atr_period,
                            key_value=key_value,
                            super_trend_factor=super_trend_factor,
                            use_heikin_ashi=use_heikin_ashi
                        )
                        
                        # Use previous bar's close price (the bar that just closed)
                        if len(df) >= 2:
                            if use_heikin_ashi:
                                ha_df = calculate_heikin_ashi(df)
                                last_price = float(ha_df['ha_close'].iloc[-2])
                            else:
                                last_price = float(df["close"].iloc[-2])
                        else:
                            if use_heikin_ashi:
                                ha_df = calculate_heikin_ashi(df)
                                last_price = float(ha_df['ha_close'].iloc[-1])
                            else:
                                last_price = float(df["close"].iloc[-1])
                        
                        # No multi-timeframe check - only 2h timeframe is used
            
            # Process signal if we have one (either from intra-bar confirmation or bar-close logic)
            if side:
                # Log ATR + Super Trend signal
                logger.info(f"   ATR Trailing Stop: ${signal_info.get('atr_trailing_stop', 0):.4f}")
                logger.info(f"   Current Price: ${last_price:.4f}")
                logger.info(f"   Super Trend: ${signal_info.get('super_trend', 0):.4f}")
                logger.info(f"   Position: {signal_info.get('position', 0)}")
                logger.info(f"   Buy Signal: {signal_info.get('buy_signal', False)}")
                logger.info(f"   Sell Signal: {signal_info.get('sell_signal', False)}")
                logger.info(f"   Buy Super Trend: {signal_info.get('buy_super_trend', False)}")
                logger.info(f"   Sell Super Trend: {signal_info.get('sell_super_trend', False)}")
                
                # MINIMUM BAR KONTROLÜ - Hızlı ardışık sinyalleri engelle
                min_bars_after_entry = 1  # 2h timeframe için 1 bar ≈ 2 saat
                try:
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
                            timeframe_seconds_map = {
                                "1m": 60,
                                "3m": 180,
                                "5m": 300,
                                "15m": 900,
                                "30m": 1800,
                                "1h": 3600,
                                "2h": 7200,
                                "4h": 14400,
                                "6h": 21600
                            }
                            bar_duration = timeframe_seconds_map.get(timeframe, 7200)
                            bars_passed = int((current_dt - entry_dt).total_seconds() / bar_duration)
                            
                            if bars_passed < min_bars_after_entry:
                                logger.warning(f"🚫 MINIMUM BAR FİLTER: {side} pozisyonu {bars_passed} bar önce açıldı (< {min_bars_after_entry} bar) - Çok hızlı yeni sinyal, reddedildi")
                                logger.warning(f"   Entry: {entry_dt.strftime('%Y-%m-%d %H:%M:%S')}, Şimdi: {current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                                side = None  # Reject signal instead of continue
                except Exception as e:
                    logger.debug(f"Minimum bar check error: {e}")
                
                if side:  # Only proceed if signal still valid after minimum bar check
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
                if not intra_bar_enabled or not pending_signal['side']:
                    logger.info(f"⚪ No signal (ATR + Super Trend)")
            
            # Wait for next check (use check_interval for intra-bar signals, or full timeframe for bar-close only)
            if intra_bar_enabled:
                time.sleep(check_interval)
            else:
                time.sleep(timeframe_seconds)
            
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
