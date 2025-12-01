#!/bin/bash
# ETH Projesi - Sunucu Kurulum Scripti
# Bu script sunucuda çalıştırılmalı

set -e

echo "🚀 ETH Projesi - Sunucu Kurulumu"
echo ""

PROJECT_DIR="/root/ATR/ETH"
cd "$PROJECT_DIR"

# 1. Virtual environment kontrol ve oluştur
echo "1️⃣ Virtual environment kontrol ediliyor..."
if [ ! -d "venv" ]; then
    echo "   Virtual environment oluşturuluyor..."
    python3 -m venv venv
    echo "   ✅ Virtual environment oluşturuldu"
else
    echo "   ✅ Virtual environment mevcut"
fi

# 2. Dependencies kurulumu
echo ""
echo "2️⃣ Dependencies kuruluyor..."
source venv/bin/activate
pip install --upgrade pip -q
pip install torch ccxt pandas numpy scikit-learn typer -q
echo "   ✅ Dependencies kuruldu"

# 3. Dependencies test
echo ""
echo "3️⃣ Dependencies test ediliyor..."
python3 -c "import torch, ccxt, pandas; print('   ✅ Dependencies OK')" || {
    echo "   ❌ Dependencies hatası!"
    exit 1
}

# 4. Model dosyaları kontrol
echo ""
echo "4️⃣ Model dosyaları kontrol ediliyor..."
if [ ! -f "models/seqcls.pt" ]; then
    echo "   ⚠️  models/seqcls.pt bulunamadı!"
    echo "   Model dosyalarını kopyalayın: models/seqcls.pt, models/feat_cols.json"
    exit 1
fi
if [ ! -f "models/feat_cols.json" ]; then
    echo "   ⚠️  models/feat_cols.json bulunamadı!"
    exit 1
fi
echo "   ✅ Model dosyaları mevcut"

# 5. Config kontrol
echo ""
echo "5️⃣ Config dosyaları kontrol ediliyor..."
if [ ! -f "configs/llm_config.json" ]; then
    echo "   ❌ configs/llm_config.json bulunamadı!"
    exit 1
fi
if [ ! -f "configs/train_15m.json" ]; then
    echo "   ❌ configs/train_15m.json bulunamadı!"
    exit 1
fi
echo "   ✅ Config dosyaları mevcut"

# 6. Runs dizini oluştur
echo ""
echo "6️⃣ Runs dizini oluşturuluyor..."
mkdir -p runs
echo "   ✅ Runs dizini hazır"

# 7. Systemd service kurulumu
echo ""
echo "7️⃣ Systemd service kuruluyor..."
if [ -f "eth_live.service" ]; then
    cp eth_live.service /etc/systemd/system/
    systemctl daemon-reload
    echo "   ✅ Service dosyası kopyalandı"
    echo "   ✅ Systemd daemon reload edildi"
else
    echo "   ⚠️  eth_live.service bulunamadı!"
    exit 1
fi

# 8. Service etkinleştir ve başlat
echo ""
echo "8️⃣ Service etkinleştiriliyor..."
systemctl enable eth_live.service
echo "   ✅ Service etkinleştirildi (boot'ta başlayacak)"

echo ""
echo "9️⃣ Service başlatılıyor..."
systemctl start eth_live.service
sleep 2

# 10. Service durumu kontrol
echo ""
echo "🔟 Service durumu kontrol ediliyor..."
if systemctl is-active --quiet eth_live.service; then
    echo "   ✅ Service çalışıyor!"
else
    echo "   ⚠️  Service çalışmıyor. Logları kontrol edin:"
    echo "      journalctl -u eth_live.service -n 50 --no-pager"
    exit 1
fi

echo ""
echo "✅ Kurulum tamamlandı!"
echo ""
echo "📊 Logları görmek için:"
echo "   tail -f $PROJECT_DIR/runs/llm_live.log"
echo ""
echo "📋 Service durumu:"
echo "   systemctl status eth_live.service"
echo ""
echo "🔄 Service yönetimi:"
echo "   systemctl restart eth_live.service  # Yeniden başlat"
echo "   systemctl stop eth_live.service      # Durdur"
echo "   systemctl start eth_live.service     # Başlat"

