#!/bin/bash

# Volensy Quik Gain Otomatik Deployment Script
# Bu script dosyaları paketler, sunucuya kopyalar ve kurulum yapar

set -e

SSH_KEY="$HOME/deneme_oto"
SSH_HOST="root@139.59.163.105"
TARGET_DIR="/root/volensy_quik_gain"
TAR_FILE="/tmp/volensy_quik_gain.tar.gz"
PROJECT_DIR="/Users/eralpcukurova/volensy_quik_gain/volensy_quik_gain"

echo "🚀 Volensy Quik Gain otomatik kurulum başlatılıyor..."

# Projeyi paketle
echo "📦 Proje paketleniyor..."
cd "$PROJECT_DIR"
tar -czf /tmp/volensy_quik_gain.tar.gz \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='*.tar.gz' \
    --exclude='*.log' \
    .

echo "✅ Paket oluşturuldu: /tmp/volensy_quik_gain.tar.gz"

# Dosyaları sunucuya kopyala
echo "📤 Dosyalar sunucuya kopyalanıyor..."
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
    /tmp/volensy_quik_gain.tar.gz \
    "$SSH_HOST:/tmp/" || {
    echo "❌ SCP hatası! Manuel kopyalama gerekebilir."
    echo "Manuel komut:"
    echo "  scp -i $SSH_KEY /tmp/volensy_quik_gain.tar.gz $SSH_HOST:/tmp/"
    exit 1
}

echo "✅ Dosyalar sunucuya kopyalandı"

# Kurulum scriptini sunucuya kopyala
echo "📤 Kurulum scripti kopyalanıyor..."
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
    "$PROJECT_DIR/deploy_setup.sh" \
    "$SSH_HOST:/tmp/" || {
    echo "⚠️  Kurulum scripti kopyalanamadı, manuel çalıştırılacak"
}

# Sunucuda kurulumu çalıştır
echo "🔧 Sunucuda kurulum yapılıyor..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_HOST" << 'ENDSSH'
    chmod +x /tmp/deploy_setup.sh
    /tmp/deploy_setup.sh
ENDSSH

echo ""
echo "✅ Kurulum tamamlandı!"
echo "📁 Proje dizini: $TARGET_DIR"
echo ""
echo "🔧 Sunucuya bağlanmak için:"
echo "   ssh -i $SSH_KEY $SSH_HOST"
echo ""
echo "📋 Projeyi çalıştırmak için:"
echo "   ssh -i $SSH_KEY $SSH_HOST 'cd $TARGET_DIR && python3 <script_name>.py'"

