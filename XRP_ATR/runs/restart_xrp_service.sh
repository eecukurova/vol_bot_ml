#!/bin/bash

# XRP ATR Live Service Restart Script
# Bu script XRP ATR servisini restart eder ve durumunu kontrol eder

set -e

SERVICE_NAME="xrp_atr_live"
PROJECT_DIR="/root/volensy_quik_gain/XRP_ATR"
LOG_FILE="$PROJECT_DIR/runs/xrp_live.log"
CONFIG_FILE="$PROJECT_DIR/configs/llm_config.json"

echo "🔄 XRP ATR Live Service Restart Script"
echo "========================================"
echo ""

# 1. Servisi durdur
echo "⏹️  Stopping service..."
systemctl stop $SERVICE_NAME 2>/dev/null || echo "   Service was not running"
sleep 2

# 2. Eski process'leri temizle (güvenlik için)
echo "🧹 Cleaning up old processes..."
pkill -9 -f "run_live_continuous.py" 2>/dev/null || true
sleep 2

# 3. Config dosyasını kontrol et
echo "📋 Checking configuration..."
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# API key kontrolü
if ! grep -q "api_key" "$CONFIG_FILE"; then
    echo "❌ ERROR: API key not found in config file"
    exit 1
fi

# Telegram kontrolü
TELEGRAM_ENABLED=$(grep -A 1 '"telegram"' "$CONFIG_FILE" | grep -c '"enabled": true' || echo "0")
if [ "$TELEGRAM_ENABLED" -eq 0 ]; then
    echo "⚠️  WARNING: Telegram is not enabled in config"
else
    echo "✅ Telegram is enabled"
fi

# 4. Systemd service dosyasını kontrol et
echo "📋 Checking systemd service..."
if [ ! -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    echo "❌ ERROR: Systemd service file not found"
    echo "   Creating service file..."
    cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=XRP ATR Live Trading Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=/root/volensy_quik_gain/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/root/volensy_quik_gain/venv/bin/python3 $PROJECT_DIR/scripts/run_live_continuous.py
Restart=always
RestartSec=10
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    echo "✅ Service file created"
fi

# 5. Log dosyasını temizle (opsiyonel - yorum satırını kaldırarak aktif edebilirsiniz)
# echo "🧹 Clearing old logs..."
# > "$LOG_FILE"

# 6. Servisi başlat
echo "🚀 Starting service..."
systemctl daemon-reload
systemctl start $SERVICE_NAME
sleep 5

# 7. Servis durumunu kontrol et
echo ""
echo "📊 Service Status:"
echo "=================="
systemctl status $SERVICE_NAME --no-pager -l | head -15

# 8. Process kontrolü
echo ""
echo "🔍 Process Check:"
echo "================="
if ps aux | grep -v grep | grep -q "run_live_continuous.py"; then
    echo "✅ Process is running:"
    ps aux | grep -v grep | grep "run_live_continuous.py"
else
    echo "❌ Process is NOT running!"
    echo "   Checking logs for errors..."
    tail -50 "$LOG_FILE" | grep -E "(ERROR|Exception|Traceback|Failed)" || echo "   No errors found in recent logs"
fi

# 9. Son logları göster
echo ""
echo "📋 Recent Logs (last 20 lines):"
echo "================================"
tail -20 "$LOG_FILE" 2>/dev/null || echo "   Log file is empty or not accessible"

# 10. Config özeti
echo ""
echo "⚙️  Configuration Summary:"
echo "=========================="
if [ -f "$CONFIG_FILE" ]; then
    echo "   Symbol: $(grep -o '"symbol": "[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)"
    echo "   Trade Amount: $(grep -o '"trade_amount_usd": [0-9]*' "$CONFIG_FILE" | cut -d' ' -f2) USDT"
    echo "   Leverage: $(grep -o '"leverage": [0-9]*' "$CONFIG_FILE" | cut -d' ' -f2)x"
    echo "   Timeframe: $(grep -A 2 '"atr_supertrend"' "$CONFIG_FILE" | grep '"timeframe"' | cut -d'"' -f4)"
    echo "   Shadow Mode: $(grep -A 1 '"shadow_mode"' "$CONFIG_FILE" | grep '"enabled"' | grep -o 'true\|false')"
fi

echo ""
echo "✅ Restart completed!"
echo ""
echo "📝 Useful commands:"
echo "   View logs: tail -f $LOG_FILE"
echo "   Service status: systemctl status $SERVICE_NAME"
echo "   Stop service: systemctl stop $SERVICE_NAME"
echo "   Restart service: systemctl restart $SERVICE_NAME"
echo ""

