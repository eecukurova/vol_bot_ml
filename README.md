# ATR + SuperTrend Auto Trader

Otomatik kripto para trading sistemi - ATR + SuperTrend stratejisi ile Binance Futures üzerinde otomatik işlem yapar.

## 🎯 **Sistem Özellikleri**

### **✅ Otomatik Trading:**
- **Gerçek zamanlı sinyal üretimi** - ATR + SuperTrend + EMA(1) kombinasyonu
- **Binance Futures entegrasyonu** - Otomatik pozisyon açma/kapama
- **Stop Loss & Take Profit** - Otomatik risk yönetimi
- **Telegram bildirimleri** - Anlık sinyal ve pozisyon bildirimleri
- **Idempotent Order Management** - Çift emir koruması ve state management

### **🛡️ Risk Yönetimi:**
- **Pozisyon büyüklüğü**: $100 sabit (5 EIGEN × 10x leverage)
- **Stop Loss**: 0.6% sabit
- **Take Profit**: 0.6% sabit
- **Sinyal cooldown**: 5 dakika (spam engelleme)
- **Çoklu pozisyon koruması**: Aynı coin için tek pozisyon
- **SL/TP Monitor**: 20 saniye sonra eksik SL/TP kontrolü

### **📊 Desteklenen Coinler:**
- **EIGEN/USDT** - Ana trading coin
- **SOL/USDT** - İkincil trading coin
- **Genişletilebilir** - Yeni coinler kolayca eklenebilir

## 🚀 **Kurulum**

### **Gereksinimler:**
- Python 3.8+
- Binance Futures hesabı
- Telegram bot token

### **Kurulum Adımları:**

```bash
# Repository'yi klonla
git clone <repository-url>
cd ATR

# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### **Konfigürasyon:**

`simple_trader/auto_config.json` dosyasını düzenle:

```json
{
  "api_key": "BINANCE_API_KEY",
  "secret": "BINANCE_SECRET",
  "sandbox": false,
  "symbol": "EIGEN/USDT",
  "position_size": 5,
  "leverage": 10,
  "sl": 0.006,
  "tp": 0.006,
  "trailing_mult": 8.0,
  "interval": 60
}
```

### **Telegram Bot Kurulumu:**

1. **Bot oluştur**: @BotFather ile yeni bot oluştur
2. **Token al**: Bot token'ını al
3. **Chat ID al**: Hedef chat'in ID'sini al
4. **Kodda güncelle**: `auto_trader.py` dosyasında token ve chat ID'yi güncelle

## 📈 **Sinyal Mantığı**

### **LONG Sinyali (3 Koşul):**
1. **C1**: `close > SuperTrend`
2. **C2**: `EMA(1) > SuperTrend`  
3. **C3**: `prev_EMA(1) <= prev_SuperTrend` (EMA SuperTrend'i yukarı kesiyor)

### **SHORT Sinyali (3 Koşul):**
1. **C1**: `close < SuperTrend`
2. **C2**: `EMA(1) < SuperTrend`
3. **C3**: `prev_EMA(1) >= prev_SuperTrend` (EMA SuperTrend'i aşağı kesiyor)

### **HOLD Durumu:**
- Yukarıdaki koşullardan hiçbiri sağlanmıyorsa HOLD

## 🔧 **Kullanım**

### **Manuel Çalıştırma:**

```bash
# EIGEN/USDT için
cd simple_trader
python3 auto_trader.py

# SOL/USDT için
python3 sol_trader.py
```

### **Systemd Servisleri:**

```bash
# Servisleri başlat
sudo systemctl start eigen-trader.service
sudo systemctl start sol-trader.service

# Servisleri durdur
sudo systemctl stop eigen-trader.service
sudo systemctl stop sol-trader.service

# Servis durumunu kontrol et
sudo systemctl status eigen-trader.service
sudo systemctl status sol-trader.service

# Logları izle
sudo journalctl -u eigen-trader.service -f
sudo journalctl -u sol-trader.service -f
```

### **Servis Kurulumu:**

```bash
# Servis dosyalarını kopyala
sudo cp /etc/systemd/system/eigen-trader.service /etc/systemd/system/
sudo cp /etc/systemd/system/sol-trader.service /etc/systemd/system/

# Servisleri etkinleştir
sudo systemctl enable eigen-trader.service
sudo systemctl enable sol-trader.service
```

## 📊 **Monitoring**

### **Log Takibi:**

```bash
# Canlı log takibi
sudo journalctl -u eigen-trader.service -f --no-pager

# Son 50 log
sudo journalctl -u eigen-trader.service -n 50 --no-pager

# Belirli tarih aralığı
sudo journalctl -u eigen-trader.service --since "2024-01-01" --until "2024-01-02"
```

### **Pozisyon Kontrolü:**

```bash
# Manuel pozisyon kontrolü
cd simple_trader
python3 -c "
import ccxt
import json

with open('auto_config.json', 'r') as f:
    cfg = json.load(f)

exchange = ccxt.binance({
    'apiKey': cfg['api_key'],
    'secret': cfg['secret'],
    'sandbox': cfg.get('sandbox', False),
    'options': {'defaultType': 'future'}
})

positions = exchange.fetch_positions()
for pos in positions:
    if float(pos['contracts']) > 0:
        print(f'{pos[\"symbol\"]}: {pos[\"side\"]} {pos[\"contracts\"]} @ {pos[\"entryPrice\"]}')
"
```

## 🛡️ **Güvenlik Özellikleri**

### **Pozisyon Koruması:**
- **Symbol-specific kontrol**: Aynı coin için tek pozisyon (EIGEN/USDT:USDT format desteği)
- **Çift kontrol**: Pozisyon açmadan önce 2 kez kontrol
- **Sinyal cooldown**: 5 dakika bekleme süresi
- **Persistent signal state**: Servis restart sonrası signal state korunur

### **Idempotent Order Management:**
- **Deterministic client order IDs**: SHA1 hash ile benzersiz ID üretimi
- **State persistence**: JSON dosyasında order durumu saklanır
- **Retry mechanism**: Ağ hatalarında exponential backoff ile yeniden deneme
- **Duplicate detection**: Aynı order'ın tekrar gönderilmesini engeller
- **Reconciliation**: Servis restart sonrası pending order'ları uzlaştırır

### **Risk Yönetimi:**
- **Sabit pozisyon büyüklüğü**: $100 limit (5 EIGEN)
- **Sabit SL/TP**: 0.6% risk
- **Leverage kontrolü**: 10x maksimum
- **Margin kontrolü**: Yetersiz margin kontrolü
- **SL/TP Monitor**: 20 saniye sonra eksik SL/TP kontrolü ve otomatik oluşturma

### **Hata Yönetimi:**
- **API hata kontrolü**: Bağlantı kopması durumunda yeniden deneme
- **Pozisyon kontrolü**: Hatalı pozisyon durumunda sistem durdurma
- **Log kayıtları**: Tüm işlemler detaylı loglanır

## 📱 **Telegram Bildirimleri**

### **Sinyal Bildirimi:**
```
🎯 YENİ SİNYAL!

📊 Symbol: EIGEN/USDT
📈 Sinyal: LONG
💰 Fiyat: $1.8960
💪 Güç: 0.11%
📊 SuperTrend: $1.8938
📈 EMA(1): $1.8960
⏰ Zaman: 07:30:50 UTC

🚀 Pozisyon açılıyor...
```

### **Pozisyon Bildirimi:**
```
🚀 YENİ POZİSYON AÇILDI

📊 Symbol: EIGEN/USDT
📈 Yön: LONG
💰 Fiyat: $1.8973
🛡️ Stop Loss: $1.8859
🎯 Take Profit: $1.9087
📦 Miktar: 1054.129553
⏰ Zaman: 09:10:38 UTC
💪 Güç: 0.18%
```

## 🔧 **Konfigürasyon Parametreleri**

### **Trading Parametreleri:**
- `position_size`: Pozisyon büyüklüğü ($)
- `leverage`: Leverage çarpanı (1-10x)
- `sl`: Stop Loss yüzdesi (0.006 = 0.6%)
- `tp`: Take Profit yüzdesi (0.006 = 0.6%)
- `interval`: Kontrol aralığı (saniye)

### **Sinyal Parametreleri:**
- `atr_period`: ATR periyodu (varsayılan: 14)
- `atr_multiplier`: ATR çarpanı (varsayılan: 2.0)
- `supertrend_period`: SuperTrend periyodu (varsayılan: 14)
- `supertrend_multiplier`: SuperTrend çarpanı (varsayılan: 1.5)
- `ema_period`: EMA periyodu (varsayılan: 1)

## 📈 **Performance Tracking**

### **Backtesting:**
```bash
# Backtest çalıştır
cd simple_trader
python3 backtest_comparison.py
```

### **TradingView Pine Script:**
- `atr_supertrend_signals.pine` dosyası TradingView'de kullanılabilir
- Gerçek zamanlı sinyal görselleştirmesi
- Strateji kurallarının doğrulanması

## 🚨 **Troubleshooting**

### **Yaygın Sorunlar:**

1. **API Bağlantı Hatası:**
   ```bash
   # API anahtarlarını kontrol et
   # Sandbox modunu kontrol et
   # İnternet bağlantısını kontrol et
   ```

2. **Pozisyon Açılamıyor:**
   ```bash
   # Futures hesabında yeterli bakiye var mı?
   # Leverage ayarları doğru mu?
   # Symbol doğru mu?
   ```

3. **Telegram Bildirimleri Gelmiyor:**
   ```bash
   # Bot token doğru mu?
   # Chat ID doğru mu?
   # Bot chat'e eklenmiş mi?
   ```

### **Log Analizi:**

```bash
# Hata logları
sudo journalctl -u eigen-trader.service | grep "❌"

# Pozisyon logları
sudo journalctl -u eigen-trader.service | grep "📊"

# Sinyal logları
sudo journalctl -u eigen-trader.service | grep "🎯"
```

## 📋 **Dosya Yapısı**

```
ATR/
├── simple_trader/
│   ├── auto_trader.py          # Ana trading script
│   ├── sol_trader.py           # SOL/USDT trading script
│   ├── order_client.py         # Idempotent order management
│   ├── auto_config.json        # EIGEN/USDT konfigürasyonu
│   ├── sol_config.json         # SOL/USDT konfigürasyonu
│   ├── backtest_comparison.py  # Backtesting script
│   ├── atr_supertrend_signals.pine # TradingView Pine Script
│   ├── scripts/                # Test scriptleri
│   │   ├── sim_network_glitch.py
│   │   ├── restart_reconcile_demo.py
│   │   └── duplicate_id_demo.py
│   └── requirements.txt        # Python bağımlılıkları
├── /etc/systemd/system/
│   ├── eigen-trader.service    # EIGEN/USDT systemd servisi
│   └── sol-trader.service      # SOL/USDT systemd servisi
└── README.md                   # Bu dosya
```

## 🔄 **Güncellemeler**

### **Sistem Güncellemesi:**
```bash
# Yeni kodu çek
git pull origin main

# Servisleri yeniden başlat
sudo systemctl restart eigen-trader.service
sudo systemctl restart sol-trader.service
```

### **Konfigürasyon Güncellemesi:**
```bash
# Konfigürasyonu düzenle
nano simple_trader/auto_config.json

# Servisleri yeniden başlat
sudo systemctl restart eigen-trader.service
```

## ⚠️ **Önemli Notlar**

1. **Risk Uyarısı**: Kripto para tradingi yüksek risk içerir
2. **Test Et**: Gerçek para ile işlem yapmadan önce test edin
3. **Monitor Et**: Sistemin sürekli izlenmesi gerekir
4. **Backup**: Konfigürasyon dosyalarını yedekleyin
5. **Güncel Tut**: Sistem güncellemelerini takip edin

## 📞 **Destek**

- **GitHub Issues**: Hata raporları ve öneriler
- **Telegram**: Anlık bildirimler ve durum takibi
- **Loglar**: Detaylı sistem logları

## 📄 **Lisans**

MIT License - Detaylar için LICENSE dosyasına bakın.

---

**⚠️ UYARI**: Bu sistem yüksek risk içerir. Sadece kaybetmeyi göze alabileceğiniz para ile kullanın.