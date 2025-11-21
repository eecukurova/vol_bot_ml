import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import ccxt

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "llm_config.json"
START_TIME = datetime(2025, 11, 9, 18, 43, 50, tzinfo=timezone.utc)
LOOKBACK_DAYS = 7

with CONFIG_PATH.open() as f:
    cfg = json.load(f)

exchange = ccxt.binance({
    "apiKey": cfg["api_key"],
    "secret": cfg["secret"],
    "options": {"defaultType": "future"},
    "enableRateLimit": True,
})

symbol = "BTC/USDT:USDT"
since = int((datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000)
trades = exchange.fetch_my_trades(symbol, since=since, limit=1000)
trades = [t for t in trades if datetime.fromtimestamp(t["timestamp"] / 1000, tz=timezone.utc) >= START_TIME]
trades.sort(key=lambda t: t["timestamp"])

positions: List[Dict] = []
current = None

for trade in trades:
    ts = datetime.fromtimestamp(trade["timestamp"] / 1000, tz=timezone.utc)
    price = float(trade["price"])
    amount = float(trade["amount"])
    side = trade["side"]

    if current is None:
        current = {
            "side": side,
            "entry_time": ts,
            "entry_price": price,
            "amount": amount,
            "trade_id": trade.get("id"),
        }
        continue

    if side == current["side"]:
        total_amount = current["amount"] + amount
        if total_amount > 0:
            current["entry_price"] = (
                current["entry_price"] * current["amount"] + price * amount
            ) / total_amount
            current["amount"] = total_amount
        continue

    position_side = "LONG" if current["side"] == "buy" else "SHORT"
    entry_price = current["entry_price"]
    entry_time = current["entry_time"]
    exit_price = price
    exit_time = ts

    if position_side == "LONG":
        pnl_pct = (exit_price - entry_price) / entry_price
    else:
        pnl_pct = (entry_price - exit_price) / entry_price

    positions.append(
        {
            "side": position_side,
            "entry_time": entry_time.isoformat(),
            "exit_time": exit_time.isoformat(),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl_pct": pnl_pct,
            "duration_min": (exit_time - entry_time).total_seconds() / 60,
        }
    )

    current = None

positions_path = Path("runs/positions_post_deploy.json")
positions_path.parent.mkdir(parents=True, exist_ok=True)
with positions_path.open("w") as f:
    json.dump(positions, f, indent=2)

print(f"Saved {len(positions)} positions to {positions_path}")
