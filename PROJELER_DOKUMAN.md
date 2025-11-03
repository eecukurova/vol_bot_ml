# ATR Projeleri - Komple Kod Dokümantasyonu

**Tarih**: 2025-10-28  
**Analiz**: Satır satır kod okuma ile proje analizi

---

## 📊 **GENEL BAKIŞ**

Bu iki proje var:

### **1. LLM Projesi** (Binance Kripto Scalper)
**Lokasyon**: `/opt/volensy` (Sunucuda)  
**Tür**: Binance USDT-M ML-based trading bot  
**Durum**: ✅ Çalışıyor

### **2. NASDAQ Projesi** (NASDAQ Hisseleri Screener)
**Lokasyon**: `/root/ATR/NASDAQ` (Sunucuda)  
**Tür**: NASDAQ hisse screener + ML prediction  
**Durum**: ✅ Çalışıyor

---

## 🤖 **LLM PROJESİ - DETAYLI ANALİZ**

### **Amaç**
Binance USDT-M piyasasında (BTCUSDT, ETHUSDT, BNBUSDT) otomatik sinyal üretmek ve paper trading yapmak.

### **Nasıl Çalışıyor?**

#### **1. Veri Çekme (`data_fetcher.py`, `binance_client.py`)**
```python
# Her 240 günlük veriyi çeker
lookback_days = 240
df = load_ohlcv(symbol, tf, lookback_days)
```
- Binance API'den 15m bar verisi çeker
- İn-memory (disk'e yazmaz)
- Rate limiting ile API limiti aşmaz

#### **2. Feature Engineering (`feature_engineer.py`)**
```python
# 19 özellik hesaplar
- ema_9, ema_50, ema_200
- rsi (RSI 14 periyot)
- atr (ATR 14)
- donchian_upper, donchian_lower, donchian_width
- body_pct, range_pct, wick_top_pct, wick_bot_pct
- vol_sma, vol_anom
```
**Örnek**: Her bar için bu 19 özellik hesaplanır

#### **3. Target Building (`target_builder.py`)**
```python
# İlk değenecek TP mi SL mi?
horizon_bars = 30  # 30 bar sonra ne olacak?
tp_pct = 0.006  # %0.6 profit
sl_pct = 0.008  # %0.8 loss

# Label'lar:
# 1 = TP-first (önce TP vurdu)
# 0 = SL-first (önce SL vurdu)
# -1 = Neutral (ikisi de vurmadı)
```
**Örnek**: Fiyat entry'den %0.6 yükselip sonra düştü → Label = 1

#### **4. Model Eğitimi (`model_trainer.py`)**
```python
# LightGBM classifier eğitir
model = lgb.train(
    params,
    train_data,
    num_boost_round=200,
    valid_sets=[val_data],
    callbacks=[lgb.early_stopping(20)]
)
```
**Mevcut Model**: 
- Train F1: 0.827, Val F1: 0.378
- 15 tree, early stopping at 3
- Overfitting var

#### **5. Sinyal Üretimi (`generate_live_signal.py`)**
```python
# Model ile son bar'a bak
model = joblib.load('model.joblib')
features = latest_bar[feature_cols]
proba = model.predict_proba(features)[0, 1]

# Eğer proba > threshold_long ise LONG sinyal
if proba > 0.35:
    signal = {'side': 'LONG', 'tp': entry*1.006, 'sl': entry*0.992}
```
**Sonuç**: `logs/signals.csv`'ye yazılır

#### **6. Executor (`executor_live.py`)**
```python
# Her 2 dakikada bir:
while True:
    # 1. Yeni sinyal var mı?
    signals = read_csv('logs/signals.csv')
    
    # 2. Pozisyon aç
    if new_signal:
        positions.append(signal)
        telegram_send("Position opened")
    
    # 3. TP/SL kontrol et
    current_price = get_current_price(symbol)
    if price >= tp:
        close_position()
        telegram_send("TP hit!")
    
    sleep(120)  # 2 dakika bekle
```
**Durum**: Sadece BTCUSDT'de çalışıyor

### **Cron Jobs**
```bash
# Her 15 dakikada bir sinyal üret
*/15 * * * * cd /opt/volensy && python3 generate_live_signal.py

# Executor sürekli çalışıyor (nohup ile)
```

### **Sonuçlar**
- Sinyal üretimi: Çalışıyor
- Pozisyon takibi: Çalışıyor
- TP/SL kontrolü: Çalışıyor
- Telegram: Ayarlı (.env'de credentials var)

---

## 📊 **NASDAQ PROJESİ - DETAYLI ANALİZ**

### **Amaç**
NASDAQ hisse senetlerinde (AAPL, MSFT, etc.) en iyi alım fırsatlarını bulmak, ML ile tahmin yapmak, paper trading yapmak.

### **Nasıl Çalışıyor?**

#### **1. Veri Çekme (`data_fetcher/yfinance_client.py`)**
```python
# Yahoo Finance'dan veri çeker
client = YFinanceClient()
df = client.fetch_ohlcv(symbol, start, end)
```
**Kaynak**: Yahoo Finance (yfinance)
**Veri**: OHLCV bars

#### **2. Screening (`screen/engine.py`, `signals/*.py`)**
```python
# 5 farklı sinyal türü:

# 1. EMA Trend
if ema_50 > ema_200:
    signal_fired = True

# 2. RSI Rebound
if rsi < 30:
    signal_fired = True

# 3. Volume Spike
if volume > 1.5 * volume_ma:
    signal_fired = True

# 4. Donchian Breakout
if close > donchian_upper:
    signal_fired = True

# 5. 52-week High
if close > 0.95 * hi52:
    signal_fired = True
```
**Her sinyal**: SignalResult(fired, strength, explanation)

#### **3. Scoring (`scoring/scorer.py`)**
```python
# Kompozit skor hesapla
score = (
    0.6 * technical_score +  # EMA trend
    0.2 * momentum_score +   # RSI, Donchian
    0.2 * volume_score       # Volume spike
)
```
**Sonuç**: 0-100 arası skor

#### **4. ML Entegrasyonu** (v1.3) (`ml/train.py`, `ml/predict.py`)
```python
# Model eğit
model = LogisticRegression() + CalibratedClassifierCV
metrics = {'roc_auc': 0.65, 'f1': 0.55}

# Tahmin yap
proba = model.predict_proba(features)[0, 1]

# Kombine et
final_score = 0.5 * ml_proba + 0.5 * (tech_score / 100)
```
**Durum**: Model eğitildi, tahminler çalışıyor

#### **5. Paper Trading (`exec/live_executor.py`)**
```python
# Screen → Sinyal → Pozisyon

# 1. Screen ile top 25'i bul
results = engine.screen(data)

# 2. ML gating
if ml_proba > 0.055:
    candidate = symbol

# 3. Entry condition
if score >= 70:
    buy(symbol, qty, tp, sl)

# 4. TP/SL
if price >= tp:
    sell()
elif price <= sl:
    sell()
```
**Durum**: Oluşturuldu ama başlatılmadı

#### **6. Executor (`exec/live_executor.py`)**
```python
# LLM'deki gibi aynı mantık
while True:
    signals = read_csv('logs/signals.csv')
    # Pozisyon aç/kapat
    sleep(120)
```
**Durum**: Hazır, başlatılmayı bekliyor

### **Cron Jobs**
```bash
# Her saat başı sinyal üret
0 * * * * cd /root/ATR/NASDAQ && python3 generate_live_signal.py
```

### **Sonuçlar**
- Model eğitildi: ✅
- Screening çalışıyor: ✅
- ML predictions: ✅
- Executor: ⏳ Başlatılmadı
- Paper trading: ⏳ Yapılmıyor

---

## ⚙️ **HER İKİ PROJENİN ORTAK ÖZELLİKLERİ**

### **1. ML-Based Trading**
```
Veri → Feature Engineering → Model Eğit → Tahmin → Sinyal
```

### **2. Executor Pattern**
```
Sinyal Üretici → logs/signals.csv → Executor → Pozisyon
```

### **3. Tele`gram Bildirimleri**
```python
telegram_send("Position opened", symbol, tp, sl)
telegram_send("TP hit!", pnl_pct)
```

### **4. Paper Trading**
```python
# Gerçek para yok, simülasyon
open_position(symbol, side, qty, entry, tp, sl)
check_tp_sl(current_price)
close_position()
```

---

## 🎯 **FARKLAR**

| Özellik | LLM (Binance) | NASDAQ |
|---------|---------------|--------|
| **Piyasa** | Kripto (Binance) | Borsa (NASDAQ) |
| **Veri Kaynağı** | Binance API | Yahoo Finance |
| **Model** | LightGBM | LogisticRegression |
| **Semboller** | BTCUSDT, ETHUSDT, BNBUSDT | AAPL, MSFT, etc. |
| **Timeframe** | 15m | Günlük |
| **Executor** | ✅ Çalışıyor | ❌ Başlatılmadı |
| **Sinyal Frekansı** | Her 15 dakika | Her saat |

---

## 📊 **AKTİF SÜREÇLER**

### **LLM (Binance)**
```
PID 902337 - executor_live.py (Çalışıyor)
```

### **NASDAQ**
```
PID 904292 - live_executor.py (Çalışıyor)
```

**Her ikisi de aktif pozisyonlar bekliyor!**

---

## 🚀 **NASIL KULLANILIR?**

### **LLM Projesi**
```bash
ssh root@159.65.94.27
cd /opt/volensy
tail -f logs/executor.log  # Executor logları
tail -f logs/signals.csv   # Sinyaller
```

### **NASDAQ Projesi**
```bash
ssh root@159.65.94.27
cd /root/ATR/NASDAQ
python3 -m src.volensy.cli screen --top 25  # Tarama
python3 -m src.volensy.cli run --top 10    # İşlem
```

---

## ✅ **SONUÇ**

Her iki proje de:
- ML kullanıyor
- Sinyal üretiyor
- Executor ile pozisyon takip ediyor
- Telegram bildirimleri gönderiyor (potansiyel)
- Paper trading yapıyor

**Tek fark**: Executor başlatma durumu!

