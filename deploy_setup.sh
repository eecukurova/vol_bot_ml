#!/bin/bash

# Volensy Quik Gain Deployment Script
# Bu script sunucuda /tmp/volensy_quik_gain.tar.gz dosyasının olduğunu varsayar

set -e

TARGET_DIR="/root/volensy_quik_gain"
TAR_FILE="/tmp/volensy_quik_gain.tar.gz"

echo "🚀 Volensy Quik Gain kurulumu başlatılıyor..."

# Hedef dizini oluştur
echo "📁 Hedef dizin oluşturuluyor: $TARGET_DIR"
mkdir -p "$TARGET_DIR"

# Eski dosyaları temizle (varsa)
if [ -d "$TARGET_DIR" ] && [ "$(ls -A $TARGET_DIR)" ]; then
    echo "🧹 Eski dosyalar temizleniyor..."
    rm -rf "$TARGET_DIR"/*
fi

# Dosyaları çıkar
if [ -f "$TAR_FILE" ]; then
    echo "📦 Dosyalar çıkarılıyor..."
    tar -xzf "$TAR_FILE" -C "$TARGET_DIR" --strip-components=0
    echo "✅ Dosyalar başarıyla çıkarıldı"
else
    echo "❌ Hata: $TAR_FILE bulunamadı!"
    echo "Lütfen önce dosyaları sunucuya kopyalayın:"
    echo "  scp -i ~/deneme_oto /tmp/volensy_quik_gain.tar.gz root@139.59.163.105:/tmp/"
    exit 1
fi

# Python3 kontrolü
echo "🐍 Python kontrolü yapılıyor..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 bulunamadı! Kurulum yapılıyor..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version)
echo "✅ $PYTHON_VERSION bulundu"

# Virtual environment oluştur
echo "📦 Virtual environment oluşturuluyor..."
cd "$TARGET_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment oluşturuldu"
else
    echo "✅ Virtual environment zaten mevcut"
fi

# Geçici dosyalar için proje dizini altında tmp klasörü oluştur
mkdir -p "$TARGET_DIR/tmp"
export TMPDIR="$TARGET_DIR/tmp"
export TMP="$TARGET_DIR/tmp"
export TEMP="$TARGET_DIR/tmp"

# Virtual environment'ı aktif et
source venv/bin/activate

# pip güncelle (cache olmadan, geçici dosyalar proje dizinine)
echo "📦 pip güncelleniyor..."
pip install --upgrade pip --quiet --no-cache-dir

# Bağımlılıkları kur (cache olmadan)
echo "📚 Python bağımlılıkları kuruluyor..."

# Ana dizindeki requirements.txt varsa kur
if [ -f "requirements.txt" ]; then
    echo "📋 Ana requirements.txt kuruluyor..."
    pip install -r requirements.txt --quiet --no-cache-dir
fi

# Alt dizinlerdeki requirements.txt dosyalarını bul ve kur
echo "📋 Alt dizinlerdeki requirements.txt dosyaları kontrol ediliyor..."
find . -name "requirements.txt" -type f | while read req_file; do
    if [ "$req_file" != "./requirements.txt" ]; then
        echo "  📋 $req_file kuruluyor..."
        pip install -r "$req_file" --quiet --no-cache-dir
    fi
done

# Geçici dosyaları temizle
echo "🧹 Geçici dosyalar temizleniyor..."
rm -rf "$TARGET_DIR/tmp"/* 2>/dev/null || true

# Çalıştırılabilir dosyaları kontrol et
echo "🔧 Çalıştırılabilir dosyalar kontrol ediliyor..."
find . -name "*.py" -type f -exec chmod +x {} \; 2>/dev/null || true
find . -name "*.sh" -type f -exec chmod +x {} \; 2>/dev/null || true

# .env dosyası kontrolü
if [ ! -f "$TARGET_DIR/.env" ] && [ -f "$TARGET_DIR/env.example" ]; then
    echo "⚠️  .env dosyası bulunamadı. env.example'dan kopyalanıyor..."
    cp "$TARGET_DIR/env.example" "$TARGET_DIR/.env"
    echo "📝 Lütfen .env dosyasını düzenleyin: nano $TARGET_DIR/.env"
fi

echo ""
echo "✅ Kurulum tamamlandı!"
echo ""
echo "📁 Proje dizini: $TARGET_DIR"
echo "🔧 Sonraki adımlar:"
echo "   1. .env dosyasını düzenleyin (gerekirse): nano $TARGET_DIR/.env"
echo "   2. Virtual environment'ı aktif edin: cd $TARGET_DIR && source venv/bin/activate"
echo "   3. Projeyi çalıştırın: python3 <script_name>.py"
echo ""
echo "📋 Kurulu Python paketleri:"
pip list | head -20

# Virtual environment'dan çık
deactivate

