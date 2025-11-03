"""
Configuration module for ATR + SuperTrend Strategy Optimizer.

This module defines all configuration settings using Pydantic for validation.
"""

from typing import List, Dict, Any, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
import os
from pathlib import Path


class DataConfig(BaseSettings):
    """Data-related configuration."""
    
    exchange: str = Field(default="binance", description="Exchange name for ccxt")
    api_key: Optional[str] = Field(default=None, description="API key")
    secret: Optional[str] = Field(default=None, description="API secret")
    proxy_url: Optional[str] = Field(default=None, description="Proxy URL")
    sandbox_mode: bool = Field(default=False, description="Use sandbox mode")
    
    cache_dir: str = Field(default="./cache", description="Cache directory")
    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours")
    
    class Config:
        env_prefix = ""


class StrategyConfig(BaseSettings):
    """Strategy parameter configuration."""
    
    # Default coins and timeframes
    default_coins: List[str] = Field(
        default=["BTC/USDT", "SOL/USDT", "EIGEN/USDT"],
        description="Default coins for optimization"
    )
    default_timeframes: List[str] = Field(
        default=["15m", "1h", "4h", "1d"],
        description="Default timeframes"
    )
    history_days: int = Field(default=720, description="Days of historical data")
    
    # Parameter spaces for optimization
    param_space: Dict[str, List[Any]] = Field(
        default={
            "a": [1.5, 2.0, 2.5, 3.0],  # ATR sensitivity
            "c": [7, 10, 14, 20],        # ATR period
            "st_factor": [1.2, 1.5, 2.0],  # SuperTrend multiplier
            "min_delay_m": [0, 30, 60, 120],  # Minimum delay between trades
            "atr_sl_mult": [1.5, 2.0, 2.5],  # ATR-based SL multiplier
            "atr_rr": [1.5, 2.0, 3.0],       # Risk-reward ratio
            "use_trailing_stop": [True, False],  # Trailing stop
            "trailing_stop_mult": [0.8, 1.0, 1.2],  # Trailing stop multiplier
            "use_ema_confirmation": [True, False],  # EMA confirmation
            "ema_fast_len": [9, 12, 15],  # EMA Fast length
            "ema_slow_len": [21, 26, 30],  # EMA Slow length
        },
        description="Parameter space for optimization"
    )
    
    # Trailing stop parameters
    use_trailing_stop: bool = Field(default=True, description="Use trailing stop")
    trailing_stop_mult: float = Field(default=1.0, description="Trailing stop multiplier")
    
    # EMA Confirmation parameters
    ema_fast_len: int = Field(default=12, description="EMA Fast length")
    ema_slow_len: int = Field(default=26, description="EMA Slow length")
    pre_lookback_bars: int = Field(default=5, description="Pre-confirm window bars")
    post_confirm_bars: int = Field(default=5, description="Post-confirm window bars")
    use_ema_confirmation: bool = Field(default=True, description="Use EMA confirmation")
    
    class Config:
        env_prefix = ""


class OptimizationConfig(BaseSettings):
    """Optimization configuration."""
    
    default_jobs: int = Field(default=4, description="Default number of parallel jobs")
    top_n_results: int = Field(default=10, description="Number of top results to keep")
    
    # Walk-forward configuration
    wf_scheme: str = Field(default="rolling", description="WF scheme: rolling or expanding")
    train_windows: int = Field(default=3, description="Number of training windows")
    train_window_days: int = Field(default=90, description="Training window size in days")
    test_window_days: int = Field(default=30, description="Test window size in days")
    overlap_days: int = Field(default=0, description="Overlap between windows in days")
    
    class Config:
        env_prefix = ""


class ReportingConfig(BaseSettings):
    """Reporting configuration."""
    
    output_dir: str = Field(default="./reports", description="Output directory")
    save_plots: bool = Field(default=True, description="Save plots to files")
    plot_format: str = Field(default="png", description="Plot format")
    plot_dpi: int = Field(default=300, description="Plot DPI")
    
    class Config:
        env_prefix = ""


class Config(BaseSettings):
    """Main configuration class."""
    
    data: DataConfig = Field(default_factory=DataConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    
    @validator('data', pre=True)
    def load_env_vars(cls, v):
        """Load environment variables for data config."""
        if isinstance(v, dict):
            return v
        
        return DataConfig(
            exchange=os.getenv("EXCHANGE", "binance"),
            api_key=os.getenv("BINANCE_API_KEY"),
            secret=os.getenv("BINANCE_SECRET"),
            proxy_url=os.getenv("PROXY_URL"),
            sandbox_mode=os.getenv("SANDBOX_MODE", "false").lower() == "true",
            cache_dir=os.getenv("CACHE_DIR", "./cache"),
            cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "24")),
        )
    
    @validator('strategy', pre=True)
    def load_strategy_env_vars(cls, v):
        """Load environment variables for strategy config."""
        if isinstance(v, dict):
            return v
            
        return StrategyConfig(
            default_coins=os.getenv("DEFAULT_COINS", "BTC/USDT,SOL/USDT,EIGEN/USDT").split(","),
            default_timeframes=os.getenv("DEFAULT_TIMEFRAMES", "15m,1h,4h,1d").split(","),
            history_days=int(os.getenv("DEFAULT_HISTORY_DAYS", "720")),
        )
    
    @validator('optimization', pre=True)
    def load_optimization_env_vars(cls, v):
        """Load environment variables for optimization config."""
        if isinstance(v, dict):
            return v
            
        return OptimizationConfig(
            default_jobs=int(os.getenv("DEFAULT_JOBS", "4")),
        )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global config instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config


def validate_coins(coins: List[str]) -> List[str]:
    """Validate coin symbols."""
    # Basic validation - can be extended
    valid_coins = []
    for coin in coins:
        if '/' in coin and len(coin.split('/')) == 2:
            valid_coins.append(coin)
    return valid_coins


def get_wf_windows(scheme: str, train_window: int, test_window: int, train_steps: int) -> List[Dict[str, Any]]:
    """Generate walk-forward windows."""
    windows = []
    
    if scheme == "rolling":
        # Rolling window
        for i in range(train_steps):
            train_start = i * test_window
            train_end = train_start + train_window
            test_start = train_end
            test_end = test_start + test_window
            
            windows.append({
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end
            })
    else:
        # Expanding window
        for i in range(train_steps):
            train_start = 0
            train_end = train_window + i * test_window
            test_start = train_end
            test_end = test_start + test_window
            
            windows.append({
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end
            })
    
    return windows


def update_config(**kwargs) -> None:
    """Update configuration with new values."""
    global config
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)


# Validation functions
def validate_coins(coins: List[str]) -> List[str]:
    """Validate coin symbols."""
    valid_coins = []
    for coin in coins:
        if "/" in coin and len(coin.split("/")) == 2:
            valid_coins.append(coin)
        else:
            print(f"Warning: Invalid coin symbol '{coin}', skipping...")
    return valid_coins


def validate_timeframes(timeframes: List[str]) -> List[str]:
    """Validate timeframe strings."""
    valid_timeframes = []
    valid_tf_patterns = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
    
    for tf in timeframes:
        if tf in valid_tf_patterns:
            valid_timeframes.append(tf)
        else:
            print(f"Warning: Invalid timeframe '{tf}', skipping...")
    return valid_timeframes


def get_param_combinations() -> List[Dict[str, Any]]:
    """Generate all parameter combinations for grid search."""
    import itertools
    
    param_space = config.strategy.param_space
    param_names = list(param_space.keys())
    param_values = list(param_space.values())
    
    combinations = []
    for combo in itertools.product(*param_values):
        combinations.append(dict(zip(param_names, combo)))
    
    return combinations


def get_wf_windows(total_days: int) -> List[Dict[str, Any]]:
    """Generate walk-forward windows."""
    windows = []
    train_days = config.optimization.train_window_days
    test_days = config.optimization.test_window_days
    overlap_days = config.optimization.overlap_days
    num_windows = config.optimization.train_windows
    
    if config.optimization.wf_scheme == "rolling":
        # Rolling windows
        for i in range(num_windows):
            start_train = i * (train_days - overlap_days)
            end_train = start_train + train_days
            start_test = end_train
            end_test = start_test + test_days
            
            if end_test <= total_days:
                windows.append({
                    "window_id": i,
                    "train_start": start_train,
                    "train_end": end_train,
                    "test_start": start_test,
                    "test_end": end_test,
                })
    
    elif config.optimization.wf_scheme == "expanding":
        # Expanding windows
        for i in range(num_windows):
            start_train = 0
            end_train = train_days + i * (train_days - overlap_days)
            start_test = end_train
            end_test = start_test + test_days
            
            if end_test <= total_days:
                windows.append({
                    "window_id": i,
                    "train_start": start_train,
                    "train_end": end_train,
                    "test_start": start_test,
                    "test_end": end_test,
                })
    
    return windows
