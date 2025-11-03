# ATR SuperTrend Strategy

Pine Script'teki "ATR with Super Trend" stratejisinin Python implementasyonu.

## 🎯 Özellikler

- **ATR Trailing Stop**: Dinamik stop loss
- **SuperTrend**: Trend takip indikatörü
- **Heikin Ashi**: Smooth trend analizi
- **Kombine Sinyaller**: Her iki strateji de aynı yönde sinyal verirse

## 📊 Parametreler

| **Parametre** | **Açıklama** | **Varsayılan** | **Aralık** |
|---------------|--------------|----------------|------------|
| `a` | Key Value (Sensitivity) | 3 | 0.1 - 10 |
| `c` | ATR Period | 10 | 1 - 50 |
| `factor` | SuperTrend Multiplier | 1.5 | 0.1 - 5 |
| `h` | Heikin Ashi | false | true/false |

## 🚀 Kullanım

### CLI ile Optimize Etme

```bash
# NASDAQ hisseleri için optimize et
python3 cli.py optimize --coins "AMD,NVDA,TSLA" --timeframes "4h" --strategy atr_supertrend --params nasdaq_params.json

# Heikin Ashi ile optimize et
python3 cli.py optimize --coins "AMD,NVDA,TSLA" --timeframes "4h" --strategy atr_supertrend --param-string "a=2,3,4 c=8,10,12 factor=1.2,1.5,1.8 h=true"
```

### Python ile Kullanım

```python
from strategy.atr_supertrend import create_strategy

# Parametreler
params = {
    'a': 3,      # Key Value
    'c': 10,     # ATR Period
    'h': False,  # Heikin Ashi
    'factor': 1.5  # SuperTrend multiplier
}

# Strateji oluştur
strategy = create_strategy(params)

# Veri ile çalıştır
result = strategy.run_strategy(df)
```

## 📈 Sinyal Mantığı

### ATR Trailing Stop Sinyalleri
- **BUY**: `src > xATRTrailingStop` ve `crossover(ema1, xATRTrailingStop)`
- **SELL**: `src < xATRTrailingStop` ve `crossover(xATRTrailingStop, ema1)`

### SuperTrend Sinyalleri
- **BUY**: `crossover(close, superTrendLine)`
- **SELL**: `crossunder(close, superTrendLine)`

### Kombine Sinyaller
- **BUY**: ATR Trailing Stop BUY + SuperTrend BUY
- **SELL**: ATR Trailing Stop SELL + SuperTrend SELL

## 🕯️ Heikin Ashi

Heikin Ashi aktif olduğunda:
- Smooth trend analizi
- Daha az false signal
- Daha güvenilir trend takibi

## 📊 Pine Script Versiyonu

`atr_supertrend_optimized.pine` dosyası Pine Script versiyonunu içerir.

### Özellikler:
- ATR Trailing Stop çizgisi
- SuperTrend çizgisi
- Buy/Sell sinyalleri
- Trend background renklendirme
- Bilgi tablosu
- Alert koşulları

## 🎯 NASDAQ Optimizasyonu

NASDAQ hisseleri için optimize edilmiş parametreler:

```json
{
  "a": [2, 3, 4, 5],
  "c": [8, 10, 12, 14],
  "factor": [1.2, 1.5, 1.8, 2.0],
  "h": [false, true]
}
```

## 📈 Test Sonuçları

### AMD (4H, 60 günlük veri)
- **Normal**: 0 buy, 0 sell sinyali
- **Heikin Ashi**: 0 buy, 0 sell sinyali
- **ATR**: 7.99
- **SuperTrend**: $229.80

### NVDA (4H, 60 günlük veri)
- **Normal**: 1 buy sinyali
- **Son Buy**: 2025-09-10 - $178.01
- **ATR**: 3.79
- **SuperTrend**: $187.28

### TSLA (4H, 60 günlük veri)
- **Normal**: 1 buy sinyali
- **Son Buy**: 2025-09-05 - $352.08
- **ATR**: 10.34
- **SuperTrend**: $436.39

## 🔍 Strateji Avantajları

1. **Dinamik Stop Loss**: ATR ile adaptif stop loss
2. **Trend Takibi**: SuperTrend ile güçlü trend takibi
3. **Heikin Ashi**: Smooth analiz için opsiyonel
4. **Kombine Sinyaller**: Daha güvenilir sinyaller
5. **NASDAQ Uyumlu**: Hisse senetleri için optimize edilmiş

## ⚙️ Konfigürasyon

`nasdaq_params.json` dosyasından parametreleri düzenleyebilirsin:

```json
{
  "a": [2, 3, 4, 5],
  "c": [8, 10, 12, 14],
  "factor": [1.2, 1.5, 1.8, 2.0],
  "h": [false, true]
}
```

Bu parametrelerle 4×4×4×2 = 128 farklı kombinasyon test edilir.
