"""Latency tracking and monitoring."""

import time
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Global latency tracker
_latency_data = []


class LatencyTracker:
    """Track latency for signal generation and order execution."""
    
    def __init__(self, threshold_ms: float = 300.0):
        """
        Initialize latency tracker.
        
        Args:
            threshold_ms: Alert threshold in milliseconds
        """
        self.threshold_ms = threshold_ms
        self.timers = {}
        
    def start_timer(self, name: str) -> None:
        """Start timer for a named operation."""
        self.timers[name] = time.time()
    
    def end_timer(self, name: str) -> Optional[float]:
        """
        End timer and return elapsed time in milliseconds.
        
        Args:
            name: Timer name
            
        Returns:
            Elapsed time in milliseconds, or None if timer not found
        """
        if name not in self.timers:
            logger.warning(f"Timer '{name}' not started")
            return None
        
        elapsed = (time.time() - self.timers[name]) * 1000  # Convert to ms
        del self.timers[name]
        
        return elapsed
    
    def track_signal_generation(self, func):
        """Decorator to track signal generation latency."""
        def wrapper(*args, **kwargs):
            self.start_timer("signal_generation")
            try:
                result = func(*args, **kwargs)
                latency = self.end_timer("signal_generation")
                if latency:
                    self._log_latency("signal_generation", latency)
                return result
            except Exception as e:
                self.end_timer("signal_generation")
                raise
        return wrapper
    
    def track_order_execution(self, func):
        """Decorator to track order execution latency."""
        def wrapper(*args, **kwargs):
            self.start_timer("order_execution")
            try:
                result = func(*args, **kwargs)
                latency = self.end_timer("order_execution")
                if latency:
                    self._log_latency("order_execution", latency)
                return result
            except Exception as e:
                self.end_timer("order_execution")
                raise
        return wrapper
    
    def _log_latency(self, operation: str, latency_ms: float) -> None:
        """Log latency and alert if threshold exceeded."""
        logger.info(f"⏱️  {operation} latency: {latency_ms:.2f}ms")
        
        if latency_ms > self.threshold_ms:
            self._alert_high_latency(operation, latency_ms)
    
    def _alert_high_latency(self, operation: str, latency_ms: float) -> None:
        """Send alert for high latency."""
        logger.warning(
            f"🚨 HIGH LATENCY: {operation} took {latency_ms:.2f}ms "
            f"(threshold: {self.threshold_ms}ms)"
        )
        
        # Store for Telegram alert
        global _latency_data
        _latency_data.append({
            "operation": operation,
            "latency_ms": latency_ms,
            "timestamp": time.time()
        })


# Global tracker instance
_tracker = LatencyTracker(threshold_ms=300.0)


def get_latency_tracker() -> LatencyTracker:
    """Get global latency tracker instance."""
    return _tracker


def check_latency_alerts() -> list:
    """Check for recent latency alerts (for Telegram)."""
    global _latency_data
    recent = [d for d in _latency_data if time.time() - d["timestamp"] < 3600]  # Last hour
    return recent


def format_latency_alert(operation: str, latency_ms: float) -> str:
    """Format latency alert message for Telegram."""
    return (
        f"🚨 Latency Alert\n\n"
        f"Operation: {operation}\n"
        f"Latency: {latency_ms:.2f}ms\n"
        f"Threshold: 300ms\n"
        f"Status: EXCEEDED"
    )

