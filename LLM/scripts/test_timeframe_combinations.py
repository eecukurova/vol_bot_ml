#!/usr/bin/env python3
"""Test different timeframe combinations for signal generation and trend checking."""

import sys
from pathlib import Path
import json
import ccxt
import pandas as pd
import torch
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.transformer import SeqClassifier
from src.utils import load_feat_cols
from src.features import add_features
from src.infer import predict_proba, decide_side, tp_sl_from_pct

def fetch_bars(symbol="BTCUSDT", timeframe="3m", limit=200):
    """Fetch bars from Binance."""
    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df

def test_timeframe_combination(
    model,
    feat_cols,
    window,
    symbol,
    signal_timeframe,
    trend_timeframe,
    thr_long,
    thr_short,
    days_back=7
):
    """Test a specific timeframe combination."""
    print(f"\n{'='*80}")
    print(f"Testing: Signal={signal_timeframe}, Trend={trend_timeframe}")
    print(f"{'='*80}")
    
    # Fetch data
    print(f"📥 Fetching {signal_timeframe} data...")
    df_signal = fetch_bars(symbol=symbol, timeframe=signal_timeframe, limit=500)
    df_signal = add_features(df_signal)
    
    print(f"📥 Fetching {trend_timeframe} data...")
    df_trend = fetch_bars(symbol=symbol, timeframe=trend_timeframe, limit=500)
    df_trend = add_features(df_trend)
    
    # Align timeframes
    # Get last N bars from signal timeframe
    n_bars = min(len(df_signal), 200)
    df_signal = df_signal.iloc[-n_bars:]
    
    # Get corresponding trend bars
    start_time = df_signal.index[0]
    end_time = df_signal.index[-1]
    df_trend_aligned = df_trend[(df_trend.index >= start_time) & (df_trend.index <= end_time)]
    
    if len(df_trend_aligned) < 50:
        print(f"⚠️ Not enough trend data: {len(df_trend_aligned)} bars")
        return None
    
    signals = []
    passed_signals = []
    rejected_signals = []
    
    # Test each bar
    for i in range(window, len(df_signal)):
        # Get signal
        window_data = df_signal[feat_cols].iloc[i-window:i].values
        probs = predict_proba(model, window_data)
        side, conf = decide_side(probs, thr_long, thr_short)
        
        if side == "FLAT":
            continue
        
        signals.append({
            "time": df_signal.index[i],
            "side": side,
            "conf": conf,
            "probs": probs,
            "price": float(df_signal["close"].iloc[i])
        })
        
        # Get trend info
        signal_time = df_signal.index[i]
        
        # Find closest trend bar
        trend_idx = df_trend_aligned.index.get_indexer([signal_time], method='nearest')[0]
        if trend_idx < 0:
            continue
        
        trend_ema50 = df_trend_aligned["ema50"].iloc[trend_idx] if "ema50" in df_trend_aligned.columns else df_signal["close"].iloc[i]
        trend_ema200 = df_trend_aligned["ema200"].iloc[trend_idx] if "ema200" in df_trend_aligned.columns else df_signal["close"].iloc[i]
        
        # 3m/15m EMA (for comparison)
        ema50_signal = df_signal["ema50"].iloc[i] if "ema50" in df_signal.columns else df_signal["close"].iloc[i]
        ema200_signal = df_signal["ema200"].iloc[i] if "ema200" in df_signal.columns else df_signal["close"].iloc[i]
        
        # Trend check
        trend_ok = False
        if side == "LONG":
            trend_ok = (trend_ema50 > trend_ema200) and (ema50_signal > ema200_signal)
        elif side == "SHORT":
            trend_ok = (trend_ema50 < trend_ema200) and (ema50_signal < ema200_signal)
        
        if trend_ok:
            passed_signals.append({
                "time": signal_time,
                "side": side,
                "conf": conf,
                "trend_ema50": trend_ema50,
                "trend_ema200": trend_ema200,
                "signal_ema50": ema50_signal,
                "signal_ema200": ema200_signal
            })
        else:
            rejected_signals.append({
                "time": signal_time,
                "side": side,
                "conf": conf,
                "trend_ema50": trend_ema50,
                "trend_ema200": trend_ema200,
                "signal_ema50": ema50_signal,
                "signal_ema200": ema200_signal,
                "reason": "trend_mismatch"
            })
    
    # Results
    total_signals = len(signals)
    passed_count = len(passed_signals)
    rejected_count = len(rejected_signals)
    pass_rate = (passed_count / total_signals * 100) if total_signals > 0 else 0
    
    print(f"\n📊 Results:")
    print(f"   Total Signals: {total_signals}")
    print(f"   Passed: {passed_count} ({pass_rate:.1f}%)")
    print(f"   Rejected: {rejected_count} ({100-pass_rate:.1f}%)")
    
    # Signal quality (confidence distribution)
    if passed_signals:
        confs = [s["conf"] for s in passed_signals]
        print(f"   Avg Confidence (Passed): {np.mean(confs):.2%}")
        print(f"   Min Confidence (Passed): {np.min(confs):.2%}")
        print(f"   Max Confidence (Passed): {np.max(confs):.2%}")
    
    if rejected_signals:
        confs = [s["conf"] for s in rejected_signals]
        print(f"   Avg Confidence (Rejected): {np.mean(confs):.2%}")
    
    return {
        "signal_timeframe": signal_timeframe,
        "trend_timeframe": trend_timeframe,
        "total_signals": total_signals,
        "passed": passed_count,
        "rejected": rejected_count,
        "pass_rate": pass_rate,
        "passed_signals": passed_signals,
        "rejected_signals": rejected_signals
    }

def main():
    print("="*80)
    print("TIMEFRAME COMBINATION TEST")
    print("="*80)
    
    # Load config
    with open("configs/llm_config.json", "r") as f:
        llm_cfg = json.load(f)
    
    with open("configs/train_3m.json", "r") as f:
        train_cfg = json.load(f)
    
    # Load model
    model_path = Path("models/seqcls.pt")
    feat_cols_path = Path("models/feat_cols.json")
    
    feat_cols = load_feat_cols(feat_cols_path)
    model = SeqClassifier(n_features=len(feat_cols))
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()
    
    window = train_cfg["window"]
    symbol = llm_cfg["symbol"]
    trading_params = llm_cfg.get("trading_params", {})
    thr_long = trading_params.get("thr_long", 0.85)
    thr_short = trading_params.get("thr_short", 0.85)
    
    print(f"\n📊 Model: {len(feat_cols)} features, window={window}")
    print(f"📈 Symbol: {symbol}")
    print(f"🎯 Thresholds: Long={thr_long}, Short={thr_short}")
    
    # Test combinations
    combinations = [
        {
            "name": "Mevcut: 3m Sinyal + 15m Trend",
            "signal": "3m",
            "trend": "15m"
        },
        {
            "name": "Yeni: 15m Sinyal + 30m Trend",
            "signal": "15m",
            "trend": "30m"
        },
        {
            "name": "Alternatif 1: 5m Sinyal + 15m Trend",
            "signal": "5m",
            "trend": "15m"
        },
        {
            "name": "Alternatif 2: 15m Sinyal + 1h Trend",
            "signal": "15m",
            "trend": "1h"
        }
    ]
    
    results = []
    
    for combo in combinations:
        try:
            result = test_timeframe_combination(
                model=model,
                feat_cols=feat_cols,
                window=window,
                symbol=symbol,
                signal_timeframe=combo["signal"],
                trend_timeframe=combo["trend"],
                thr_long=thr_long,
                thr_short=thr_short
            )
            if result:
                result["name"] = combo["name"]
                results.append(result)
        except Exception as e:
            print(f"❌ Error testing {combo['name']}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary comparison
    print(f"\n{'='*80}")
    print("SUMMARY COMPARISON")
    print(f"{'='*80}")
    
    print(f"\n{'Combination':<40} {'Signals':>10} {'Passed':>10} {'Rejected':>10} {'Pass Rate':>12}")
    print("-"*80)
    
    for r in results:
        print(f"{r['name']:<40} {r['total_signals']:>10} {r['passed']:>10} {r['rejected']:>10} {r['pass_rate']:>11.1f}%")
    
    # Best combination
    if results:
        best = max(results, key=lambda x: x['pass_rate'])
        print(f"\n🏆 Best Pass Rate: {best['name']} ({best['pass_rate']:.1f}%)")
        
        # Save results
        results_file = Path("runs/timeframe_comparison.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to JSON-serializable
        results_json = []
        for r in results:
            r_copy = {k: v for k, v in r.items() if k not in ['passed_signals', 'rejected_signals']}
            results_json.append(r_copy)
        
        with open(results_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "thr_long": thr_long,
                "thr_short": thr_short,
                "results": results_json
            }, f, indent=2)
        
        print(f"\n💾 Results saved to: {results_file}")

if __name__ == "__main__":
    main()

