"""Live loop with hooks for order execution and alerts."""

from typing import Dict, Tuple, Optional, Any
import logging
import ccxt
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

from src.infer import predict_proba, decide_side, tp_sl_from_pct
from src.models.transformer import SeqClassifier

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


def check_active_position(symbol: str) -> Optional[str]:
    """
    Check if there is an active position for the symbol.
    
    Args:
        symbol: Trading symbol
        
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
                # Filter for BTC positions
                for pos in all_positions:
                    pos_symbol = pos.get('symbol', '')
                    if 'BTC' in pos_symbol and 'USDT' in pos_symbol:
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


def send_order(
    side: str,
    entry: float,
    tp: float,
    sl: float,
    leverage: int,
    qty: float,
) -> Optional[str]:
    """
    Send order to exchange (hook to implement).

    Args:
        side: "LONG" or "SHORT"
        entry: Entry price
        tp: Take-profit price
        sl: Stop-loss price
        leverage: Leverage (e.g., 5x)
        qty: Quantity (USD)
    """
    logger.info(f"Order hook: {side} @ {entry}, TP={tp}, SL={sl}")
    
    if _order_client is None:
        logger.warning("Order client not initialized - skipping order")
        return "ERROR_NO_CLIENT"
    
    # Convert side
    if side == "LONG":
        order_side = "buy"
        position_side = "LONG"
    elif side == "SHORT":
        order_side = "sell"
        position_side = "SHORT"
    else:
        logger.warning(f"Unknown side: {side}")
        return "ERROR_UNKNOWN_SIDE"
    
    symbol = "BTCUSDT"
    
    # Check if there's already an active position in the same direction
    active_position = None
    try:
        active_position = check_active_position(symbol)
        logger.info(f"🔍 Position check: Active={active_position}, Signal={side}")
        
        if active_position == side:
            logger.info(f"⏸️ Skipping {side} order: Already have active {side} position")
            # Return active_position info so caller can add it to Telegram message
            return active_position  # Returns "LONG" or "SHORT"
        elif active_position is not None and active_position != side:
            logger.info(f"⚠️ Active {active_position} position exists, but new signal is {side}. Will close opposite position first.")
            # Binance will automatically close opposite position when opening new one
            # But we need to wait longer for the position to be fully closed
    except Exception as e:
        logger.error(f"❌ Position check failed: {e}. Proceeding with order anyway...")
        import traceback
        logger.error(traceback.format_exc())
        # If check fails, proceed with caution but don't block
    
    try:
        # Calculate quantity
        amount = qty / entry
        
        # Binance minimum precision check: minimum 0.001 BTC
        min_btc_amount = 0.001
        if amount < min_btc_amount:
            required_usd = min_btc_amount * entry
            logger.error(f"❌ Amount too small: {amount:.6f} BTC < {min_btc_amount} BTC (minimum)")
            logger.error(f"   Required trade amount: ${required_usd:.2f} (current: ${qty:.2f})")
            return "ERROR_AMOUNT_TOO_SMALL"
        
        # Apply exchange precision and minimum amount
        if _exchange is not None:
            # Get market info for precision (with retry)
            market = None
            for attempt in range(3):
                try:
                    markets = _exchange.load_markets(reload=(attempt == 0))  # Reload on first attempt
                    market = markets.get(symbol)
                    if market:
                        break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"⚠️ Failed to load markets (attempt {attempt+1}/3): {e}")
                        import time
                        time.sleep(1)
                    else:
                        logger.error(f"❌ Failed to load markets after 3 attempts: {e}")
            if market:
                # Apply amount precision
                amount_precision = market.get('precision', {}).get('amount', 8)
                amount = round(amount, amount_precision)
                
                # Get minimum amount
                limits = market.get('limits', {})
                min_amount = limits.get('amount', {}).get('min', 0.001)
                
                # Check minimum amount requirement
                if amount < min_amount:
                    logger.warning(f"⚠️ Amount {amount} below minimum {min_amount}, adjusting to minimum")
                    amount = min_amount
                
                # Round again after adjustment
                amount = round(amount, amount_precision)
        
        # Place entry order
        logger.info(f"Placing {order_side} order for {amount} BTC")
        entry_result = _order_client.place_entry_market(
            symbol=symbol,
            side=order_side,
            amount=amount,
            position_side=position_side,
            extra="LLM"
        )
        
        # Check if entry order was successful
        entry_id = entry_result.get('id')
        entry_status = entry_result.get('status', '')
        
        # Entry order başarısızsa TP/SL yerleştirme
        # 'duplicate' veya 'duplicate_resolved' durumları başarılı sayılır (order zaten yerleştirilmiş)
        if not entry_id:
            logger.error(f"❌ Entry order failed: No order ID returned. Result: {entry_result}. Not placing TP/SL orders.")
            return "ERROR_ENTRY_FAILED"
        
        if entry_status in ['FAILED', 'failed']:
            logger.error(f"❌ Entry order failed with status '{entry_status}': {entry_result}. Not placing TP/SL orders.")
            return "ERROR_ENTRY_FAILED"
        
        # 'duplicate' veya 'duplicate_resolved' durumları başarılı sayılır
        if entry_status in ['duplicate', 'duplicate_resolved']:
            logger.info(f"ℹ️ Entry order already exists (duplicate): {entry_id}. Proceeding with TP/SL placement.")
        
        logger.info(f"✅ Entry order placed: {entry_id}")
        
        # Entry order'dan sonra pozisyonun gerçekten açılıp açılmadığını kontrol et
        # Zıt pozisyon varsa daha uzun bekleme süresi gerekir (Binance otomatik kapatır)
        import time
        if active_position is not None and active_position != side:
            # Zıt pozisyon kapatılıyor, daha uzun bekle
            wait_time = 3  # 3 saniye bekle
            logger.info(f"⏳ Waiting {wait_time}s for opposite position to close...")
            time.sleep(wait_time)
        else:
            time.sleep(1)  # Normal durumda 1 saniye bekle
        
        # Pozisyon kontrolü - retry mekanizması ile
        position_verified = False
        max_retries = 3
        retry_delay = 2  # 2 saniye
        
        for attempt in range(max_retries):
            try:
                verified_position = check_active_position(symbol)
                if verified_position == position_side:
                    position_verified = True
                    logger.info(f"✅ Position verified: {position_side} position is active")
                    break
                elif verified_position is None and attempt < max_retries - 1:
                    # Pozisyon henüz açılmamış, tekrar dene
                    logger.info(f"⏳ Position not yet opened (attempt {attempt+1}/{max_retries}), waiting {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.warning(f"⚠️ Position verification failed: Expected {position_side}, but active position is {verified_position}")
                    if attempt < max_retries - 1:
                        logger.info(f"⏳ Retrying position check (attempt {attempt+1}/{max_retries})...")
                        time.sleep(retry_delay)
                        continue
            except Exception as pos_check_error:
                logger.warning(f"⚠️ Position verification check failed (attempt {attempt+1}/{max_retries}): {pos_check_error}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    # Son denemede de başarısız olursa, güvenli tarafta kal
                    logger.warning("⚠️ Position verification failed after all retries. Proceeding with TP/SL placement anyway.")
                    position_verified = True  # Güvenli tarafta kal
                    break
        
        if not position_verified:
            logger.error(f"❌ Position not opened after entry order after {max_retries} attempts. Not placing TP/SL orders.")
            return "ERROR_POSITION_NOT_OPENED"
        
        # Entry order başarılı ve pozisyon açıldı, şimdi TP/SL yerleştir
        close_order_side = "sell" if position_side == "LONG" else "buy"
        
        try:
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
        except Exception as tp_error:
            logger.error(f"❌ Failed to place TP order: {tp_error}")
            # TP başarısız olsa bile devam et (SL yerleştir)
        
        try:
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
        except Exception as sl_error:
            logger.error(f"❌ Failed to place SL order: {sl_error}")
            # SL başarısız olsa bile entry başarılı olduğu için devam et
        
        # Return None to indicate position was successfully opened
        return None
        
    except Exception as e:
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
        position_opened = payload.get("position_opened", True)  # Default True for backward compatibility
        
        # Build message
        blocked = payload.get("blocked", False)
        block_reason = payload.get("block_reason", "")
        vol_warning = payload.get("vol_warning", "")
        
        if blocked:
            message = f"""
🚫 LLM Futures Signal - ENGELLENDİ

📌 Pair: {symbol}
📊 Side: {side}
💰 Entry: ${entry:,.2f}
🎯 TP: ${tp:,.2f}
🛑 SL: ${sl:,.2f}
📈 Confidence: {conf:.2%}

⚠️ PATTERN BLOCKER:
{block_reason}
"""
            if vol_warning:
                message += f"\n{vol_warning}"
        else:
            message = f"""
🤖 LLM Futures Signal

📌 Pair: {symbol}
📊 Side: {side}
💰 Entry: ${entry:,.2f}
🎯 TP: ${tp:,.2f}
🛑 SL: ${sl:,.2f}
📈 Confidence: {conf:.2%}
"""
            
            # Add volume warning if present
            if vol_warning:
                message += f"\n{vol_warning}"
            
            # Add position status
            if not position_opened:
                active_pos = payload.get("active_position", "N/A")
                message += f"\n⏸️ Aktif {active_pos} pozisyon var - Yeni pozisyon açılmadı"
            else:
                message += f"\n✅ Pozisyon açıldı"
        
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


def save_skipped_signal(
    side: str,
    entry: float,
    tp: float,
    sl: float,
    confidence: float,
    probs: Dict[str, float],
    active_position: str,
    features: Optional[Dict[str, Any]] = None,
    symbol: str = "BTCUSDT"
) -> None:
    """
    Save skipped signal to JSON file for later analysis.
    
    Args:
        side: LONG or SHORT
        entry: Entry price
        tp: Take-profit price
        sl: Stop-loss price
        confidence: Signal confidence
        probs: Probability distribution
        active_position: Active position that caused skip
        features: Optional market features dict
        symbol: Trading symbol
    """
    try:
        skipped_file = Path("runs/skipped_signals.json")
        skipped_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing skipped signals
        skipped_signals = []
        if skipped_file.exists():
            try:
                with open(skipped_file, 'r') as f:
                    skipped_signals = json.load(f)
            except:
                skipped_signals = []
        
        # Create new skipped signal entry
        skipped_signal = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'side': side,
            'entry': entry,
            'tp': tp,
            'sl': sl,
            'confidence': confidence,
            'probs': probs,
            'active_position': active_position,
            'features': features or {}
        }
        
        skipped_signals.append(skipped_signal)
        
        # Save (keep last 1000 signals)
        if len(skipped_signals) > 1000:
            skipped_signals = skipped_signals[-1000:]
        
        # Atomic write
        temp_file = skipped_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(skipped_signals, f, indent=2)
        temp_file.replace(skipped_file)
        
        logger.debug(f"💾 Skipped signal saved: {side} @ ${entry:.2f}")
        
    except Exception as e:
        logger.error(f"❌ Failed to save skipped signal: {e}")


def save_closed_position(
    side: str,
    entry: float,
    exit_price: float,
    tp: float,
    sl: float,
    confidence: float,
    probs: Dict[str, float],
    pnl: float,
    exit_reason: str,  # "TP" or "SL"
    entry_time: str,
    exit_time: str,
    features: Optional[Dict[str, Any]] = None,
    symbol: str = "BTCUSDT"
) -> None:
    """
    Save closed position to JSON file for pattern analysis.
    
    Args:
        side: LONG or SHORT
        entry: Entry price
        exit_price: Exit price
        tp: Take-profit price
        sl: Stop-loss price
        confidence: Signal confidence
        probs: Probability distribution
        pnl: Realized PnL
        exit_reason: "TP" or "SL"
        entry_time: Entry timestamp
        exit_time: Exit timestamp
        features: Optional market features dict
        symbol: Trading symbol
    """
    try:
        positions_file = Path("runs/closed_positions.json")
        positions_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing positions
        closed_positions = []
        if positions_file.exists():
            try:
                with open(positions_file, 'r') as f:
                    closed_positions = json.load(f)
            except:
                closed_positions = []
        
        # Create new position entry
        position = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'side': side,
            'entry': entry,
            'exit': exit_price,
            'tp': tp,
            'sl': sl,
            'confidence': confidence,
            'probs': probs,
            'pnl': pnl,
            'exit_reason': exit_reason,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'features': features or {}
        }
        
        closed_positions.append(position)
        
        # Save (keep last 500 positions)
        if len(closed_positions) > 500:
            closed_positions = closed_positions[-500:]
        
        # Atomic write
        temp_file = positions_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(closed_positions, f, indent=2)
        temp_file.replace(positions_file)
        
        logger.debug(f"💾 Closed position saved: {side} @ ${entry:.2f} → ${exit_price:.2f} ({exit_reason})")
        
        # Update entry_features.json with exit information
        try:
            from src.entry_features_logger import update_entry_with_exit
            update_entry_with_exit(
                entry_time=entry_time,
                exit_reason=exit_reason,
                exit_price=exit_price,
                exit_time=exit_time,
                pnl=pnl
            )
        except Exception as e:
            logger.debug(f"Failed to update entry features with exit: {e}")
        
    except Exception as e:
        logger.error(f"❌ Failed to save closed position: {e}")


def on_new_bar(
    df: pd.DataFrame,
    model: SeqClassifier,
    feature_cols: list,
    window: int,
    tp_pct: float,
    sl_pct: float,
    thr_long: float,
    thr_short: float,
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
    """
    n = len(df)
    
    if n < max(window, 200):
        logger.warning("Not enough data")
        return
    
    # Get latest window
    window_data = df[feature_cols].iloc[-window:].values
    
    # Predict
    probs = predict_proba(model, window_data)
    side, conf = decide_side(probs, thr_long, thr_short)
    
    if side == "FLAT":
        logger.info(f"FLAT signal (conf: {conf:.3f})")
        return
    
    # Get last price
    last_price = float(df["close"].iloc[-1])
    
    # Calculate TP/SL
    tp, sl = tp_sl_from_pct(last_price, tp_pct, sl_pct, side)
    
    # Regime filter disabled by default (can be enabled via config in run_live_continuous.py)
    # All signals will pass through
    
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
    
    # Send hooks
    send_order(
        side=side,
        entry=last_price,
        tp=tp,
        sl=sl,
        leverage=5,
        qty=1000,
    )
    
    send_telegram_alert(payload)
