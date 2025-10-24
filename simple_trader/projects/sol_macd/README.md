# SOL MACD Trend Trader

SOL/USDT için optimize edilmiş Volensy MACD Trend strategy'si ile otomatik trading botu.

## 🚀 Özellikler

- **Volensy MACD Trend Strategy**: Pine Script'ten Python'a çevrilmiş
- **Heikin Ashi Mumları**: Daha smooth sinyaller için
- **4H Timeframe**: Sadece 4 saatlik mumlarla işlem
- **Optimize TP/SL**: %1.5 SL, %3.0 TP (Risk/Reward: 1:2)
- **Telegram Bildirimleri**: Pozisyon açma/kapama bildirimleri
- **Idempotent Orders**: Duplicate order koruması

## 📊 Strategy Detayları

### Pine Script Parametreleri:
- **EMA Length**: 20 (trend filtresi)
- **MACD Fast**: 12 (hızlı EMA)
- **MACD Slow**: 26 (yavaş EMA)
- **MACD Signal**: 9 (sinyal EMA)
- **RSI Length**: 14 (RSI periyodu)
- **RSI OB**: 70 (aşırı alım)
- **RSI OS**: 30 (aşırı satım)
- **ATR Length**: 14 (ATR periyodu)

### Sinyal Mantığı:
1. **Trend Kontrolü**: Heikin Ashi Close > EMA (bullish trend)
2. **Momentum Kontrolü**: RSI > 50 (bullish momentum)
3. **Güç Kontrolü**: MACD > Signal (bullish power)
4. **Skor Sistemi**: 3/3 skor = AL sinyali
5. **Filtreleme**: RSI < 70 (aşırı alım değil)

### Risk Yönetimi:
- **Stop Loss**: %1.5
- **Take Profit**: %3.0
- **Risk/Reward**: 1:2
- **Leverage**: 10x
- **Position Size**: $100

## 🛠️ Kurulum

### 1. Dosyaları Kopyala
```bash
# Sunucuya kopyala
scp -i ~/.ssh/ahmet_key -r /Users/ahmet/ATR/simple_trader/projects/sol_macd/* root@159.65.94.27:/root/simple_trader/projects/sol_macd/
```

### 2. Service Kurulumu
```bash
# Sunucuda
cd /root/simple_trader/projects/sol_macd
sudo cp sol-macd-trader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sol-macd-trader.service
sudo systemctl start sol-macd-trader.service
```

### 3. Durum Kontrolü
```bash
# Service durumu
sudo systemctl status sol-macd-trader.service

# Logları kontrol et
tail -f sol_macd_trading.log

# Service'i yeniden başlat
sudo systemctl restart sol-macd-trader.service
```

## 📈 Performans Beklentileri

### Optimizasyon Sonuçları (SOL/USDT 4h):
- **Profit Factor**: 4.50
- **Total Return**: 2.48%
- **Max Drawdown**: -2.71%
- **Win Rate**: 91.30%
- **Trades**: 23

### Risk Metrikleri:
- **Sharpe Ratio**: 0.17
- **MAR Ratio**: 0.92
- **Expectancy**: 12.78

## ⚙️ Konfigürasyon

### sol_macd_config.json:
```json
{
  "symbol": "SOL/USDT",
  "trade_amount_usd": 100,
  "leverage": 10,
  "multi_timeframe": {
    "timeframes": {
      "4h": {
        "enabled": true,
        "take_profit": 0.03,
        "stop_loss": 0.015
      }
    }
  },
  "volensy_macd": {
    "ema_len": 20,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "rsi_len": 14,
    "rsi_ob": 70,
    "rsi_os": 30,
    "atr_len": 14
  }
}
```

## 🔍 Monitoring

### Log Dosyaları:
- `sol_macd_trading.log`: Ana trading logları
- `runs/sol_macd_state.json`: Pozisyon durumu

### Telegram Bildirimleri:
- Pozisyon açma bildirimleri
- Pozisyon kapatma bildirimleri
- Hata bildirimleri

## 🚨 Önemli Notlar

1. **Backtest Sonuçları**: Geçmiş performans gelecek performansı garanti etmez
2. **Risk Yönetimi**: Her zaman stop loss kullanılır
3. **Market Koşulları**: Farklı market koşullarında performans değişebilir
4. **Monitoring**: Bot sürekli izlenmeli
5. **Backup**: Konfigürasyon dosyaları yedeklenmeli

## 📞 Destek


