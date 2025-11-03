# ⚠️ LLM Projesi - Tespit Edilen Sorunlar

## 🔴 Kritik Sorunlar

### 1. OOM (Out of Memory) Kill - ÇOK KRİTİK
**Durum**: Son 24 saatte 7 kez OOM kill
- Servis sürekli öldürülüyor ve yeniden başlatılıyor
- Memory kullanımı: ~350MB (peak 472-484MB)
- Sistem RAM: 1.9GB (sadece 275MB available)
- Swap: Yok (0B)

**Etki**: 
- Servis sürekli restart oluyor (restart counter: 9)
- Potansiyel sinyal kaybı
- Kararsız çalışma

**Çözüm önerileri**:
1. Swap ekle (önerilen)
2. Memory limit ekle service'e
3. State dosyasını temizle (70 orders state'de kalıyor)
4. Model yükleme optimize et

### 2. Binance API Error
**Hata**: 
```
ERROR:__main__:Error: binance GET https://api.binance.com/api/v3/exchangeInfo
```

**Etki**: Exchange info çekerken hata, market bilgileri alınamıyor olabilir

**Çözüm**: Retry mekanizması güçlendirilmeli

## 📊 Sistem Durumu

```
RAM: 1.9GB total, 1.7GB used, 89MB free, 275MB available
Swap: 0B
Servis Memory: ~350MB (peak 484MB)
Restart count: 9
```

## ✅ Önerilen Düzeltmeler

1. **Swap ekle** (2GB önerilir)
2. **Service memory limit ekle**
3. **State dosyasını optimize et**
4. **Retry mekanizması güçlendir**

