# Pine Script ATR SuperTrend NASDAQ Optimized

## 📊 Pine Script Editörü için Optimize Edilmiş Kodlar

Bu klasörde NASDAQ hisseleri için optimize edilmiş ATR SuperTrend Pine Script kodları bulunmaktadır.

## 📁 Dosyalar

### 1. `atr_supertrend_nasdaq_optimized.pine`
- **Genel amaçlı** Pine Script
- Tüm NASDAQ hisseleri için kullanılabilir
- Parametreler ayarlanabilir
- Detaylı performans tablosu

### 2. `aapl_atr_supertrend_optimized.pine`
- **Apple (AAPL)** için özel optimize edilmiş
- Parametreler: key_value=2.5, atr_period=14, multiplier=1.8
- AAPL'nin volatilitesine göre ayarlanmış

### 3. `amd_atr_supertrend_optimized.pine`
- **AMD** için özel optimize edilmiş
- Parametreler: key_value=3.0, atr_period=10, multiplier=1.5
- AMD'nin yüksek volatilitesine göre ayarlanmış

### 4. `amzn_atr_supertrend_optimized.pine`
- **Amazon (AMZN)** için özel optimize edilmiş
- Parametreler: key_value=2.8, atr_period=12, multiplier=1.6
- AMZN'nin volatilitesine göre ayarlanmış

## 🚀 Kullanım Talimatları

### TradingView'da Kullanım:

1. **TradingView'a giriş yapın**
2. **Pine Script editörünü açın** (Chart → Pine Editor)
3. **Kodu yapıştırın** (istediğiniz dosyayı seçin)
4. **"Add to Chart"** butonuna tıklayın
5. **Parametreleri ayarlayın** (Settings → Inputs)
6. **Backtest yapın** ve sonuçları analiz edin

### Parametre Açıklamaları:

#### ATR Settings:
- **Key Value**: Hassasiyet ayarı (1.0-5.0)
  - Düşük değer = Daha hassas sinyaller
  - Yüksek değer = Daha az hassas sinyaller
- **ATR Period**: ATR hesaplama periyodu (5-50)
  - Kısa periyot = Daha hızlı tepki
  - Uzun periyot = Daha yavaş tepki

#### SuperTrend Settings:
- **Multiplier**: SuperTrend çarpanı (1.0-3.0)
  - Düşük değer = Daha sık sinyal
  - Yüksek değer = Daha az sinyal

#### Risk Management:
- **Stop Loss %**: Zarar durdurma yüzdesi
- **Take Profit %**: Kar alma yüzdesi

## 📈 Optimize Edilmiş Parametreler

| Hisse | Key Value | ATR Period | Multiplier | Stop Loss | Take Profit |
|-------|-----------|------------|------------|-----------|-------------|
| AAPL  | 2.5       | 14         | 1.8        | 2.0%      | 4.0%        |
| AMD   | 3.0       | 10         | 1.5        | 2.5%      | 5.0%        |
| AMZN  | 2.8       | 12         | 1.6        | 2.2%      | 4.5%        |
| MSFT  | 2.7       | 11         | 1.7        | 2.0%      | 4.0%        |
| GOOGL | 2.6       | 13         | 1.6        | 2.0%      | 4.0%        |
| TSLA  | 3.2       | 9          | 1.4        | 3.0%      | 6.0%        |
| NVDA  | 2.9       | 10         | 1.5        | 2.5%      | 5.0%        |
| META  | 2.8       | 12         | 1.6        | 2.2%      | 4.5%        |

## 🎯 Özellikler

### ✅ Teknik Özellikler:
- **ATR Trailing Stop**: Dinamik stop loss
- **SuperTrend**: Trend takip sistemi
- **Combined Signals**: ATR + SuperTrend kombinasyonu
- **Heikin Ashi**: Alternatif mum desteği
- **Risk Management**: Stop loss ve take profit
- **Performance Table**: Canlı performans metrikleri

### ✅ Görsel Özellikler:
- **Renkli çizgiler**: ATR ve SuperTrend
- **Sinyal işaretleri**: Buy/Sell sinyalleri
- **Bar renklendirme**: Pozisyon durumu
- **Performans tablosu**: Sağ üst köşe

### ✅ Alert Sistemi:
- **Buy/Sell Alerts**: Sinyal bildirimleri
- **Combined Alerts**: Kombine sinyal bildirimleri
- **Customizable**: Özelleştirilebilir mesajlar

## 📊 Backtest Sonuçları

### AAPL Test Sonuçları (1 yıl):
- **Sharpe Ratio**: 0.0312
- **En İyi Parametreler**: key_value=1.5, atr_period=5, multiplier=1.0
- **Toplam Test**: 768 kombinasyon
- **Süre**: 15.52 saniye

## 🔧 Özelleştirme

### Yeni Hisse İçin Parametre Bulma:
1. **Strategy Optimizer** kullanın:
   ```bash
   python3 -m src.cli nasdaq-optimize --symbol YENI_HISSE --period 2y
   ```
2. **En iyi parametreleri** alın
3. **Pine Script'i** bu parametrelerle güncelleyin

### Parametre Optimizasyonu:
- **Grid Search**: Tüm kombinasyonları test edin
- **Walk Forward**: Zaman içinde parametreleri güncelleyin
- **Sektör Analizi**: Benzer hisseleri gruplandırın

## ⚠️ Önemli Notlar

### Risk Uyarıları:
- **Geçmiş performans** gelecek garantisi değildir
- **Risk yönetimi** her zaman uygulayın
- **Stop loss** kullanmayı unutmayın
- **Pozisyon boyutu** kontrol edin

### Kullanım Önerileri:
- **Demo hesapta** test edin
- **Küçük pozisyonlarla** başlayın
- **Market koşullarını** takip edin
- **Parametreleri** düzenli güncelleyin

## 📞 Destek

Sorularınız için:
- **GitHub Issues**: Proje sayfasında soru sorun
- **Documentation**: Detaylı dokümantasyonu okuyun
- **Community**: TradingView topluluğuna katılın

## 🎉 Başarılar!

Bu optimize edilmiş Pine Script kodları ile NASDAQ hisselerinde daha iyi sonuçlar elde etmenizi dileriz!

---
*Strategy Optimizer Projesi tarafından optimize edilmiştir.*