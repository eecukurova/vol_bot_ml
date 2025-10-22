# PENGU EMA Crossover Trader

## 📊 Strateji
Basit EMA crossover stratejisi - PENGU/USDT için optimize edilmiş

## ⚙️ Parametreler
- **EMA Fast**: 10
- **EMA Slow**: 26
- **Take Profit**: 0.5%
- **Stop Loss**: 1.5%
- **Leverage**: 10x (Isolated)
- **Trade Amount**: $100

## 🚀 Özellikler
- Basit EMA crossover sinyalleri
- Otomatik TP/SL yerleştirme
- Idempotent order management
- Telegram bildirimleri
- Detaylı logging

## 📁 Dosya Yapısı
```
pengu_ema/
├── pengu_ema_trader.py      # Ana trader kodu
├── pengu_ema_config.json   # Konfigürasyon
├── pengu-ema-trader.service # Systemd servisi
├── deploy.sh               # Deploy scripti
├── runs/                   # State dosyaları
└── pengu_ema_trading.log   # Log dosyası
```

## 🔧 Kurulum
```bash
./deploy.sh
```

## 📊 Servis Kontrolü
```bash
# Servis durumu
systemctl status pengu-ema-trader.service

# Logları izle
tail -f pengu_ema_trading.log

# Servisi yeniden başlat
systemctl restart pengu-ema-trader.service
```

## 🎯 Sinyal Mantığı
- **LONG**: EMA Fast > EMA Slow (crossover)
- **SHORT**: EMA Fast < EMA Slow (crossunder)
- Sadece bar kapanışında sinyal üretir
- Ters sinyalde pozisyon kapatılır ve yeni pozisyon açılır