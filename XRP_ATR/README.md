# XRP ATR Live Trading – ATR + Super Trend Strategy

XRP ATR Live Trading Signal Generator using ATR + Super Trend strategy for XRPUSDT futures trading with configurable take-profit and stop-loss.

## 🎯 Approach

- **Target**: XRPUSDT futures trading with ATR + Super Trend signals
- **Model**: Small Transformer encoder (64-dim, 2 layers, 4 heads)
- **Labeling**: Triple-barrier first-touch with configurable TP/SL
- **Validation**: Time-based split, weighted CE loss for class imbalance
- **Optimization**: Grid search on SL thresholds and decision thresholds
- **Backtest**: Commission (0.05%) + slippage included

## 📦 Installation

```bash
make venv          # Create virtual environment
source venv/bin/activate
make install       # Install dependencies
make fmt           # Format code
make lint          # Lint code
```

## 🔄 Workflow

### 1. Data Preparation

Download 3-minute klines from Binance:

```bash
python scripts/download_binance_klines.py --symbol XRPUSDT --interval 15m --start 2024-01-01
```

Data saved to `data/XRPUSDT_15m.csv` with columns: `time,open,high,low,close,volume`.

### 2. Training

```bash
make train
# or
python scripts/train_runner.py --symbol XRPUSDT --timeframe 15m
```

Trainer will:
- Load CSV data
- Add features (EMA distances, RSI, volume spikes, z-scores)
- Apply triple-barrier labeling (TP=0.5%, SL candidates)
- Create windows (length=128)
- Train Transformer with validation split
- Save `models/seqcls.pt` and `models/feat_cols.json`

Configuration: `configs/train_15m.json`

### 3. Grid Search

Find optimal SL and decision thresholds:

```bash
make grid
# or
python scripts/gridsearch_runner.py --symbol XRPUSDT --timeframe 15m
```

Tests combinations of:
- `sl_pct`: [0.006, 0.008, 0.010]
- `thr_long/thr_short`: [0.55, 0.60, 0.65]

Outputs top-5 combinations with metrics (hit-rate, PF, trades, drawdown).

### 4. Backtest

Run backtest with trained model and best thresholds:

```bash
make backtest
# or
python scripts/backtest_runner.py --symbol XRPUSDT --timeframe 15m \
    --sl-pct 0.008 --thr-long 0.60 --thr-short 0.60
```

Outputs:
- Final equity curve
- Profit Factor
- Win-rate (%)
- Total trades
- Max drawdown

### 5. Live Loop Demo

Simulate live inference (no actual orders):

```bash
make live
# or
python scripts/live_demo_runner.py --symbol XRPUSDT --timeframe 15m \
    --sl-pct 0.008 --thr-long 0.60
```

Prints:
- Each bar decision
- ML probabilities
- TP/SL values
- Telegram-style alert payloads

## 🚀 Production Live Runner

The production process runs via `run_llm_live.py` and a systemd service. It loads the trained model, fetches new 15m bars, makes decisions, sends Futures orders with TP/SL, and posts Telegram alerts.

- Entry point: `run_llm_live.py`
- Service: `llm_live.service` (systemd)
- Working directory: `/root/ATR/XRP_ATR`
- Logs: `runs/xrp_atr_live.log`

### What it does
- Loads `models/seqcls.pt` and `models/feat_cols.json`.
- Reads config from `configs/llm_config.json` (API keys, leverage, trade amount, Telegram).
- Reads training/live settings from `configs/train_15m.json` (e.g. `timeframe`, `window`, `tp_pct`).
- Pulls latest `timeframe` klines from Binance Spot for features.
- Applies features and the Transformer to generate probabilities and a side (LONG/SHORT/FLAT).
- Applies regime filter (e.g. `ema50 > ema200`, `vol_spike > 0.85`).
- If eligible, places a market entry and attaches TP/SL (closePosition) on Binance Futures via `src.live_loop -> init_order_client -> src.order_client`.
- Sends a Telegram alert if enabled.

### Configuration (`configs/llm_config.json`)
Key fields used by the live runner:

```json
{
  "api_key": "...",
  "secret": "...",
  "symbol": "XRPUSDT",
  "trade_amount_usd": 100,
  "leverage": 5,
  "idempotency": { "state_file": "runs/llm_state.json", "retry_attempts": 3, "retry_delay": 1.0 },
  "sl_tp": { "trigger_source": "MARK_PRICE", "hedge_mode": false },
  "telegram": { "enabled": true, "bot_token": "...", "chat_id": "..." },
  "logging": { "level": "INFO", "file": "llm_trading.log" }
}
```

Update trade size or leverage by editing `trade_amount_usd` and `leverage`. The runner reads these dynamically on start.

### Service management

```bash
# Status
systemctl status llm_live.service --no-pager -l

# Start/Stop/Restart
systemctl start llm_live.service
systemctl stop llm_live.service
systemctl restart llm_live.service

# Enable on boot
systemctl enable llm_live.service
```

### Logs

```bash
tail -f runs/llm_live.log
```

Typical startup lines:

```
INFO:__main__:🚀 Starting LLM Live Signal Generator
INFO:src.live_loop:✅ Order client initialized
INFO:__main__:Model loaded: 17 features
INFO:__main__:📊 Monitoring: XRPUSDT 15m
```

### Time and timestamps
- Exchange data and orders are UTC-based; the server logs local time (+03). A UTC vs local mismatch may make entries look like “previous day.” This is expected.

## ⚙️ Runtime Behavior (Important)

- Bar cadence: runs when a new bar appears for the configured `timeframe` (default 15m). Sleeps between checks.
- Position sizing: `trade_amount_usd` notional with `leverage` → entry size computed from latest price.
- Orders: Market entry; TP/SL sent as `TAKE_PROFIT_MARKET`/`STOP_MARKET` with `closePosition=true`, `workingType=MARK_PRICE`.
- Safety: TP/SL stop prices are adjusted against mark price to avoid Binance `-2021 Order would immediately trigger` errors.
- State: Idempotent order client persists to `runs/llm_state.json` and dedupes/retries.

## 🧰 Troubleshooting

- No logs: check service status and permissions in `/root/ATR/XRP_ATR`.
- `-2021` errors: TP/SL safety adjustment is enabled; if seen, verify `workingType=MARK_PRICE` and price precision.
- No signals: thresholds too strict or regime filter rejects; adjust `thr_long/thr_short`, `sl_pct`, or regime.
- API errors: validate `api_key/secret`; ensure Futures trading is enabled on the account.

## 📁 Project Structure

```
LLM/
├── configs/
│   └── train_15m.json
├── data/              # CSV raw data
├── models/            # Saved weights + feat_cols.json
├── notebooks/         # Optional analysis
├── scripts/
│   ├── download_binance_klines.py
│   ├── train_runner.py
│   ├── backtest_runner.py
│   ├── gridsearch_runner.py
│   └── live_demo_runner.py
├── src/
│   ├── fetch_binance.py
│   ├── features.py
│   ├── labeling.py
│   ├── dataset.py
│   ├── models/
│   │   └── transformer.py
│   ├── train.py
│   ├── infer.py
│   ├── backtest_core.py
│   ├── gridsearch.py
│   ├── live_loop.py
│   └── utils.py
└── tests/
    ├── test_labeling.py
    ├── test_features.py
    └── test_model_forward.py
```

## 🧪 Testing

```bash
make test
```

Runs unit tests for labeling logic, feature engineering, and model forward pass.

## ⚠️ Warnings

- **Funding rates**: Not modeled in backtest (XRPUSDT perp funding ~0.01% per 8h)
- **Slippage**: Default 0; add realistic slippage for live trading
- **Latency**: 100ms+ execution can miss TP
- **Overfitting**: Use walk-forward validation for production
- **Regime dependency**: Model trained on 2024 data may fail in 2025 if regime shifts
- **Risk**: Start with paper trading; 0.5% TP requires high hit-rate to be profitable

## 🎯 Integration Hooks

Orders and alerts are already integrated:

- Orders: `src/live_loop.init_order_client` wires to `src.order_client` (Binance Futures via ccxt) using idempotent client and `runs/llm_state.json`.
- Alerts: `src.live_loop.send_telegram_alert` uses `telegram` block from `llm_config.json` when enabled.
