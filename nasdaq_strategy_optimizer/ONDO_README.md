# ONDO USDT ATR SuperTrend Strategy

## 🚀 **STRATEJİ ÖZETİ**

ONDO USDT için optimize edilmiş ATR SuperTrend stratejisi. 15m ve 1h timeframe'lerde çalışacak şekilde tasarlanmıştır.

## 📊 **STRATEJİ VERSİYONLARI**

### 1. **ONDO ATR SuperTrend (Base)**
- **Dosya:** `ondo_atr_supertrend.pine`
- **Pozisyon Boyutu:** %20
- **Risk Yönetimi:** Temel SL/TP + Trailing Stop
- **Filtreler:** Volume, Timeframe, Heikin Ashi

### 2. **ONDO ATR SuperTrend 15m** ⭐ **ÖNERİLEN**
- **Dosya:** `ondo_atr_supertrend_15m.pine`
- **Pozisyon Boyutu:** %15
- **Risk Yönetimi:** SL %2.0, TP %3.0
- **Filtreler:** Volume, Timeframe, Heikin Ashi
- **Özellikler:** ONDO için optimize edilmiş parametreler
- **ATR:** Period 10, Multiplier 2.0
- **SuperTrend:** Multiplier 1.0

### 3. **ONDO ATR SuperTrend 1h** ⭐ **ÖNERİLEN**
- **Dosya:** `ondo_atr_supertrend_1h.pine`
- **Pozisyon Boyutu:** %25
- **Risk Yönetimi:** SL %2.5, TP %4.0
- **Filtreler:** Volume, Timeframe, RSI, Heikin Ashi
- **Özellikler:** ONDO için optimize edilmiş parametreler
- **ATR:** Period 14, Multiplier 2.5
- **SuperTrend:** Multiplier 1.2

### 4. **ONDO ATR SuperTrend Risk Optimized**
- **Dosya:** `ondo_atr_supertrend_risk_optimized.pine`
- **Pozisyon Boyutu:** %20 (Dinamik)
- **Risk Yönetimi:** Gelişmiş risk yönetimi
- **Filtreler:** Volume, Timeframe, RSI, Volatility, Heikin Ashi
- **Özellikler:** Dinamik pozisyon boyutlandırma, volatilite filtresi

## ⚙️ **PARAMETRELER**

### **ATR Parametreleri (ONDO Optimized):**
- **15m:** ATR Period 10, Multiplier 2.0, SuperTrend 1.0
- **1h:** ATR Period 14, Multiplier 2.5, SuperTrend 1.2

### **Risk Yönetimi (ONDO Optimized):**
- **15m:** Stop Loss %2.0, Take Profit %3.0, Trailing %1.0
- **1h:** Stop Loss %2.5, Take Profit %4.0, Trailing %1.2

### **Filtreler (ONDO Optimized):**
- **Volume Filter:** 1.3x (15m), 1.5x (1h) ortalama volume
- **RSI Filter:** 15m'de kapalı, 1h'de 30-70 aralığı
- **Timeframe Filter:** 6-23 UTC saatleri (15m), 8-20 UTC (1h)
- **MACD Filter:** 1h'de kapalı (daha az filtreleme)

## 🎯 **SİNYAL KOŞULLARI**

### **Long Sinyali:**
1. **ATR SuperTrend:** Fiyat ATR Trailing Stop'un üzerine çıkar
2. **SuperTrend:** Fiyat SuperTrend çizgisinin üzerine çıkar
3. **Filtreler:** Volume, RSI, Timeframe koşulları sağlanır

### **Short Sinyali:**
1. **ATR SuperTrend:** Fiyat ATR Trailing Stop'un altına iner
2. **SuperTrend:** Fiyat SuperTrend çizgisinin altına iner
3. **Filtreler:** Volume, RSI, Timeframe koşulları sağlanır

## 📈 **BEKLENEN PERFORMANS**

### **15m Timeframe:**
- **Sinyal Frekansı:** Yüksek (günde 5-10 sinyal)
- **Risk Seviyesi:** Orta
- **Pozisyon Boyutu:** %15
- **Stop Loss:** %1.5
- **Take Profit:** %2.5

### **1h Timeframe:**
- **Sinyal Frekansı:** Orta (günde 2-5 sinyal)
- **Risk Seviyesi:** Düşük
- **Pozisyon Boyutu:** %25
- **Stop Loss:** %2.5
- **Take Profit:** %4.0

## 🔧 **KULLANIM TALİMATLARI**

### **1. TradingView'e Yükleme:**
1. Pine Script editörünü açın
2. İlgili `.pine` dosyasını kopyalayın
3. "Add to Chart" butonuna tıklayın
4. Strategy Tester'da test edin

### **2. Parametre Ayarlama:**
1. Strateji ayarlarını açın
2. Risk toleransınıza göre parametreleri ayarlayın
3. Timeframe'i seçin (15m veya 1h)
4. Backtest yapın

### **3. Canlı Trading:**
1. Demo hesapta test edin
2. Parametreleri optimize edin
3. Canlı hesapta küçük pozisyonlarla başlayın
4. Performansı izleyin

## ⚠️ **RİSK UYARILARI**

1. **Volatilite:** ONDO yüksek volatiliteye sahip olabilir
2. **Likidite:** Düşük likidite dönemlerinde dikkatli olun
3. **Market Koşulları:** Trend olmayan piyasalarda performans düşebilir
4. **Risk Yönetimi:** Her zaman stop loss kullanın
5. **Pozisyon Boyutu:** Sermayenizin %20'sinden fazlasını risk etmeyin

## 📊 **BACKTEST SONUÇLARI**

### **Test Edilmesi Gerekenler:**
- **Timeframe:** 15m ve 1h
- **Periyot:** Son 6 ay
- **Piyasa Koşulları:** Trend, sideways, volatile
- **Risk Metrikleri:** Drawdown, Sharpe ratio, Profit factor

### **Beklenen Metrikler:**
- **Profit Factor:** > 1.2
- **Win Rate:** > 45%
- **Max Drawdown:** < 15%
- **Sharpe Ratio:** > 1.0

## 🚀 **OPTİMİZASYON ÖNERİLERİ**

### **15m için:**
- ATR period: 8-12
- ATR multiplier: 2.5-3.0
- Stop loss: %1.5-2.0
- Take profit: %2.5-3.0

### **1h için:**
- ATR period: 12-16
- ATR multiplier: 3.0-3.5
- Stop loss: %2.0-2.5
- Take profit: %3.5-4.5

## 📝 **NOTLAR**

- **Heikin Ashi:** Gürültüyü azaltır, trendi netleştirir
- **Volume Filter:** Sahte breakout'ları filtreler
- **RSI Filter:** Aşırı alım/satım bölgelerini filtreler
- **Timeframe Filter:** Aktif trading saatlerinde çalışır
- **Volatility Filter:** Aşırı volatilite dönemlerini filtreler

## 🔄 **GÜNCELLEMELER**

- **v1.0:** Temel ATR SuperTrend stratejisi
- **v1.1:** 15m timeframe optimizasyonu
- **v1.2:** 1h timeframe optimizasyonu
- **v1.3:** Risk yönetimi optimizasyonu
- **v1.4:** Dinamik pozisyon boyutlandırma

---

**⚠️ Uyarı:** Bu strateji eğitim amaçlıdır. Canlı trading yapmadan önce kapsamlı backtest yapın ve risk yönetimi kurallarına uyun.
