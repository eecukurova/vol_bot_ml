#!/usr/bin/env python3
"""Live LLM signal generator - runs continuously."""
import time
import ccxt
import pandas as pd
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.transformer import SeqClassifier
from src.utils import load_feat_cols
from src.features import add_features
from src.infer import predict_proba, decide_side, tp_sl_from_pct
from src.live_loop import init_order_client, init_telegram, send_order, send_telegram_alert
import logging
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_model():
    """Load trained model."""
    model_path = Path("models/seqcls.pt")
    feat_cols_path = Path("models/feat_cols.json")
    
    feat_cols = load_feat_cols(feat_cols_path)
    
    model = SeqClassifier(n_features=len(feat_cols))
    model.load_state_dict(torch.load(model_path))
    model.eval()
    
    logger.info(f"Model loaded: {len(feat_cols)} features")
    return model, feat_cols

def fetch_latest_bars(symbol="ETHUSDT", timeframe="3m", limit=200):
    """Fetch latest bars from Binance."""
    # Use futures data (same as trading)
    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    
    return df

def main():
    logger.info("🚀 Starting LLM Live Signal Generator")
    
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
    
    # Load configs first
    with open("configs/llm_config.json", "r") as f:
        llm_cfg = json.load(f)
    
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
    
    # Load model
    model, feat_cols = load_model()
    
    # Training config
    with open("configs/train_3m.json", "r") as f:
        train_cfg = json.load(f)
    
    window = train_cfg["window"]
    
    # Trading params from config (prefer llm_config, fallback to train_3m)
    trading_params = llm_cfg.get("trading_params", {})
    tp_pct = trading_params.get("tp_pct", train_cfg["tp_pct"])
    sl_pct = trading_params.get("sl_pct", 0.008)
    thr_long = trading_params.get("thr_long", 0.80)  # Increased from 0.65 to filter low-confidence signals
    thr_short = trading_params.get("thr_short", 0.80)  # Increased from 0.65 to filter low-confidence signals
    
    # Get leverage and trade amount from config
    leverage = llm_cfg.get("leverage", 5)
    trade_amount_usd = llm_cfg.get("trade_amount_usd", 1000)
    
    logger.info("✅ All systems ready. Starting live loop...")
    logger.info(f"📊 Monitoring: ETH/USDT {train_cfg['timeframe']}")
    logger.info(f"🎯 TP: {tp_pct*100}%, SL: {sl_pct*100}%")
    logger.info(f"📈 Thresholds: Long={thr_long}, Short={thr_short}")
    logger.info(f"💰 Trade Amount: ${trade_amount_usd}, Leverage: {leverage}x")
    if shadow_mode.is_active():
        logger.info(f"👻 Shadow mode ACTIVE (will not place real orders for {shadow_config.get('duration_days', 7)} days)")
    else:
        logger.info(f"✅ Shadow mode INACTIVE (real orders will be placed)")
    
    last_bar_time = None
    
    while True:
        try:
            # Fetch latest data
            df = fetch_latest_bars()
            
            # Check if new bar
            current_bar_time = df.index[-1]
            
            if last_bar_time is None or current_bar_time != last_bar_time:
                logger.info(f"\n🔄 New bar: {current_bar_time}")
                
                # Add features
                df_featured = add_features(df)
                
                if len(df_featured) >= window:
                    # Get window
                    window_data = df_featured[feat_cols].iloc[-window:].values
                    
                    # Predict
                    probs = predict_proba(model, window_data)
                    side, conf = decide_side(probs, thr_long, thr_short)
                    
                    last_price = float(df_featured["close"].iloc[-1])
                    
                    if side != "FLAT":
                        # Regime filter
                        ema50 = df_featured["ema50"].iloc[-1] if "ema50" in df_featured.columns else last_price
                        ema200 = df_featured["ema200"].iloc[-1] if "ema200" in df_featured.columns else last_price
                        vol_spike = df_featured["vol_spike"].iloc[-1] if "vol_spike" in df_featured.columns else 1.0
                        
                        regime_ok = ema50 > ema200 and vol_spike > 0.8
                        
                        if regime_ok:
                            # TP/SL
                            tp, sl = tp_sl_from_pct(last_price, tp_pct, sl_pct, side)
                            
                            # Log signal
                            logger.info(f"🎯 SIGNAL: {side} @ ${last_price:.2f}")
                            logger.info(f"   TP: ${tp:.2f}, SL: ${sl:.2f}, Confidence: {conf:.2%}")
                            logger.info(f"   Probs: Flat={probs['flat']:.2%}, Long={probs['long']:.2%}, Short={probs['short']:.2%}")
                            
                            # Shadow mode check
                            if shadow_mode.is_active():
                                shadow_mode.record_signal(side, last_price, tp, sl, conf, probs)
                                logger.info("👻 Shadow mode: Signal recorded (order not placed)")
                                
                                # Telegram alert with shadow mode indicator
                                payload = {
                                    "symbol": "ETHUSDT",
                                    "side": side,
                                    "entry": last_price,
                                    "tp": tp,
                                    "sl": sl,
                                    "confidence": conf,
                                    "probs": probs,
                                    "leverage": leverage,
                                    "qty_usd": trade_amount_usd,
                                    "shadow_mode": True,
                                }
                                send_telegram_alert(payload)
                            else:
                                # Production mode: send real orders (use config values)
                                send_order(side, last_price, tp, sl, leverage, trade_amount_usd)
                                
                                # Telegram alert
                                payload = {
                                    "symbol": "ETHUSDT",
                                    "side": side,
                                    "entry": last_price,
                                    "tp": tp,
                                    "sl": sl,
                                    "confidence": conf,
                                    "probs": probs,
                                    "leverage": leverage,
                                    "qty_usd": trade_amount_usd,
                                    "shadow_mode": False,
                                }
                                send_telegram_alert(payload)
                        else:
                            logger.info(f"⏸️ Regime filter REJECTED (EMA50={ema50:.0f} > EMA200={ema200:.0f}, Vol={vol_spike:.2f})")
                    else:
                        logger.info(f"⚪ FLAT (conf: {conf:.2%})")
                
                last_bar_time = current_bar_time
            
            # Wait for next bar (3 minutes)
            time.sleep(180)
            
        except KeyboardInterrupt:
            logger.info("Stopping live loop...")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

