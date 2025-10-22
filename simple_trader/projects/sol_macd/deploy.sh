#!/bin/bash
# SOL MACD Trend Trader Deploy Script

echo "🚀 SOL MACD Trend Trader Deploy Script"
echo "======================================"

# Sunucu bilgileri
SERVER="159.65.94.27"
USER="root"
KEY="~/.ssh/ahmet_key"
PROJECT_DIR="/root/simple_trader/projects/sol_macd"

# Local dosya yolu
LOCAL_DIR="/Users/ahmet/ATR/simple_trader/projects/sol_macd"

echo "📁 Dosyaları sunucuya kopyalıyor..."

# Dosyaları kopyala
scp -i $KEY -r $LOCAL_DIR/* $USER@$SERVER:$PROJECT_DIR/

if [ $? -eq 0 ]; then
    echo "✅ Dosyalar başarıyla kopyalandı"
else
    echo "❌ Dosya kopyalama hatası"
    exit 1
fi

echo "🔧 Service'i kuruyor..."

# SSH ile sunucuda komutları çalıştır
ssh -i $KEY $USER@$SERVER << 'EOF'
cd /root/simple_trader/projects/sol_macd

# Service dosyasını kopyala
sudo cp sol-macd-trader.service /etc/systemd/system/

# Systemd reload
sudo systemctl daemon-reload

# Service'i enable et
sudo systemctl enable sol-macd-trader.service

# Service'i başlat
sudo systemctl start sol-macd-trader.service

# Durumu kontrol et
echo "📊 Service durumu:"
sudo systemctl status sol-macd-trader.service --no-pager

echo "📝 Son loglar:"
tail -n 20 sol_macd_trading.log 2>/dev/null || echo "Log dosyası henüz oluşmadı"

echo "✅ Deploy tamamlandı!"
EOF

if [ $? -eq 0 ]; then
    echo "🎉 SOL MACD Trend Trader başarıyla deploy edildi!"
    echo ""
    echo "📋 Kontrol komutları:"
    echo "  sudo systemctl status sol-macd-trader.service"
    echo "  sudo systemctl restart sol-macd-trader.service"
    echo "  tail -f /root/simple_trader/projects/sol_macd/sol_macd_trading.log"
else
    echo "❌ Deploy hatası"
    exit 1
fi
