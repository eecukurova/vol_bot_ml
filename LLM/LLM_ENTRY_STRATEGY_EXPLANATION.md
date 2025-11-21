# LLM Entry Strategy - Pine Script Açıklaması

## 📋 Genel Bakış

Bu dokümantasyon, LLM projesinin pozisyon giriş stratejisini Pine Script formatında gösterir. **ÖNEMLİ**: Gerçek sistem bir Transformer model kullanır ve Pine Script'te tam olarak çoğaltılamaz, ama giriş mantığı ve kriterleri burada açıklanmıştır.

## 🎯 Giriş Kriterleri

### 1. Model Prediction (Ana Kriter)

**Gerçek Sistem:**
- Transformer model 128 bar window'dan feature'ları alır
- Model 3 sınıf prediction yapar: `FLAT`, `LONG`, `SHORT`
- Her sınıf için probability hesaplanır: `prob_flat`, `prob_long`, `prob_short`

**Pine Script'te:**
- Model prediction yapılamaz (Transformer gerektirir)
- Basit bir proxy gösterilmiştir (EMA trend + RSI + Volume kombinasyonu)
- Gerçek sistemde bu Python'da çalışan eğitilmiş bir modeldir

### 2. Threshold Kontrolü

```python
# LLM/src/infer.py - decide_side()
if prob_long >= thr_long:  # thr_long = 0.85 (85%)
    return "LONG", prob_long
elif prob_short >= thr_short:  # thr_short = 0.85 (85%)
    return "SHORT", prob_short
else:
    return "FLAT", prob_flat
```

**Kurallar:**
- `prob_long >= 0.85` → LONG sinyali
- `prob_short >= 0.85` → SHORT sinyali
- Diğer durumlarda → FLAT (pozisyon açılmaz)

### 3. Regime Filter (Şu Anda Disabled)

**Config:**
```json
"regime_filter": {
    "enabled": false,
    "use_ema_filter": false,
    "use_vol_filter": false,
    "vol_spike_threshold": 0.4
}
```

**Mantık (Eğer enabled olsaydı):**
```python
# LONG için:
regime_ok = (ema50 > ema200) and (vol_spike > vol_spike_threshold)

# SHORT için:
regime_ok = (ema50 < ema200) and (vol_spike > vol_spike_threshold)
```

**Şu Anki Durum:**
- Regime filter **DISABLED**
- Tüm sinyaller threshold kontrolünden sonra direkt işlenir

### 4. Pattern Blocker

**Mantık:**
- Geçmiş kayıplı pozisyonlarla pattern matching yapar
- Benzer pattern tespit edilirse sinyal engellenir
- Python'da çalışır, Pine Script'te gösterilmez

### 5. Volume Spike Monitor

**Mantık:**
- Volume spike düşükse uyarı verir
- Pozisyon açmayı engellemez, sadece uyarı
- `vol_spike = volume / rolling_mean(volume, 20)`

## 📊 Kullanılan Feature'lar

LLM modeli şu feature'ları kullanır (128 bar window):

### Price Features
- `log_ret`: Log return (1 bar)
- `log_ret_3`: Log return (3 bar toplam)
- `log_ret_5`: Log return (5 bar toplam)
- `hl_range_norm`: High-Low range (normalize)
- `body_norm`: Candle body (normalize)
- `upper_wick_ratio`: Üst wick oranı
- `lower_wick_ratio`: Alt wick oranı

### EMA Features
- `ema10`, `ema20`, `ema50`, `ema200`: EMA değerleri
- `ema10_dist`, `ema20_dist`, `ema50_dist`, `ema200_dist`: EMA distance (relative)
- `ema10_slope`, `ema20_slope`, `ema50_slope`, `ema200_slope`: EMA slope (3-bar change)

### Technical Indicators
- `rsi`: RSI(14)
- `vol_spike`: Volume spike (volume / rolling_mean(20))

### Z-Score Normalization
- Tüm feature'lar 200-period rolling z-score ile normalize edilir
- `feature_z = (feature - rolling_mean) / rolling_std`

## 🎯 TP/SL Hesaplama

```python
# LLM/src/infer.py - tp_sl_from_pct()
if side == "LONG":
    tp = close * (1 + tp_pct)  # tp_pct = 0.008 (0.8%)
    sl = close * (1 - sl_pct)   # sl_pct = 0.008 (0.8%)
elif side == "SHORT":
    tp = close * (1 - tp_pct)
    sl = close * (1 + sl_pct)
```

**Mevcut Ayarlar:**
- `tp_pct`: 0.008 (0.8%)
- `sl_pct`: 0.008 (0.8%)
- Risk/Reward: 1:1

## 📈 Giriş Akışı

```
1. Yeni bar geldiğinde:
   ├─ 128 bar window'dan feature'lar çıkarılır
   ├─ Model prediction yapar (prob_flat, prob_long, prob_short)
   │
2. Threshold kontrolü:
   ├─ prob_long >= 0.85? → LONG sinyali
   ├─ prob_short >= 0.85? → SHORT sinyali
   └─ Diğer durumlar → FLAT
   │
3. Regime filter (disabled):
   └─ Şu anda kontrol edilmiyor
   │
4. Pattern blocker:
   ├─ Geçmiş kayıplı pozisyonlarla karşılaştır
   └─ Benzer pattern varsa engelle
   │
5. Volume spike monitor:
   └─ Düşük volume spike ise uyarı ver
   │
6. Pozisyon aç:
   ├─ TP/SL hesapla
   ├─ Order gönder
   └─ Telegram bildirimi gönder
```

## ⚠️ Önemli Notlar

1. **Model Prediction Pine Script'te Yapılamaz:**
   - Gerçek sistem Transformer model kullanır
   - Model Python'da eğitilmiş ve çalışır
   - Pine Script'te sadece proxy gösterilmiştir

2. **Feature Engineering:**
   - 128 bar window kullanılır
   - Tüm feature'lar z-score normalize edilir
   - Model bu feature'ları sequence olarak işler

3. **Threshold Değerleri:**
   - `thr_long`: 0.85 (85%)
   - `thr_short`: 0.85 (85%)
   - Bu değerler backtest sonuçlarına göre optimize edilmiştir

4. **Regime Filter:**
   - Şu anda **DISABLED**
   - Backtest sonuçlarına göre disabled edilmiştir (daha iyi performans)

5. **Pattern Blocker:**
   - Geçmiş kayıplı pozisyonlarla pattern matching yapar
   - Benzer pattern tespit edilirse sinyal engellenir
   - Python'da çalışır, Pine Script'te gösterilmez

## 🔧 Config Dosyası

```json
{
  "trading_params": {
    "sl_pct": 0.008,
    "tp_pct": 0.008,
    "thr_long": 0.85,
    "thr_short": 0.85
  },
  "regime_filter": {
    "enabled": false,
    "use_ema_filter": false,
    "use_vol_filter": false,
    "vol_spike_threshold": 0.4
  }
}
```

## 📝 Pine Script Kullanımı

1. TradingView'de Pine Script editörünü açın
2. `LLM_ENTRY_STRATEGY.pine` dosyasını yükleyin
3. Timeframe: 3m (LLM projesi 3m kullanır)
4. Symbol: BTCUSDT (veya başka bir symbol)
5. Ayarları config'e göre yapın:
   - `thr_long`: 0.85
   - `thr_short`: 0.85
   - `tp_pct`: 0.008
   - `sl_pct`: 0.008
   - `regime_enabled`: false

**NOT:** Pine Script'teki sinyaller gerçek model prediction'ı değildir. Sadece giriş mantığını ve kriterleri gösterir. Gerçek sistem Python'da çalışan eğitilmiş Transformer model kullanır.

