# 🔧 Tüm Servisler - Optimizasyon Raporu

## 📊 Bulunan Servisler

### Trading Servisleri (Yüksek Memory Kullanımı):
1. **eth_live.service** - 306MB ⚠️
2. **llm_live.service** - 254MB ✅ (Düzeltildi)
3. **sol-macd-trader.service** - 214MB 🔴 (OOM kill olmuş!)
4. **pengu-ema-trader.service** - 169MB 🔴 (OOM kill olmuş!)
5. **nasdaq-dynamic-scanner.service** - 65MB
6. **nasdaq-ipo-scanner.service** - 65MB
7. **bist-signal-generator.service** - 63MB

## 🔴 OOM Kill Olan Servisler

Son 24 saatte:
- **llm_live.service**: 7 kez OOM kill ✅ (Düzeltildi)
- **sol-macd-trader.service**: 2 kez OOM kill ❌ (Düzeltilmeli)
- **pengu-ema-trader.service**: 1 kez OOM kill ❌ (Düzeltilmeli)

## ✅ Yapılacak Optimizasyonlar

Her servis için:
1. Memory limit ekle (500MB limit, 400MB high)
2. MemoryMax ekle (600MB)
3. State dosyalarını kontrol et ve temizle

