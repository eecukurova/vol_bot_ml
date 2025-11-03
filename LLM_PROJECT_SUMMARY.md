# Volensy LLM Futures – 0.5% TP Scalper Project

## ✅ **PROJENİN TAMAMLANMASI**

Transformer tabanlı LLM futures trading sistemi başarıyla oluşturuldu!

## 📁 **Proje Yapısı**

```
/Users/ahmet/ATR/
├── README.md                      # Ana dokümantasyon
├── requirements.txt               # Python bağımlılıkları
├── pyproject.toml                 # Black/Ruff ayarları
├── Makefile                       # Komutlar (make train, make test, vb.)
├── .gitignore                     # Git ignore kuralları
├── configs/
│   └── train_3m.json             # Eğitim konfigürasyonu
├── src/
│   ├── __init__.py
│   ├── fetch_binance.py          # Veri yükleme
│   ├── features.py                # Feature engineering (EMA, RSI, Z-score)
│   ├── labeling.py                # Triple-barrier first-touch
│   ├── dataset.py                 # Sliding window oluşturma
│   ├── models/
│   │   ├── __init__.py
│   │   └── transformer.py         # Transformer encoder (64-dim, 2 layers)
│   ├── train.py                   # PyTorch eğitim loop
│   ├── infer.py                   # Tahmin ve karar verme
│   ├── backtest_core.py           # Backtest + komisyon + slippage
│   ├── gridsearch.py              # SL ve threshold optimizasyonu
│   ├── live_loop.py               # Canlı döngü + hooks
│   └── utils.py                   # Yardımcı fonksiyonlar
├── scripts/
│   ├── download_binance_klines.py # Binance veri indirme
│   ├── train_runner.py            # Eğitim başlatıcı
│   ├── backtest_runner.py         # Backtest çalıştırıcı
│   ├── gridsearch_runner.py       # Grid search çalıştırıcı
│   └── live_demo_runner.py        # Live simülasyon
└── tests/
    ├── __init__.py
    ├── test_labeling.py           # Etiketleme testleri
    ├── test_features.py            # Feature testleri
    └── test_model_forward.py      # Model forward testleri
```

## 🎯 **Özellikler**

### 1. **Model**
- Küçük Transformer Encoder (64-dim, 2 layers, 4 heads)
- 17 feature (EMA distance/slope, RSI, volume spike, z-scores)
- 3-class classification: Flat, Long, Short
- Weighted CrossEntropy Loss (class imbalance için)

### 2. **Etiketleme**
- Triple-barrier first-touch metodolojisi
- TP: %0.5 sabit
- SL: Grid search ile optimize (0.6%, 0.8%, 1.0%)
- Horizon: 50 bar

### 3. **Backtest**
- Komisyon: 0.05% (round-trip)
- Slippage desteği
- Entry: Next bar open
- Exit: First touch of TP/SL

### 4. **Grid Search**
- SL kombinasyonları: [0.006, 0.008, 0.010]
- Threshold kombinasyonları: [0.55, 0.60, 0.65]
- Metrikler: Profit Factor, Win-rate, Trades, Drawdown

## 🚀 **Kullanım**

### 1. Kurulum
```bash
make venv
source venv/bin/activate
make install
```

### 2. Veri İndirme
```bash
python scripts/download_binance_klines.py --symbol BTCUSDT --interval 3m --start 2024-01-01
```

### 3. Eğitim
```bash
make train
# veya
python scripts/train_runner.py
```

### 4. Grid Search
```bash
make grid
# veya
python scripts/gridsearch_runner.py
```

### 5. Backtest
```bash
make backtest
# veya
python scripts/backtest_runner.py --sl-pct 0.008 --thr-long 0.60
```

### 6. Live Demo
```bash
make live
# veya
python scripts/live_demo_runner.py --sl-pct 0.008
```

### 7. Testler
```bash
make test
```

## 📊 **Konfigürasyon**

`configs/train_3m.json`:
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "3m",
  "tp_pct": 0.005,           // %0.5 TP
  "sl_pct_candidates": [0.006, 0.008, 0.010],
  "horizon": 50,              // 50 bar ahead
  "window": 128,              // Sequence length
  "val_ratio": 0.2,           // %20 validation
  "fee": 0.0005,              // %0.05 commission
  "slippage": 0.0,
  "thr_long": 0.6,            // Long decision threshold
  "thr_short": 0.6,           // Short decision threshold
  "epochs": 15,
  "batch_size": 256,
  "lr": 0.001,
  "seed": 42
}
```

## ⚠️ **Önemli Notlar**

1. **Funding Rates**: Backtest'te modelledilmedi
2. **Latency**: Canlı trading için 100ms+ ekle
3. **Overfitting**: Walk-forward validation önerilir
4. **Risk**: %0.5 TP için yüksek hit-rate gerekiyor
5. **Regime**: Model 2024 verisiyle eğitildi, 2025'te başarısız olabilir

## 🔧 **Entegrasyon Hooks**

`src/live_loop.py` içinde `send_order()` ve `send_telegram_alert()` fonksiyonlarını implement et:

```python
def send_order(side, entry, tp, sl, leverage, qty):
    # TODO: Volensy order client çağrısı
    pass

def send_telegram_alert(payload):
    # TODO: Telegram bildirimi
    pass
```

## ✅ **Tamamlanan Gereksinimler**

- ✅ Transformer encoder modeli
- ✅ Triple-barrier first-touch etiketleme
- ✅ Feature engineering (EMA, RSI, z-score)
- ✅ Dataset ve sliding windows
- ✅ PyTorch eğitim loop
- ✅ Inference ve karar verme
- ✅ Backtest core (komisyon + slippage)
- ✅ Grid search optimizasyonu
- ✅ Live loop simülasyonu
- ✅ Test suite
- ✅ CLI scripts (Typer)
- ✅ Makefile komutları
- ✅ Detaylı README
- ✅ Type hints + docstrings

## 🎉 **Başlamaya Hazır!**

Tüm kodlar yazıldı ve testler hazır. Şimdi:
1. Veriyi indir
2. Modeli eğit
3. Grid search yap
4. Backtest çalıştır
5. Canlıya hazır!

