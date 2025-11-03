"""Inference module for Volensy LLM."""

from typing import Dict, Tuple

import numpy as np
import torch

from src.models.transformer import SeqClassifier
from src.calibration import calibrate_probabilities


def predict_proba(
    model: SeqClassifier,
    window_np: np.ndarray,
) -> Dict[str, float]:
    """
    Get probability predictions from model.

    Args:
        model: Trained SeqClassifier
        window_np: (T, F) numpy array (single window)

    Returns:
        {"flat": p0, "long": p1, "short": p2}
    """
    model.eval()
    
    # Add batch dimension
    window_tensor = torch.FloatTensor(window_np).unsqueeze(0)
    
    with torch.no_grad():
        logits = model(window_tensor)
        probs = torch.softmax(logits, dim=1).numpy()[0]
    
    # Get uncalibrated probabilities
    uncalibrated = {
        "flat": float(probs[0]),
        "long": float(probs[1]),
        "short": float(probs[2]),
    }
    
    # Apply calibration if available
    calibrated = calibrate_probabilities(uncalibrated)
    
    return calibrated


def decide_side(
    probs: Dict[str, float],
    thr_long: float,
    thr_short: float,
) -> Tuple[str, float]:
    """
    Decide trading side from probabilities.

    Args:
        probs: {"flat": p0, "long": p1, "short": p2}
        thr_long: Threshold for long signal
        thr_short: Threshold for short signal

    Returns:
        ("LONG"|"SHORT"|"FLAT", confidence)
    """
    p_flat = probs["flat"]
    p_long = probs["long"]
    p_short = probs["short"]
    
    if p_long >= thr_long:
        return "LONG", p_long
    elif p_short >= thr_short:
        return "SHORT", p_short
    else:
        return "FLAT", p_flat


def tp_sl_from_pct(
    last_price: float,
    tp_pct: float,
    sl_pct: float,
    side: str,
) -> Tuple[float, float]:
    """
    Calculate TP/SL from percentages.

    Args:
        last_price: Current price
        tp_pct: Take-profit percentage (0.005 = 0.5%)
        sl_pct: Stop-loss percentage
        side: "LONG" or "SHORT"

    Returns:
        (tp, sl)
    """
    if side == "LONG":
        tp = last_price * (1 + tp_pct)
        sl = last_price * (1 - sl_pct)
    elif side == "SHORT":
        tp = last_price * (1 - tp_pct)
        sl = last_price * (1 + sl_pct)
    else:  # FLAT
        tp = last_price
        sl = last_price
    
    return tp, sl
