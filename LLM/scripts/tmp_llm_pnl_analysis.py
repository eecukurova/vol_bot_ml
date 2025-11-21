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
    side = trade["side"]  # "buy" or "sell"

    if current is None:
        current = {
            "side": side,
            "entry_time": ts,
            "entry_price": price,
            "amount": amount,
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
            "entry_time": entry_time,
            "entry_price": entry_price,
            "exit_time": exit_time,
            "exit_price": exit_price,
            "pnl_pct": pnl_pct,
            "duration_min": (exit_time - entry_time).total_seconds() / 60,
        }
    )

    current = None

if not positions:
    print("No closed positions after deployment window.")
    raise SystemExit

positive = [p for p in positions if p["pnl_pct"] > 0]
negative = [p for p in positions if p["pnl_pct"] <= 0]

print("==============================")
print("📊 LLM PnL Breakdown (Post-Deployment)")
print("==============================")
print(f"Total closed positions: {len(positions)}")
print(f"  Positive: {len(positive)} | Sum PnL: {sum(p['pnl_pct'] for p in positive)*100:.2f}%")
print(f"  Negative: {len(negative)} | Sum PnL: {sum(p['pnl_pct'] for p in negative)*100:.2f}%")
print(f"Overall PnL: {sum(p['pnl_pct'] for p in positions)*100:.2f}%\n")

print("Detailed trades (latest first):")
for pos in reversed(positions):
    print(
        f"{pos['exit_time'].astimezone():%Y-%m-%d %H:%M:%S} | {pos['side']} | PnL {pos['pnl_pct']*100:.2f}% | duration {pos['duration_min']:.2f} min"
    )
