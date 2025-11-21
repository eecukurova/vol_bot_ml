# 📊 Analiz Scriptleri - Kullanım Kılavuzu

## 🎯 Soru: Şu Anda Çalıştırsak Ne İşe Yarar?

### ✅ Şu Anda Çalıştırılabilir ve İşe Yarar:

#### 1. `analyze_negative_patterns.py` ✅
**Durum**: ✅ Hemen çalıştırılabilir  
**Veri Kaynağı**: Binance API'den direkt trade'leri alıyor (60 gün geriye gidiyor)  
**İşe Yarar**: 
- **ESKİ POZİSYONLAR** için çalışır
- Geçmiş 60 gün içindeki tüm pozisyonları analiz eder
- Arka arkaya 5+ negatif pozisyon pattern'lerini bulur
- Zaman, PnL, side dağılımı analizi yapar
- **Şu anda çalıştırıldığında değerli bilgiler verir**

**Örnek Çıktı**:
```
📊 Sequence 1: 5 negatif pozisyon
⏰ Zaman Pattern: En çok pozisyon açılan saat: 2:00
💰 PnL Dağılımı: Ortalama: $-10.41
```

#### 2. `import_historical_data.py` ✅ (YENİ)
**Durum**: ✅ Hemen çalıştırılabilir  
**Veri Kaynağı**: Binance API'den geçmiş trade'leri alıp `closed_positions.json` oluşturuyor  
**İşe Yarar**:
- Geçmiş pozisyonları `closed_positions.json` formatına dönüştürür
- Diğer scriptlerin çalışması için veri hazırlar
- **Şu anda çalıştırıldığında diğer scriptleri aktif hale getirir**

---

### ⏳ Şu Anda Veri Yok, Ama İçe Aktarma Sonrası Çalışır:

#### 3. `pattern_matcher.py` ⏳
**Durum**: `closed_positions.json` dosyası gerekiyor  
**Veri Kaynağı**: `runs/closed_positions.json`  
**İşe Yarar**:
- **ESKİ POZİSYONLAR** için çalışır (import sonrası)
- Benzer özelliklere sahip SL pozisyonlarını gruplar
- Pattern analizi ve öneriler sunar
- **Import sonrası hemen çalıştırılabilir**

**Çalıştırmak İçin**:
```bash
# Önce import yap
python3 scripts/import_historical_data.py

# Sonra pattern matching
python3 scripts/pattern_matcher.py
```

#### 4. `prepare_hard_negatives.py` ⏳
**Durum**: `closed_positions.json` dosyası gerekiyor  
**Veri Kaynağı**: `runs/closed_positions.json` ve `runs/skipped_signals_evaluated.json`  
**İşe Yarar**:
- **ESKİ POZİSYONLAR** için çalışır (import sonrası)
- Model eğitimi için hard negative examples hazırlar
- **Import sonrası hemen çalıştırılabilir**

**Çalıştırmak İçin**:
```bash
# Önce import yap
python3 scripts/import_historical_data.py

# Sonra hard negatives hazırla
python3 scripts/prepare_hard_negatives.py
```

---

### ❌ Şu Anda Çalışmaz (Yeni Sistem Verisi Gerekiyor):

#### 5. `evaluate_skipped_signals.py` ❌
**Durum**: `runs/skipped_signals.json` ve `runs/closed_positions.json` gerekiyor  
**Veri Kaynağı**: 
- `runs/skipped_signals.json` (yeni sistem - henüz yok)
- `runs/closed_positions.json` (import sonrası olabilir)  
**İşe Yarar**:
- **YENİ SİSTEM** için çalışır
- Skip edilen sinyallerin doğruluğunu ölçer
- Model doğruluk analizi yapar
- **Şu anda çalışmaz** (skip edilen sinyal verisi yok)

**Ne Zaman Çalışır**:
- Live loop'ta aktif pozisyon varken sinyal geldiğinde
- Skip edilen sinyaller `runs/skipped_signals.json`'a kaydedildiğinde
- O zaman çalıştırılabilir

---

## 📋 Önerilen Çalıştırma Sırası

### Şimdi Çalıştırılabilir (Eski Verilerle):

```bash
cd /root/ATR/LLM

# 1. Negatif pozisyon pattern analizi (direkt çalışır)
python3 scripts/analyze_negative_patterns.py

# 2. Geçmiş verileri içe aktar (diğer scriptler için)
python3 scripts/import_historical_data.py

# 3. Pattern matching (import sonrası)
python3 scripts/pattern_matcher.py

# 4. Hard negatives hazırla (import sonrası)
python3 scripts/prepare_hard_negatives.py
```

### Gelecekte Çalıştırılacak (Yeni Verilerle):

```bash
# Skip edilen sinyaller biriktikten sonra
python3 scripts/evaluate_skipped_signals.py
```

---

## 🎯 Sonuç

### Şu Anda İşe Yarar:

1. ✅ **`analyze_negative_patterns.py`**: ESKİ pozisyonları analiz eder, pattern'leri bulur
2. ✅ **`import_historical_data.py`**: Geçmiş verileri hazırlar, diğer scriptleri aktif hale getirir
3. ✅ **`pattern_matcher.py`**: Import sonrası ESKİ pozisyonlarda pattern'leri bulur
4. ✅ **`prepare_hard_negatives.py`**: Import sonrası ESKİ pozisyonlardan hard negatives hazırlar

### Şu Anda İşe Yaramaz:

1. ❌ **`evaluate_skipped_signals.py`**: YENİ sistem verisi gerekiyor (henüz skip edilen sinyal yok)

---

## 💡 Öneri

**Şimdi yapılacaklar**:
1. `analyze_negative_patterns.py` çalıştır → Eski pozisyon pattern'lerini gör
2. `import_historical_data.py` çalıştır → Veri hazırla
3. `pattern_matcher.py` çalıştır → Pattern'leri bul
4. `prepare_hard_negatives.py` çalıştır → Model eğitimi için hazırla

**Sonuç**: Eski pozisyonlardan öğrenilen pattern'ler model eğitiminde kullanılabilir!

