"""Live loop with hooks for order execution and alerts."""

from typing import Dict, Tuple, Optional
import logging
import ccxt
import json

import pandas as pd
import numpy as np

from src.infer import predict_proba, decide_side, tp_sl_from_pct
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
    
    symbol = "BTCUSDT"
    
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
        logger.info(f"Placing {order_side} order for {amount} BTC")
        entry_result = _order_client.place_entry_market(
            symbol=symbol,
            side=order_side,
            amount=amount,
            position_side=position_side,
            extra="LLM"
        )
        logger.info(f"✅ Entry order placed: {entry_result.get('id')}")
        
        # Place TP/SL orders
        close_order_side = "sell" if position_side == "LONG" else "buy"
        
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
        
        # Register position for break-even/trailing management
        pos_manager = get_position_manager()
        position_id = entry_result.get('id', 'unknown')
        pos_manager.register_position(
            symbol=symbol,
            side=position_side,
            entry_price=entry,
            initial_sl=sl,
            position_id=position_id,
        )
        
        # Track latency
        latency = tracker.end_timer("order_execution")
        if latency and latency > 300:
            logger.warning(f"🚨 High order latency: {latency:.2f}ms")
        
        return {
            "entry_id": entry_result.get('id'),
            "tp_id": tp_result.get('id'),
            "sl_id": sl_result.get('id'),
            "latency_ms": latency,
            "position_id": position_id,
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
        symbol = payload.get("symbol", "BTCUSDT")
        
        # Build message with optional latency info
        latency_info = ""
        if "signal_latency_ms" in payload:
            latency_info += f"⏱️ Signal: {payload['signal_latency_ms']:.1f}ms\n"
        if "order_latency_ms" in payload:
            latency_info += f"⏱️ Order: {payload['order_latency_ms']:.1f}ms\n"
        
        message = f"""
🤖 LLM Futures Signal

📌 Pair: {symbol}
📊 Side: {side}
💰 Entry: ${entry:,.2f}
🎯 TP: ${tp:,.2f}
🛑 SL: ${sl:,.2f}
📈 Confidence: {conf:.2%}
{latency_info}"""
        
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
    
    side, conf = decide_side(probs, regime_thr_long, regime_thr_short)
    
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
    regime_ok = ema50 > ema200 and vol_spike > 0.8
    
    if not regime_ok:
        logger.info(f"Regime filter: REJECTED")
        return
    
    # Shadow mode check
    shadow_mode = get_shadow_mode()
    if shadow_mode.is_active():
        shadow_mode.record_signal(side, last_price, tp, sl, conf, probs)
        logger.info("👻 Shadow mode: Signal recorded (order not placed)")
        return
    
    # Prepare alert payload
    payload = {
        "symbol": "BTCUSDT",
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
    
    # Send hooks (only if not in shadow mode)
    order_result = None
    if not shadow_mode.is_active():
        order_result = send_order(
            side=side,
            entry=last_price,
            tp=tp,
            sl=sl,
            leverage=5,
            qty=1000,
            df_for_slippage=df,  # Pass DataFrame for slippage calculation
        )
    
    # Add latency info to payload
    if order_result:
        payload["order_latency_ms"] = order_result.get("latency_ms", 0)
    payload["signal_latency_ms"] = signal_latency if signal_latency else 0
    
    send_telegram_alert(payload)
