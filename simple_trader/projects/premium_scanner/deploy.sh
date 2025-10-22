#!/bin/bash

echo "🚀 Premium Stock Scanner Deployment"
echo "=================================="

# Proje dizini
PROJECT_DIR="/root/simple_trader/projects/premium_scanner"
SERVICE_NAME="premium-scanner.service"

echo "📁 Proje dizini: $PROJECT_DIR"

# Dizin oluştur
mkdir -p $PROJECT_DIR

# Service dosyasını kopyala
echo "📋 Service dosyası kopyalanıyor..."
cp premium-scanner.service /etc/systemd/system/

# Service'i etkinleştir
echo "⚙️ Service etkinleştiriliyor..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# Service'i başlat
echo "🚀 Service başlatılıyor..."
systemctl start $SERVICE_NAME

# Durum kontrolü
echo "📊 Service durumu:"
systemctl status $SERVICE_NAME --no-pager -l | head -10

echo ""
echo "✅ Premium Stock Scanner başarıyla deploy edildi!"
echo "📱 Telegram bildirimleri aktif"
echo "🕯️ Heikin Ashi ile 4H ve 1H timeframe"
echo "📈 AMD, NVDA, TSLA gibi teknoloji hisseleri taranıyor"
echo ""
echo "🔍 Logları kontrol etmek için:"
echo "journalctl -u $SERVICE_NAME -f"
echo ""
echo "📁 Log dosyası: $PROJECT_DIR/premium_scanner.log"
