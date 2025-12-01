"""Probability calibration using Platt scaling and Isotonic regression."""

import numpy as np
from typing import Dict, Optional, Tuple
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
import logging

logger = logging.getLogger(__name__)


class ProbabilityCalibrator:
    """Calibrate model probabilities to improve reliability."""
    
    def __init__(self, method: str = "isotonic"):
        """
        Initialize calibrator.
        
        Args:
            method: "platt" (LogisticRegression) or "isotonic" (IsotonicRegression)
        """
        self.method = method
        self.calibrator_long = None
        self.calibrator_short = None
        self.calibrator_flat = None
        self.is_fitted = False
    
    def fit(
        self,
        probs: np.ndarray,  # (N, 3) array of [flat, long, short] probabilities
        actual: np.ndarray,  # (N,) array of actual labels (0=flat, 1=long, 2=short)
    ):
        """
        Fit calibrators on validation data.
        
        Args:
            probs: Model probabilities
            actual: Actual labels
        """
        if self.method == "platt":
            self.calibrator_long = LogisticRegression()
            self.calibrator_short = LogisticRegression()
            self.calibrator_flat = LogisticRegression()
        else:  # isotonic
            self.calibrator_long = IsotonicRegression(out_of_bounds='clip')
            self.calibrator_short = IsotonicRegression(out_of_bounds='clip')
            self.calibrator_flat = IsotonicRegression(out_of_bounds='clip')
        
        # Fit for each class
        # Long
        long_labels = (actual == 1).astype(float)
        if long_labels.sum() > 1:
            self.calibrator_long.fit(probs[:, 1].reshape(-1, 1), long_labels)
        
        # Short
        short_labels = (actual == 2).astype(float)
        if short_labels.sum() > 1:
            self.calibrator_short.fit(probs[:, 2].reshape(-1, 1), short_labels)
        
        # Flat
        flat_labels = (actual == 0).astype(float)
        if flat_labels.sum() > 1:
            self.calibrator_flat.fit(probs[:, 0].reshape(-1, 1), flat_labels)
        
        self.is_fitted = True
        logger.info(f"✅ Calibrator fitted using {self.method}")
    
    def predict_proba(self, probs: np.ndarray) -> np.ndarray:
        """
        Calibrate probabilities.
        
        Args:
            probs: (N, 3) or (3,) array of uncalibrated probabilities
            
        Returns:
            Calibrated probabilities with same shape
        """
        if not self.is_fitted:
            logger.warning("⚠️ Calibrator not fitted, returning original probs")
            return probs
        
        original_shape = probs.shape
        if len(probs.shape) == 1:
            probs = probs.reshape(1, -1)
        
        calibrated = probs.copy()
        
        # Calibrate each class
        if self.calibrator_flat is not None:
            calibrated[:, 0] = self.calibrator_flat.predict(probs[:, 0].reshape(-1, 1)).flatten()
        if self.calibrator_long is not None:
            calibrated[:, 1] = self.calibrator_long.predict(probs[:, 1].reshape(-1, 1)).flatten()
        if self.calibrator_short is not None:
            calibrated[:, 2] = self.calibrator_short.predict(probs[:, 2].reshape(-1, 1)).flatten()
        
        # Renormalize to sum to 1
        calibrated = calibrated / (calibrated.sum(axis=1, keepdims=True) + 1e-8)
        
        if len(original_shape) == 1:
            calibrated = calibrated.flatten()
        
        return calibrated
    
    def calibrate_single(self, probs_dict: Dict[str, float]) -> Dict[str, float]:
        """
        Calibrate a single prediction.
        
        Args:
            probs_dict: {"flat": p0, "long": p1, "short": p2}
            
        Returns:
            Calibrated probabilities
        """
        probs_array = np.array([
            probs_dict.get("flat", 0.0),
            probs_dict.get("long", 0.0),
            probs_dict.get("short", 0.0),
        ])
        
        calibrated = self.predict_proba(probs_array)
        
        return {
            "flat": float(calibrated[0]),
            "long": float(calibrated[1]),
            "short": float(calibrated[2]),
            "ml_proba_cal": True,  # Flag indicating calibration applied
        }


# Global calibrator instance
_calibrator: Optional[ProbabilityCalibrator] = None


def get_calibrator() -> Optional[ProbabilityCalibrator]:
    """Get global calibrator instance."""
    return _calibrator


def set_calibrator(calibrator: ProbabilityCalibrator):
    """Set global calibrator instance."""
    global _calibrator
    _calibrator = _calibrator


def calibrate_probabilities(probs: Dict[str, float]) -> Dict[str, float]:
    """
    Calibrate probabilities if calibrator is available.
    
    Args:
        probs: Uncalibrated probabilities
        
    Returns:
        Calibrated probabilities (or original if no calibrator)
    """
    calibrator = get_calibrator()
    if calibrator and calibrator.is_fitted:
        return calibrator.calibrate_single(probs)
    return probs

