#!/bin/bash
# XRP ATR Projesi - Sunucuya Deploy Scripti

set -e

echo "🚀 XRP ATR Projesi - Sunucuya Deploy"
echo ""

# Sunucu bilgileri
SERVER="root@159.65.94.27"
SERVER_DIR="/root/ATR/XRP_ATR"
LOCAL_DIR="/Users/ahmet/ATR/XRP_ATR"

# 1. Dosyaları sunucuya kopyala
echo "1️⃣ Dosyalar sunucuya kopyalanıyor..."
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
    --exclude 'runs/*.log' --exclude 'runs/*.json' \
    "$LOCAL_DIR/" "$SERVER:$SERVER_DIR/"

echo "   ✅ Dosyalar kopyalandı"

# 2. Sunucuda setup script'ini çalıştır
echo ""
echo "2️⃣ Sunucuda kurulum yapılıyor..."
ssh "$SERVER" << 'ENDSSH'
cd /root/ATR/XRP_ATR

# Virtual environment kontrol ve oluştur
echo "📦 Virtual environment kontrol ediliyor..."
if [ ! -d "venv" ]; then
    echo "   Virtual environment oluşturuluyor..."
    python3 -m venv venv
    echo "   ✅ Virtual environment oluşturuldu"
else
    echo "   ✅ Virtual environment mevcut"
fi

# Dependencies kurulumu
echo ""
echo "📥 Dependencies kuruluyor..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "   ✅ Dependencies kuruldu"

# Model dosyaları kontrol
echo ""
echo "🤖 Model dosyaları kontrol ediliyor..."
if [ ! -f "models/seqcls.pt" ]; then
    echo "   ⚠️  models/seqcls.pt bulunamadı!"
    exit 1
fi
if [ ! -f "models/feat_cols.json" ]; then
    echo "   ⚠️  models/feat_cols.json bulunamadı!"
    exit 1
fi
echo "   ✅ Model dosyaları mevcut"

# Config kontrol
echo ""
echo "⚙️  Config dosyaları kontrol ediliyor..."
if [ ! -f "configs/llm_config.json" ]; then
    echo "   ❌ configs/llm_config.json bulunamadı!"
    exit 1
fi
if [ ! -f "configs/train_15m.json" ]; then
    echo "   ❌ configs/train_15m.json bulunamadı!"
    exit 1
fi
echo "   ✅ Config dosyaları mevcut"

# Runs dizini oluştur
echo ""
echo "📁 Runs dizini oluşturuluyor..."
mkdir -p runs
echo "   ✅ Runs dizini hazır"

# Systemd service kurulumu
echo ""
echo "🔧 Systemd service kuruluyor..."
if [ -f "xrp_atr_live.service" ]; then
    cp xrp_atr_live.service /etc/systemd/system/
    systemctl daemon-reload
    echo "   ✅ Service dosyası kopyalandı"
    echo "   ✅ Systemd daemon reload edildi"
else
    echo "   ⚠️  xrp_atr_live.service bulunamadı!"
    exit 1
fi

# Service etkinleştir
echo ""
echo "🔄 Service etkinleştiriliyor..."
systemctl enable xrp_atr_live.service
echo "   ✅ Service etkinleştirildi (boot'ta başlayacak)"

# Mevcut service'i durdur (varsa)
echo ""
echo "⏸️  Mevcut service durduruluyor (varsa)..."
systemctl stop xrp_atr_live.service 2>/dev/null || true
sleep 1

# Service başlat
echo ""
echo "▶️  Service başlatılıyor..."
systemctl start xrp_atr_live.service
sleep 3

# Service durumu kontrol
echo ""
echo "📊 Service durumu kontrol ediliyor..."
if systemctl is-active --quiet xrp_atr_live.service; then
    echo "   ✅ Service çalışıyor!"
    systemctl status xrp_atr_live.service --no-pager -l | head -20
else
    echo "   ⚠️  Service çalışmıyor. Logları kontrol edin:"
    echo "      tail -f /root/ATR/XRP_ATR/runs/xrp_atr_live.log"
    echo "      journalctl -u xrp_atr_live.service -n 50 --no-pager"
    exit 1
fi

echo ""
echo "✅ Kurulum tamamlandı!"
ENDSSH

echo ""
echo "🎉 Deploy tamamlandı!"
echo ""
echo "📊 Sunucuda logları görmek için:"
echo "   ssh $SERVER 'tail -f $SERVER_DIR/runs/xrp_atr_live.log'"
echo ""
echo "📋 Service durumu:"
echo "   ssh $SERVER 'systemctl status xrp_atr_live.service'"
echo ""
echo "🔄 Service yönetimi:"
echo "   ssh $SERVER 'systemctl restart xrp_atr_live.service'  # Yeniden başlat"
echo "   ssh $SERVER 'systemctl stop xrp_atr_live.service'      # Durdur"
echo "   ssh $SERVER 'systemctl start xrp_atr_live.service'      # Başlat"

