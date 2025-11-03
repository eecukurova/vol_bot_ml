"""Binance CSV data loading utilities."""

import time
import requests
import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


def load_csv(symbol: str, timeframe: str, data_dir: Path = Path("data")) -> pd.DataFrame:
    """
    Load CSV OHLCV data.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
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


def download_klines(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str = None,
    data_dir: Path = Path("data"),
) -> Optional[Path]:
    """
    Download Binance Futures klines.

    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        interval: Kline interval (e.g., 3m, 5m, 1h)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD), if None uses today
        data_dir: Output directory

    Returns:
        Path to saved CSV, or None if failed
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    
    # Binance API endpoint
    base_url = "https://fapi.binance.com/fapi/v1/klines"
    
    # Fetch all klines
    all_klines = []
    current = start
    
    while current < end:
        # Request params
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": int(current.timestamp() * 1000),
            "limit": 1000,
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()
            
            if not klines:
                break
            
            all_klines.extend(klines)
            
            # Move to next batch
            last_time = klines[-1][0] / 1000
            current = datetime.fromtimestamp(last_time) + timedelta(minutes=1)
            
            time.sleep(0.5)  # Rate limit
            
        except requests.RequestException as e:
            print(f"Error: {e}")
            time.sleep(2)
    
    if not all_klines:
        print("No data retrieved")
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        "time_ms", "open", "high", "low", "close", "volume",
        "close_time_ms", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    
    # Convert timestamp
    df["time"] = pd.to_datetime(df["time_ms"], unit="ms")
    
    # Select columns
    df = df[["time", "open", "high", "low", "close", "volume"]].copy()
    
    # Convert to float
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    
    # Sort and drop duplicates
    df = df.sort_values("time").drop_duplicates(subset=["time"])
    
    # Merge with existing data if exists
    existing_csv = data_dir / f"{symbol}_{interval}.csv"
    if existing_csv.exists():
        df_existing = pd.read_csv(existing_csv)
        df_existing["time"] = pd.to_datetime(df_existing["time"])
        # Combine and remove duplicates
        df_combined = pd.concat([df_existing, df], ignore_index=True)
        df_combined = df_combined.sort_values("time").drop_duplicates(subset=["time"])
        df = df_combined
    
    # Save
    csv_path = save_csv(df, symbol, interval, data_dir)
    
    print(f"Downloaded {len(df)} bars from {df['time'].min()} to {df['time'].max()}")
    print(f"Saved to {csv_path}")
    
    return csv_path
