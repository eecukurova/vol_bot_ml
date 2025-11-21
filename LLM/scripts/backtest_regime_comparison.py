#!/usr/bin/env python3
"""Comprehensive backtest comparing different regime filter settings."""

import json
import sys
from pathlib import Path
import torch
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fetch_binance import load_csv, download_klines
from src.features import add_features, get_feature_columns
from src.models.transformer import SeqClassifier
from src.utils import load_feat_cols
from src.infer import predict_proba, decide_side, tp_sl_from_pct
from src.utils import calculate_profit_factor, calculate_drawdown
import numpy as np

def run_backtest_with_regime(
    model: SeqClassifier,
    df: pd.DataFrame,
    feature_cols: list,
    window: int,
    tp_pct: float,
    sl_pct: float,
    thr_long: float,
    thr_short: float,
    fee: float,
    slippage: float,
    vol_spike_threshold: float = 0.4,
    use_ema_filter: bool = True,
    use_vol_filter: bool = True,
) -> dict:
    """
    Run backtest with regime filter.
    
    Args:
        vol_spike_threshold: Volume spike threshold (0.4, 0.3, 0.25, or None to disable)
        use_ema_filter: Whether to use EMA50/EMA200 filter
        use_vol_filter: Whether to use volume spike filter
    """
    signals = []
    trades = []
    rejected_signals = []
    
    n = len(df)
    
    for i in range(window, n):
        # Get window
        window_data = df[feature_cols].iloc[i-window:i].values
        
        # Predict
        probs = predict_proba(model, window_data)
        side, conf = decide_side(probs, thr_long, thr_short)
        
        if side == "FLAT":
            continue
        
        # Regime filter
        ema50 = df["ema50"].iloc[i] if "ema50" in df.columns else df["close"].iloc[i]
        ema200 = df["ema200"].iloc[i] if "ema200" in df.columns else df["close"].iloc[i]
        vol_spike = df["vol_spike"].iloc[i] if "vol_spike" in df.columns else 1.0
        
        regime_ok = True
        
        if use_ema_filter:
            if side == "LONG":
                regime_ok = regime_ok and (ema50 > ema200)
            elif side == "SHORT":
                regime_ok = regime_ok and (ema50 < ema200)
        
        if use_vol_filter and vol_spike_threshold is not None:
            regime_ok = regime_ok and (vol_spike > vol_spike_threshold)
        
        if not regime_ok:
            rejected_signals.append({
                "idx": i,
                "side": side,
                "conf": conf,
                "ema50": ema50,
                "ema200": ema200,
                "vol_spike": vol_spike,
            })
            continue
        
        signals.append({
            "idx": i,
            "side": side,
            "conf": conf,
        })
        
        # Entry on next bar open
        if i + 1 >= n:
            continue
        
        entry_price = df["open"].iloc[i+1]
        
        # Calculate TP/SL
        tp, sl = tp_sl_from_pct(entry_price, tp_pct, sl_pct, side)
        
        # Look ahead to find exit
        for j in range(i+1, min(i+1+200, n)):
            high = df["high"].iloc[j]
            low = df["low"].iloc[j]
            close = df["close"].iloc[j]
            
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
    print("LLM Regime Filter Backtest Comparison")
    print("=" * 100)
    
    # Load config
    config_path = Path("configs/train_3m.json")
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Load LLM config for current settings
    llm_config_path = Path("configs/llm_config.json")
    with open(llm_config_path, "r") as f:
        llm_config = json.load(f)
    
    trading_params = llm_config.get("trading_params", {})
    tp_pct = trading_params.get("tp_pct", 0.008)
    sl_pct = trading_params.get("sl_pct", 0.008)
    thr_long = trading_params.get("thr_long", 0.85)
    thr_short = trading_params.get("thr_short", 0.85)
    
    print(f"\n📊 Current Settings:")
    print(f"   TP: {tp_pct*100:.2f}%")
    print(f"   SL: {sl_pct*100:.2f}%")
    print(f"   Threshold Long: {thr_long*100:.1f}%")
    print(f"   Threshold Short: {thr_short*100:.1f}%")
    
    # Download latest data (last 30 days for backtest)
    print(f"\n📥 Downloading latest data (last 30 days)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    csv_path = download_klines(
        symbol=config["symbol"],
        interval=config["timeframe"],
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        data_dir=Path("data"),
    )
    
    if csv_path is None:
        print("❌ Failed to download data")
        return
    
    # Load data
    print(f"\n📊 Loading data...")
    df = load_csv(config["symbol"], config["timeframe"])
    df = add_features(df)
    feature_cols = get_feature_columns(df)
    
    print(f"   Total bars: {len(df)}")
    if isinstance(df.index, pd.DatetimeIndex):
        print(f"   Period: {df.index.min()} to {df.index.max()}")
    else:
        print(f"   Period: N/A (index is not datetime)")
    
    # Load model
    model_path = Path("models/seqcls.pt")
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        return
    
    feat_cols = load_feat_cols(Path("models/feat_cols.json"))
    model = SeqClassifier(n_features=len(feat_cols))
    model.load_state_dict(torch.load(model_path))
    model.eval()
    
    print(f"✅ Model loaded: {len(feat_cols)} features")
    
    # Test scenarios
    scenarios = [
        {
            "name": "Mevcut (Vol 0.4 + EMA)",
            "vol_threshold": 0.4,
            "use_ema": True,
            "use_vol": True,
        },
        {
            "name": "Vol 0.3 + EMA",
            "vol_threshold": 0.3,
            "use_ema": True,
            "use_vol": True,
        },
        {
            "name": "Vol 0.25 + EMA",
            "vol_threshold": 0.25,
            "use_ema": True,
            "use_vol": True,
        },
        {
            "name": "Sadece Vol 0.3 (EMA yok)",
            "vol_threshold": 0.3,
            "use_ema": False,
            "use_vol": True,
        },
        {
            "name": "Sadece Vol 0.25 (EMA yok)",
            "vol_threshold": 0.25,
            "use_ema": False,
            "use_vol": True,
        },
        {
            "name": "Regime Filter YOK",
            "vol_threshold": None,
            "use_ema": False,
            "use_vol": False,
        },
    ]
    
    results = []
    
    print(f"\n🔄 Running backtests...")
    print("=" * 100)
    
    for scenario in scenarios:
        print(f"\n📊 Testing: {scenario['name']}")
        print("-" * 100)
        
        result = run_backtest_with_regime(
            model=model,
            df=df,
            feature_cols=feature_cols,
            window=config["window"],
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            thr_long=thr_long,
            thr_short=thr_short,
            fee=config["fee"],
            slippage=config["slippage"],
            vol_spike_threshold=scenario["vol_threshold"],
            use_ema_filter=scenario["use_ema"],
            use_vol_filter=scenario["use_vol"],
        )
        
        result["scenario"] = scenario["name"]
        results.append(result)
        
        print(f"   Trades: {result['trades']}")
        print(f"   Signals: {result['signals']} (Rejected: {result['rejected']})")
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
    
    # Sort by final equity
    results_sorted = sorted(results, key=lambda x: x['final_equity'], reverse=True)
    
    print(f"\n{'Scenario':<40} {'Trades':>8} {'Equity':>12} {'PF':>8} {'WR%':>8} {'DD%':>8} {'TP':>6} {'SL':>6}")
    print("-" * 100)
    
    for r in results_sorted:
        equity_pct = (r['final_equity'] - 1.0) * 100
        print(f"{r['scenario']:<40} {r['trades']:>8} {equity_pct:>+11.2f}% {r['profit_factor']:>7.2f} "
              f"{r['win_rate']:>7.1f}% {r['max_drawdown']:>7.2f}% {r['tp_count']:>6} {r['sl_count']:>6}")
    
    # Best scenario
    best = results_sorted[0]
    print(f"\n🏆 BEST SCENARIO: {best['scenario']}")
    print(f"   Final Equity: {best['final_equity']:.4f} ({best['final_equity']*100-100:+.2f}%)")
    print(f"   Profit Factor: {best['profit_factor']:.2f}")
    print(f"   Win Rate: {best['win_rate']:.2f}%")
    print(f"   Trades: {best['trades']} (TP: {best['tp_count']}, SL: {best['sl_count']})")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    print("-" * 100)
    
    current_result = next((r for r in results if "Mevcut" in r['scenario']), None)
    if current_result:
        current_rank = results_sorted.index(current_result) + 1
        print(f"   Mevcut ayarlar: {current_rank}. sırada (Toplam {len(results)} senaryo)")
        
        if current_rank > 1:
            best_improvement = ((best['final_equity'] - current_result['final_equity']) / current_result['final_equity']) * 100
            print(f"   ⚠️  En iyi senaryo {best_improvement:+.2f}% daha iyi performans gösteriyor")
            print(f"   → Önerilen: {best['scenario']} ayarlarına geçiş yapılmalı")
        else:
            print(f"   ✅ Mevcut ayarlar en iyi performansı gösteriyor")
    
    # Save results
    results_file = Path("runs/backtest_regime_comparison.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to JSON-serializable format
    results_json = []
    for r in results:
        r_copy = {k: v for k, v in r.items() if k != 'trades_df'}
        results_json.append(r_copy)
    
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "config": {
                "tp_pct": tp_pct,
                "sl_pct": sl_pct,
                "thr_long": thr_long,
                "thr_short": thr_short,
            },
            "results": results_json,
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")

if __name__ == "__main__":
    main()

