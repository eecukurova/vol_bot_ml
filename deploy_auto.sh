#!/bin/bash

# Volensy Quik Gain Otomatik Deployment Script
# Passphrase sorulduğunda "deneme_oto" yazın

set -e

SSH_KEY="$HOME/deneme_oto"
SSH_HOST="root@139.59.163.105"
TARGET_DIR="/root/volensy_quik_gain"
TAR_FILE="/tmp/volensy_quik_gain.tar.gz"
PROJECT_DIR="/Users/eralpcukurova/volensy_quik_gain/volensy_quik_gain"

echo "🚀 Volensy Quik Gain otomatik kurulum başlatılıyor..."
echo ""

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
    . 2>/dev/null

echo "✅ Paket oluşturuldu: /tmp/volensy_quik_gain.tar.gz"
echo ""

# Dosyaları sunucuya kopyala
echo "📤 Dosyalar sunucuya kopyalanıyor..."
echo "   (Passphrase sorulduğunda 'deneme_oto' yazın)"
scp -i "$SSH_KEY" \
    /tmp/volensy_quik_gain.tar.gz \
    "$SSH_HOST:/tmp/"

echo "✅ Dosyalar sunucuya kopyalandı"
echo ""

# Kurulum scriptini sunucuya kopyala
echo "📤 Kurulum scripti kopyalanıyor..."
scp -i "$SSH_KEY" \
    "$PROJECT_DIR/deploy_setup.sh" \
    "$SSH_HOST:/tmp/"

echo "✅ Kurulum scripti kopyalandı"
echo ""

# Sunucuda kurulumu çalıştır
echo "🔧 Sunucuda kurulum yapılıyor..."
echo "   (Passphrase sorulduğunda 'deneme_oto' yazın)"
ssh -i "$SSH_KEY" "$SSH_HOST" << 'ENDSSH'
    chmod +x /tmp/deploy_setup.sh
    /tmp/deploy_setup.sh
ENDSSH

echo ""
echo "✅ Kurulum tamamlandı!"
echo ""
echo "📁 Proje dizini: $TARGET_DIR"
echo ""
echo "🔧 Sunucuya bağlanmak için:"
echo "   ssh -i $SSH_KEY $SSH_HOST"
echo ""
echo "📋 Projeyi kontrol etmek için:"
echo "   ssh -i $SSH_KEY $SSH_HOST 'ls -la $TARGET_DIR'"

