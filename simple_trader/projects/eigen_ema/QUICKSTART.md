# Eigen EMA Multi-Timeframe Crossover Trader

## 🚀 Quick Start

1. **Clone and Setup**
```bash
git clone <repository-url>
cd simple_trader/projects/eigen_ema
pip install -r requirements.txt
```

2. **Configure**
```bash
cp eigen_ema_multi_config.json.example eigen_ema_multi_config.json
# Edit config with your API keys and settings
```

3. **Run**
```bash
python3 eigen_ema_multi_trader.py
```

## 📊 Key Features

- **Multi-Timeframe Analysis**: 15m, 30m, 1h
- **EMA Crossover Strategy**: 12/26 EMA crossovers
- **Heikin Ashi Candles**: Cleaner signals
- **Risk Management**: TP/SL + Break-even
- **Telegram Notifications**: Real-time alerts
- **Idempotent Orders**: Duplicate protection

## ⚙️ Configuration

### Basic Settings
- `symbol`: Trading pair (e.g., "PENGU/USDT")
- `trade_amount_usd`: Position size in USD
- `leverage`: Leverage multiplier (default: 10)

### Timeframe Settings
- `15m`: TP 0.1%, SL 1.0%
- `30m`: TP 0.2%, SL 1.0%  
- `1h`: TP 0.4%, SL 1.0%

### Risk Management
- `break_even_enabled`: Move SL to entry when profitable
- `break_even_percentage`: Trigger level (default: 2.5%)
- `max_positions`: Maximum concurrent positions

## 🛠️ Service Management

```bash
# Install service
sudo cp eigen-ema-multi-trader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable eigen-ema-multi-trader.service

# Start/Stop/Restart
sudo systemctl start eigen-ema-multi-trader.service
sudo systemctl stop eigen-ema-multi-trader.service
sudo systemctl restart eigen-ema-multi-trader.service

# Check status
sudo systemctl status eigen-ema-multi-trader.service

# View logs
sudo journalctl -u eigen-ema-multi-trader.service -f
```

## 📱 Telegram Setup

1. Create bot with @BotFather
2. Get bot token
3. Get chat ID
4. Update config:
```json
"telegram": {
  "enabled": true,
  "bot_token": "YOUR_BOT_TOKEN",
  "chat_id": "YOUR_CHAT_ID"
}
```

## 🔍 Monitoring

### Check Positions
```bash
python3 -c "
import ccxt, json
with open('eigen_ema_multi_config.json', 'r') as f: cfg = json.load(f)
exchange = ccxt.binance({'apiKey': cfg['api_key'], 'secret': cfg['secret'], 'options': {'defaultType': 'future'}})
positions = exchange.fetch_positions()
active = [p for p in positions if float(p['contracts']) > 0]
print(f'Active positions: {len(active)}')
for pos in active: print(f'{pos[\"symbol\"]}: {pos[\"side\"]} {pos[\"contracts\"]} @ {pos[\"entryPrice\"]}')
"
```

### Check Open Orders
```bash
python3 -c "
import ccxt, json
with open('eigen_ema_multi_config.json', 'r') as f: cfg = json.load(f)
exchange = ccxt.binance({'apiKey': cfg['api_key'], 'secret': cfg['secret'], 'options': {'defaultType': 'future'}})
orders = exchange.fetch_open_orders('PENGU/USDT:USDT')
print(f'Open orders: {len(orders)}')
for order in orders: print(f'{order[\"type\"]} {order[\"side\"]} {order[\"amount\"]} @ {order.get(\"stopPrice\", \"N/A\")}')
"
```

## 🧪 Testing

```bash
# Test API connection
python3 test_binance_api.py

# Test EMA crossover
python3 test_ema_crossover.py

# Test with mock data
python3 test_mock_signals.py
```

## 📊 Strategy Logic

1. **Signal Detection**: EMA crossover on multiple timeframes
2. **Priority System**: 1h > 30m > 15m
3. **Position Opening**: Market order with SL/TP
4. **Risk Management**: Break-even when profitable
5. **Position Monitoring**: Real-time PnL tracking

## 🚨 Troubleshooting

### Common Issues
- **API Key Error**: Check API permissions
- **Position Not Opening**: Check logs for ORDER_FAILED
- **No Telegram**: Verify bot token and chat ID
- **State Issues**: Delete `runs/ema_crossover_state.json`

### Debug Commands
```bash
# Check service status
sudo systemctl status eigen-ema-multi-trader.service

# View recent errors
sudo journalctl -u eigen-ema-multi-trader.service -n 50 | grep ERROR

# Restart service
sudo systemctl restart eigen-ema-multi-trader.service
```

## ⚠️ Disclaimer

This software is for educational purposes only. Use at your own risk. The developers are not responsible for any financial losses.

## 📞 Support

- **Issues**: GitHub Issues
- **Documentation**: Full README.md
- **Telegram**: @your_telegram

---

**⭐ Star this project if you find it useful!**
