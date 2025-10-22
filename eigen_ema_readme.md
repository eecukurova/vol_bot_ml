# 🚀 EigenEMA Multi-Timeframe Trading Bot

## 📊 Genel Bakış

EigenEMA, Binance Futures üzerinde çoklu zaman dilimlerinde (15m, 30m, 1h) EMA crossover stratejisini kullanarak otomatik alım-satım yapan gelişmiş bir trading bot sistemidir. Sistem, farklı zaman dilimlerinde EMA kesişimlerini izler ve belirlenen kurallara göre pozisyon açar, yönetir ve kapatır.

## 🌟 Temel Özellikler

- **Çoklu Zaman Dilimi Analizi**: 15m, 30m ve 1h zaman dilimlerinde EMA crossover sinyallerini değerlendirir
- **Tek Pozisyon Kontrolü**: Aynı anda sadece bir pozisyon açılmasını sağlar (`single_position_only`)
- **Dinamik Risk Yönetimi**: Pozisyon kârlılığına göre Stop Loss ve Take Profit seviyelerini otomatik ayarlar
- **Trailing Stop Loss**: Pozisyon kârda iken Stop Loss seviyesini yukarı kaydırarak riski azaltır
- **Heikin Ashi Filtreleme**: Daha güvenilir sinyaller için Heikin Ashi mum grafiklerini kullanır
- **İdempotent Order Client**: Ağ sorunları ve duplike emirlere karşı koruma sağlar
- **Telegram Entegrasyonu**: Sinyal ve pozisyon bilgilerini Telegram üzerinden bildirir
- **Sistemd Servis Yapısı**: 7/24 kesintisiz çalışma için systemd servis yapısı

## 🛠️ Teknik Mimari

### 📋 Dosya Yapısı

```
eigen_ema/
├── eigen_ema_multi_trader.py     # Ana trading bot kodu
├── eigen_ema_multi_config.json   # Konfigürasyon dosyası
├── eigen-ema-multi-trader.service # Systemd servis dosyası
├── test_binance_api.py           # API test scripti
├── README.md                     # Bu dokümantasyon
├── runs/                         # Çalışma verileri
│   └── ema_crossover_state.json  # Durum kaydı
└── logs/                         # Log dosyaları
    └── ema_crossover_trading.log # Trading logları
```

### 🧩 Bileşenler

#### 1. MultiTimeframeEMATrader Sınıfı

Ana trading mantığını içeren sınıftır. Temel sorumlulukları:

- Farklı zaman dilimlerinde EMA hesaplaması ve sinyal üretimi
- Pozisyon açma, izleme ve kapatma
- Stop Loss ve Take Profit emirlerini yönetme
- Dinamik risk yönetimi ve trailing stop loss

#### 2. TechnicalIndicators Sınıfı

Teknik analiz indikatörlerini hesaplayan statik metotlar içerir:

- EMA (Exponential Moving Average)
- RSI (Relative Strength Index)
- Bollinger Bantları
- Hacim oranları
- Momentum hesaplamaları

#### 3. HeikinAshiCalculator Sınıfı

Heikin Ashi mumlarını hesaplayan statik metotlar içerir.

#### 4. IdempotentOrderClient Sınıfı

Emir gönderme işlemlerini güvenli şekilde yöneten sınıftır:

- Deterministik client order ID üretimi
- Durum yönetimi ve kalıcılığı
- Yeniden deneme mekanizması
- Duplike emir tespiti
- Reconciliation mekanizması

## ⚙️ Konfigürasyon

Sistem, `eigen_ema_multi_config.json` dosyası üzerinden yapılandırılır:

```json
{
  "api_key": "YOUR_BINANCE_API_KEY",
  "secret": "YOUR_BINANCE_SECRET_KEY",
  "sandbox": false,
  "symbol": "PENGU/USDT",
  "trade_amount_usd": 100,
  "leverage": 10,
  
  "timeframes": {
    "15m": {
      "take_profit": 0.2,
      "stop_loss": 1.0,
      "trailing_activation": 0.15,
      "trailing_step": 0.05,
      "trailing_distance": 0.3,
      "dynamic_tp": {
        "enabled": true,
        "levels": [
          {"threshold": 0.3, "tp_pct": 0.5},
          {"threshold": 0.5, "tp_pct": 0.8},
          {"threshold": 1.0, "tp_pct": 1.5}
        ]
      }
    },
    "30m": {
      "take_profit": 0.3,
      "stop_loss": 1.2,
      "trailing_activation": 0.2,
      "trailing_step": 0.05,
      "trailing_distance": 0.4,
      "dynamic_tp": {
        "enabled": true,
        "levels": [
          {"threshold": 0.4, "tp_pct": 0.6},
          {"threshold": 0.7, "tp_pct": 1.0},
          {"threshold": 1.2, "tp_pct": 2.0}
        ]
      }
    },
    "1h": {
      "take_profit": 0.5,
      "stop_loss": 1.5,
      "trailing_activation": 0.3,
      "trailing_step": 0.1,
      "trailing_distance": 0.5,
      "dynamic_tp": {
        "enabled": true,
        "levels": [
          {"threshold": 0.5, "tp_pct": 0.8},
          {"threshold": 1.0, "tp_pct": 1.5},
          {"threshold": 2.0, "tp_pct": 3.0}
        ]
      }
    }
  },
  
  "ema": {
    "fast_period": 10,
    "slow_period": 26
  },
  
  "heikin_ashi": {
    "enabled": true
  },
  
  "signal_management": {
    "single_position_only": true,
    "cooldown_after_exit": 0,
    "priority_order": ["1h", "30m", "15m"],
    "timeframe_validation": {
      "enabled": true,
      "min_candles_for_signal": 50,
      "require_confirmed_candle": true,
      "confirmation_percent": {
        "15m": 0.8,
        "30m": 0.8,
        "1h": 0.8
      }
    }
  },
  
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "notification_level": "all"
  },
  
  "idempotency": {
    "enabled": true,
    "state_file": "runs/ema_crossover_state.json",
    "retry_attempts": 3,
    "retry_delay": 1.0
  },
  
  "sl_tp": {
    "trigger_source": "MARK_PRICE",
    "hedge_mode": false
  },
  
  "logging": {
    "level": "INFO",
    "file": "logs/ema_crossover_trading.log",
    "format": "%(asctime)s - %(levelname)s - %(message)s"
  }
}
```

### 🔧 Önemli Konfigürasyon Parametreleri

#### Trading Parametreleri

- **symbol**: İşlem yapılacak sembol (örn. "PENGU/USDT")
- **trade_amount_usd**: Her işlem için kullanılacak USDT miktarı
- **leverage**: Kullanılacak kaldıraç oranı

#### Timeframe Ayarları

Her zaman dilimi için ayrı ayarlar:

- **take_profit**: Kâr alma yüzdesi
- **stop_loss**: Zarar durdurma yüzdesi
- **trailing_activation**: Trailing stop'un aktifleşeceği kâr yüzdesi
- **trailing_step**: Her adımda trailing stop'un ne kadar kaydırılacağı
- **trailing_distance**: Fiyat ile trailing stop arasındaki mesafe
- **dynamic_tp**: Kâr oranına göre dinamik TP seviyeleri

#### EMA Ayarları

- **fast_period**: Hızlı EMA periyodu
- **slow_period**: Yavaş EMA periyodu

#### Sinyal Yönetimi

- **single_position_only**: `true` ise aynı anda sadece bir pozisyon açılır
- **cooldown_after_exit**: Pozisyon kapandıktan sonra bekleme süresi (saniye)
- **priority_order**: Sinyal çakışması durumunda öncelik sırası
- **timeframe_validation**: Sinyal validasyon kuralları

#### Telegram Bildirimleri

- **enabled**: Telegram bildirimlerini aktifleştirir
- **bot_token**: Telegram bot token
- **chat_id**: Bildirim gönderilecek chat ID
- **notification_level**: Bildirim seviyesi (all, signals, positions, none)

## 🚦 Sinyal Mantığı

### EMA Crossover Stratejisi

Sistem, hızlı ve yavaş EMA'ların kesişimini izler:

- **LONG Sinyal**: Hızlı EMA, yavaş EMA'nın üzerine çıktığında
- **SHORT Sinyal**: Hızlı EMA, yavaş EMA'nın altına indiğinde

### Sinyal Doğrulama

Sinyaller, aşağıdaki kriterlere göre doğrulanır:

1. **Minimum Mum Sayısı**: Yeterli tarihsel veri olmalı
2. **Mum Onayı**: Mum yeterince oluşmuş olmalı
3. **Heikin Ashi Filtresi**: Heikin Ashi mumları kullanılarak trend doğrulanır

### Çoklu Zaman Dilimi Önceliği

Birden fazla zaman diliminde sinyal olduğunda, `priority_order` ayarına göre önceliklendirilir:

```json
"priority_order": ["1h", "30m", "15m"]
```

Bu örnekte, 1 saatlik sinyaller en yüksek önceliğe sahiptir.

## 🛡️ Risk Yönetimi

### Sabit Stop Loss ve Take Profit

Her zaman dilimi için sabit SL ve TP değerleri ayarlanabilir:

```json
"15m": {
  "take_profit": 0.2,
  "stop_loss": 1.0
}
```

### Trailing Stop Loss

Pozisyon belirli bir kâr seviyesine ulaştığında aktifleşir:

```json
"trailing_activation": 0.15,  // %15 kâr seviyesinde aktifleşir
"trailing_step": 0.05,        // Her adımda %5 kaydırılır
"trailing_distance": 0.3      // Fiyat ile stop arasında %30 mesafe korunur
```

### Dinamik Take Profit

Pozisyon kârlılığına göre TP seviyesi otomatik olarak artırılır:

```json
"dynamic_tp": {
  "enabled": true,
  "levels": [
    {"threshold": 0.3, "tp_pct": 0.5},  // %30 kârda TP %0.5'e ayarlanır
    {"threshold": 0.5, "tp_pct": 0.8},  // %50 kârda TP %0.8'e ayarlanır
    {"threshold": 1.0, "tp_pct": 1.5}   // %100 kârda TP %1.5'e ayarlanır
  ]
}
```

## 🔄 Sistem Akışı

1. **Başlangıç**:
   - Konfigürasyon yüklenir
   - Exchange bağlantısı kurulur
   - Önceki durumlar yüklenir

2. **Ana Döngü**:
   - Aktif pozisyon kontrolü yapılır
   - Pozisyon varsa izlenir ve risk yönetimi uygulanır
   - Pozisyon yoksa tüm zaman dilimleri için sinyal kontrolü yapılır

3. **Sinyal Tespiti**:
   - Her zaman dilimi için mum verileri alınır
   - EMA hesaplamaları yapılır
   - Crossover kontrol edilir

4. **Pozisyon Açma**:
   - Sinyal tespit edildiğinde pozisyon açılır
   - SL ve TP emirleri yerleştirilir
   - Telegram bildirimi gönderilir

5. **Pozisyon İzleme**:
   - Pozisyon durumu sürekli kontrol edilir
   - Kâr durumuna göre trailing stop ve dinamik TP uygulanır
   - Pozisyon kapandığında SL/TP emirleri iptal edilir

## 🔌 Servis Yönetimi

Bot, systemd servis olarak çalıştırılır:

```
[Unit]
Description=EMA Crossover Multi-Timeframe Auto Trader
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/simple_trader/projects/eigen_ema
ExecStart=/root/simple_trader/venv/bin/python3 /root/simple_trader/projects/eigen_ema/eigen_ema_multi_trader.py
Restart=always
RestartSec=5
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=eigen-ema-multi-trader

[Install]
WantedBy=multi-user.target
```

### Servis Komutları

```bash
# Servisi başlatma
systemctl start eigen-ema-multi-trader.service

# Servisi durdurma
systemctl stop eigen-ema-multi-trader.service

# Servis durumunu kontrol etme
systemctl status eigen-ema-multi-trader.service

# Servisi yeniden başlatma
systemctl restart eigen-ema-multi-trader.service

# Servisin otomatik başlamasını sağlama
systemctl enable eigen-ema-multi-trader.service
```

## 📊 Performans İzleme

Sistem performansı şu şekilde izlenebilir:

1. **Log Dosyaları**:
   ```bash
   tail -f /root/simple_trader/projects/eigen_ema/logs/ema_crossover_trading.log
   ```

2. **Servis Durumu**:
   ```bash
   systemctl status eigen-ema-multi-trader.service
   ```

3. **Telegram Bildirimleri**:
   Telegram kanalında tüm işlem bildirimleri görüntülenebilir.

## 🔧 Sorun Giderme

### Yaygın Sorunlar ve Çözümleri

1. **API Bağlantı Hataları**:
   ```
   ERROR - ❌ Pozisyon kontrol hatası: binance {"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}
   ```
   **Çözüm**: API anahtarının doğru olduğunu ve futures işlemleri için yetkilendirildiğini kontrol edin.

2. **Mum Validasyon Hataları**:
   ```
   WARNING - ⚠️ 15m validation failed: Candle not confirmed: 6.2min < 12.0min
   ```
   **Çözüm**: Validasyon ayarlarını gevşetin veya mum onaylama süresini azaltın.

3. **SL/TP Emir İptal Hataları**:
   ```
   WARNING - ⚠️ SL emri iptal hatası: binance {"code":-2011,"msg":"Unknown order sent."}
   ```
   **Çözüm**: Symbol formatının doğru olduğundan emin olun ve params={"type": "future"} parametresini ekleyin.

4. **Birden Fazla Pozisyon Açılması**:
   ```
   INFO - ✅ BUY pozisyon açıldı @ $0.0235
   INFO - ✅ BUY pozisyon açıldı @ $0.0235
   ```
   **Çözüm**: `single_position_only` ayarını `true` olarak ayarlayın ve `active_position` değişkeninin doğru yönetildiğinden emin olun.

### Kritik Kod Bölümleri

1. **Symbol Format Kullanımı**:
   - `fetch_positions()` için: `futures_symbol = f"{self.symbol.replace('/', '')}"`
   - Order fonksiyonları için: `futures_symbol = f"{self.symbol}:USDT"`

2. **SL/TP Emir İptali**:
   ```python
   cancel_result = self.exchange.cancel_order(
       sl_order_id, 
       f"{self.symbol.replace('/', '')}", 
       params={"type": "future"}
   )
   ```

3. **Single Position Only Kontrolü**:
   ```python
   if self.single_position_only and self.active_position:
       self.log.info(f"🚫 Single position only aktif - Yeni pozisyon açılamaz")
       return False
   ```

## 📝 Değişiklik Geçmişi

### v1.0.0 (16.10.2025)
- İlk sürüm

### v1.1.0 (16.10.2025)
- `fetch_positions` parametresi düzeltildi
- SL/TP cancel fonksiyonlarına params parametresi eklendi
- `single_position_only` kontrolü eklendi

## 👨‍💻 Geliştirici Notları

- Sistem, CCXT kütüphanesini kullanarak Binance Futures API'si ile etkileşime girer
- Futures işlemleri için symbol formatı önemlidir ve API çağrısına göre değişir
- Pozisyon yönetimi için `active_position` değişkeni kritik öneme sahiptir
- Risk yönetimi için trailing stop ve dinamik TP mekanizmaları kullanılır
- Telegram entegrasyonu ile uzaktan izleme sağlanır

## 📚 Kaynaklar

- [CCXT Dokümantasyonu](https://docs.ccxt.com/)
- [Binance Futures API Dokümantasyonu](https://binance-docs.github.io/apidocs/futures/en/)
- [EMA Crossover Stratejisi](https://www.investopedia.com/terms/e/ema.asp)
- [Heikin Ashi Teknik Analizi](https://www.investopedia.com/terms/h/heikinashi.asp)
- [Trailing Stop Stratejileri](https://www.investopedia.com/terms/t/trailingstop.asp)
