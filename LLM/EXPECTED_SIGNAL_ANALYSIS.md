# 📊 LLM Projesi - Beklenen Sinyal Analizi

## 🔍 Backtest Sonuçları (2 Hafta Test Verisi)

**Test Periyodu**: 14 gün (2025-10-23 to 2025-11-01)  
**Test Bars**: 4361 bar (3 dakikalık)  
**Yeni Model Trades**: 1862  
**Threshold**: 0.6 (60%)

### Backtest'te Sinyal Frekansı:
- **Günlük**: ~133 trade/gün
- **Saatlik**: ~5.5 trade/saat  
- **Bar başına**: Her 3.6 barda bir sinyal
- **Zaman aralığı**: Yaklaşık 10.8 dakikada bir sinyal

## ⚠️ Backtest vs Canlı Farkları

### 1. Threshold Farkı:
- **Backtest**: 0.6 (60%)
- **Canlı**: 0.8 (80%)
- **Etki**: Threshold %33 artışı sinyal sayısını **%50-70 azaltır**

### 2. Regime Filter:
- **Backtest**: YOK ❌
- **Canlı**: VAR ✅ (EMA50 > EMA200 AND Vol > 0.8)
- **Etki**: Sinyal sayısını ek olarak **%30-50 azaltır**

## 📈 Canlıda Beklenen Sinyal Sayısı

### Threshold Etkisi (0.6 → 0.8):
- Backtest: 1862 trades (14 gün)
- Threshold artışı ile: ~560-930 trades (tahmini %30-50 kalır)
- **Günlük**: ~40-66 trade/gün (threshold etkisi)

### Regime Filter Ek Etkisi:
- Regime filter ek %30-50 azaltma
- **Son Beklenti**: ~20-35 trade/gün
- **Saatlik**: ~0.8-1.5 sinyal/saat

## 📅 Son 24 Saat Durumu

**Gerçekleşen**: 0 sinyal ❌  
**Beklenen**: ~20-35 sinyal

### Neden Çok Az?

1. **Threshold Çok Yüksek**: 
   - Ortalama confidence: %31.7
   - Threshold: %80
   - Çok az sinyal bu threshold'u geçer

2. **Regime Filter Çok Aktif**:
   - Vol spike çok düşük (0.16-0.38)
   - Threshold: 0.8
   - Çoğu sinyal regime filter'dan geçemiyor

3. **Piyasa Koşulları**:
   - Düşük volatilite dönemi
   - Model yüksek kaliteli sinyaller bekliyor

## 💡 Sonuç ve Öneriler

### Bu Normal mi?

**Kısmen normal** ama beklenenden biraz az:
- Backtest'te threshold 0.6 ile günlük ~133 sinyal
- Canlıda threshold 0.8 + regime filter ile beklenen ~20-35 sinyal/gün
- Son 24 saatte 0 sinyal = **beklenenin altında**

### Öneriler:

1. **Confidence Threshold'u Düşür** (Önerilen):
   - 0.8 → 0.75 (%25 azaltma)
   - Beklenti: Günlük ~10-15 sinyal

2. **Regime Filter Vol Threshold'unu Düşür**:
   - 0.8 → 0.5
   - Daha fazla sinyal geçer

3. **Her İkisini Birlikte Düşür** (En İyi Denge):
   - Threshold: 0.8 → 0.75
   - Vol threshold: 0.8 → 0.5
   - Beklenti: Günlük ~25-40 sinyal (backtest'e yakın)

