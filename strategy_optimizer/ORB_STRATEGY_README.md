# ORB Breakout Strategy

## 📋 Genel Bakış

ORB (Opening Range Breakout) stratejisi, açılış aralığı breakout'larını tespit eden bir trading stratejisidir. Multi-stage ORB (5/15/30/60 dakika) desteği ile çalışır.

## 🎯 Özellikler

### Entry (Giriş)
- **Long Entry**: ORB High üzerinde breakout
- **Short Entry**: ORB Low altında breakout
- Multi-stage ORB desteği (5, 15, 30, 60 dakika)
- Breakout buffer ile false signal filtreleme
- Minimum bar dışında kalma kontrolü

### Filtreler
- **Volume Filter**: Volume onayı
- **Trend Filter**: VWAP, EMA, SuperTrend desteği
- **HTF Bias**: Higher timeframe trend kontrolü
- **FVG Filter**: Fair Value Gap kontrolü
- **Pullback Filter**: Pullback onayı (opsiyonel)

### Exit (Çıkış)
- **3 Take Profit Seviyesi**: TP1 (1R), TP2 (2R), TP3 (3R)
- **Stop Loss**: ATR, ORB %, Swing, Smart Adaptive modları
- **Position Sizing**: Otomatik risk yönetimi

## 📁 Dosya

- `orb_breakout_strategy.pine` - TradingView Pine Script stratejisi

## 🚀 Kullanım

### TradingView'da Kullanım

1. TradingView'ı açın
2. Pine Editor'ü açın
3. `orb_breakout_strategy.pine` dosyasını yükleyin
4. "Add to Chart" butonuna tıklayın
5. Strategy Tester'da backtest yapın

### Parametreler

#### Session Settings
- **Session Mode**: Auto-Detect, New-York, London, Tokyo, Sydney, Frankfurt, Custom
- **Extended Hours**: Pre-market ve after-hours dahil etme

#### ORB Stages
- **Enable ORB 5/15/30/60**: Hangi ORB aşamalarını kullanacağınızı seçin

#### Breakout Detection
- **Breakout Buffer**: False breakout'ları filtrelemek için buffer (%)
- **Min Bars Outside**: Breakout'un geçerli olması için minimum bar sayısı
- **Signal Mode**: First Only veya Track Cycles
- **Max Cycles**: Track Cycles modunda maksimum cycle sayısı

#### Filters
- **Volume Filter**: Volume onayı aktif/pasif
- **Trend Filter**: Trend filtreleme (VWAP, EMA, SuperTrend)
- **HTF Bias**: Higher timeframe trend kontrolü
- **FVG Filter**: Fair Value Gap kontrolü
- **Pullback Filter**: Pullback onayı

#### Exit Parameters
- **Stop Method**: ATR, ORB %, Swing, Smart Adaptive, vb.
- **TP1/TP2/TP3**: Take profit yüzdeleri
- **ATR Length/Multiplier**: ATR hesaplama parametreleri

## ⚠️ Önemli Notlar

1. **Long/Short Mantığı Korundu**: Entry ve exit mantığı orijinal kodla aynı
2. **Gereksiz Görselleştirmeler Kaldırıldı**: Dashboard, fazla label/box kaldırıldı
3. **Temiz Kod**: Sadece trading mantığı kaldı, görsel karmaşıklık azaltıldı
4. **Test Edilebilir**: TradingView Strategy Tester'da direkt test edilebilir

## 🔧 Test Etme

### Önerilen Timeframe
- **5 dakika**: ORB 5 için
- **15 dakika**: ORB 15 için
- **30 dakika**: ORB 30 için
- **1 saat**: ORB 60 için

### Önerilen Coinler
- BTC/USDT
- ETH/USDT
- SOL/USDT
- ARB/USDT
- Diğer likit coinler

## 📊 Backtest Sonuçları

Stratejiyi test etmek için:
1. TradingView Strategy Tester'ı açın
2. İstediğiniz coin'i seçin
3. Timeframe'i ayarlayın
4. Parametreleri optimize edin
5. Backtest sonuçlarını inceleyin

## 🎨 Görselleştirme

- **ORB High/Low**: Yeşil/Kırmızı çizgiler
- **ORB Mid**: Gri çizgi
- **Long Signal**: Yeşil background
- **Short Signal**: Kırmızı background

## 📝 Notlar

- Strateji `strategy()` fonksiyonu kullanıyor (indicator değil)
- Gerçek işlem yapmaz, sadece backtest için
- Long ve short entry mantığı korundu
- Exit mantığı 3 TP seviyesi ile çalışıyor

