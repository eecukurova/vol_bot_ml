"""Live demo runner script."""

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
from src.live_loop import on_new_bar, init_order_client, init_telegram

app = typer.Typer()


@app.command()
def main(
    config_path: str = typer.Option("configs/train_2h.json", "--config"),
    sl_pct: float = typer.Option(0.008, "--sl-pct"),
    thr_long: float = typer.Option(0.60, "--thr-long"),
    thr_short: float = typer.Option(0.60, "--thr-short"),
    num_bars: int = typer.Option(10, "--num-bars"),
    llm_config: str = typer.Option("configs/llm_config.json", "--llm-config"),
):
    """Simulate live inference with real API and Telegram."""
    # Load training config
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Load LLM config (API keys, Telegram)
    try:
        with open(llm_config, "r") as f:
            llm_cfg = json.load(f)
        
        # Initialize order client
        init_order_client(
            api_key=llm_cfg["api_key"],
            api_secret=llm_cfg["secret"],
            sandbox=llm_cfg["sandbox"]
        )
        
        # Initialize Telegram
        if llm_cfg["telegram"]["enabled"]:
            init_telegram(
                bot_token=llm_cfg["telegram"]["bot_token"],
                chat_id=llm_cfg["telegram"]["chat_id"]
            )
        
        print(f"✅ API & Telegram initialized")
        
    except Exception as e:
        print(f"⚠️ Config not found, running in demo mode: {e}")
    
    print(f"Live demo: processing last {num_bars} bars")
    print(f"SL={sl_pct}, thr_long={thr_long}, thr_short={thr_short}")
    
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
    
    # Simulate live loop on last N bars
    n = len(df)
    
    for i in range(max(200, config["window"]), n, 20):  # Every 20 bars
        df_window = df.iloc[:i+1]
        
        print(f"\nBar {i}: {df_window.index[-1]}")
        print("-" * 50)
        
        on_new_bar(
            df=df_window,
            model=model,
            feature_cols=feature_cols,
            window=config["window"],
            tp_pct=config["tp_pct"],
            sl_pct=sl_pct,
            thr_long=thr_long,
            thr_short=thr_short,
        )
        
        if i >= n - 1:
            break


if __name__ == "__main__":
    app()
