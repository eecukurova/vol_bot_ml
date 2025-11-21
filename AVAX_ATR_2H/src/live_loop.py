"""Live loop with hooks for order execution and alerts."""

from typing import Dict, Tuple, Optional
import logging
import ccxt
import json

import pandas as pd
import numpy as np

from src.infer import predict_proba, decide_side

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
from src.models.transformer import SeqClassifier
from src.regime import detect_volatility_regime, detect_trend_regime, get_regime_thresholds
from src.slippage import calculate_dynamic_slippage, apply_slippage_to_price, calculate_atr
from src.latency import get_latency_tracker, format_latency_alert
from src.position_management import get_position_manager
from src.shadow_mode import get_shadow_mode, is_shadow_mode_active
from src.leverage import get_adaptive_leverage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global order client (initialized once)
_order_client = None
_exchange = None


def get_order_client():
    """Get the global order client instance."""
    return _order_client


def init_order_client(api_key: str, api_secret: str, sandbox: bool = False):
    """Initialize order client for Volensy LLM."""
    global _order_client, _exchange
    
    # Exchange config
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'sandbox': sandbox,
        'options': {'defaultType': 'future'}
    })
    
    # Config
    config = {
        'idempotency': {
            'enabled': True,
            'state_file': 'runs/llm_state.json',
            'retry_attempts': 3,
            'retry_delay': 1.0
        },
        'sl_tp': {
            'trigger_source': 'MARK_PRICE',
            'hedge_mode': False
        }
    }
    
    try:
        from src.order_client import IdempotentOrderClient
        _order_client = IdempotentOrderClient(exchange, config)
        _exchange = exchange
        logger.info("✅ Order client initialized")
    except Exception as e:
        logger.warning(f"⚠️ Order client not available: {e}")
        _order_client = None


def check_active_position(symbol: str) -> Optional[str]:
    """
    Check if there is an active position for the symbol.
    
    Args:
        symbol: Trading symbol (e.g., "ETHUSDT")
        
    Returns:
        "LONG", "SHORT", or None if no active position
    """
    if _exchange is None:
        return None
    
    try:
        # Fetch all positions and find the one for our symbol
        # Try multiple symbol formats to be sure
        symbol_variants = [symbol, symbol.replace('USDT', '/USDT'), symbol.replace('USDT', '/USDT:USDT')]
        
        positions_found = []
        for sym_variant in symbol_variants:
            try:
                positions = _exchange.fetch_positions([sym_variant])
                if positions:
                    positions_found.extend(positions)
            except:
                continue
        
        # If no positions found with variants, try fetching all
        if not positions_found:
            try:
                all_positions = _exchange.fetch_positions()
                # Filter for symbol positions (extract base symbol from symbol like AVAXUSDT -> AVAX)
                base_symbol = symbol.replace('USDT', '').replace('/', '')
                for pos in all_positions:
                    pos_symbol = pos.get('symbol', '')
                    if base_symbol in pos_symbol and 'USDT' in pos_symbol:
                        positions_found.append(pos)
            except:
                pass
        
        if positions_found:
            for pos in positions_found:
                # Check if position is open (contracts > 0)
                contracts = float(pos.get('contracts', 0))
                
                if abs(contracts) > 0.0001:  # Use small threshold to avoid floating point issues
                    # Get side from position (usually 'long' or 'short')
                    side = str(pos.get('side', '')).lower()
                    
                    logger.debug(f"🔍 Found active position: {pos.get('symbol')} {side} {contracts}")
                    
                    if side == 'long':
                        return "LONG"
                    elif side == 'short':
                        return "SHORT"
                    # Fallback: positive contracts = LONG in one-way mode
                    elif contracts > 0:
                        return "LONG"
                    else:
                        return "SHORT"
        
        return None
    except Exception as e:
        logger.error(f"❌ Could not check active position: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def update_position_management(symbol: str, current_price: float):
    """
    Update position management (break-even, trailing stop).
    This should be called periodically (e.g., on each new bar).
    """
    pos_manager = get_position_manager()
    
    # Check for position updates
    update = pos_manager.update_position_price(symbol, current_price)
    
    if update and update.get('actions'):
        # Need to update SL order on exchange
        for action in update['actions']:
            if action['type'] == 'break_even':
                logger.info(f"✅ Break-even triggered: {symbol}")
            elif action['type'] == 'trail':
                logger.info(f"📈 Trailing stop updated: {symbol}")
        
        # TODO: Update SL order on exchange via order_client
        # For now, just log - in production, you'd cancel old SL and place new one
        new_sl = update['current_sl']
        logger.info(f"⚠️ Need to update SL order to {new_sl:.2f} (manual update required)")


def send_order(
    side: str,
    entry: float,
    tp: float,
    sl: float,
    leverage: int,
    qty: float,
    df_for_slippage: Optional[pd.DataFrame] = None,
    symbol: str = "AVAXUSDT",
    trend_following_exit_enabled: bool = False,
) -> Optional[Dict]:
    """
    Send order to exchange with latency tracking and dynamic slippage.

    Args:
        side: "LONG" or "SHORT"
        entry: Entry price
        tp: Take-profit price
        sl: Stop-loss price
        leverage: Leverage (e.g., 5x)
        qty: Quantity (USD)
        df_for_slippage: DataFrame for slippage calculation (optional)

    Returns:
        Dict with order results or None if failed
    """
    tracker = get_latency_tracker()
    tracker.start_timer("order_execution")
    
    logger.info(f"Order hook: {side} @ {entry}, TP={tp}, SL={sl}")
    
    if _order_client is None:
        logger.warning("Order client not initialized - skipping order")
        tracker.end_timer("order_execution")
        return None
    
    # Convert side
    if side == "LONG":
        order_side = "buy"
        position_side = "LONG"
    elif side == "SHORT":
        order_side = "sell"
        position_side = "SHORT"
    else:
        logger.warning(f"Unknown side: {side}")
        tracker.end_timer("order_execution")
        return None
    
    # Symbol is passed as parameter (default: AVAXUSDT)
    
    # Check if there's already an active position in the same direction
    active_position = None
    try:
        active_position = check_active_position(symbol)
        logger.info(f"🔍 Position check: Active={active_position}, Signal={side}")
        
        if active_position == side:
            logger.info(f"⏸️ Skipping {side} order: Already have active {side} position")
            # Return dict indicating position already exists
            latency_ms = tracker.end_timer("order_execution")
            return {
                "status": "skipped",
                "reason": f"Active {side} position exists",
                "active_position": active_position,
                "latency_ms": latency_ms
            }
        elif active_position is not None and active_position != side:
            logger.info(f"⚠️ Active {active_position} position exists, but new signal is {side}. Opening anyway (will close opposite position first).")
            # Continue to open position (will close opposite)
    except Exception as e:
        logger.error(f"❌ Position check failed: {e}. Proceeding with order anyway...")
        import traceback
        logger.error(traceback.format_exc())
        # If check fails, proceed with caution but don't block
    
    try:
        # Calculate quantity
        amount = qty / entry
        
        # Apply dynamic slippage if DataFrame provided
        if df_for_slippage is not None:
            slippage = calculate_dynamic_slippage(df_for_slippage, entry)
            entry_with_slippage = apply_slippage_to_price(entry, side, slippage)
            logger.info(f"📊 Dynamic slippage: {slippage*100:.4f}%, Adjusted entry: ${entry_with_slippage:.2f}")
            # Use slippage-adjusted entry for quantity calculation
            amount = qty / entry_with_slippage
        
        # Place entry order
        logger.info(f"Placing {order_side} order for {amount} {symbol.replace('USDT', '')}")
        entry_result = _order_client.place_entry_market(
            symbol=symbol,
            side=order_side,
            amount=amount,
            position_side=position_side,
            extra="LLM"
        )
        logger.info(f"✅ Entry order placed: {entry_result.get('id')}")
        
        # Place TP/SL orders (skip if trend following exit is enabled)
        close_order_side = "sell" if position_side == "LONG" else "buy"
        
        tp_result = None
        sl_result = None
        
        if not trend_following_exit_enabled:
            # TP
            tp_result = _order_client.place_take_profit_market_close(
                symbol=symbol,
                side=close_order_side,
                price=tp,
                position_side=position_side,
                intent="TP",
                extra="LLM"
            )
            logger.info(f"✅ TP order placed: {tp_result.get('id')}")
            
            # SL
            sl_result = _order_client.place_stop_market_close(
                symbol=symbol,
                side=close_order_side,
                stop_price=sl,
                position_side=position_side,
                intent="SL",
                extra="LLM"
            )
            logger.info(f"✅ SL order placed: {sl_result.get('id')}")
        else:
            # Trend following exit enabled - cancel TP orders, but keep initial SL for safety
            # TP orders will be managed dynamically by trend following exit
            tp_cancelled = _order_client.cancel_tp_sl_orders(symbol, order_type="TP")
            if tp_cancelled > 0:
                logger.info(f"🔄 Cancelled {tp_cancelled} existing TP orders (trend following exit active)")
            
            # Place initial SL order for safety (will be updated by trailing stop later)
            sl_result = _order_client.place_stop_market_close(
                symbol=symbol,
                side=close_order_side,
                stop_price=sl,
                position_side=position_side,
                intent="SL",
                extra="LLM_INITIAL"
            )
            logger.info(f"✅ Initial SL order placed: {sl_result.get('id')} (will be updated by trailing stop)")
        
        # Register position for break-even/trailing management
        pos_manager = get_position_manager()
        position_id = entry_result.get('id', 'unknown')
        pos_info = pos_manager.register_position(
            symbol=symbol,
            side=position_side,
            entry_price=entry,
            initial_sl=sl,
            position_id=position_id,
        )
        
        # Track latency and return results
        latency_ms = tracker.end_timer("order_execution")
        if latency_ms and latency_ms > 300:
            logger.warning(f"🚨 High order latency: {latency_ms:.2f}ms")
        
        # Return dict with order results
        return {
            "status": "success",
            "order_id": entry_result.get('id'),
            "position_id": pos_info.get('position_id') if pos_info else None,
            "latency_ms": latency_ms
        }
        
    except Exception as e:
        tracker.end_timer("order_execution")
        logger.error(f"❌ Failed to place order: {e}")
        return None


# Global telegram config
_telegram_config = None


def init_telegram(bot_token: str, chat_id: str):
    """Initialize Telegram configuration."""
    global _telegram_config
    _telegram_config = {
        "bot_token": bot_token,
        "chat_id": chat_id,
        "base_url": f"https://api.telegram.org/bot{bot_token}/sendMessage"
    }


def send_telegram_alert(payload: Dict) -> None:
    """
    Send Telegram alert.

    Args:
        payload: Alert payload with side, TP, SL, confidence, etc.
    """
    if _telegram_config is None:
        logger.warning("Telegram not configured - skipping alert")
        return
    
    try:
        side = payload["side"]
        entry = payload["entry"]
        tp = payload["tp"]
        sl = payload["sl"]
        conf = payload["confidence"]
        symbol = payload.get("symbol", "AVAXUSDT")
        
        # Check if shadow mode
        shadow_indicator = ""
        if payload.get("shadow_mode", False):
            shadow_indicator = "\n👻 SHADOW MODE (No order placed)\n"
        
        position_opened = payload.get("position_opened", True)  # Default True for backward compatibility
        
        # Check if position was opened or skipped
        position_info = ""
        if not position_opened:
            active_pos = payload.get("active_position", "N/A")
            position_info = f"\n⏸️ Aktif {active_pos} pozisyon var - Yeni pozisyon açılmadı"
        else:
            position_info = f"\n✅ Pozisyon açıldı"
        
        # Build message with optional latency info
        latency_info = ""
        if "signal_latency_ms" in payload:
            latency_info += f"⏱️ Signal: {payload['signal_latency_ms']:.1f}ms\n"
        if "order_latency_ms" in payload:
            latency_info += f"⏱️ Order: {payload['order_latency_ms']:.1f}ms\n"
        
        message = f"""
📊 ATR AVAX Signal{shadow_indicator}
📌 Pair: {symbol}
📊 Side: {side}
💰 Entry: ${entry:,.2f}
🎯 TP: ${tp:,.2f}
🛑 SL: ${sl:,.2f}
📈 Confidence: {conf:.2%}
{position_info}"""
        
        if latency_info:
            message += f"\n{latency_info}"
        
        import requests
        response = requests.post(
            _telegram_config["base_url"],
            json={
                "chat_id": _telegram_config["chat_id"],
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=5
        )
        response.raise_for_status()
        logger.info("✅ Telegram alert sent")
        
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram alert: {e}")


def on_new_bar(
    df: pd.DataFrame,
    model: SeqClassifier,
    feature_cols: list,
    window: int,
    tp_pct: float,
    sl_pct: float,
    thr_long: float,
    thr_short: float,
    use_regime_thresholds: bool = True,
    min_prob_ratio: float = 3.0,
    symbol: str = "AVAXUSDT",
) -> None:
    """
    Process new bar and emit signal if criteria met.

    Args:
        df: DataFrame with latest bars (needs ≥200 for rolling z-scores)
        model: Trained model
        feature_cols: List of feature column names
        window: Window length (typically 128)
        tp_pct: Take-profit percentage
        sl_pct: Stop-loss percentage
        thr_long: Long threshold
        thr_short: Short threshold
        use_regime_thresholds: Use regime-based thresholds
        min_prob_ratio: Minimum ratio between long/short probs (default: 3.0)
    """
    tracker = get_latency_tracker()
    tracker.start_timer("signal_generation")
    
    n = len(df)
    
    if n < max(window, 200):
        logger.warning("Not enough data")
        tracker.end_timer("signal_generation")
        return
    
    # Get latest window
    window_data = df[feature_cols].iloc[-window:].values
    
    # Predict
    probs = predict_proba(model, window_data)
    
    # Apply regime-based thresholds if enabled
    if use_regime_thresholds and n >= 200:
        vol_regime = detect_volatility_regime(df).iloc[-1]
        trend_regime = detect_trend_regime(df).iloc[-1]
        regime_thr_long, regime_thr_short = get_regime_thresholds(vol_regime, trend_regime, thr_long, thr_short)
        logger.info(f"📊 Regime: Vol={vol_regime}, Trend={trend_regime}, Thresholds: Long={regime_thr_long:.2f}, Short={regime_thr_short:.2f}")
    else:
        regime_thr_long = thr_long
        regime_thr_short = thr_short
    
    side, conf = decide_side(probs, regime_thr_long, regime_thr_short, min_prob_ratio=min_prob_ratio)
    
    # Track signal generation latency
    signal_latency = tracker.end_timer("signal_generation")
    
    # Check trade blocker
    pos_manager = get_position_manager()
    should_block, block_reason = pos_manager.should_block_trades(
        max_consecutive_losses=5,
        cooldown_minutes=60,
    )
    if should_block:
        logger.warning(f"🚫 Trade blocked: {block_reason}")
        return
    
    if side == "FLAT":
        logger.info(f"FLAT signal (conf: {conf:.3f})")
        return
    
    # Get last price
    last_price = float(df["close"].iloc[-1])
    
    # Calculate TP/SL
    tp, sl = tp_sl_from_pct(last_price, tp_pct, sl_pct, side)
    
    # Optional regime filter (EMA50 > EMA200, vol spike)
    ema50 = df["ema50"].iloc[-1] if "ema50" in df.columns else last_price
    ema200 = df["ema200"].iloc[-1] if "ema200" in df.columns else last_price
    vol_spike = df["vol_spike"].iloc[-1] if "vol_spike" in df.columns else 1.0
    
    # Gate: filter noisy signals
    regime_ok = ema50 > ema200 and vol_spike > 0.85
    
    if not regime_ok:
        logger.info(f"Regime filter: REJECTED")
        return
    
    # Prepare alert payload (always prepare, even in shadow mode)
    payload = {
        "symbol": symbol,
        "side": side,
        "entry": last_price,
        "tp": tp,
        "sl": sl,
        "confidence": conf,
        "probs": probs,
        "leverage": 5,  # Config
        "qty_usd": 1000,  # Config
    }
    
    logger.info(
        f"Signal: {side} @ {last_price:.2f}, TP={tp:.2f}, SL={sl:.2f}, conf={conf:.3f}"
    )
    
    # Shadow mode check
    shadow_mode = get_shadow_mode()
    is_shadow = shadow_mode.is_active()
    
    if is_shadow:
        # Record signal in shadow mode
        shadow_mode.record_signal(side, last_price, tp, sl, conf, probs)
        logger.info("👻 Shadow mode: Signal recorded (order not placed)")
        
        # Add shadow mode indicator to payload
        payload["shadow_mode"] = True
        payload["signal_latency_ms"] = signal_latency if signal_latency else 0
        
        # Send Telegram alert with shadow mode indicator
        send_telegram_alert(payload)
        return
    
    # Production mode: place real orders
    payload["shadow_mode"] = False
    
    # Send hooks (only if not in shadow mode)
    order_result = None
    order_result = send_order(
        side=side,
        entry=last_price,
        tp=tp,
        sl=sl,
        leverage=5,
        qty=1000,
        df_for_slippage=df,  # Pass DataFrame for slippage calculation
    )
    
    # Check if order was skipped due to active position
    if order_result and order_result.get("status") == "skipped":
        active_pos = order_result.get("active_position")
        logger.info(f"⏸️ Order skipped: Active {active_pos} position exists")
        payload["position_opened"] = False
        payload["active_position"] = active_pos
        # Still send Telegram alert to inform about skipped order
        send_telegram_alert(payload)
        return
    
    # Add latency info to payload
    if order_result:
        payload["order_latency_ms"] = order_result.get("latency_ms", 0)
        payload["position_opened"] = True
    else:
        payload["position_opened"] = False
    payload["signal_latency_ms"] = signal_latency if signal_latency else 0
    
    send_telegram_alert(payload)
