"""Download Binance Futures klines."""

import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import typer

app = typer.Typer()


def download_klines(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str = None,
    data_dir: Path = Path("data"),
) -> Path:
    """
    Download Binance Futures klines.

    Args:
        symbol: Trading symbol (e.g., ETHUSDT)
        interval: Kline interval (e.g., 3m, 5m, 1h)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD), if None uses today
        data_dir: Output directory

    Returns:
        Path to saved CSV
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
    df = pd.DataFrame(klines, columns=[
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
    csv_path = data_dir / f"{symbol}_{interval}.csv"
    df.to_csv(csv_path, index=False)
    
    print(f"Total bars: {len(df)} from {df['time'].min()} to {df['time'].max()}")
    print(f"Saved to {csv_path}")
    
    return csv_path


@app.command()
def main(
    symbol: str = typer.Option("ETHUSDT", "--symbol"),
    interval: str = typer.Option("3m", "--interval"),
    start: str = typer.Option("2024-01-01", "--start"),
    end: str = typer.Option(None, "--end"),
):
    """Download Binance Futures klines."""
    download_klines(symbol, interval, start, end)


if __name__ == "__main__":
    app()
