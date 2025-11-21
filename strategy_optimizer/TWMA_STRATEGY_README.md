# TWMA 4H Trend Strategy

## 📋 Genel Bakış

TWMA (Time Weighted Moving Average) 4H Trend Stratejisi, zaman ağırlıklı hareketli ortalama kullanarak trend takip eden bir trading stratejisidir. Strateji, TWMA çizgisini test eden (touch) ve setup bar oluşturan sinyalleri kullanır.

## 🎯 Özellikler

### Entry (Giriş)
- **Long Entry**: Setup bar (close > TWMA ve TWMA yukarı) + Touch bar (low <= TWMA ve close >= TWMA)
- **Short Entry**: Setup bar (close < TWMA ve TWMA aşağı) + Touch bar (high >= TWMA ve close <= TWMA)
- Entry, touch bar'dan sonraki kapanışta gerçekleşir

### Exit (Çıkış)
- **Stop Loss**: TWMA ± (ATR × SL Multiplier)
- **Take Profit**: Last Swing High/Low ± (ATR × TP Multiplier)
- Swing high/low yoksa, TWMA baz alınır

### İndikatörler
- **TWMA**: Zaman Ağırlıklı Hareketli Ortalama (recent values have higher weight)
- **ATR**: Average True Range (volatilite ölçümü)
- **Pivot High/Low**: Swing noktaları tespiti

## 📁 Dosyalar

- `src/strategy/twma_trend.py` - Python strateji implementasyonu
- `optimize_twma_4h.py` - Optimizasyon scripti
- Pine Script kodu (kullanıcı tarafından sağlandı)

## 🚀 Kullanım

### Optimizasyon Çalıştırma

```bash
cd /Users/ahmet/ATR/strategy_optimizer

# Varsayılan (BTCUSDT 4h)
python3 optimize_twma_4h.py

# Farklı coin ve timeframe
python3 optimize_twma_4h.py --symbol ETHUSDT --timeframe 4h
python3 optimize_twma_4h.py --symbol SOLUSDT --timeframe 4h
```

### Parametreler

Optimizasyon scripti şu parametreleri test eder:

- **TWMA Length**: 10, 15, 20, 25, 30
- **ATR Length**: 10, 14, 20
- **Stop Loss ATR Multiplier**: 0.3, 0.5, 0.7, 1.0
- **Take Profit ATR Multiplier**: 0.8, 1.0, 1.5, 2.0
- **Pivot Length**: 3, 5, 7, 10

### Sonuçlar

Optimizasyon tamamlandığında:
- JSON dosyası: `twma_4h_optimization_{symbol}_{timestamp}.json`
- Top 20 sonuç konsola yazdırılır
- En iyi parametreler gösterilir

## ⚙️ Strateji Parametreleri

### Pine Script Parametreleri

```pinescript
twmaLen   = 20      // TWMA Periyodu (2-200)
atrLen    = 14      // ATR Periyodu
slAtrMult = 0.5     // Stop: ATR Katsayısı
tpAtrMult = 1.0     // TP: ATR Katsayısı
pivotLen  = 5       // Pivot Sol/Sağ Mum Sayısı (2-20)
```

### Python Parametreleri

```python
params = {
    'twma_len': 20,
    'atr_len': 14,
    'sl_atr_mult': 0.5,
    'tp_atr_mult': 1.0,
    'pivot_len': 5,
    'leverage': 5.0,
    'commission': 0.0005,  # 0.05%
    'slippage': 0.0002,    # 0.02%
}
```

## 📊 Backtest Metrikleri

Optimizasyon sonuçları şu metrikleri içerir:

- **Total Trades**: Toplam işlem sayısı
- **Win Rate**: Kazanma oranı (%)
- **Profit Factor**: Kar faktörü
- **Total Return**: Toplam getiri (%)
- **Max Drawdown**: Maksimum düşüş (%)
- **Avg Win/Loss**: Ortalama kazanç/kayıp (%)

## 🎨 Strateji Mantığı

### Long Entry
1. Setup Bar (2 bar önce): `close > TWMA` ve `TWMA yukarı`
2. Touch Bar (1 bar önce): `low <= TWMA` ve `close >= TWMA`
3. Entry: Touch bar'dan sonraki kapanışta

### Short Entry
1. Setup Bar (2 bar önce): `close < TWMA` ve `TWMA aşağı`
2. Touch Bar (1 bar önce): `high >= TWMA` ve `close <= TWMA`
3. Entry: Touch bar'dan sonraki kapanışta

### Stop Loss & Take Profit
- **Long SL**: `TWMA - (ATR × SL Multiplier)`
- **Long TP**: `Last Swing High + (ATR × TP Multiplier)`
- **Short SL**: `TWMA + (ATR × SL Multiplier)`
- **Short TP**: `Last Swing Low - (ATR × TP Multiplier)`

## ⚠️ Önemli Notlar

1. **Timeframe**: Strateji 4H timeframe için tasarlanmıştır
2. **Leverage**: Varsayılan 5x leverage kullanılır
3. **Commission**: Binance Futures komisyonu (0.05%)
4. **Slippage**: Gerçekçi slippage simülasyonu (0.02%)
5. **Position Size**: Equity'nin %10'u leverage ile kullanılır

## 🔧 Test Etme

### Önerilen Coinler
- BTCUSDT
- ETHUSDT
- SOLUSDT
- AVAXUSDT
- Diğer likit coinler

### Önerilen Timeframe
- **4H**: Ana timeframe (strateji bu için tasarlandı)
- **1H**: Daha fazla sinyal için test edilebilir

## 📝 Notlar

- Strateji hem long hem short pozisyonları destekler
- Swing high/low kullanımı TP hesaplamasını iyileştirir
- TWMA, son değerlere daha fazla ağırlık verir (zaman ağırlıklı)
- Optimizasyon yaklaşık 240 kombinasyon test eder (5×3×4×4×4)

