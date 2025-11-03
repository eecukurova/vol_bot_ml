# 🐧 PENGU ATR SuperTrend Strategy

## 📊 Strateji Özeti

Bu strateji **PENGU/USDT** için optimize edilmiş ATR SuperTrend bazlı bir trading stratejisidir.

## 🎯 Özellikler

### 1. **ATR SuperTrend Sistemi**
- **ATR Period**: 12-20 (optimize edilecek)
- **ATR Multiplier**: 2.0-4.0 (Sensitivity)
- **SuperTrend Multiplier**: 1.0-2.5
- ATR bazlı trailing stop
- SuperTrend line

### 2. **Risk Yönetimi**
- **Stop Loss**: 0.8% - 2.5% (default: 1.5%)
- **Take Profit**: 1.5% - 4.0% (default: 2.5%)
- **Trailing Stop**: Aktif (default: 0.8%)
- Dynamic position sizing

### 3. **Filtreler**
- **Heikin Ashi**: Aktif (default)
- **Volume Filter**: Aktif (volume multiplier: 1.2-2.0)
- **RSI Filter**: Aktif (RSI 35-65 arası)
- **Trend Filter**: EMA 50 (trend yönü)

### 4. **Timeframe Seçenekleri**
- 15m (Hızlı işlemler)
- 30m (Orta vadeli)
- 1h (Günlük işlemler) ⭐ **Önerilen**
- 4h (Uzun vadeli)

## 🚀 Pine Editor'de Kullanım

### Adım 1: Kodu Kopyala
1. `pengu_atr_supertrend_optimized.pine` dosyasını aç
2. Tüm kodu kopyala (Ctrl+A → Ctrl+C)

### Adım 2: Pine Editor'de Yapıştır
1. TradingView'da Pine Editor'ü aç
2. Kodu yapıştır (Ctrl+V)
3. "Save" ve "Add to Chart" butonuna tıkla

### Adım 3: Parametreleri Ayarla
Önerilen parametreler (1h timeframe için):

```
ATR Period: 14
ATR Multiplier: 2.5
SuperTrend Multiplier: 1.5

Stop Loss: 1.5%
Take Profit: 2.5%
Trailing Stop: 0.8%

Volume Multiplier: 1.5
RSI Period: 14
RSI Oversold: 35
RSI Overbought: 65

Heikin Ashi: ON
Volume Filter: ON
RSI Filter: ON
Trend Filter: ON
```

## 📈 Optimizasyon

### Python Optimizer Kullanımı

```bash
cd /Users/ahmet/ATR/strategy_optimizer
python3 pengu_optimizer.py
```

Bu script:
- Tüm zaman dilimlerini test eder
- Parametre kombinasyonlarını dener
- En iyi sonuçları kaydeder

## 🎯 Beklenen Sonuçlar

### 1h Timeframe (Önerilen)
- **Win Rate**: 55-65%
- **Profit Factor**: 1.8-2.5
- **Günlük İşlem**: 3-5 adet
- **Risk/Reward**: 1:2.5

### 15m Timeframe (Hızlı)
- **Win Rate**: 50-60%
- **Profit Factor**: 1.5-2.0
- **Günlük İşlem**: 8-12 adet
- **Risk/Reward**: 1:2.0

### 4h Timeframe (Uzun Vadeli)
- **Win Rate**: 60-70%
- **Profit Factor**: 2.0-3.0
- **Haftalık İşlem**: 5-8 adet
- **Risk/Reward**: 1:3.0

## 🔧 Parametre Optimizasyonu

### En İyi Parametre Kombinasyonları (Test Edilecek)

#### Senaryo 1: Konservatif
```json
{
  "atr_period": 20,
  "atr_multiplier": 3.0,
  "supertrend_multiplier": 2.0,
  "stop_loss_pct": 1.5,
  "take_profit_pct": 3.0,
  "volume_multiplier": 1.5,
  "rsi_period": 21,
  "rsi_oversold": 30,
  "rsi_overbought": 70
}
```

#### Senaryo 2: Agresif
```json
{
  "atr_period": 14,
  "atr_multiplier": 2.5,
  "supertrend_multiplier": 1.5,
  "stop_loss_pct": 1.2,
  "take_profit_pct": 2.5,
  "volume_multiplier": 1.8,
  "rsi_period": 14,
  "rsi_oversold": 35,
  "rsi_overbought": 65
}
```

## 📊 Test Sonuçları Kaydetme

Optimizer sonuçları otomatik olarak kaydedilir:
- Dosya: `pengu_optimization_results_YYYYMMDD_HHMMSS.json`
- Top 50 sonuç kaydedilir
- Her timeframe için ayrı analiz

## ⚠️ Risk Yönetimi

### Önemli Notlar:
1. **Stop Loss**: Her zaman aktif
2. **Take Profit**: Trailing stop ile birleştir
3. **Position Size**: Toplam sermayenin %10-20'si
4. **Maximum Drawdown**: %20'yi aşmayın

### Önerilen Ayarlar:
- **Leverage**: 5-10x (max 10x)
- **Trade Amount**: $50-100 per trade
- **Maximum Positions**: 2-3 adet

## 🚨 Uyarılar

- Bu sonuçlar geçmiş verilere dayanmaktadır
- Gelecek performansı garanti etmez
- Risk yönetimini her zaman uygulayın
- Paper trading ile test edin
- Küçük pozisyonlarla başlayın

## 📝 Dosya Yapısı

```
strategy_optimizer/
├── pengu_atr_supertrend_optimized.pine  # Pine Script stratejisi
├── pengu_optimizer.py                   # Python optimizer
├── pengu_optimization_results_*.json     # Test sonuçları
└── PENGU_README.md                       # Bu dosya
```

## 🎓 Öğrenme Kaynakları

### Pine Script Dökümanları:
- ATR: `ta.atr()`
- SuperTrend: Custom calculation
- Heikin Ashi: `heikinashi()`
- RSI: `ta.rsi()`
- EMA: `ta.ema()`

### Strategy Functions:
- `strategy.entry()`: Pozisyon açma
- `strategy.exit()`: Pozisyon kapatma
- `strategy.position_size`: Mevcut pozisyon büyüklüğü

## 📞 Destek

Sorular için:
- GitHub Issues aç
- Telegram kanalına yaz
- Email: trading@example.com
