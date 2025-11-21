# 📊 Model Eğitimi Analiz Araçları

Bu dizinde model eğitimi için geliştirilmiş analiz araçları bulunmaktadır.

## 🛠️ Araçlar

### 1. `analyze_negative_patterns.py`
**Amaç**: Arka arkaya negatif pozisyonların pattern'lerini analiz eder.

**Kullanım**:
```bash
python scripts/analyze_negative_patterns.py
```

**Çıktı**:
- Arka arkaya 5+ negatif pozisyon sequence'leri
- Zaman pattern'leri (saat, gün)
- PnL dağılımı
- Side dağılımı
- Fiyat hareketi analizi

### 2. `evaluate_skipped_signals.py`
**Amaç**: Skip edilen sinyallerin doğruluğunu değerlendirir.

**Kullanım**:
```bash
python scripts/evaluate_skipped_signals.py
```

**Çıktı**:
- Skip edilen sinyallerin TP/SL hit oranları
- Model doğruluk analizi
- Aktif pozisyonlarla karşılaştırma
- `runs/skipped_signals_evaluated.json` dosyası

### 3. `prepare_hard_negatives.py`
**Amaç**: Model eğitimi için hard negative examples hazırlar.

**Kullanım**:
```bash
python scripts/prepare_hard_negatives.py
```

**Çıktı**:
- Hard negative kategorileri:
  - Yüksek confidence SL pozisyonları
  - Skip edilen SL sinyalleri
  - Arka arkaya SL pozisyonları
- `models/hard_negatives.json` dosyası (training için)

### 4. `pattern_matcher.py`
**Amaç**: Tekrarlayan negatif pattern'leri bulur.

**Kullanım**:
```bash
python scripts/pattern_matcher.py
```

**Çıktı**:
- Benzer özelliklere sahip SL pozisyon grupları
- Pattern analizi ve öneriler
- `runs/detected_patterns.json` dosyası

## 📋 Veri Dosyaları

### `runs/skipped_signals.json`
Skip edilen sinyaller (live loop tarafından otomatik oluşturulur).

### `runs/closed_positions.json`
Kapanan pozisyonlar (live loop tarafından otomatik oluşturulur).

### `runs/skipped_signals_evaluated.json`
Skip edilen sinyallerin değerlendirme sonuçları (`evaluate_skipped_signals.py` tarafından oluşturulur).

### `runs/detected_patterns.json`
Bulunan pattern'ler (`pattern_matcher.py` tarafından oluşturulur).

### `models/hard_negatives.json`
Hard negative examples (`prepare_hard_negatives.py` tarafından oluşturulur).

## 🔄 Çalışma Akışı

1. **Live Trading**: Skip edilen sinyaller ve kapanan pozisyonlar otomatik kaydedilir
2. **Pattern Analizi**: `analyze_negative_patterns.py` ile pattern'leri bul
3. **Sinyal Değerlendirme**: `evaluate_skipped_signals.py` ile model doğruluğunu ölç
4. **Pattern Matching**: `pattern_matcher.py` ile tekrarlayan pattern'leri bul
5. **Hard Negative Hazırlama**: `prepare_hard_negatives.py` ile training örnekleri hazırla
6. **Model Retraining**: Hard negatives'i model eğitiminde kullan

## 💡 Kullanım Örnekleri

### Tam Analiz Döngüsü
```bash
# 1. Pattern analizi
python scripts/analyze_negative_patterns.py

# 2. Skip edilen sinyalleri değerlendir
python scripts/evaluate_skipped_signals.py

# 3. Pattern matching
python scripts/pattern_matcher.py

# 4. Hard negatives hazırla
python scripts/prepare_hard_negatives.py
```

### Model Retraining Öncesi
```bash
# Hard negatives'i hazırla
python scripts/prepare_hard_negatives.py

# models/hard_negatives.json dosyasını kontrol et
# Sonra model retraining sırasında bu dosyayı kullan
```

## 📊 Örnek Çıktılar

### Pattern Analizi
```
📊 Sequence 1: 5 negatif pozisyon

⏰ Zaman Pattern:
   İlk Entry: 2025-11-04 02:27
   Son Exit: 2025-11-04 08:30
   Süre: 6.0 saat
   En çok pozisyon açılan saat: 2:00 (3 pozisyon)

💰 PnL Dağılımı:
   Ortalama: $-10.41
   Min: $-11.25
   Max: $-8.19
```

### Model Doğruluk Analizi
```
=== MODEL DOĞRULUK ANALİZİ ===

✅ Model Doğru Sinyal: 8
❌ Model Yanlış Sinyal: 2

📊 Model Doğruluk Oranı: 80.0%
```

## 🎯 Sonraki Adımlar

1. Bu araçları düzenli olarak çalıştır
2. Bulunan pattern'leri model eğitiminde kullan
3. Hard negatives'i retraining pipeline'ına entegre et
4. Pattern'lerden öğrenilen özellikleri feature engineering'de kullan

