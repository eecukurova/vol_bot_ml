"""Binance CSV data loading utilities."""

import pandas as pd
from pathlib import Path
from typing import Optional


def load_csv(symbol: str, timeframe: str, data_dir: Path = Path("data")) -> pd.DataFrame:
    """
    Load CSV OHLCV data.

    Args:
        symbol: Trading symbol (e.g., "ETHUSDT")
        timeframe: Timeframe (e.g., "3m")
        data_dir: Data directory path

    Returns:
        DataFrame with columns: time, open, high, low, close, volume

    Raises:
        FileNotFoundError: If CSV not found
    """
    csv_path = data_dir / f"{symbol}_{timeframe}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    # Ensure time column is datetime
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
    
    # Validate columns
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    
    return df


def save_csv(df: pd.DataFrame, symbol: str, timeframe: str, data_dir: Path = Path("data")) -> Path:
    """
    Save DataFrame to CSV.

    Args:
        df: DataFrame with OHLCV data
        symbol: Trading symbol
        timeframe: Timeframe
        data_dir: Data directory path

    Returns:
        Path to saved CSV
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / f"{symbol}_{timeframe}.csv"
    
    # Reset index if time is indexed
    if isinstance(df.index, pd.DatetimeIndex):
        df_copy = df.reset_index()
    else:
        df_copy = df.copy()
    
    df_copy.to_csv(csv_path, index=False)
    return csv_path
