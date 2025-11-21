#!/bin/bash
# LLM Projesi - Sunucuya Deploy Script
# Kullanım: ./deploy_to_server.sh

set -e

# Sunucu bilgileri
SERVER_USER="root"
SERVER_HOST="159.65.94.27"
SERVER_PATH="/root/ATR/LLM"
SERVICE_NAME="llm_live.service"
LOCAL_DIR="/Users/ahmet/ATR/LLM"

echo "🚀 LLM Projesi - Sunucuya Deploy"
echo "=================================="
echo ""

# Değiştirilen dosyalar
FILES_TO_DEPLOY=(
    "configs/llm_config.json"
    "scripts/run_live_continuous.py"
)

echo "📤 Sunucuya gönderilecek dosyalar:"
for file in "${FILES_TO_DEPLOY[@]}"; do
    echo "   → $file"
done
echo ""

# Dosyaları sunucuya gönder
echo "📤 Dosyalar sunucuya gönderiliyor..."
for file in "${FILES_TO_DEPLOY[@]}"; do
    if [ -f "$LOCAL_DIR/$file" ]; then
        echo "   → $file"
        scp "$LOCAL_DIR/$file" "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/$file"
    else
        echo "   ⚠️  $file bulunamadı!"
    fi
done

echo ""
echo "✅ Dosyalar gönderildi!"
echo ""

# Servisi restart et
echo "🔄 Servis restart ediliyor..."
ssh "$SERVER_USER@$SERVER_HOST" "systemctl restart $SERVICE_NAME"

echo ""
echo "⏳ Servis durumu kontrol ediliyor..."
sleep 5

# Servis durumunu kontrol et
echo ""
echo "📊 Servis durumu:"
ssh "$SERVER_USER@$SERVER_HOST" "systemctl status $SERVICE_NAME --no-pager -l | head -25"

echo ""
echo "📋 Son log'lar (son 50 satır):"
ssh "$SERVER_USER@$SERVER_HOST" "tail -50 $SERVER_PATH/runs/llm_live_remote.log 2>/dev/null || tail -50 $SERVER_PATH/runs/llm_live.log 2>/dev/null || echo 'Log dosyası bulunamadı'"

echo ""
echo "✅ Deploy tamamlandı!"
echo ""
echo "📊 Log'ları izlemek için:"
echo "   ssh $SERVER_USER@$SERVER_HOST 'tail -f $SERVER_PATH/runs/llm_live_remote.log'"

