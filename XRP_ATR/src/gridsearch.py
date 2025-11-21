"""Grid search for optimal SL and thresholds."""

import pandas as pd
import numpy as np
from typing import List, Dict
from itertools import product

from src.backtest_core import run_backtest
from src.models.transformer import SeqClassifier


def run_grid_search(
    model: SeqClassifier,
    df: pd.DataFrame,
    feature_cols: list,
    window: int,
    tp_pct: float,
    sl_pct_candidates: List[float],
    thr_long_candidates: List[float],
    thr_short_candidates: List[float],
    fee: float,
    slippage: float,
) -> pd.DataFrame:
    """
    Run grid search over SL and threshold combinations.

    Args:
        model: Trained model
        df: DataFrame with features
        feature_cols: List of feature column names
        window: Window length
        tp_pct: Take-profit percentage
        sl_pct_candidates: List of SL candidates
        thr_long_candidates: List of long thresholds
        thr_short_candidates: List of short thresholds
        fee: Commission fee
        slippage: Slippage percentage

    Returns:
        DataFrame with results for each combination
    """
    results = []
    
    combinations = list(product(
        sl_pct_candidates,
        thr_long_candidates,
        thr_short_candidates,
    ))
    
    total = len(combinations)
    
    for idx, (sl_pct, thr_long, thr_short) in enumerate(combinations):
        print(f"Testing {idx+1}/{total}: SL={sl_pct}, thr_long={thr_long}, thr_short={thr_short}")
        
        result = run_backtest(
            model=model,
            df=df,
            feature_cols=feature_cols,
            window=window,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            thr_long=thr_long,
            thr_short=thr_short,
            fee=fee,
            slippage=slippage,
        )
        
        results.append({
            "sl_pct": sl_pct,
            "thr_long": thr_long,
            "thr_short": thr_short,
            "trades": result["trades"],
            "final_equity": result["final_equity"],
            "profit_factor": result["profit_factor"],
            "win_rate": result["win_rate"],
            "max_drawdown": result["max_drawdown"],
        })
    
    df_results = pd.DataFrame(results)
    
    # Sort by multiple criteria (prioritize stability)
    df_results = df_results.sort_values(
        by=["profit_factor", "win_rate", "trades"],
        ascending=[False, False, True]
    )
    
    return df_results
