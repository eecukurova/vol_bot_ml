"""Grid search runner script."""

import json
import sys
import typer
from pathlib import Path
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fetch_binance import load_csv
from src.features import add_features, get_feature_columns
from src.models.transformer import SeqClassifier
from src.utils import load_feat_cols
from src.gridsearch import run_grid_search

app = typer.Typer()


@app.command()
def main(
    config_path: str = typer.Option("configs/train_3m.json", "--config"),
    top_n: int = typer.Option(5, "--top-n"),
):
    """Run grid search for optimal SL and thresholds."""
    # Load config
    with open(config_path, "r") as f:
        config = json.load(f)
    
    print("Running grid search...")
    print(f"Candidates: SL={config['sl_pct_candidates']}, "
          f"thr_long={[0.55, 0.60, 0.65]}, thr_short={[0.55, 0.60, 0.65]}")
    
    # Load data
    df = load_csv(config["symbol"], config["timeframe"])
    df = add_features(df)
    feature_cols = get_feature_columns(df)
    
    # Load model
    model_path = Path("models/seqcls.pt")
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return
    
    feat_cols = load_feat_cols(Path("models/feat_cols.json"))
    
    model = SeqClassifier(n_features=len(feat_cols))
    model.load_state_dict(torch.load(model_path))
    
    # Run grid search
    df_results = run_grid_search(
        model=model,
        df=df,
        feature_cols=feature_cols,
        window=config["window"],
        tp_pct=config["tp_pct"],
        sl_pct_candidates=config["sl_pct_candidates"],
        thr_long_candidates=[0.55, 0.60, 0.65],
        thr_short_candidates=[0.55, 0.60, 0.65],
        fee=config["fee"],
        slippage=config["slippage"],
    )
    
    # Print top N
    print("\n" + "="*80)
    print(f"TOP {top_n} COMBINATIONS")
    print("="*80)
    print(df_results.head(top_n).to_string(index=False))
    print("="*80)


if __name__ == "__main__":
    app()
