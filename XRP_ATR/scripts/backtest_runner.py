"""Backtest runner script."""

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
from src.backtest_core import run_backtest

app = typer.Typer()


@app.command()
def main(
    config_path: str = typer.Option("configs/train_15m.json", "--config"),
    sl_pct: float = typer.Option(0.008, "--sl-pct"),
    thr_long: float = typer.Option(0.60, "--thr-long"),
    thr_short: float = typer.Option(0.60, "--thr-short"),
):
    """Run backtest with trained model."""
    # Load config
    with open(config_path, "r") as f:
        config = json.load(f)
    
    print(f"Backtesting: SL={sl_pct}, thr_long={thr_long}, thr_short={thr_short}")
    
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
    
    # Run backtest
    result = run_backtest(
        model=model,
        df=df,
        feature_cols=feature_cols,
        window=config["window"],
        tp_pct=config["tp_pct"],
        sl_pct=sl_pct,
        thr_long=thr_long,
        thr_short=thr_short,
        fee=config["fee"],
        slippage=config["slippage"],
    )
    
    # Print results
    print("\n" + "="*50)
    print("BACKTEST RESULTS")
    print("="*50)
    print(f"Trades: {result['trades']}")
    print(f"Final Equity: {result['final_equity']:.4f}")
    print(f"Profit Factor: {result['profit_factor']:.2f}")
    print(f"Win Rate: {result['win_rate']:.2f}%")
    print(f"Max Drawdown: {result['max_drawdown']:.2f}%")
    print("="*50)


if __name__ == "__main__":
    app()
