# 🚀 SOL Projesi - Deployment Guide

## 📋 Adımlar

### 1. Model Dosyaları (✅ HAZIR)

ETH modeli SOL'e kopyalandı (hızlı başlangıç için):
- ✅ `models/seqcls.pt` - ETH modeli (SOL'de test edilecek)
- ✅ `models/feat_cols.json` - Feature columns

**Not**: ETH modeli SOL'de çalışır ama optimal olmayabilir. İleride SOL için özel model eğitilebilir.

### 1.1. (Opsiyonel) SOL için Özel Model Eğitimi

SOL için optimal performans için yeni model eğitilebilir:

```bash
cd /Users/ahmet/ATR/SOL

# Veri indir
python scripts/download_binance_klines.py --symbol SOLUSDT --interval 3m --start 2024-01-01

# Model eğit
make train
# veya
python scripts/train_runner.py --symbol SOLUSDT --timeframe 3m
```

### 2. (Opsiyonel) Grid Search (Parametre Optimizasyonu)

SOL için en iyi parametreleri bul:

```bash
make grid
# veya
python scripts/gridsearch_runner.py --symbol SOLUSDT --timeframe 3m
```

### 3. (Opsiyonel) Backtest

Eğitilmiş model ve optimal parametrelerle backtest:

```bash
make backtest
# veya
python scripts/backtest_runner.py --symbol SOLUSDT --timeframe 3m \
    --sl-pct 0.008 --thr-long 0.60 --thr-short 0.60
```

### 4. Config Kontrolü

`configs/llm_config.json` dosyasında:
- ✅ Symbol: SOLUSDT (zaten güncellendi)
- ✅ Log file: runs/sol_live.log (zaten güncellendi)
- ✅ Trading params: ETH'deki gibi ayarlı (test için)
  - `sl_pct`: 0.010 (1.0%)
  - `tp_pct`: 0.005 (0.5%)
  - `thr_long`: 0.85 (85%)
  - `thr_short`: 0.85 (85%)
  - `min_prob_ratio`: 3.0

**Not**: İleride grid search yapılırsa, bu değerler güncellenebilir.

### 5. Sunucuya Deploy

```bash
# Sunucuya bağlan
ssh -i ~/.ssh/ahmet_key root@159.65.94.27

# SOL klasörünü oluştur ve dosyaları kopyala
cd /root/ATR
# (Local'den dosyaları kopyala)

# Virtual environment oluştur
cd SOL
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Systemd service dosyasını kopyala
cp sol_live.service /etc/systemd/system/

# Service'i aktif et
systemctl daemon-reload
systemctl enable sol_live.service
systemctl start sol_live.service

# Logları kontrol et
tail -f runs/sol_live.log
```

### 6. Service Kontrolü

```bash
# Service durumu
systemctl status sol_live.service

# Service restart
systemctl restart sol_live.service

# Service stop
systemctl stop sol_live.service

# Loglar
journalctl -u sol_live.service -f
```

---

## 📊 Trend Following Exit Entegrasyonu

SOL için trend following exit stratejisi kullanılacak. Backtest sonuçlarına göre:
- **Win Rate**: 65.2%
- **Total PnL**: +3.56%
- **Profit Factor**: 1.25

Bu parametreler `configs/llm_config.json`'a eklenecek veya `src/live_loop.py`'a entegre edilecek.

---

## ⚠️ Önemli Notlar

1. **Model Eğitimi**: SOL için mutlaka yeni model eğitilmeli (ETH modeli kullanılmamalı)
2. **Grid Search**: SOL için optimal parametreleri bulmak için grid search yapılmalı
3. **Shadow Mode**: İlk 7 gün shadow mode aktif olabilir (test için)
4. **Leverage**: Config'de 5x olarak ayarlı (ihtiyaca göre değiştirilebilir)

---

## ✅ Checklist

- [x] SOL klasörü oluşturuldu
- [x] Config dosyaları güncellendi (SOLUSDT)
- [x] Systemd service dosyası oluşturuldu
- [x] Model dosyaları kopyalandı (ETH modeli)
- [ ] Sunucuya deploy
- [ ] Service başlatma ve test
- [ ] (Opsiyonel) SOL için özel model eğitimi
- [ ] (Opsiyonel) Grid search (SOL için)
- [ ] (Opsiyonel) Backtest (SOL için)

---

**Tarih**: 4 Kasım 2025  
**Coin**: SOL/USDT  
**Timeframe**: 3m  
**Strateji**: Trend Following Exit (Multi-coin test sonuçlarına göre)

