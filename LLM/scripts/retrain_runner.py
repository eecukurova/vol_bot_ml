"""
Automated retraining script with walk-forward validation and model selection.

Features:
1. Weekly retraining: Trains model with latest data
2. Walk-forward validation: Tests on recent unseen data
3. Automatic model selection: Deploys new model only if it outperforms current
"""

import json
import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
import typer
import pandas as pd
import torch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fetch_binance import load_csv, save_csv, download_klines
from src.features import add_features, get_feature_columns
from src.labeling import make_barrier_labels
from src.dataset import make_windows
from src.train import train_model, save_model
from src.utils import time_based_split, set_seed, load_feat_cols
from src.models.transformer import SeqClassifier
from src.backtest_core import run_backtest
from src.hard_negatives_loader import add_hard_negatives_to_training

app = typer.Typer()

# Model comparison weights (higher = more important)
WEIGHTS = {
    "profit_factor": 0.4,    # Most important
    "win_rate": 0.3,
    "max_drawdown": 0.2,     # Lower is better, so we'll invert
    "final_equity": 0.1,
}


def download_latest_data(
    symbol: str,
    interval: str,
    days_back: int = 7,
    data_dir: Path = Path("data"),
) -> Path:
    """Download latest data (last N days)."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    print(f"📥 Downloading latest data: {start_date.date()} to {end_date.date()}")
    csv_path = download_klines(
        symbol=symbol,
        interval=interval,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        data_dir=data_dir,
    )
    
    if csv_path is None:
        raise RuntimeError("Failed to download data")
    
    return csv_path


def evaluate_model(
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
    test_weeks: int = 2,
) -> Dict:
    """
    Evaluate model on recent data (walk-forward validation).
    
    Args:
        test_weeks: Number of weeks to use for testing (from end of data)
    """
    # Get test period (last N weeks)
    df_sorted = df.sort_values("time")
    test_start = df_sorted["time"].max() - timedelta(weeks=test_weeks)
    df_test = df_sorted[df_sorted["time"] >= test_start].copy()
    
    if len(df_test) < window * 2:
        print(f"⚠️  Test data too short: {len(df_test)} bars (need {window * 2})")
        return None
    
    print(f"🧪 Testing on last {test_weeks} weeks: {len(df_test)} bars")
    print(f"   Period: {df_test['time'].min()} to {df_test['time'].max()}")
    
    result = run_backtest(
        model=model,
        df=df_test,
        feature_cols=feature_cols,
        window=window,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        thr_long=thr_long,
        thr_short=thr_short,
        fee=fee,
        slippage=slippage,
    )
    
    return result


def compare_models(
    old_metrics: Dict,
    new_metrics: Dict,
    min_improvement: float = 0.05,  # 5% minimum improvement
) -> tuple[bool, float]:
    """
    Compare two models and decide if new model is better.
    
    Returns:
        (is_better, improvement_score)
    """
    if old_metrics is None:
        print("✅ No old model to compare, deploying new model")
        return True, 1.0
    
    # Calculate weighted score
    def score(metrics: Dict) -> float:
        # Higher profit factor = better (multiply by weight)
        pf_score = metrics.get("profit_factor", 0.0) * WEIGHTS["profit_factor"]
        
        # Higher win rate = better
        wr_score = (metrics.get("win_rate", 0.0) / 100.0) * WEIGHTS["win_rate"]
        
        # Lower drawdown = better (invert)
        dd_score = (1.0 - min(metrics.get("max_drawdown", 100.0) / 100.0, 1.0)) * WEIGHTS["max_drawdown"]
        
        # Higher final equity = better (normalize)
        equity_score = min(metrics.get("final_equity", 0.0) / 2.0, 1.0) * WEIGHTS["final_equity"]
        
        return pf_score + wr_score + dd_score + equity_score
    
    old_score = score(old_metrics)
    new_score = score(new_metrics)
    
    improvement = (new_score - old_score) / old_score if old_score > 0 else float('inf')
    
    print(f"\n📊 Model Comparison:")
    print(f"   Old Score: {old_score:.4f}")
    print(f"   New Score: {new_score:.4f}")
    print(f"   Improvement: {improvement*100:.2f}%")
    
    is_better = improvement >= min_improvement
    
    if is_better:
        print(f"✅ New model is better (≥{min_improvement*100:.0f}% improvement)")
    else:
        print(f"⏸️  New model not significantly better (<{min_improvement*100:.0f}% improvement)")
    
    return is_better, improvement


def backup_model(models_dir: Path, backup_dir: Path) -> Optional[Path]:
    """Backup current model before replacing."""
    model_path = models_dir / "seqcls.pt"
    feat_cols_path = models_dir / "feat_cols.json"
    
    if not model_path.exists():
        return None
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_model_path = backup_dir / f"seqcls_{timestamp}.pt"
    backup_feat_path = backup_dir / f"feat_cols_{timestamp}.json"
    
    shutil.copy2(model_path, backup_model_path)
    if feat_cols_path.exists():
        shutil.copy2(feat_cols_path, backup_feat_path)
    
    print(f"💾 Backed up model to {backup_model_path}")
    return backup_model_path


@app.command()
def main(
    config_path: str = typer.Option("configs/train_3m.json", "--config"),
    test_weeks: int = typer.Option(2, "--test-weeks", help="Weeks of data to use for walk-forward validation"),
    min_improvement: float = typer.Option(0.05, "--min-improvement", help="Minimum improvement % to deploy new model"),
    force: bool = typer.Option(False, "--force", help="Force retrain even if new model is not better"),
    days_back: int = typer.Option(7, "--days-back", help="Days of new data to download"),
):
    """
    Automated retraining with walk-forward validation and model selection.
    
    Workflow:
    1. Download latest data
    2. Test current model on recent data (walk-forward)
    3. Train new model on all available data
    4. Test new model on same recent data
    5. Compare and deploy if better (or if --force)
    """
    print("=" * 60)
    print("🔄 AUTOMATED RETRAINING")
    print("=" * 60)
    
    # Load config
    with open(config_path, "r") as f:
        config = json.load(f)
    
    symbol = config["symbol"]
    timeframe = config["timeframe"]
    models_dir = Path("models")
    backup_dir = Path("models/backups")
    
    set_seed(config.get("seed", 42))
    
    # Step 1: Download latest data
    print(f"\n[1/5] 📥 Downloading latest data...")
    download_latest_data(symbol, timeframe, days_back=days_back)
    
    # Step 2: Load all data
    print(f"\n[2/5] 📊 Loading all data...")
    df = load_csv(symbol, timeframe)
    
    # Reset index to access 'time' column
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
    
    if len(df) < config["window"] * 10:
        print(f"❌ Insufficient data: {len(df)} bars")
        return
    
    print(f"   Total bars: {len(df)}")
    print(f"   Period: {df['time'].min()} to {df['time'].max()}")
    
    # Add features
    print("\n   Adding features...")
    df = add_features(df)
    # Use existing feature columns if available, otherwise extract from data
    feat_cols_path = models_dir / "feat_cols.json"
    if feat_cols_path.exists():
        try:
            feature_cols = load_feat_cols(feat_cols_path)
            print(f"   Loaded {len(feature_cols)} feature columns from existing model")
        except Exception as e:
            print(f"   Warning: Failed to load feature cols: {e}, extracting from data")
            feature_cols = get_feature_columns(df)
    else:
        feature_cols = get_feature_columns(df)
        print(f"   Extracted {len(feature_cols)} feature columns from data")
    
    # Step 3: Test current model (walk-forward validation)
    print(f"\n[3/5] 🧪 Testing current model (walk-forward validation)...")
    old_model_path = models_dir / "seqcls.pt"
    old_metrics = None
    
    if old_model_path.exists():
        try:
            old_model = SeqClassifier(n_features=len(feature_cols))
            old_model.load_state_dict(torch.load(old_model_path))
            old_model.eval()
            
            old_metrics = evaluate_model(
                model=old_model,
                df=df,
                feature_cols=feature_cols,
                window=config["window"],
                tp_pct=config["tp_pct"],
                sl_pct=config["sl_pct_candidates"][1],  # Use middle SL
                thr_long=config["thr_long"],
                thr_short=config["thr_short"],
                fee=config["fee"],
                slippage=config["slippage"],
                test_weeks=test_weeks,
            )
            
            if old_metrics:
                print(f"   Old Model Performance:")
                print(f"      Trades: {old_metrics['trades']}")
                print(f"      Profit Factor: {old_metrics['profit_factor']:.2f}")
                print(f"      Win Rate: {old_metrics['win_rate']:.2f}%")
                print(f"      Max Drawdown: {old_metrics['max_drawdown']:.2f}%")
                print(f"      Final Equity: {old_metrics['final_equity']:.4f}")
        except Exception as e:
            print(f"⚠️  Failed to test old model: {e}")
            old_metrics = None
    else:
        print("   No existing model found, will deploy new model")
    
    # Step 4: Train new model
    print(f"\n[4/5] 🎓 Training new model...")
    
    # Labeling
    df_labeled = make_barrier_labels(
        df,
        tp_pct=config["tp_pct"],
        sl_pct=config["sl_pct_candidates"][1],
        horizon=config["horizon"],
    )
    
    # Make windows
    X, Y, _ = make_windows(
        df_labeled,
        feature_cols=feature_cols,
        y_col="y",
        win=config["window"],
    )
    
    # Split
    val_start, _ = time_based_split(df_labeled, config["val_ratio"])
    X_train = X[:val_start-config["window"]]
    Y_train = Y[:val_start-config["window"]]
    X_val = X[val_start-config["window"]:]
    Y_val = Y[val_start-config["window"]:]
    
    print(f"   Train: {len(X_train)}, Val: {len(X_val)}")
    
    # Add hard negatives to training data
    print(f"\n   📋 Integrating hard negatives...")
    X_train_enhanced, Y_train_enhanced = add_hard_negatives_to_training(
        X_train, Y_train,
        df_labeled,
        feature_cols,
        config["window"],
        y_col="y"
    )
    
    # Train
    new_model, history = train_model(
        X_train_enhanced, Y_train_enhanced,
        X_val, Y_val,
        feature_cols,
        config,
    )
    
    # Step 5: Test new model (same walk-forward validation)
    print(f"\n[5/5] 🧪 Testing new model (walk-forward validation)...")
    new_metrics = evaluate_model(
        model=new_model,
        df=df,
        feature_cols=feature_cols,
        window=config["window"],
        tp_pct=config["tp_pct"],
        sl_pct=config["sl_pct_candidates"][1],
        thr_long=config["thr_long"],
        thr_short=config["thr_short"],
        fee=config["fee"],
        slippage=config["slippage"],
        test_weeks=test_weeks,
    )
    
    if not new_metrics:
        print("❌ Failed to evaluate new model")
        return
    
    print(f"   New Model Performance:")
    print(f"      Trades: {new_metrics['trades']}")
    print(f"      Profit Factor: {new_metrics['profit_factor']:.2f}")
    print(f"      Win Rate: {new_metrics['win_rate']:.2f}%")
    print(f"      Max Drawdown: {new_metrics['max_drawdown']:.2f}%")
    print(f"      Final Equity: {new_metrics['final_equity']:.4f}")
    
    # Step 6: Compare and deploy
    print(f"\n[6/6] 🔍 Comparing models...")
    is_better, improvement = compare_models(old_metrics, new_metrics, min_improvement)
    
    if is_better or force:
        if force:
            print("⚠️  --force flag: Deploying new model regardless of comparison")
        
        # Backup old model
        backup_model(models_dir, backup_dir)
        
        # Deploy new model
        print(f"\n🚀 Deploying new model...")
        save_model(new_model, feature_cols, models_dir)
        
        print("\n" + "=" * 60)
        print("✅ RETRAINING COMPLETE - New model deployed!")
        print("=" * 60)
        print(f"📊 Improvement: {improvement*100:.2f}%")
        print(f"💾 Backup saved to: {backup_dir}")
    else:
        print("\n" + "=" * 60)
        print("⏸️  RETRAINING COMPLETE - Keeping current model")
        print("=" * 60)
        print(f"📊 Improvement was only: {improvement*100:.2f}% (need ≥{min_improvement*100:.0f}%)")


if __name__ == "__main__":
    app()

