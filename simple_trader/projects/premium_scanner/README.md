# Premium Stock Scanner

AMD, NVDA, TSLA gibi teknoloji hisselerini tarayan gelişmiş scanner.

## 🎯 Özellikler

- **4H ve 1H Heikin Ashi** mumları ile analiz
- **ATR SuperTrend** stratejisi
- **Teknoloji hisseleri**: AMD, NVDA, TSLA, AAPL, MSFT, GOOGL, META, AMZN
- **Telegram bildirimleri** aktif
- **30 dakika** tarama aralığı

## 📊 Strateji

### ATR SuperTrend Parametreleri
- **ATR Period**: 10
- **Key Value**: 3
- **Factor**: 1.5
- **Timeframe**: 4H ve 1H
- **Heikin Ashi**: Aktif

### Sinyal Koşulları
- **LONG**: Fiyat SuperTrend çizgisini yukarı kırarsa
- **SHORT**: Fiyat SuperTrend çizgisini aşağı kırarsa

## 🚀 Kurulum

```bash
# Deploy et
./deploy.sh

# Service durumu
systemctl status premium-scanner.service

# Logları izle
journalctl -u premium-scanner.service -f
```

## 📱 Telegram Bildirimi Örneği

```
🚀 Premium Stock Scanner - Sinyaller

🟢 LONG AMD (4H)
💰 Fiyat: $120.45
📊 SuperTrend: $118.20
📈 Trend: BULLISH
🕯️ Heikin Ashi: Aktif

🟢 LONG NVDA (1H)
💰 Fiyat: $450.30
📊 SuperTrend: $445.80
📈 Trend: BULLISH
🕯️ Heikin Ashi: Aktif

⏰ Zaman: 2025-10-20 17:30:00
```

## 📈 Teknoloji Hisseleri

- **Semiconductor**: AMD, NVDA, INTC, QCOM, AVGO, TXN, MU, AMAT, LRCX, KLAC, MRVL
- **Software**: MSFT, GOOGL, META, CRM, ADBE, SNPS, CDNS, ORCL, IBM, CSCO, ACN
- **Cloud/Security**: FTNT, CRWD, ZS, NET, DDOG, SNOW, PANW, CYBR, MDB, ESTC
- **Hardware**: AAPL, AMZN, NFLX, TSLA, ROKU, ZM, DOCU, OKTA, TWLO, SQ
- **Automotive**: RIVN, LCID, F, GM, FORD, NIO, XPEV, LI
- **Chinese Tech**: BABA, JD, PDD, TME, BIDU, NTES, WB, DOYU
- **Gig Economy**: UBER, LYFT, DASH, GRUB, PTON, SPOT, SNAP, PINS
- **Media/Telecom**: TWTR, DIS, NFLX, CMCSA, VZ, T, TMUS, CHTR

## ⚙️ Konfigürasyon

`premium_scanner_config.json` dosyasından:
- Tarama aralığı
- Teknoloji hisse listesi
- Telegram ayarları
- Logging seviyesi

## 🔍 Log Dosyaları

- **Systemd**: `journalctl -u premium-scanner.service`
- **File**: `premium_scanner.log`
