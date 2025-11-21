import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List
import ccxt

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "llm_config.json"
START_TIME = datetime(2025, 11, 9, 18, 43, 50, tzinfo=timezone.utc)
LOOKBACK_DAYS = 7

with open(CONFIG_PATH) as f:
    cfg = json.load(f)

exchange = ccxt.binance({
    "apiKey": cfg["api_key"],
    "secret": cfg["secret"],
    "options": {"defaultType": "future"},
    "enableRateLimit": True,
})

symbol = "BTC/USDT:USDT"
since = int((datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000)

print("📥 Fetching recent orders...")
orders = exchange.fetch_orders(symbol, since=since, limit=1000)
print(f"   Orders fetched: {len(orders)}")

# Sort by timestamp
orders.sort(key=lambda o: o.get("timestamp", 0))

entry_orders: Dict[str, Dict] = {}
positions: List[Dict] = []

for order in orders:
    status = order.get("status", "").lower()
    if status != "closed":
        continue
    client_id = (order.get("clientOrderId") or "").lower()
    order_type = (order.get("type") or "").lower()
    side = (order.get("side") or "").upper()
    ts = datetime.fromtimestamp(order["timestamp"] / 1000, tz=timezone.utc)
    price = float(order.get("average") or order.get("price") or 0)

    if ts < START_TIME:
        continue

    # Identify entry (market order with client id containing '-en-')
    if "-en-" in client_id and order_type == "market":
        pos_id = client_id.split("-en-")[-1]
        entry_orders[pos_id] = {
            "id": pos_id,
            "client_id": client_id,
            "side": "LONG" if side == "BUY" else "SHORT",
            "entry_price": price,
            "entry_time": ts,
        }
        continue

    # Identify exits (TP/SL)
    exit_reason = None
    if "-sl-" in client_id:
        exit_reason = "SL"
    elif "-tp-" in client_id or order_type in {"take_profit_market", "take_profit"}:
        exit_reason = "TP"

    if exit_reason is None:
        continue

    # Find matching entry (closest prior entry)
    matched_id = None
    for pos_id, entry in reversed(list(entry_orders.items())):
        if entry.get("matched"):
            continue
        if (ts - entry["entry_time"]).total_seconds() < 24 * 3600:  # within 24h
            matched_id = pos_id
            break

    if matched_id is None:
        continue

    entry = entry_orders[matched_id]
    entry["matched"] = True

    pnl_pct = None
    if entry["side"] == "LONG":
        pnl_pct = (price - entry["entry_price"]) / entry["entry_price"]
    else:
        pnl_pct = (entry["entry_price"] - price) / entry["entry_price"]

    positions.append({
        "side": entry["side"],
        "entry_price": entry["entry_price"],
        "exit_price": price,
        "entry_time": entry["entry_time"],
        "exit_time": ts,
        "exit_reason": exit_reason,
        "pnl_pct": pnl_pct,
        "entry_client_id": entry["client_id"],
        "exit_client_id": client_id,
    })

if not positions:
    print("⚠️ No closed positions found after the latest deployment window.")
    raise SystemExit

positions.sort(key=lambda p: p["entry_time"])

sl_positions = [p for p in positions if p["exit_reason"] == "SL"]
tp_positions = [p for p in positions if p["exit_reason"] == "TP"]

print("\n============================")
print("📊 LLM SL/TP Analysis (Post-Deployment)")
print("============================\n")
print(f"Total closed positions: {len(positions)}")
print(f"  ✅ TP: {len(tp_positions)}")
print(f"  ❌ SL: {len(sl_positions)}")

if tp_positions or sl_positions:
    win_rate = len(tp_positions) / len(positions) * 100 if positions else 0
    print(f"Win rate: {win_rate:.1f}%")

    avg_tp = sum(p["pnl_pct"] for p in tp_positions) / len(tp_positions) if tp_positions else 0
    avg_sl = sum(p["pnl_pct"] for p in sl_positions) / len(sl_positions) if sl_positions else 0
    print(f"Avg TP PnL: {avg_tp*100:.2f}%")
    print(f"Avg SL PnL: {avg_sl*100:.2f}%")

print("\nDetailed trades:")
for pos in positions:
    duration = (pos["exit_time"] - pos["entry_time"]).total_seconds() / 60
    print(
        f"- {pos['exit_reason']} | {pos['side']} | entry {pos['entry_time'].isoformat()} @ {pos['entry_price']:.2f} "
        f"-> exit {pos['exit_time'].isoformat()} @ {pos['exit_price']:.2f} | PnL {pos['pnl_pct']*100:.2f}% | duration {duration:.1f} min"
    )
