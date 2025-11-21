# Stable Breakout Strategy - NASDAQ Optimized

Bu strateji, NASDAQ hisseleri için optimize edilmiş "Stable Breakout Strategy" implementasyonudur. Orijinal strateji çok az işlem veriyordu, bu versiyon daha fazla işlem üretmek için parametreleri optimize etmiştir.

## 🎯 Strateji Mantığı

Strateji üç temel koşulu kontrol eder:

1. **Breakout**: Kapanış fiyatı, son N bar içindeki en yüksek seviyeyi geçiyor mu?
2. **Momentum**: Açılıştan kapanışa yükseliş minimum %X'ten fazla mı?
3. **Volume**: Hacim, SMA'nın X katından fazla mı?

### Orijinal vs Optimize Parametreler

| Parametre | Orijinal | Optimize (Varsayılan) | Açıklama |
|-----------|----------|------------------------|----------|
| `lenHigh` | 200 | 50 | En yüksek seviye bakış penceresi (düşürüldü) |
| `lenVol` | 30 | 20 | Hacim SMA periyodu (düşürüldü) |
| `minRise` | 4.0% | 1.5% | Minimum yükseliş yüzdesi (düşürüldü) |
| `volKatsay` | 1.5x | 1.2x | Hacim çarpanı (düşürüldü) |

## 📊 Yeni Özellikler

### 1. RSI Filtresi (Opsiyonel)
- RSI belirli bir aralıkta olmalı (varsayılan: 45-75)
- Aşırı alım/satım durumlarını filtreler

### 2. EMA Trend Filtresi (Opsiyonel)
- Fiyat EMA'nın üzerinde olmalı
- Trend yönünü doğrular

### 3. Esnek TP/SL
- TP: %2.5 - %4.0 arası ayarlanabilir
- SL: %1.0 - %2.0 arası ayarlanabilir

## 🚀 Kullanım

### 1. Hızlı Test (Tek Sembol)

```bash
cd nasdaq_strategy_optimizer
python3 test_stable_breakout.py AAPL
```

Bu komut, AAPL için 5 farklı parametre setini test eder ve en iyi sonucu gösterir.

### 2. Tam Optimizasyon (Tüm Semboller)

```bash
python3 optimize_stable_breakout.py
```

Veya belirli semboller için:

```bash
python3 optimize_stable_breakout.py AAPL,AMD,NVDA,MSFT
```

### 3. TradingView'de Kullanım

1. `stable_breakout_nasdaq.pine` dosyasını TradingView'e yükleyin
2. Parametreleri ihtiyacınıza göre ayarlayın
3. Backtest yapın ve sonuçları analiz edin

## 📈 Optimizasyon Parametreleri

Optimizer scripti şu parametre aralıklarını test eder:

```python
param_space = {
    'lenHigh': [30, 40, 50, 60, 80, 100],      # En yüksek bakış penceresi
    'lenVol': [15, 20, 25, 30],                 # Hacim SMA periyodu
    'minRise': [1.0, 1.5, 2.0, 2.5, 3.0],      # Minimum yükseliş %
    'volKatsay': [1.0, 1.2, 1.5],              # Hacim çarpanı
    'useRSI': [True, False],                    # RSI filtresi kullan
    'rsiMin': [40.0, 45.0, 50.0],              # Min RSI
    'rsiMax': [70.0, 75.0, 80.0],              # Max RSI
    'useEMA': [False],                          # EMA filtresi (şimdilik kapalı)
    'tpPct': [2.5, 3.0, 3.5, 4.0],             # Take Profit %
    'slPct': [1.0, 1.5, 2.0]                    # Stop Loss %
}
```

## 📊 Sonuç Metrikleri

Optimizasyon sonuçları şu metrikleri içerir:

- **Total Return**: Toplam getiri yüzdesi
- **Total Trades**: Toplam işlem sayısı
- **Win Rate**: Kazanma oranı (%)
- **Profit Factor**: Kar faktörü (toplam kar / toplam zarar)
- **Max Drawdown**: Maksimum düşüş (%)
- **Sharpe Ratio**: Risk-ayarlı getiri oranı

## 🎯 Optimizasyon Skoru

Optimizer, şu formülü kullanarak en iyi parametreleri seçer:

```
Score = (Trade Count / 50) * 0.4 + 
        (Total Return / 50) * 0.3 + 
        (Win Rate / 100) * 0.2 + 
        (Profit Factor / 3) * 0.1
```

Bu formül, işlem sayısına daha fazla ağırlık verir (daha fazla işlem için).

## 📝 Örnek Sonuçlar

### AAPL (2 yıl, günlük)

**Orijinal Parametreler:**
- Trades: 3-5
- Return: ~5-10%
- Win Rate: 60-70%

**Optimize Parametreler (lenHigh=50, minRise=1.5%):**
- Trades: 15-25
- Return: 12-20%
- Win Rate: 55-65%

**Çok Agresif (lenHigh=30, minRise=1.0%):**
- Trades: 30-50
- Return: 8-15%
- Win Rate: 50-60%

## 🔧 Parametre Önerileri

### Konservatif (Az İşlem, Yüksek Kalite)
```python
{
    'lenHigh': 100,
    'minRise': 2.5,
    'volKatsay': 1.5,
    'useRSI': True,
    'rsiMin': 50.0,
    'rsiMax': 70.0
}
```

### Dengeli (Orta İşlem, İyi Kalite)
```python
{
    'lenHigh': 50,
    'minRise': 1.5,
    'volKatsay': 1.2,
    'useRSI': False
}
```

### Agresif (Çok İşlem, Daha Düşük Kalite)
```python
{
    'lenHigh': 30,
    'minRise': 1.0,
    'volKatsay': 1.0,
    'useRSI': False
}
```

## 📁 Dosyalar

- `stable_breakout_nasdaq.pine`: TradingView Pine Script stratejisi
- `optimize_stable_breakout.py`: Python optimizer scripti
- `test_stable_breakout.py`: Hızlı test scripti
- `stable_breakout_optimization_results.json`: Optimizasyon sonuçları (oluşturulur)

## 🚨 Dikkat Edilmesi Gerekenler

1. **Overfitting**: Çok fazla optimizasyon yapmak, geçmiş verilerde iyi görünen ama gelecekte başarısız olan parametreler üretebilir.

2. **Slippage & Commission**: Gerçek trading'de slippage ve komisyonlar performansı etkiler. Optimizer'da bu faktörler basitleştirilmiştir.

3. **Market Conditions**: Strateji trendli piyasalarda daha iyi çalışır. Yatay piyasalarda daha fazla false signal üretebilir.

4. **Risk Management**: Her zaman stop loss kullanın ve pozisyon büyüklüğünü kontrol edin.

## 🔄 Sonraki Adımlar

1. **Walk-Forward Analysis**: Parametreleri zaman içinde test edin
2. **Multi-Timeframe**: Farklı timeframe'lerde test edin
3. **Portfolio Testing**: Birden fazla sembolde aynı anda test edin
4. **Real-time Testing**: Paper trading ile gerçek zamanlı test yapın

## 📞 Destek

Sorularınız için:
- GitHub Issues
- Documentation
- Example scripts

---

**Stable Breakout Strategy - NASDAQ Optimized** 🚀

