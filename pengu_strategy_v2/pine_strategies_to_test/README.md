# 🚀 Pine Editor Stratejilerini Test Et

## 📁 Klasör Hazır!

**`pine_strategies_to_test/`** klasörü oluşturuldu. Bu klasöre Pine Editor dosyalarını yükleyebilirsin.

## 🔧 Nasıl Çalışır?

1. **Pine Script dosyalarını yükle**: `.pine` uzantılı dosyaları `pine_strategies_to_test/` klasörüne kopyala
2. **Test çalıştır**: `python3 test_pine_strategies.py` komutunu çalıştır
3. **Sonuçları gör**: Tüm stratejiler sırasıyla test edilir ve en iyi sonuçlar gösterilir

## 📊 Test Edilen Parametreler:

- **ATR Sensitivity** (`a`)
- **ATR Period** (`c`) 
- **SuperTrend Factor** (`st_factor`)
- **Stop Loss %** (`stop_loss_pct`)
- **Take Profit %** (`take_profit_pct`)

## 🎯 Test Sonuçları:

- **Win Rate**: Kazanma oranı
- **Total Return**: Toplam getiri
- **Total Trades**: Toplam işlem sayısı
- **Signals Count**: Sinyal sayısı

## 📋 Örnek Pine Script Formatı:

```pinescript
//@version=5
strategy("My Strategy", shorttitle="MyStrat", overlay=true)

a = input.float(0.5, "ATR Sensitivity")
c = input.int(2, "ATR Period")
st_factor = input.float(0.4, "SuperTrend Factor")
stop_loss_pct = input.float(0.5, "Stop Loss %")
take_profit_pct = input.float(1.0, "Take Profit %")

// Strateji kodu...
```

## 🏆 En İyi Sonuçlar:

Test tamamlandıktan sonra en iyi 5 strateji gösterilir ve en iyi strateji önerilir.

---

**Hazır! Pine Script dosyalarını `pine_strategies_to_test/` klasörüne yükle ve test et!** 🚀
