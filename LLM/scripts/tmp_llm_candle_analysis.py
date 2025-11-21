import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import statistics
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
positions = json.loads(Path("runs/positions_post_deploy.json").read_text())

rows: List[Dict] = []
for pos in positions:
    entry = datetime.fromisoformat(pos["entry_time"]).replace(tzinfo=timezone.utc)
    since = int((entry - timedelta(minutes=5)).timestamp() * 1000)
    candles = exchange.fetch_ohlcv(symbol, timeframe="1m", since=since, limit=15)
    entry_ts = int(entry.timestamp() * 1000)
    entry_candle = None
    prev_candle = None
    for ts, o, h, l, c, v in candles:
        if ts <= entry_ts < ts + 60_000:
            entry_candle = {"open": o, "high": h, "low": l, "close": c, "volume": v}
        if ts < entry_ts:
            prev_candle = {"open": o, "high": h, "low": l, "close": c, "volume": v}
    if not entry_candle or not prev_candle:
        continue
    gap = (entry_candle["open"] - prev_candle["close"]) / prev_candle["close"]
    range_ratio = (entry_candle["high"] - entry_candle["low"]) / entry_candle["open"]
    body_ratio = abs(entry_candle["close"] - entry_candle["open"]) / entry_candle["open"]
    wick_ratio = range_ratio - body_ratio
    prev_change = (prev_candle["close"] - prev_candle["open"]) / prev_candle["open"]
    rows.append({
        "side": pos["side"],
        "pnl_pct": pos["pnl_pct"],
        "entry_time": pos["entry_time"],
        "gap": gap,
        "range_ratio": range_ratio,
        "body_ratio": body_ratio,
        "wick_ratio": wick_ratio,
        "prev_change": prev_change,
    })

positive = [r for r in rows if r["pnl_pct"] > 0]
negative = [r for r in rows if r["pnl_pct"] <= 0]

print("Counts -> positive:", len(positive), "negative:", len(negative))

for key in ["gap", "range_ratio", "body_ratio", "wick_ratio", "prev_change"]:
    pos_vals = [r[key] for r in positive]
    neg_vals = [r[key] for r in negative]
    if pos_vals:
        print(f"{key} pos mean: {statistics.mean(pos_vals)*100:.3f}%")
    if neg_vals:
        print(f"{key} neg mean: {statistics.mean(neg_vals)*100:.3f}%")

print("\nNegative trades details:")
for r in negative:
    print(
        f"{r['entry_time']} | pnl {r['pnl_pct']*100:.2f}% | gap {r['gap']*100:.3f}% | "
        f"range {r['range_ratio']*100:.3f}% | body {r['body_ratio']*100:.3f}% | prev_change {r['prev_change']*100:.3f}%"
    )

print("\nPositive trades details:")
for r in positive:
    print(
        f"{r['entry_time']} | pnl {r['pnl_pct']*100:.2f}% | gap {r['gap']*100:.3f}% | "
        f"range {r['range_ratio']*100:.3f}% | body {r['body_ratio']*100:.3f}% | prev_change {r['prev_change']*100:.3f}%"
    )
