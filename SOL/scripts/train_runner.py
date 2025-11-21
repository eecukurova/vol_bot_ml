"""Training runner script."""

import json
import sys
from pathlib import Path
import typer
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fetch_binance import load_csv
from src.features import add_features, get_feature_columns
from src.labeling import make_barrier_labels
from src.dataset import make_windows
from src.train import train_model, save_model
from src.utils import time_based_split, set_seed

app = typer.Typer()


@app.command()
def main(
    config_path: str = typer.Option("configs/train_3m.json", "--config"),
):
    """Train Transformer model."""
    # Load config
    with open(config_path, "r") as f:
        config = json.load(f)
    
    print(f"Training with config: {config['symbol']} {config['timeframe']}")
    
    # Load data
    print("Loading CSV...")
    df = load_csv(config["symbol"], config["timeframe"])
    
    # Add features
    print("Adding features...")
    df = add_features(df)
    feature_cols = get_feature_columns(df)
    print(f"Created {len(feature_cols)} features")
    
    # Labeling - Use enhanced early reversal labeling if available
    print("Applying labeling...")
    try:
        from src.labeling_enhanced import make_early_reversal_labels
        print("  Using enhanced early reversal labeling...")
        df = make_early_reversal_labels(
            df,
            tp_pct=config["tp_pct"],
            sl_pct=config["sl_pct_candidates"][1],  # Use middle value
            horizon=config["horizon"],
            early_bars=5,  # Label 5 bars before reversal
        )
    except ImportError:
        print("  Using standard triple-barrier labeling...")
        df = make_barrier_labels(
            df,
            tp_pct=config["tp_pct"],
            sl_pct=config["sl_pct_candidates"][1],  # Use middle value
            horizon=config["horizon"],
        )
    
    # Class distribution
    print("\nClass distribution:")
    print(df["y"].value_counts().sort_index())
    
    # Make windows
    print("\nCreating windows...")
    X, Y, _ = make_windows(
        df,
        feature_cols=feature_cols,
        y_col="y",
        win=config["window"],
    )
    print(f"Windows shape: X={X.shape}, Y={Y.shape}")
    
    # Split
    print("\nSplitting train/validation...")
    val_start, _ = time_based_split(df, config["val_ratio"])
    
    X_train = X[:val_start-config["window"]]
    Y_train = Y[:val_start-config["window"]]
    X_val = X[val_start-config["window"]:]
    Y_val = Y[val_start-config["window"]:]
    
    print(f"Train: {len(X_train)}, Val: {len(X_val)}")
    
    # Train
    print("\nTraining model...")
    model, history = train_model(
        X_train, Y_train,
        X_val, Y_val,
        feature_cols,
        config,
    )
    
    # Save
    print("\nSaving model...")
    save_model(model, feature_cols, Path("models"))
    
    print("\nTraining complete!")


if __name__ == "__main__":
    app()
