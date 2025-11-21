#!/usr/bin/env python3
"""Backtest different timeframe combinations for signal generation and trend checking."""

import json
import sys
from pathlib import Path
import torch
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fetch_binance import load_csv, download_klines
from src.features import add_features, get_feature_columns
from src.models.transformer import SeqClassifier
from src.utils import load_feat_cols
from src.infer import predict_proba, decide_side, tp_sl_from_pct
from src.utils import calculate_profit_factor, calculate_drawdown
import ccxt

def fetch_bars(symbol, timeframe, limit=500):
    """Fetch bars from Binance."""
    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df

def run_backtest_timeframe_combo(
    model: SeqClassifier,
    signal_df: pd.DataFrame,
    trend_df: pd.DataFrame,
    feature_cols: list,
    window: int,
    tp_pct: float,
    sl_pct: float,
    thr_long: float,
    thr_short: float,
    fee: float,
    slippage: float,
    signal_timeframe: str,
    trend_timeframe: str,
) -> dict:
    """
    Run backtest with different timeframe combinations.
    
    Args:
        signal_df: DataFrame for signal generation (e.g., 3m or 15m)
        trend_df: DataFrame for trend checking (e.g., 15m or 30m)
    """
    signals = []
    trades = []
    rejected_signals = []
    
    n = len(signal_df)
    
    # Align trend data with signal data
    # For each signal bar, find corresponding trend bar
    for i in range(window, n):
        # Get signal window
        window_data = signal_df[feature_cols].iloc[i-window:i].values
        
        # Predict (using signal timeframe)
        probs = predict_proba(model, window_data)
        side, conf = decide_side(probs, thr_long, thr_short)
        
        if side == "FLAT":
            continue
        
        signals.append({
            "idx": i,
            "side": side,
            "conf": conf,
            "time": signal_df.index[i]
        })
        
        # Trend check (if trend timeframe specified)
        if trend_timeframe and trend_df is not None:
            # Get trend info from trend timeframe
            signal_time = signal_df.index[i]
            
            # Find closest trend bar (before or at signal time)
            trend_bars_before = trend_df[trend_df.index <= signal_time]
            if len(trend_bars_before) < 50:  # Need enough trend data
                continue
            
            # Use last trend bar before or at signal time
            trend_idx = len(trend_bars_before) - 1
            trend_ema50 = trend_bars_before["ema50"].iloc[trend_idx] if "ema50" in trend_bars_before.columns else signal_df["close"].iloc[i]
            trend_ema200 = trend_bars_before["ema200"].iloc[trend_idx] if "ema200" in trend_bars_before.columns else signal_df["close"].iloc[i]
            
            # Signal timeframe EMA (for comparison)
            signal_ema50 = signal_df["ema50"].iloc[i] if "ema50" in signal_df.columns else signal_df["close"].iloc[i]
            signal_ema200 = signal_df["ema200"].iloc[i] if "ema200" in signal_df.columns else signal_df["close"].iloc[i]
            
            # Trend check
            trend_ok = False
            if side == "LONG":
                trend_ok = (trend_ema50 > trend_ema200) and (signal_ema50 > signal_ema200)
            elif side == "SHORT":
                trend_ok = (trend_ema50 < trend_ema200) and (signal_ema50 < signal_ema200)
            
            if not trend_ok:
                rejected_signals.append({
                    "idx": i,
                    "side": side,
                    "conf": conf,
                    "trend_ema50": trend_ema50,
                    "trend_ema200": trend_ema200,
                    "signal_ema50": signal_ema50,
                    "signal_ema200": signal_ema200,
                })
                continue
        else:
            # No trend check - all signals pass
            pass
        
        # Entry on next bar open
        if i + 1 >= n:
            continue
        
        entry_price = signal_df["open"].iloc[i+1]
        
        # Calculate TP/SL
        tp, sl = tp_sl_from_pct(entry_price, tp_pct, sl_pct, side)
        
        # Look ahead to find exit
        for j in range(i+1, min(i+1+200, n)):
            high = signal_df["high"].iloc[j]
            low = signal_df["low"].iloc[j]
            close = signal_df["close"].iloc[j]
            
            if side == "LONG":
                if high >= tp:
                    exit_price = tp
                    pnl = (exit_price - entry_price) / entry_price
                    exit_reason = "TP"
                    break
                elif low <= sl:
                    exit_price = sl
                    pnl = (exit_price - entry_price) / entry_price
                    exit_reason = "SL"
                    break
            elif side == "SHORT":
                if low <= tp:
                    exit_price = tp
                    pnl = (entry_price - exit_price) / entry_price
                    exit_reason = "TP"
                    break
                elif high >= sl:
                    exit_price = sl
                    pnl = (entry_price - exit_price) / entry_price
                    exit_reason = "SL"
                    break
        else:
            # No exit, close at last bar
            exit_price = close
            if side == "LONG":
                pnl = (exit_price - entry_price) / entry_price
            else:
                pnl = (entry_price - exit_price) / entry_price
            exit_reason = "TIME"
        
        # Apply slippage
        entry_price *= (1 + slippage) if side == "LONG" else (1 - slippage)
        exit_price *= (1 - slippage) if side == "LONG" else (1 + slippage)
        
        # Apply fee
        pnl -= (fee * 2)  # Entry + exit
        
        trades.append({
            "entry_idx": i+1,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "tp": tp,
            "sl": sl,
            "pnl": pnl,
            "conf": conf,
            "exit_reason": exit_reason,
        })
    
    # Calculate metrics
    if not trades:
        return {
            "trades": 0,
            "signals": len(signals),
            "rejected": len(rejected_signals),
            "equity": [1.0],
            "final_equity": 1.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "tp_count": 0,
            "sl_count": 0,
        }
    
    df_trades = pd.DataFrame(trades)
    pnl_array = np.array(df_trades["pnl"])
    
    # Equity curve
    equity = 1.0 + np.cumsum(pnl_array)
    
    # Profit factor
    pf = calculate_profit_factor(pnl_array)
    
    # Win rate
    win_rate = (pnl_array > 0).sum() / len(pnl_array) * 100
    
    # Drawdown
    dd_result = calculate_drawdown(equity)
    
    # TP/SL counts
    tp_count = (df_trades["exit_reason"] == "TP").sum()
    sl_count = (df_trades["exit_reason"] == "SL").sum()
    
    return {
        "trades": len(trades),
        "signals": len(signals),
        "rejected": len(rejected_signals),
        "equity": equity.tolist(),
        "final_equity": float(equity[-1]),
        "profit_factor": float(pf),
        "win_rate": float(win_rate),
        "max_drawdown": float(dd_result["max_dd_pct"]),
        "total_pnl": float(pnl_array.sum()),
        "avg_pnl": float(pnl_array.mean()),
        "tp_count": int(tp_count),
        "sl_count": int(sl_count),
        "trades_df": df_trades,
    }

def main():
    print("=" * 100)
    print("TIMEFRAME COMBINATION BACKTEST")
    print("=" * 100)
    
    # Load config
    config_path = Path("configs/train_3m.json")
    with open(config_path, "r") as f:
        config = json.load(f)
    
    llm_config_path = Path("configs/llm_config.json")
    with open(llm_config_path, "r") as f:
        llm_config = json.load(f)
    
    trading_params = llm_config.get("trading_params", {})
    tp_pct = trading_params.get("tp_pct", 0.008)
    sl_pct = trading_params.get("sl_pct", 0.008)
    thr_long = trading_params.get("thr_long", 0.85)
    thr_short = trading_params.get("thr_short", 0.85)
    
    symbol = config["symbol"]
    
    print(f"\n📊 Settings:")
    print(f"   Symbol: {symbol}")
    print(f"   TP: {tp_pct*100:.2f}%")
    print(f"   SL: {sl_pct*100:.2f}%")
    print(f"   Threshold Long: {thr_long*100:.1f}%")
    print(f"   Threshold Short: {thr_short*100:.1f}%")
    
    # Download data for all timeframes (GERÇEK VERİ - 60 günlük)
    print(f"\n📥 Downloading REAL DATA from Binance for all timeframes (last 60 days)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    timeframes = ["3m", "5m", "15m", "30m", "1h"]
    data_dict = {}
    
    for tf in timeframes:
        print(f"   Downloading {tf}...")
        try:
            # Gerçek Binance verisi - daha fazla bar için limit artır
            limit = 2000 if tf in ["3m", "5m"] else 1000
            df = fetch_bars(symbol=symbol, timeframe=tf, limit=limit)
            df = add_features(df)
            data_dict[tf] = df
            print(f"      ✅ {tf}: {len(df)} bars (Period: {df.index[0]} to {df.index[-1]})")
        except Exception as e:
            print(f"      ❌ {tf}: {e}")
            import traceback
            traceback.print_exc()
    
    # Load model
    model_path = Path("models/seqcls.pt")
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        return
    
    feat_cols = load_feat_cols(Path("models/feat_cols.json"))
    model = SeqClassifier(n_features=len(feat_cols))
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()
    
    print(f"\n✅ Model loaded: {len(feat_cols)} features")
    
    # Test combinations - TÜM KOMBİNASYONLAR
    combinations = [
        # Mevcut ve yakın varyasyonlar
        {
            "name": "1. Mevcut: 3m Sinyal + 15m Trend",
            "signal": "3m",
            "trend": "15m"
        },
        {
            "name": "2. 3m Sinyal + 30m Trend",
            "signal": "3m",
            "trend": "30m"
        },
        {
            "name": "3. 3m Sinyal + 1h Trend",
            "signal": "3m",
            "trend": "1h"
        },
        # 5m kombinasyonları
        {
            "name": "4. 5m Sinyal + 15m Trend",
            "signal": "5m",
            "trend": "15m"
        },
        {
            "name": "5. 5m Sinyal + 30m Trend",
            "signal": "5m",
            "trend": "30m"
        },
        {
            "name": "6. 5m Sinyal + 1h Trend",
            "signal": "5m",
            "trend": "1h"
        },
        # 15m kombinasyonları (model 3m'de eğitilmiş - suboptimal)
        {
            "name": "7. 15m Sinyal + 30m Trend",
            "signal": "15m",
            "trend": "30m"
        },
        {
            "name": "8. 15m Sinyal + 1h Trend",
            "signal": "15m",
            "trend": "1h"
        },
        # Sadece trend kontrolü olmadan (karşılaştırma için)
        {
            "name": "9. 3m Sinyal (Trend Kontrolü YOK)",
            "signal": "3m",
            "trend": None  # Trend kontrolü yok
        },
        {
            "name": "10. 5m Sinyal (Trend Kontrolü YOK)",
            "signal": "5m",
            "trend": None
        }
    ]
    
    results = []
    
    print(f"\n🔄 Running backtests...")
    print("=" * 100)
    
    for combo in combinations:
        signal_tf = combo["signal"]
        trend_tf = combo.get("trend")  # None olabilir
        
        if signal_tf not in data_dict:
            print(f"⚠️ Skipping {combo['name']}: Missing signal data ({signal_tf})")
            continue
        
        if trend_tf is not None and trend_tf not in data_dict:
            print(f"⚠️ Skipping {combo['name']}: Missing trend data ({trend_tf})")
            continue
        
        print(f"\n📊 Testing: {combo['name']}")
        print("-" * 100)
        
        signal_df = data_dict[signal_tf]
        trend_df = data_dict.get(trend_tf) if trend_tf else None
        
        # Ensure we have feature columns
        signal_feature_cols = [col for col in feat_cols if col in signal_df.columns]
        if len(signal_feature_cols) < len(feat_cols) * 0.8:  # At least 80% of features
            print(f"⚠️ Missing features in {signal_tf} data")
            continue
        
        result = run_backtest_timeframe_combo(
            model=model,
            signal_df=signal_df,
            trend_df=trend_df,
            feature_cols=signal_feature_cols,
            window=config["window"],
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            thr_long=thr_long,
            thr_short=thr_short,
            fee=config["fee"],
            slippage=config["slippage"],
            signal_timeframe=signal_tf,
            trend_timeframe=trend_tf if trend_tf else "none",
        )
        
        result["name"] = combo["name"]
        result["signal_timeframe"] = signal_tf
        result["trend_timeframe"] = trend_tf
        results.append(result)
        
        print(f"   Trades: {result['trades']}")
        print(f"   Signals: {result['signals']} (Rejected: {result['rejected']}, Pass Rate: {(result['signals']-result['rejected'])/result['signals']*100 if result['signals']>0 else 0:.1f}%)")
        print(f"   Final Equity: {result['final_equity']:.4f} ({result['final_equity']*100-100:+.2f}%)")
        print(f"   Profit Factor: {result['profit_factor']:.2f}")
        print(f"   Win Rate: {result['win_rate']:.2f}%")
        print(f"   Max Drawdown: {result['max_drawdown']:.2f}%")
        print(f"   TP: {result['tp_count']} | SL: {result['sl_count']}")
        print(f"   Total PnL: {result['total_pnl']*100:+.2f}%")
        print(f"   Avg PnL: {result['avg_pnl']*100:+.2f}%")
    
    # Summary comparison
    print(f"\n" + "=" * 100)
    print("📊 SUMMARY COMPARISON")
    print("=" * 100)
    
    if not results:
        print("❌ No results to compare")
        return
    
    # Sort by final equity
    results_sorted = sorted(results, key=lambda x: x['final_equity'], reverse=True)
    
    print(f"\n{'Combination':<40} {'Trades':>8} {'Equity':>12} {'PF':>8} {'WR%':>8} {'DD%':>8} {'TP':>6} {'SL':>6} {'Pass%':>8}")
    print("-" * 100)
    
    for r in results_sorted:
        equity_pct = (r['final_equity'] - 1.0) * 100
        pass_rate = ((r['signals']-r['rejected'])/r['signals']*100) if r['signals']>0 else 0
        print(f"{r['name']:<40} {r['trades']:>8} {equity_pct:>+11.2f}% {r['profit_factor']:>7.2f} "
              f"{r['win_rate']:>7.1f}% {r['max_drawdown']:>7.2f}% {r['tp_count']:>6} {r['sl_count']:>6} {pass_rate:>7.1f}%")
    
    # Best combination
    best = results_sorted[0]
    print(f"\n🏆 BEST COMBINATION: {best['name']}")
    print(f"   Final Equity: {best['final_equity']:.4f} ({best['final_equity']*100-100:+.2f}%)")
    print(f"   Profit Factor: {best['profit_factor']:.2f}")
    print(f"   Win Rate: {best['win_rate']:.2f}%")
    print(f"   Trades: {best['trades']} (TP: {best['tp_count']}, SL: {best['sl_count']})")
    print(f"   Signal Pass Rate: {((best['signals']-best['rejected'])/best['signals']*100) if best['signals']>0 else 0:.1f}%")
    
    # Save results
    results_file = Path("runs/timeframe_comparison_backtest.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to JSON-serializable format
    results_json = []
    for r in results:
        r_copy = {k: v for k, v in r.items() if k not in ['trades_df', 'equity']}
        results_json.append(r_copy)
    
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "config": {
                "tp_pct": tp_pct,
                "sl_pct": sl_pct,
                "thr_long": thr_long,
                "thr_short": thr_short,
            },
            "results": results_json,
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    print("-" * 100)
    
    current_result = next((r for r in results if "Mevcut" in r['name']), None)
    if current_result:
        current_rank = results_sorted.index(current_result) + 1
        print(f"   Mevcut yaklaşım: {current_rank}. sırada (Toplam {len(results)} kombinasyon)")
        
        if current_rank > 1:
            best_improvement = ((best['final_equity'] - current_result['final_equity']) / current_result['final_equity']) * 100
            print(f"   ⚠️  En iyi kombinasyon {best_improvement:+.2f}% daha iyi performans gösteriyor")
            print(f"   → Önerilen: {best['name']} ayarlarına geçiş yapılmalı")
            
            if best['signal_timeframe'] != "3m":
                print(f"   ⚠️  Model {best['signal_timeframe']} için yeniden eğitilmeli (şu an 3m'de eğitilmiş)")
        else:
            print(f"   ✅ Mevcut yaklaşım en iyi performansı gösteriyor")

if __name__ == "__main__":
    main()

