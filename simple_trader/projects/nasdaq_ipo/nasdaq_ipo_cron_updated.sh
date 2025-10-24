#!/bin/bash
# NASDAQ IPO Screener - Daily Cron Job with Auto Discovery
# Runs at 17:30 Istanbul time (14:30 UTC)

# Set working directory
cd /root/simple_trader/projects/nasdaq_ipo

# Activate virtual environment
source test_env/bin/activate

# Set log file with timestamp
LOG_FILE="logs/nasdaq_ipo_$(date +%Y%m%d_%H%M%S).log"

# Create logs directory if it doesn't exist
mkdir -p logs

echo "=========================================" >> "$LOG_FILE"
echo "NASDAQ IPO Screener Başlatıldı: $(date)" >> "$LOG_FILE"
echo "=========================================" >> "$LOG_FILE"

# Step 1: Otomatik IPO Keşfi
echo "Step 1: Otomatik IPO Keşfi Başlatılıyor..." >> "$LOG_FILE"
python3 auto_ipo_discovery.py >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ IPO keşfi başarılı: $(date)" >> "$LOG_FILE"
else
    echo "❌ IPO keşfi hatası: $(date)" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"

# Step 2: Mevcut IPO'ları Tara
echo "Step 2: Mevcut IPO'lar Taranıyor..." >> "$LOG_FILE"
python app.py \
  --days 180 \
  --min_price 0.30 \
  --max_price 1.00 \
  --min_vol 500000 \
  --rsi_min 30 --rsi_max 45 \
  --adx_max 25 \
  --max_consec_below1 60 \
  --min_drawdown 70 \
  --top_n 20 \
  --log-level INFO \
  2>&1 | tee -a "$LOG_FILE"

# Log completion
echo "" >> "$LOG_FILE"
echo "=========================================" >> "$LOG_FILE"
echo "NASDAQ IPO Screener Tamamlandı: $(date)" >> "$LOG_FILE"
echo "=========================================" >> "$LOG_FILE"
