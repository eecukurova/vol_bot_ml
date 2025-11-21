#!/usr/bin/env python3
"""Live LLM signal generator - runs continuously."""
import time
import ccxt
import pandas as pd
import json
import sys
from pathlib import Path
from collections import deque

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.transformer import SeqClassifier
from src.utils import load_feat_cols
from src.features import add_features
from src.infer import predict_proba, decide_side, tp_sl_from_pct
from src.live_loop import init_order_client, init_telegram, send_order, send_telegram_alert, save_skipped_signal
from src.entry_features_logger import save_entry_features, update_entry_with_exit
from src.pattern_blocker import PatternBlocker
from src.volume_spike_monitor import VolumeSpikeMonitor
from datetime import datetime, timezone, timedelta
import logging
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRADE_STATE_FILE = Path("runs/trade_state.json")
CLOSED_POSITIONS_FILE = Path("runs/closed_positions.json")
QUICK_LOSS_WINDOW_MINUTES = 30
QUICK_LOSS_DURATION_MINUTES = 5
QUICK_LOSS_CONF_THRESHOLD = 0.97
QUICK_LOSS_RATIO_THRESHOLD = 10.0
BODY_PCT_THRESHOLD = 0.0006  # ~0.06%
BODY_WITH_LOW_VOL_THRESHOLD = 0.7


def refresh_trade_state(exchange, symbol, sl_pct, tp_pct, state_file=TRADE_STATE_FILE):
    """Fetch recent trades, update closed positions, and detect quick losses."""
    state = {
        "last_trade_ts": 0,
        "open_position": None,
    }
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception:
            logger.warning("Unable to read trade state file, starting fresh")

    last_trade_ts = state.get("last_trade_ts", 0)
    since = last_trade_ts - 60_000  # overlap 1 minute to avoid gaps
    if since <= 0:
        since = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000)

    try:
        trades = exchange.fetch_my_trades(symbol, since=since, limit=500)
    except Exception as exc:
        logger.debug(f"Trade fetch failed: {exc}")
        return []

    trades = sorted(trades, key=lambda t: t["timestamp"])
    new_quick_losses = []

    # Load open_position and convert entry_time string to datetime if needed
    open_position_raw = state.get("open_position")
    open_position = None
    if open_position_raw:
        open_position = {
            "side": open_position_raw["side"],
            "entry_time": datetime.fromisoformat(open_position_raw["entry_time"].replace("Z", "+00:00")) if isinstance(open_position_raw.get("entry_time"), str) else open_position_raw["entry_time"],
            "entry_price": open_position_raw["entry_price"],
            "amount": open_position_raw["amount"],
        }

    closed_positions = []
    if CLOSED_POSITIONS_FILE.exists():
        try:
            closed_positions = json.loads(CLOSED_POSITIONS_FILE.read_text())
        except Exception:
            closed_positions = []

    for trade in trades:
        ts = trade["timestamp"]
        if ts <= last_trade_ts:
            continue

        price = float(trade["price"])
        amount = float(trade["amount"])
        side = trade["side"]  # "buy" or "sell"
        trade_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

        if not open_position:
            open_position = {
                "side": side,
                "entry_time": trade_time,
                "entry_price": price,
                "amount": amount,
            }
            last_trade_ts = ts
            continue

        if side == open_position["side"]:
            total_amount = open_position["amount"] + amount
            if total_amount > 0:
                open_position["entry_price"] = (
                    open_position["entry_price"] * open_position["amount"] + price * amount
                ) / total_amount
                open_position["amount"] = total_amount
            last_trade_ts = ts
            continue

        position_side = "LONG" if open_position["side"] == "buy" else "SHORT"
        entry_price = open_position["entry_price"]
        entry_time = open_position["entry_time"]
        exit_price = price
        exit_time = trade_time

        if position_side == "LONG":
            pnl_pct = (exit_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - exit_price) / entry_price

        duration_min = (exit_time - entry_time).total_seconds() / 60
        exit_reason = "MANUAL"
        if pnl_pct <= -sl_pct * 0.9:
            exit_reason = "SL"
        elif pnl_pct >= tp_pct * 0.9:
            exit_reason = "TP"

        position_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol.replace(":", ""),
            "side": position_side,
            "entry": entry_price,
            "exit": exit_price,
            "tp": entry_price * (1 + tp_pct if position_side == "LONG" else 1 - tp_pct),
            "sl": entry_price * (1 - sl_pct if position_side == "LONG" else 1 + sl_pct),
            "confidence": None,
            "probs": {},
            "pnl": pnl_pct,
            "exit_reason": exit_reason,
            "entry_time": entry_time.isoformat(),
            "exit_time": exit_time.isoformat(),
            "features": {},
        }
        closed_positions.append(position_record)

        try:
            update_entry_with_exit(
                entry_time=entry_time.isoformat(),
                exit_reason=exit_reason,
                exit_price=exit_price,
                exit_time=exit_time.isoformat(),
                pnl=pnl_pct,
            )
        except Exception as exc:
            logger.debug(f"Failed to update entry features with exit: {exc}")

        if exit_reason == "SL" and duration_min <= QUICK_LOSS_DURATION_MINUTES:
            new_quick_losses.append((position_side, exit_time))

        open_position = None
        last_trade_ts = ts

    # Keep history manageable
    if closed_positions:
        closed_positions = closed_positions[-500:]
        try:
            CLOSED_POSITIONS_FILE.write_text(json.dumps(closed_positions, indent=2))
        except Exception as exc:
            logger.debug(f"Failed to write closed positions: {exc}")

    # Serialize datetime objects before saving
    state_to_save = {
        "last_trade_ts": last_trade_ts,
        "open_position": None,
    }
    if open_position:
        state_to_save["open_position"] = {
            "side": open_position["side"],
            "entry_time": open_position["entry_time"].isoformat() if isinstance(open_position["entry_time"], datetime) else open_position["entry_time"],
            "entry_price": open_position["entry_price"],
            "amount": open_position["amount"],
        }
    
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state_to_save, indent=2))
    except Exception as exc:
        logger.debug(f"Failed to persist trade state: {exc}")

    return new_quick_losses


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

def fetch_latest_bars(symbol="BTCUSDT", timeframe="3m", limit=200):
    """Fetch latest bars from Binance."""
    # Use futures data (same as trading)
    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    
    return df

def fetch_trend_bars(symbol="BTCUSDT", timeframe="15m", limit=200):
    """Fetch bars for trend analysis (longer timeframe)."""
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
    
    # Initialize pattern blocker and volume spike monitor
    pattern_blocker = PatternBlocker()
    volume_monitor = VolumeSpikeMonitor(warning_threshold=0.4)
    logger.info("📋 Pattern blocker initialized")
    logger.info("📊 Volume spike monitor initialized")
    
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

    trade_exchange = ccxt.binance({
        "apiKey": llm_cfg["api_key"],
        "secret": llm_cfg["secret"],
        "options": {"defaultType": "future"},
        "enableRateLimit": True,
    })
    quick_loss_tracker = {
        "LONG": deque(),
        "SHORT": deque(),
    }
    symbol_futures = "BTC/USDT:USDT"
    
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
    thr_long = trading_params.get("thr_long", 0.75)  # Optimized based on backtest: 0.75 gives higher final equity
    thr_short = trading_params.get("thr_short", 0.75)  # Optimized based on backtest: 0.75 gives higher final equity
    
    # Regime filter settings
    regime_cfg = llm_cfg.get("regime_filter", {})
    regime_enabled = regime_cfg.get("enabled", False)
    use_ema_filter = regime_cfg.get("use_ema_filter", False)
    use_vol_filter = regime_cfg.get("use_vol_filter", False)
    vol_spike_threshold = regime_cfg.get("vol_spike_threshold", 0.4)
    
    logger.info("✅ All systems ready. Starting live loop...")
    logger.info(f"📊 Monitoring: BTC/USDT {train_cfg['timeframe']}")
    logger.info(f"🎯 TP: {tp_pct*100}%, SL: {sl_pct*100}%")
    logger.info(f"📈 Thresholds: Long={thr_long}, Short={thr_short}")
    if regime_enabled:
        logger.info(f"🔍 Regime Filter: ENABLED (EMA: {use_ema_filter}, Vol: {use_vol_filter}, Threshold: {vol_spike_threshold})")
    else:
        logger.info(f"🔍 Regime Filter: DISABLED (All signals will pass)")
    
    last_bar_time = None
    
    while True:
        try:
            # Fetch latest data
            df = fetch_latest_bars()
            
            current_bar_time = df.index[-1]
            now_utc = datetime.now(timezone.utc)

            # Refresh trade state & quick-loss tracker once per bar
            try:
                new_quick_losses = refresh_trade_state(trade_exchange, symbol_futures, sl_pct, tp_pct)
                for side_name, loss_time in new_quick_losses:
                    quick_loss_tracker.setdefault(side_name, deque()).append(loss_time)
                for side_name, dq in quick_loss_tracker.items():
                    while dq and (now_utc - dq[0]).total_seconds() / 60 > QUICK_LOSS_WINDOW_MINUTES:
                        dq.popleft()
            except Exception as e:
                logger.warning(f"⚠️ Trade state refresh failed: {e}")
                # Continue with signal processing even if trade state refresh fails
            
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
                    open_price = float(df_featured["open"].iloc[-1]) if "open" in df_featured.columns else last_price
                    
                    if side != "FLAT":
                        # Minimum bar kontrolü - Entry'den sonra 7 bar beklenmeli
                        min_bars_after_entry = 7  # 3m timeframe için 7 bar = 21 dakika
                        try:
                            from pathlib import Path
                            import json
                            
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
                                    
                                    # 3m timeframe için bar sayısı hesapla
                                    minutes_diff = (current_dt - entry_dt.replace(tzinfo=None)).total_seconds() / 60
                                    bars_passed = int(minutes_diff / 3)  # 3 dakika per bar
                                    
                                    if bars_passed < min_bars_after_entry:
                                        logger.warning(f"🚫 MINIMUM BAR FİLTER: {side} pozisyonu {bars_passed} bar önce açıldı (< {min_bars_after_entry} bar) - Çok hızlı yeni sinyal, reddedildi")
                                        logger.warning(f"   Entry: {entry_dt.strftime('%Y-%m-%d %H:%M:%S')}, Şimdi: {current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                                        continue
                        except Exception as e:
                            logger.debug(f"Minimum bar check error: {e}")
                        
                        # Quick loss guard (adaptive confidence/ratio)
                        guard_events = [ts for ts in quick_loss_tracker.get(side, deque()) if (now_utc - ts).total_seconds() / 60 <= QUICK_LOSS_WINDOW_MINUTES]
                        if guard_events:
                            # Calculate probability ratio for this signal
                            if side == "LONG":
                                prob_ratio_guard = (probs["long"] / probs["short"]) if probs["short"] > 0 else float("inf")
                            else:
                                prob_ratio_guard = (probs["short"] / probs["long"]) if probs["long"] > 0 else float("inf")

                            if conf < QUICK_LOSS_CONF_THRESHOLD or prob_ratio_guard < QUICK_LOSS_RATIO_THRESHOLD:
                                logger.warning(
                                    f"🚫 QUICK LOSS GUARD: Son {len(guard_events)} hızlı SL var (<={QUICK_LOSS_DURATION_MINUTES} dk). "
                                    f"Confidence {conf:.2%}, ratio {prob_ratio_guard:.2f} – sinyal reddedildi"
                                )
                                continue

                        # Low momentum filter (3m candle body) - Güçlendirilmiş (ayrı kontrol)
                        candle_body_pct = abs(last_price - open_price) / last_price if last_price else 0
                        
                        # Log candle body değeri (her sinyalde)
                        logger.info(f"📊 MOMENTUM KONTROLÜ: Candle body = {candle_body_pct*100:.3f}% (Threshold: {BODY_PCT_THRESHOLD*100:.3f}%)")
                        
                        if candle_body_pct < BODY_PCT_THRESHOLD:
                            logger.warning(
                                f"🚫 MOMENTUM FİLTRESİ: Candle body {candle_body_pct*100:.2f}% < {BODY_PCT_THRESHOLD*100:.2f}% - Sinyal reddedildi"
                            )
                            logger.warning(f"   Sinyal: {side} @ {conf:.1%} confidence")
                            continue
                        else:
                            logger.info(f"✅ MOMENTUM FİLTRESİ: Candle body {candle_body_pct*100:.3f}% >= {BODY_PCT_THRESHOLD*100:.3f}% - Geçti")

                        # Regime filter
                        ema50 = df_featured["ema50"].iloc[-1] if "ema50" in df_featured.columns else last_price
                        ema200 = df_featured["ema200"].iloc[-1] if "ema200" in df_featured.columns else last_price
                        vol_spike = df_featured["vol_spike"].iloc[-1] if "vol_spike" in df_featured.columns else 1.0
                        
                        # Log volume spike değeri (her sinyalde)
                        vol_spike_threshold_value = regime_cfg.get("vol_spike_threshold", 0.4)
                        logger.info(f"📊 VOLUME SPIKE KONTROLÜ: Volume spike = {vol_spike:.3f} (Threshold: {vol_spike_threshold_value})")
                        
                        # Volume spike check - ZORUNLU FİLTRE (düşük volume spike'lı sinyalleri engelle)
                        if vol_spike < vol_spike_threshold_value:
                            logger.warning(
                                f"🚫 VOLUME SPIKE FİLTRESİ: {vol_spike:.2f} < {vol_spike_threshold_value} - Sinyal reddedildi"
                            )
                            logger.warning(f"   Sinyal: {side} @ {conf:.1%} confidence")
                            continue
                        else:
                            logger.info(f"✅ VOLUME SPIKE FİLTRESİ: Volume spike {vol_spike:.3f} >= {vol_spike_threshold_value} - Geçti")
                        
                        # Volume spike warning (log için)
                        vol_warning, vol_message = volume_monitor.check(vol_spike, side, conf)
                        if vol_warning:
                            logger.warning(vol_message)
                        
                        # Pattern blocker check
                        market_features = {
                            "ema50": float(ema50),
                            "ema200": float(ema200),
                            "ema50_1h": float(trend_ema50_1h),
                            "ema200_1h": float(trend_ema200_1h),
                            "vol_spike": float(vol_spike),
                            "rsi": float(df_featured["rsi"].iloc[-1]) if "rsi" in df_featured.columns else 50.0
                        }
                        
                        should_block, block_reason = pattern_blocker.should_block_signal(
                            side=side,
                            confidence=conf,
                            probs=probs,
                            features=market_features,
                            current_hour=datetime.now().hour
                        )
                        
                        if should_block:
                            logger.warning(f"🚫 PATTERN BLOCKER: {block_reason}")
                            logger.warning(f"⏸️ Sinyal engellendi - Pattern match tespit edildi")
                            # Still send Telegram alert but with warning
                            payload = {
                                "symbol": "BTCUSDT",
                                "side": side,
                                "entry": last_price,
                                "tp": tp,
                                "sl": sl,
                                "confidence": conf,
                                "probs": probs,
                                "leverage": leverage,
                                "qty_usd": trade_amount,
                                "position_opened": False,
                                "blocked": True,
                                "block_reason": block_reason,
                                "vol_warning": vol_message if vol_warning else None
                            }
                            send_telegram_alert(payload)
                            continue  # Skip this signal
                        
                        # MULTI-TIMEFRAME TREND KONTROLÜ
                        # 3m çok kısa ve noise çok fazla - 15m'de trend kontrolü yap
                        logger.info("🔍 Multi-timeframe trend kontrolü yapılıyor...")
                        
                        # 15m timeframe'den trend bilgisi al
                        df_trend = fetch_trend_bars(symbol="BTCUSDT", timeframe="15m", limit=200)
                        df_trend_featured = add_features(df_trend)
                        
                        # 1h timeframe'den makro trend bilgisi al
                        df_trend_1h = fetch_trend_bars(symbol="BTCUSDT", timeframe="1h", limit=200)
                        df_trend_1h_featured = add_features(df_trend_1h)
                        
                        # 15m'de EMA50 ve EMA200 hesapla
                        trend_ema50 = df_trend_featured["ema50"].iloc[-1] if "ema50" in df_trend_featured.columns else last_price
                        trend_ema200 = df_trend_featured["ema200"].iloc[-1] if "ema200" in df_trend_featured.columns else last_price
                        
                        # 1h'de EMA50 ve EMA200 hesapla
                        trend_ema50_1h = df_trend_1h_featured["ema50"].iloc[-1] if "ema50" in df_trend_1h_featured.columns else last_price
                        trend_ema200_1h = df_trend_1h_featured["ema200"].iloc[-1] if "ema200" in df_trend_1h_featured.columns else last_price
                        
                        # 3m'de de EMA kontrolü (ikinci seviye)
                        ema50_3m = df_featured["ema50"].iloc[-1] if "ema50" in df_featured.columns else last_price
                        ema200_3m = df_featured["ema200"].iloc[-1] if "ema200" in df_featured.columns else last_price
                        
                        trend_ok = True
                        trend_reason = "Unknown"
                        
                        if side == "LONG":
                            # Long için: 15m, 1h ve 3m'de EMA50 > EMA200 olmalı (çoklu timeframe uptrend)
                            trend_ok_15m = trend_ema50 > trend_ema200
                            trend_ok_1h = trend_ema50_1h > trend_ema200_1h
                            trend_ok_3m = ema50_3m > ema200_3m
                            
                            trend_ok = trend_ok_15m and trend_ok_1h and trend_ok_3m
                            
                            if not trend_ok:
                                if not trend_ok_15m:
                                    trend_reason = f"15m trend bearish (EMA50={trend_ema50:.2f} < EMA200={trend_ema200:.2f})"
                                elif not trend_ok_1h:
                                    trend_reason = f"1h trend bearish (EMA50={trend_ema50_1h:.2f} < EMA200={trend_ema200_1h:.2f})"
                                elif not trend_ok_3m:
                                    trend_reason = f"3m trend bearish (EMA50={ema50_3m:.2f} < EMA200={ema200_3m:.2f})"
                                
                                logger.warning(f"🚫 MULTI-TIMEFRAME TREND CHECK FAILED: LONG sinyali ama {trend_reason}")
                                logger.warning(f"   1h: EMA50={trend_ema50_1h:.2f}, EMA200={trend_ema200_1h:.2f}")
                                logger.warning(f"   15m: EMA50={trend_ema50:.2f}, EMA200={trend_ema200:.2f}")
                                logger.warning(f"   3m: EMA50={ema50_3m:.2f}, EMA200={ema200_3m:.2f}")
                            else:
                                logger.info(
                                    "✅ Trend check PASSED: "
                                    f"1h uptrend (EMA50={trend_ema50_1h:.2f} > EMA200={trend_ema200_1h:.2f}), "
                                    f"15m uptrend (EMA50={trend_ema50:.2f} > EMA200={trend_ema200:.2f}), "
                                    f"3m uptrend (EMA50={ema50_3m:.2f} > EMA200={ema200_3m:.2f})"
                                )
                                
                        elif side == "SHORT":
                            # Short için: 15m, 1h ve 3m'de EMA50 < EMA200 olmalı (çoklu timeframe downtrend)
                            trend_ok_15m = trend_ema50 < trend_ema200
                            trend_ok_1h = trend_ema50_1h < trend_ema200_1h
                            trend_ok_3m = ema50_3m < ema200_3m
                            
                            trend_ok = trend_ok_15m and trend_ok_1h and trend_ok_3m
                            
                            if not trend_ok:
                                if not trend_ok_15m:
                                    trend_reason = f"15m trend bullish (EMA50={trend_ema50:.2f} > EMA200={trend_ema200:.2f})"
                                elif not trend_ok_1h:
                                    trend_reason = f"1h trend bullish (EMA50={trend_ema50_1h:.2f} > EMA200={trend_ema200_1h:.2f})"
                                elif not trend_ok_3m:
                                    trend_reason = f"3m trend bullish (EMA50={ema50_3m:.2f} > EMA200={ema200_3m:.2f})"
                                
                                logger.warning(f"🚫 MULTI-TIMEFRAME TREND CHECK FAILED: SHORT sinyali ama {trend_reason}")
                                logger.warning(f"   1h: EMA50={trend_ema50_1h:.2f}, EMA200={trend_ema200_1h:.2f}")
                                logger.warning(f"   15m: EMA50={trend_ema50:.2f}, EMA200={trend_ema200:.2f}")
                                logger.warning(f"   3m: EMA50={ema50_3m:.2f}, EMA200={ema200_3m:.2f}")
                            else:
                                logger.info(
                                    "✅ Trend check PASSED: "
                                    f"1h downtrend (EMA50={trend_ema50_1h:.2f} < EMA200={trend_ema200_1h:.2f}), "
                                    f"15m downtrend (EMA50={trend_ema50:.2f} < EMA200={trend_ema200:.2f}), "
                                    f"3m downtrend (EMA50={ema50_3m:.2f} < EMA200={ema200_3m:.2f})"
                                )
                        
                        # Trend kontrolü başarısızsa sinyali atla
                        if not trend_ok:
                            logger.warning(f"🚫 TREND CHECK FAILED: {side} sinyali reddedildi - {trend_reason}")
                            logger.warning(f"   1h: EMA50={trend_ema50_1h:.2f}, EMA200={trend_ema200_1h:.2f}")
                            logger.warning(f"   15m: EMA50={trend_ema50:.2f}, EMA200={trend_ema200:.2f}")
                            logger.warning(f"   3m: EMA50={ema50_3m:.2f}, EMA200={ema200_3m:.2f}")
                            continue  # Sinyali atla
                        
                        # Regime filter check (if enabled)
                        if regime_enabled:
                            regime_ok = True
                            
                            if use_ema_filter:
                                # Zaten trend kontrolü yapıldı ve geçildi
                                regime_ok = regime_ok and trend_ok
                            else:
                                # EMA filter disabled ama trend kontrolü yapıldı ve geçildi
                                regime_ok = trend_ok
                            
                            if use_vol_filter:
                                regime_ok = regime_ok and (vol_spike > vol_spike_threshold)
                        else:
                            # Regime filter disabled - ama trend kontrolü yapıldı ve geçildi
                            regime_ok = trend_ok
                        
                        if regime_ok:
                            # EK FİLTRELER - Zararları Engellemek İçin
                            
                            # 1. RSI kontrolü - Aşırı overbought/oversold durumlarında işlem yapma (Sıkılaştırıldı: 80/20 → 75/25)
                            rsi = df_featured["rsi"].iloc[-1] if "rsi" in df_featured.columns else 50.0
                            rsi_ok = True
                            
                            if side == "LONG":
                                # LONG için: RSI çok yüksekse (overbought) işlem yapma (75'ten 70'e düşürüldü - daha sıkı)
                                if rsi > 70:
                                    rsi_ok = False
                                    logger.warning(f"🚫 RSI FİLTER: LONG sinyali ama RSI={rsi:.1f} (overbought, >70)")
                            elif side == "SHORT":
                                # SHORT için: RSI çok düşükse (oversold) işlem yapma (25'ten 30'a yükseltildi - daha sıkı)
                                if rsi < 30:
                                    rsi_ok = False
                                    logger.warning(f"🚫 RSI FİLTER: SHORT sinyali ama RSI={rsi:.1f} (oversold, <30)")
                            
                            if not rsi_ok:
                                continue
                            
                            # 2. Son zararlı işlemlerden sonra daha yüksek confidence gereksinimi
                            # Son 24 saatteki zararlı işlemleri kontrol et
                            try:
                                from pathlib import Path
                                import json
                                from datetime import datetime, timedelta
                                
                                positions_file = Path("runs/closed_positions.json")
                                recent_losses = 0
                                
                                if positions_file.exists():
                                    with open(positions_file, 'r') as f:
                                        closed_positions = json.load(f)
                                    
                                    # Son 24 saatteki SL pozisyonlarını say
                                    cutoff_time = datetime.now() - timedelta(hours=24)
                                    for pos in closed_positions:
                                        if pos.get('exit_reason') == 'SL':
                                            try:
                                                exit_time = datetime.fromisoformat(pos.get('exit_time', '').replace('Z', '+00:00'))
                                                if exit_time.replace(tzinfo=None) > cutoff_time:
                                                    recent_losses += 1
                                            except:
                                                pass
                                
                                # Son 24 saatte 2+ zarar varsa, confidence threshold'u artır
                                if recent_losses >= 2:
                                    min_confidence_after_losses = 0.90  # %90
                                    if conf < min_confidence_after_losses:
                                        logger.warning(f"🚫 CONFIDENCE FİLTER: Son 24 saatte {recent_losses} zarar var, confidence {conf:.2%} < {min_confidence_after_losses:.0%} - Sinyal reddedildi")
                                        continue
                                    else:
                                        logger.info(f"✅ Yüksek confidence kontrolü geçildi: {conf:.2%} >= {min_confidence_after_losses:.0%} (Son 24 saatte {recent_losses} zarar)")
                            except Exception as e:
                                logger.debug(f"Zararlı işlem kontrolü hatası: {e}")
                            
                            # 3. Volume spike kontrolü - Düşük volume'de işlem yapma
                            vol_spike = df_featured["vol_spike"].iloc[-1] if "vol_spike" in df_featured.columns else 1.0
                            if vol_spike < 0.5:  # Volume çok düşükse (0.4'ten 0.5'e yükseltildi - daha sıkı filtre)
                                logger.warning(f"🚫 VOLUME FİLTER: Volume spike çok düşük ({vol_spike:.2f} < 0.5) - Sinyal reddedildi")
                                continue
                            
                            # 4. Probability ratio kontrolü - Model belirsizliğini engelle
                            min_prob_ratio = 7.0  # Long/Short veya Short/Long ratio en az 7.0 olmalı (5.0'den yükseltildi)
                            prob_ratio = 0.0
                            
                            if side == "LONG":
                                if probs['short'] > 0:
                                    prob_ratio = probs['long'] / probs['short']
                                else:
                                    prob_ratio = float('inf')  # Short prob 0 ise ratio sonsuz
                                
                                if prob_ratio < min_prob_ratio:
                                    logger.warning(f"🚫 PROBABILITY RATIO FİLTER: LONG sinyali ama Long/Short ratio çok düşük ({prob_ratio:.2f} < {min_prob_ratio:.1f}) - Model belirsiz, sinyal reddedildi")
                                    logger.warning(f"   Probs: Long={probs['long']:.2%}, Short={probs['short']:.2%}")
                                    continue
                            elif side == "SHORT":
                                if probs['long'] > 0:
                                    prob_ratio = probs['short'] / probs['long']
                                else:
                                    prob_ratio = float('inf')  # Long prob 0 ise ratio sonsuz
                                
                                if prob_ratio < min_prob_ratio:
                                    logger.warning(f"🚫 PROBABILITY RATIO FİLTER: SHORT sinyali ama Short/Long ratio çok düşük ({prob_ratio:.2f} < {min_prob_ratio:.1f}) - Model belirsiz, sinyal reddedildi")
                                    logger.warning(f"   Probs: Long={probs['long']:.2%}, Short={probs['short']:.2%}")
                                    continue
                            
                            logger.info(f"✅ Probability ratio kontrolü geçildi: {prob_ratio:.2f} >= {min_prob_ratio:.1f}")
                            
                            # TP/SL
                            tp, sl = tp_sl_from_pct(last_price, tp_pct, sl_pct, side)
                            
                            # Log signal
                            logger.info(f"🎯 SIGNAL: {side} @ ${last_price:.2f}")
                            logger.info(f"   TP: ${tp:.2f}, SL: ${sl:.2f}, Confidence: {conf:.2%}")
                            logger.info(f"   RSI: {rsi:.1f}, Volume Spike: {vol_spike:.2f}")
                            logger.info(f"   Probs: Flat={probs['flat']:.2%}, Long={probs['long']:.2%}, Short={probs['short']:.2%}")
                            
                            # Send order (use config values)
                            trade_amount = llm_cfg.get("trade_amount_usd", 1000)
                            leverage = llm_cfg.get("leverage", 5)
                            
                            # Entry zamanını kaydet (minimum bar kontrolü için)
                            entry_time = datetime.now().isoformat()
                            
                            order_result = send_order(side, last_price, tp, sl, leverage, trade_amount)
                            
                            # Log order result immediately for debugging
                            logger.info(f"📊 Order result: {order_result} (type: {type(order_result).__name__})")
                            
                            # Entry zamanını kaydet ve entry features'ları kaydet (pozisyon açıldıysa)
                            # order_result is None if position opened successfully
                            # order_result is "LONG" or "SHORT" if position was skipped (already exists)
                            # order_result is "ERROR_*" if there was an error
                            logger.debug(f"🔍 Checking if entry time should be saved: order_result={order_result}, is None={order_result is None}, not in errors={order_result not in ['ERROR_ENTRY_FAILED', 'ERROR_POSITION_NOT_OPENED']}")
                            
                            if order_result is None or (order_result not in ["ERROR_ENTRY_FAILED", "ERROR_POSITION_NOT_OPENED"]):
                                logger.info(f"✅ Entry time save condition met: order_result={order_result}")
                                try:
                                    from pathlib import Path
                                    import json
                                    
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
                                    
                                    # Entry anındaki tüm feature'ları kaydet (SL/TP pattern analizi için)
                                    try:
                                        # Extract market features
                                        market_features = {}
                                        if "rsi" in df_featured.columns:
                                            market_features["rsi"] = float(df_featured["rsi"].iloc[-1])
                                        if "vol_spike" in df_featured.columns:
                                            market_features["vol_spike"] = float(df_featured["vol_spike"].iloc[-1])
                                        if "ema50" in df_featured.columns:
                                            market_features["ema50"] = float(df_featured["ema50"].iloc[-1])
                                        if "ema200" in df_featured.columns:
                                            market_features["ema200"] = float(df_featured["ema200"].iloc[-1])
                                        
                                        # Candle body değerini de ekle
                                        market_features["candle_body_pct"] = float(candle_body_pct)
                                        
                                        # Save entry features (window_data, feature_cols, market_features)
                                        save_entry_features(
                                            side=side,
                                            entry_price=last_price,
                                            tp_price=tp,
                                            sl_price=sl,
                                            confidence=conf,
                                            probs=probs,
                                            window_data=window_data,  # (window_size, n_features)
                                            feature_cols=feat_cols,
                                            market_features=market_features,
                                            entry_time=entry_time,
                                            symbol="BTCUSDT"
                                        )
                                        logger.info(f"✅ Entry features saved: {side} @ ${last_price:.2f} (RSI: {market_features.get('rsi', 'N/A'):.1f}, Vol Spike: {market_features.get('vol_spike', 'N/A'):.3f}, Candle Body: {candle_body_pct*100:.3f}%)")
                                    except Exception as e:
                                        logger.error(f"❌ Failed to save entry features: {e}")
                                        
                                except Exception as e:
                                    logger.warning(f"⚠️ Entry time save error: {e}")
                                    import traceback
                                    logger.warning(f"Traceback: {traceback.format_exc()}")
                            else:
                                logger.info(f"⏸️ Entry time NOT saved: order_result={order_result} (condition not met)")
                            
                            # Determine if position was opened
                            # order_result is None if position opened successfully
                            # order_result is "LONG" or "SHORT" if position was skipped (already exists)
                            # order_result is "ERROR_*" if there was an error
                            position_opened = (order_result is None)
                            active_position = None if position_opened else order_result
                            
                            logger.info(f"📊 Position opened: {position_opened}, Active position: {active_position}")
                            
                            # Save skipped signal if position was not opened due to active position
                            if not position_opened and active_position in ["LONG", "SHORT"]:
                                # Extract market features for analysis
                                market_features = {}
                                try:
                                    if "ema50" in df_featured.columns:
                                        market_features["ema50"] = float(df_featured["ema50"].iloc[-1])
                                    if "ema200" in df_featured.columns:
                                        market_features["ema200"] = float(df_featured["ema200"].iloc[-1])
                                    if "vol_spike" in df_featured.columns:
                                        market_features["vol_spike"] = float(df_featured["vol_spike"].iloc[-1])
                                    if "rsi" in df_featured.columns:
                                        market_features["rsi"] = float(df_featured["rsi"].iloc[-1])
                                except:
                                    pass
                                
                                save_skipped_signal(
                                    side=side,
                                    entry=last_price,
                                    tp=tp,
                                    sl=sl,
                                    confidence=conf,
                                    probs=probs,
                                    active_position=active_position,
                                    features=market_features,
                                    symbol="BTCUSDT"
                                )
                            
                            # Telegram alert
                            payload = {
                                "symbol": "BTCUSDT",
                                "side": side,
                                "entry": last_price,
                                "tp": tp,
                                "sl": sl,
                                "confidence": conf,
                                "probs": probs,
                                "leverage": leverage,
                                "qty_usd": trade_amount,
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
            time.sleep(60)

if __name__ == "__main__":
    main()

