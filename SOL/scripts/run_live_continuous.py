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
from src.live_loop import init_order_client, init_telegram, send_order, send_telegram_alert, get_order_client
from src.trend_following_exit import init_trend_following_exit, get_trend_following_exit
import logging
import torch
from pathlib import Path

# Configure logging with file handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("runs/sol_live.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_model():
    """Load trained model and feature columns."""
    model_path = "models/seqcls.pt"
    feat_cols_path = "models/feat_cols.json"
    
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    feat_cols = load_feat_cols(feat_cols_path)
    
    model = SeqClassifier(n_features=len(feat_cols), d_model=64, nhead=4, num_layers=2)
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()
    
    logger.info(f"✅ Model loaded: {len(feat_cols)} features")
    return model, feat_cols

def fetch_latest_bars(symbol="SOLUSDT", timeframe="3m", limit=200):
    """Fetch latest bars from Binance."""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    return df

def fetch_trend_bars(symbol="SOLUSDT", timeframe="15m", limit=200):
    """Fetch bars for trend analysis (longer timeframe)."""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
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
    
    # Initialize trend following exit
    init_trend_following_exit(llm_cfg)
    
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
    thr_long = trading_params.get("thr_long", 0.85)
    thr_short = trading_params.get("thr_short", 0.85)
    min_prob_ratio = trading_params.get("min_prob_ratio", 3.0)
    
    # Get leverage and trade amount from config
    leverage = llm_cfg.get("leverage", 5)
    trade_amount_usd = llm_cfg.get("trade_amount_usd", 1000)
    
    symbol = llm_cfg.get("symbol", "SOLUSDT")
    
    # Get trend following exit config
    trend_config = llm_cfg.get("trend_following_exit", {})
    trend_exit_enabled = trend_config.get("enabled", False)
    
    logger.info("✅ All systems ready. Starting live loop...")
    logger.info(f"📊 Monitoring: {symbol} {train_cfg['timeframe']}")
    logger.info(f"🎯 TP: {tp_pct*100}%, SL: {sl_pct*100}%")
    logger.info(f"📈 Thresholds: Long={thr_long}, Short={thr_short}")
    logger.info(f"📊 Min Prob Ratio: {min_prob_ratio} (Long/Short prob ratio check)")
    logger.info(f"💰 Trade Amount: ${trade_amount_usd}, Leverage: {leverage}x")
    logger.info(f"🎯 Trend Following Exit: {'ENABLED' if trend_exit_enabled else 'DISABLED'}")
    if shadow_mode.is_active():
        logger.info(f"👻 Shadow mode ACTIVE (will not place real orders for {shadow_config.get('duration_days', 7)} days)")
    else:
        logger.info(f"✅ Shadow mode INACTIVE (real orders will be placed)")
    
    last_bar_time = None
    
    while True:
        try:
            # Fetch latest data
            df = fetch_latest_bars(symbol=symbol, timeframe=train_cfg["timeframe"])
            
            # Check if new bar
            current_bar_time = df.index[-1]
            
            if last_bar_time is None or current_bar_time != last_bar_time:
                logger.info(f"\n🔄 New bar: {current_bar_time}")
                
                # Add features
                df_featured = add_features(df)
                
                # Check trend following exit for existing positions (BEFORE checking new signals)
                if trend_exit_enabled:
                    trend_exit = get_trend_following_exit()
                    
                    if symbol in trend_exit.positions:
                        # Get current bar data for exit checks
                        current_bar = df_featured.iloc[-1]
                        current_price = float(current_bar["close"])
                        high = float(current_bar["high"])
                        low = float(current_bar["low"])
                        
                        # Calculate EMA12 and EMA26 if not present
                        if "ema12" not in df_featured.columns:
                            df_featured["ema12"] = df_featured["close"].ewm(span=12, adjust=False).mean()
                        if "ema26" not in df_featured.columns:
                            df_featured["ema26"] = df_featured["close"].ewm(span=26, adjust=False).mean()
                        
                        ema_fast = float(df_featured["ema12"].iloc[-1])
                        ema_slow = float(df_featured["ema26"].iloc[-1])
                        volume_ratio = float(current_bar.get("vol_spike", 1.0))
                        
                        # Heikin Ashi calculation for volume exit
                        # HA close = (O + H + L + C) / 4
                        ha_close = (current_bar["open"] + current_bar["high"] + current_bar["low"] + current_bar["close"]) / 4
                        # HA open = (previous HA open + previous HA close) / 2
                        if len(df_featured) > 1:
                            prev_ha_close = (df_featured["open"].iloc[-2] + df_featured["high"].iloc[-2] + 
                                           df_featured["low"].iloc[-2] + df_featured["close"].iloc[-2]) / 4
                            prev_ha_open = (df_featured["open"].iloc[-2] + df_featured["close"].iloc[-2]) / 2 if len(df_featured) == 2 else (
                                (df_featured["open"].iloc[-3] + df_featured["close"].iloc[-3]) / 2 if len(df_featured) > 2 else current_bar["open"]
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
                
                if len(df_featured) >= window:
                    # Get window
                    window_data = df_featured[feat_cols].iloc[-window:].values
                    
                    # Predict
                    probs = predict_proba(model, window_data)
                    side, conf = decide_side(probs, thr_long, thr_short, min_prob_ratio=min_prob_ratio)
                    
                    last_price = float(df_featured["close"].iloc[-1])
                    
                    if side != "FLAT":
                        # MULTI-TIMEFRAME TREND KONTROLÜ
                        # 3m çok kısa ve noise çok fazla - 15m'de trend kontrolü yap
                        logger.info("🔍 Multi-timeframe trend kontrolü yapılıyor...")
                        
                        # 15m timeframe'den trend bilgisi al
                        df_trend = fetch_trend_bars(symbol=symbol, timeframe="15m", limit=200)
                        df_trend_featured = add_features(df_trend)
                        
                        # 15m'de EMA50 ve EMA200 hesapla
                        trend_ema50 = df_trend_featured["ema50"].iloc[-1] if "ema50" in df_trend_featured.columns else last_price
                        trend_ema200 = df_trend_featured["ema200"].iloc[-1] if "ema200" in df_trend_featured.columns else last_price
                        
                        # 3m'de de EMA kontrolü (ikinci seviye)
                        ema50_3m = df_featured["ema50"].iloc[-1] if "ema50" in df_featured.columns else last_price
                        ema200_3m = df_featured["ema200"].iloc[-1] if "ema200" in df_featured.columns else last_price
                        vol_spike = df_featured["vol_spike"].iloc[-1] if "vol_spike" in df_featured.columns else 1.0
                        
                        trend_ok = True
                        trend_reason = "Unknown"
                        
                        if side == "LONG":
                            # Long için: 15m'de EMA50 > EMA200 olmalı (uptrend)
                            trend_ok_15m = trend_ema50 > trend_ema200
                            trend_ok_3m = ema50_3m > ema200_3m
                            
                            # 1h timeframe'den trend bilgisi al (daha güçlü trend)
                            try:
                                df_1h = fetch_trend_bars(symbol=symbol, timeframe="1h", limit=200)
                                df_1h_featured = add_features(df_1h)
                                trend_1h_ema50 = df_1h_featured["ema50"].iloc[-1] if "ema50" in df_1h_featured.columns else last_price
                                trend_1h_ema200 = df_1h_featured["ema200"].iloc[-1] if "ema200" in df_1h_featured.columns else last_price
                                trend_ok_1h = trend_1h_ema50 > trend_1h_ema200
                                
                                # Early reversal detection: 1h trend reversal + 15m momentum zayıflıyor
                                # 1h'de trend dönüşü varsa, 15m'de de uptrend olmasa bile LONG açabiliriz
                                early_reversal = False
                                if trend_ok_1h and not trend_ok_15m:
                                    # 1h uptrend ama 15m henüz uptrend değil = Erken reversal sinyali
                                    # Reversal features kontrol et
                                    trend_exhaustion = df_featured.get("trend_exhaustion", pd.Series(0, index=df_featured.index)).iloc[-1]
                                    stoch_oversold = df_featured.get("stoch_oversold", pd.Series(0, index=df_featured.index)).iloc[-1]
                                    rsi_oversold = df_featured.get("rsi_oversold", pd.Series(0, index=df_featured.index)).iloc[-1]
                                    
                                    if trend_exhaustion > 0.5 or (stoch_oversold > 0 and rsi_oversold > 0):
                                        early_reversal = True
                                        logger.info(f"🎯 EARLY REVERSAL DETECTED: 1h uptrend + Reversal features active")
                                        logger.info(f"   Trend Exhaustion: {trend_exhaustion:.2f}, Stoch Oversold: {stoch_oversold}, RSI Oversold: {rsi_oversold}")
                            except Exception as e:
                                logger.warning(f"⚠️ 1h timeframe fetch failed: {e}")
                                trend_ok_1h = True  # Default to pass if fetch fails
                                early_reversal = False
                            
                            # Her iki timeframe'de de uptrend olmalı VEYA early reversal
                            trend_ok = (trend_ok_15m and trend_ok_3m) or early_reversal
                            
                            if not trend_ok:
                                if not trend_ok_15m and not early_reversal:
                                    trend_reason = f"15m trend bearish (EMA50={trend_ema50:.2f} < EMA200={trend_ema200:.2f})"
                                elif not trend_ok_3m and not early_reversal:
                                    trend_reason = f"3m trend bearish (EMA50={ema50_3m:.2f} < EMA200={ema200_3m:.2f})"
                                
                                if not early_reversal:
                                    logger.warning(f"🚫 MULTI-TIMEFRAME TREND CHECK FAILED: LONG sinyali ama {trend_reason}")
                                    logger.warning(f"   15m: EMA50={trend_ema50:.2f}, EMA200={trend_ema200:.2f}")
                                    logger.warning(f"   3m: EMA50={ema50_3m:.2f}, EMA200={ema200_3m:.2f}")
                            else:
                                if early_reversal:
                                    logger.info(f"✅ EARLY REVERSAL SIGNAL: 1h uptrend + Reversal features = LONG entry")
                                else:
                                    logger.info(f"✅ Trend check PASSED: 15m uptrend (EMA50={trend_ema50:.2f} > EMA200={trend_ema200:.2f}), 3m uptrend (EMA50={ema50_3m:.2f} > EMA200={ema200_3m:.2f})")
                                
                        elif side == "SHORT":
                            # Short için: 15m'de EMA50 < EMA200 olmalı (downtrend)
                            trend_ok_15m = trend_ema50 < trend_ema200
                            trend_ok_3m = ema50_3m < ema200_3m
                            
                            # 1h timeframe'den trend bilgisi al (daha güçlü trend)
                            try:
                                df_1h = fetch_trend_bars(symbol=symbol, timeframe="1h", limit=200)
                                df_1h_featured = add_features(df_1h)
                                trend_1h_ema50 = df_1h_featured["ema50"].iloc[-1] if "ema50" in df_1h_featured.columns else last_price
                                trend_1h_ema200 = df_1h_featured["ema200"].iloc[-1] if "ema200" in df_1h_featured.columns else last_price
                                trend_ok_1h = trend_1h_ema50 < trend_1h_ema200
                                
                                # Early reversal detection: 1h trend reversal + 15m momentum zayıflıyor
                                # 1h'de trend dönüşü varsa, 15m'de de downtrend olmasa bile SHORT açabiliriz
                                early_reversal = False
                                if trend_ok_1h and not trend_ok_15m:
                                    # 1h downtrend ama 15m henüz downtrend değil = Erken reversal sinyali
                                    # Reversal features kontrol et
                                    trend_exhaustion = df_featured.get("trend_exhaustion", pd.Series(0, index=df_featured.index)).iloc[-1]
                                    stoch_overbought = df_featured.get("stoch_overbought", pd.Series(0, index=df_featured.index)).iloc[-1]
                                    rsi_overbought = df_featured.get("rsi_overbought", pd.Series(0, index=df_featured.index)).iloc[-1]
                                    
                                    if trend_exhaustion > 0.5 or (stoch_overbought > 0 and rsi_overbought > 0):
                                        early_reversal = True
                                        logger.info(f"🎯 EARLY REVERSAL DETECTED: 1h downtrend + Reversal features active")
                                        logger.info(f"   Trend Exhaustion: {trend_exhaustion:.2f}, Stoch Overbought: {stoch_overbought}, RSI Overbought: {rsi_overbought}")
                            except Exception as e:
                                logger.warning(f"⚠️ 1h timeframe fetch failed: {e}")
                                trend_ok_1h = True  # Default to pass if fetch fails
                                early_reversal = False
                            
                            # Her iki timeframe'de de downtrend olmalı VEYA early reversal
                            trend_ok = (trend_ok_15m and trend_ok_3m) or early_reversal
                            
                            if not trend_ok:
                                if not trend_ok_15m and not early_reversal:
                                    trend_reason = f"15m trend bullish (EMA50={trend_ema50:.2f} > EMA200={trend_ema200:.2f})"
                                elif not trend_ok_3m and not early_reversal:
                                    trend_reason = f"3m trend bullish (EMA50={ema50_3m:.2f} > EMA200={ema200_3m:.2f})"
                                
                                if not early_reversal:
                                    logger.warning(f"🚫 MULTI-TIMEFRAME TREND CHECK FAILED: SHORT sinyali ama {trend_reason}")
                                    logger.warning(f"   15m: EMA50={trend_ema50:.2f}, EMA200={trend_ema200:.2f}")
                                    logger.warning(f"   3m: EMA50={ema50_3m:.2f}, EMA200={ema200_3m:.2f}")
                            else:
                                if early_reversal:
                                    logger.info(f"✅ EARLY REVERSAL SIGNAL: 1h downtrend + Reversal features = SHORT entry")
                                else:
                                    logger.info(f"✅ Trend check PASSED: 15m downtrend (EMA50={trend_ema50:.2f} < EMA200={trend_ema200:.2f}), 3m downtrend (EMA50={ema50_3m:.2f} < EMA200={ema200_3m:.2f})")
                        
                        # Trend kontrolü başarısızsa sinyali atla
                        if not trend_ok:
                            logger.warning(f"🚫 TREND CHECK FAILED: {side} sinyali reddedildi - {trend_reason}")
                            logger.warning(f"   15m: EMA50={trend_ema50:.2f}, EMA200={trend_ema200:.2f}")
                            logger.warning(f"   3m: EMA50={ema50_3m:.2f}, EMA200={ema200_3m:.2f}")
                            continue  # Sinyali atla
                        
                        # MINIMUM BAR KONTROLÜ - Hızlı ardışık sinyalleri engelle
                        min_bars_after_entry = 10  # 3m timeframe için 10 bar = 30 dakika
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
                                    
                                    # 3m timeframe için bar sayısı hesapla (her bar 3 dakika)
                                    bars_passed = int((current_dt - entry_dt).total_seconds() / 180)  # 180 saniye = 3 dakika
                                    
                                    if bars_passed < min_bars_after_entry:
                                        logger.warning(f"🚫 MINIMUM BAR FİLTER: {side} pozisyonu {bars_passed} bar önce açıldı (< {min_bars_after_entry} bar) - Çok hızlı yeni sinyal, reddedildi")
                                        logger.warning(f"   Entry: {entry_dt.strftime('%Y-%m-%d %H:%M:%S')}, Şimdi: {current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                                        continue
                        except Exception as e:
                            logger.debug(f"Minimum bar check error: {e}")
                        
                        # RSI FİLTER - Aşırı overbought/oversold durumlarında işlem yapma
                        rsi = df_featured["rsi"].iloc[-1] if "rsi" in df_featured.columns else 50.0
                        rsi_ok = True
                        
                        if side == "LONG":
                            # LONG için: RSI çok yüksekse (overbought) işlem yapma
                            if rsi > 70:
                                rsi_ok = False
                                logger.warning(f"🚫 RSI FİLTER: LONG sinyali ama RSI={rsi:.1f} (overbought, >70)")
                        elif side == "SHORT":
                            # SHORT için: RSI çok düşükse (oversold) işlem yapma
                            if rsi < 30:
                                rsi_ok = False
                                logger.warning(f"🚫 RSI FİLTER: SHORT sinyali ama RSI={rsi:.1f} (oversold, <30)")
                        
                        if not rsi_ok:
                            continue
                        
                        # Regime filter (volume spike kontrolü - ZORUNLU)
                        vol_spike_threshold = 0.7  # Threshold: 0.7 (daha güçlü sinyaller için artırıldı)
                        
                        # Log volume spike değeri (her sinyalde)
                        logger.info(f"📊 VOLUME SPIKE KONTROLÜ: Volume spike = {vol_spike:.3f} (Threshold: {vol_spike_threshold})")
                        
                        # Volume spike check - ZORUNLU FİLTRE (düşük volume spike'lı sinyalleri engelle)
                        if vol_spike < vol_spike_threshold:
                            logger.warning(
                                f"🚫 VOLUME SPIKE FİLTRESİ: {vol_spike:.2f} < {vol_spike_threshold} - Sinyal reddedildi"
                            )
                            logger.warning(f"   Sinyal: {side} @ {conf:.1%} confidence")
                            logger.warning(f"   Trend kontrolü geçti ama volume spike yetersiz")
                            continue  # Sinyal engellendi ✅
                        else:
                            logger.info(f"✅ VOLUME SPIKE FİLTRESİ: Volume spike {vol_spike:.3f} >= {vol_spike_threshold} - Geçti")
                        
                        # Regime filter - trend kontrolü zaten geçildi, volume spike de geçildi
                        regime_ok = trend_ok  # Trend kontrolü her zaman aktif ve geçildi
                        
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
                                    "symbol": symbol,
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
                                    "confidence": conf,
                                    "probs": probs,
                                    "leverage": leverage,
                                    "qty_usd": trade_amount_usd,
                                    "shadow_mode": False,
                                    "position_opened": position_opened,
                                    "active_position": active_position if active_position and not position_opened else None,
                                }
                                send_telegram_alert(payload)
                        else:
                            logger.info(f"⏸️ Regime filter REJECTED (EMA50={ema50:.0f} > EMA200={ema200:.0f}, Vol={vol_spike:.2f})")
                            logger.info(f"   Probs: Flat={probs['flat']:.2%}, Long={probs['long']:.2%}, Short={probs['short']:.2%}")
                    else:
                        logger.info(f"⚪ FLAT (conf: {conf:.2%})")
                        logger.info(f"   Probs: Flat={probs['flat']:.2%}, Long={probs['long']:.2%}, Short={probs['short']:.2%}")
                
                last_bar_time = current_bar_time
            
            # Wait for next bar (3 minutes)
            time.sleep(180)
            
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
