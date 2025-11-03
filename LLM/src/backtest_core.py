"""Backtest core with commission and slippage."""

import pandas as pd
import numpy as np
from typing import Tuple, Dict

from src.infer import predict_proba, decide_side, tp_sl_from_pct
from src.models.transformer import SeqClassifier
from src.utils import calculate_profit_factor, calculate_drawdown


def run_backtest(
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
) -> Dict:
    """
    Run backtest with model predictions.

    Args:
        model: Trained model
        df: DataFrame with features and close prices
        feature_cols: List of feature column names
        window: Window length
        tp_pct: Take-profit percentage
        sl_pct: Stop-loss percentage
        thr_long: Long threshold
        thr_short: Short threshold
        fee: Commission fee (0.0005 = 0.05%)
        slippage: Slippage percentage

    Returns:
        Dictionary with results
    """
    signals = []
    trades = []
    
    n = len(df)
    
    for i in range(window, n):
        # Get window
        window_data = df[feature_cols].iloc[i-window:i].values
        
        # Predict
        probs = predict_proba(model, window_data)
        side, conf = decide_side(probs, thr_long, thr_short)
        
        signals.append({
            "idx": i,
            "side": side,
            "conf": conf,
        })
        
        # Entry on next bar open
        if i + 1 >= n:
            continue
        
        if side == "FLAT":
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
                    # TP hit
                    exit_price = tp
                    pnl = (exit_price - entry_price) / entry_price
                    break
                elif low <= sl:
                    # SL hit
                    exit_price = sl
                    pnl = (exit_price - entry_price) / entry_price
                    break
            elif side == "SHORT":
                if low <= tp:
                    # TP hit
                    exit_price = tp
                    pnl = (entry_price - exit_price) / entry_price
                    break
                elif high >= sl:
                    # SL hit
                    exit_price = sl
                    pnl = (entry_price - exit_price) / entry_price
                    break
        else:
            # No exit, close at last bar
            exit_price = close
            if side == "LONG":
                pnl = (exit_price - entry_price) / entry_price
            else:
                pnl = (entry_price - exit_price) / entry_price
        
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
        })
    
    # Calculate metrics
    if not trades:
        return {
            "trades": 0,
            "equity": [1.0],
            "final_equity": 1.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
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
    
    return {
        "trades": len(trades),
        "equity": equity.tolist(),
        "final_equity": float(equity[-1]),
        "profit_factor": float(pf),
        "win_rate": float(win_rate),
        "max_drawdown": float(dd_result["max_dd_pct"]),
        "trades_df": df_trades,
    }
