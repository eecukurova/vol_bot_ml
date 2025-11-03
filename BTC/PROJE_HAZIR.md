# 🎉 Volensy LLM Projesi Hazır!

## ✅ Tamamlandı: 27 Dosya

### Proje Yapısı
```
LLM/
├── README.md                    # Ana dokümantasyon
├── requirements.txt              # Python bağımlılıkları
├── pyproject.toml               # Black/Ruff ayarları
├── Makefile                     # Komutlar
├── .gitignore                   # Git ignore
├── PROJE_HAZIR.md              # Bu dosya
│
├── configs/
│   └── train_3m.json          # Eğitim konfigürasyonu
│
├── scripts/
│   ├── download_binance_klines.py
│   ├── train_runner.py
│   ├── backtest_runner.py
│   ├── gridsearch_runner.py
│   └── live_demo_runner.py
│
├── src/
│   ├── __init__.py
│   ├── fetch_binance.py        # Veri yükleme
│   ├── features.py             # Feature engineering
│   ├── labeling.py             # Triple-barrier
│   ├── dataset.py              # Windows
│   ├── train.py                # Eğitim
│   ├── infer.py                # Tahmin
│   ├── backtest_core.py        # Backtest
│   ├── gridsearch.py           # Optimizasyon
│   ├── live_loop.py            # Canlı döngü
│   ├── utils.py                # Yardımcılar
│   └── models/
│       ├── __init__.py
│       └── transformer.py       # Transformer encoder
│
└── tests/
    ├── __init__.py
    ├── test_labeling.py
    ├── test_features.py
    └── test_model_forward.py
```

## 🚀 Başlamak İçin

```bash
cd LLM

# 1. Virtual environment
make venv
source venv/bin/activate

# 2. Paketleri yükle
make install

# 3. Veriyi indir (BTCUSDT 3m)
python scripts/download_binance_klines.py

# 4. Modeli eğit
make train

# 5. Grid search yap
make grid

# 6. Backtest çalıştır
make backtest

# 7. Test et
make test

# 8. Live demo
make live
```

## 📊 Özellikler

- ✅ Transformer encoder (64-dim, 2 layers, 4 heads)
- ✅ Triple-barrier first-touch etiketleme
- ✅ Feature engineering (EMA, RSI, volume, z-score)
- ✅ Grid search ile SL optimizasyonu
- ✅ Backtest (komisyon + slippage)
- ✅ Live loop + hooks
- ✅ Test suite
- ✅ Type hints + docstrings

## 🎯 Sonraki Adımlar

1. Data indir: `python scripts/download_binance_klines.py`
2. Model eğit: `make train`
3. Grid search: `make grid`
4. Backtest: `make backtest`
5. İncele ve iterasyon yap!

**Proje başlamaya hazır! 🚀**

