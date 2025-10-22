#!/bin/bash

# PENGU EMA Trader Deployment Script

echo "🚀 PENGU EMA Trader Deploy Başlatılıyor..."

# Copy files to server
echo "📁 Dosyalar sunucuya kopyalanıyor..."
scp -i ~/.ssh/ahmet_key -r /Users/ahmet/ATR/simple_trader/projects/pengu_ema/* root@159.65.94.27:/root/simple_trader/projects/pengu_ema/

# Install service
echo "⚙️ Systemd servisi kuruluyor..."
ssh -i ~/.ssh/ahmet_key root@159.65.94.27 "
    cp /root/simple_trader/projects/pengu_ema/pengu-ema-trader.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable pengu-ema-trader.service
    echo '✅ Servis kuruldu ve etkinleştirildi'
"

# Start service
echo "🔄 Servis başlatılıyor..."
ssh -i ~/.ssh/ahmet_key root@159.65.94.27 "
    systemctl start pengu-ema-trader.service
    sleep 3
    systemctl status pengu-ema-trader.service --no-pager -l | head -10
"

echo "✅ PENGU EMA Trader başarıyla deploy edildi!"
echo "📊 Servis durumu kontrol edilebilir: systemctl status pengu-ema-trader.service"
echo "📝 Loglar: tail -f /root/simple_trader/projects/pengu_ema/pengu_ema_trading.log"