#!/bin/bash
# NASDAQ IPO Otomatik Keşif Cron Job
# Her 6 saatte bir çalışır

# Proje dizinine git
cd /Users/ahmet/ATR/simple_trader/projects/nasdaq_ipo

# Log dosyası
LOG_FILE="auto_discovery.log"

# Tarih ve saat
echo "=========================================" >> $LOG_FILE
echo "Otomatik IPO Keşfi Başlatıldı: $(date)" >> $LOG_FILE
echo "=========================================" >> $LOG_FILE

# Python scriptini çalıştır
python3 auto_ipo_tracker.py >> $LOG_FILE 2>&1

# Sonuç
if [ $? -eq 0 ]; then
    echo "✅ Otomatik keşif başarılı: $(date)" >> $LOG_FILE
else
    echo "❌ Otomatik keşif hatası: $(date)" >> $LOG_FILE
fi

echo "" >> $LOG_FILE

# Log dosyasını temizle (son 1000 satır tut)
tail -n 1000 $LOG_FILE > $LOG_FILE.tmp && mv $LOG_FILE.tmp $LOG_FILE
