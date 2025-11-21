# Volensy MACD Trend Strategy Optimizer

Bu proje, Pine Script'te yazılmış Volensy MACD Trend strategy'sini Python'a çevirerek optimize etmek için geliştirilmiştir.

## 🚀 Özellikler

- **Pine Script'ten Python'a Çeviri**: Volensy MACD Trend strategy'si tamamen Python'a çevrilmiştir
- **Grid Search Optimizasyonu**: Parametrelerin otomatik optimizasyonu
- **Çoklu Coin Desteği**: BTC, ETH, SOL ve diğer coinler
- **Çoklu Timeframe**: 15m, 1h, 4h ve daha fazlası
- **Paralel İşlem**: Hızlı optimizasyon için paralel işlem desteği
- **Detaylı Raporlama**: CSV ve JSON formatında sonuçlar

## 📊 Strategy Detayları

### Pine Script Özellikleri
- **EMA Trend Filtresi**: Ana trend yönünü belirler
- **MACD Momentum**: Hızlı ve yavaş EMA'lar arasındaki fark
- **RSI Konfirmasyonu**: Aşırı alım/satım seviyeleri
- **Skor Sistemi**: 3 bileşenli skor sistemi (trend + momentum + güç)
- **Sinyal Filtreleme**: Yinelenen sinyalleri engeller

### Optimize Edilebilir Parametreler
- `ema_len`: EMA trend periyodu (20-40)
- `macd_fast`: MACD hızlı EMA (8-12)
- `macd_slow`: MACD yavaş EMA (21-26)
- `macd_signal`: MACD sinyal EMA (9)
- `rsi_len`: RSI periyodu (14)
- `rsi_ob`: RSI aşırı alım seviyesi (70)
- `rsi_os`: RSI aşırı satım seviyesi (30)
- `atr_len`: ATR periyodu (14)

## 🛠️ Kurulum

```bash
cd /Users/ahmet/ATR/strategy_optimizer
pip install -r requirements.txt
```

## 📈 Kullanım

### 1. Basit Optimizasyon
```bash
cd src
python3 cli.py optimize --strategy volensy_macd --coins BTC/USDT --timeframes 1h --param-string "ema_len=20,30 macd_fast=8,12 macd_slow=21,26 macd_signal=9 rsi_len=14 rsi_ob=70 rsi_os=30 atr_len=14"
```

### 2. Geniş Optimizasyon
```bash
python3 cli.py optimize --strategy volensy_macd --coins BTC/USDT,ETH/USDT,SOL/USDT --timeframes 15m,1h,4h --param-string "ema_len=20,30,40 macd_fast=8,12 macd_slow=21,26 macd_signal=9 rsi_len=14 rsi_ob=70 rsi_os=30 atr_len=14" --jobs 4 --parallel
```

### 3. Veri Çekme
```bash
python3 cli.py fetch --coins BTC/USDT,ETH/USDT,SOL/USDT --timeframes 15m,1h,4h --days 30
```

## 📊 Sonuçlar

### En İyi Performanslar (Örnek)
1. **SOL/USDT 4h**: PF: 4.50, Return: 2.48%, DD: -2.71%
2. **SOL/USDT 4h**: PF: 3.14, Return: 2.20%, DD: -2.73%
3. **ETH/USDT 15m**: PF: 2.79, Return: 1.20%, DD: -2.90%

### Sonuç Dosyaları
- `grid_search_results.json`: Tüm sonuçlar
- `grid_search_results.csv`: CSV formatında sonuçlar
- `grid_search_summary.json`: Özet istatistikler
- `grid_search_top_results.json`: En iyi sonuçlar

## 🔧 Gelişmiş Kullanım

### Özel Parametre Dosyası
```json
{
  "combinations": [
    {
      "ema_len": 20,
      "macd_fast": 8,
      "macd_slow": 21,
      "macd_signal": 9,
      "rsi_len": 14,
      "rsi_ob": 70,
      "rsi_os": 30,
      "atr_len": 14
    }
  ]
}
```

```bash
python3 cli.py optimize --strategy volensy_macd --coins BTC/USDT --timeframes 1h --params custom_params.json
```

### Walk-Forward Analizi
```bash
python3 cli.py walk-forward --strategy volensy_macd --coins BTC/USDT --timeframes 1h --scheme rolling --train-window 90d --test-window 30d
```

## 📁 Proje Yapısı

```
strategy_optimizer/
├── src/
│   ├── strategy/
│   │   ├── volensy_macd_trend.py    # Ana strategy
│   │   ├── atr_st_core.py           # ATR strategy (orijinal)
│   │   └── backtester.py            # Backtest motoru
│   ├── optimize/
│   │   ├── grid_search.py           # Grid search optimizasyonu
│   │   └── walk_forward.py          # Walk-forward analizi
│   ├── data/
│   │   ├── loader.py                # Veri yükleme
│   │   └── ccxt_client.py           # Exchange bağlantısı
│   └── cli.py                       # Komut satırı arayüzü
├── test_volensy_strategy.py         # Test dosyası
└── requirements.txt                  # Bağımlılıklar
```

## 🧪 Test

```bash
python3 test_volensy_strategy.py
```

## 📈 Performans Metrikleri

- **Profit Factor (PF)**: Kazanç/Kayıp oranı
- **Total Return**: Toplam getiri yüzdesi
- **Max Drawdown**: Maksimum düşüş yüzdesi
- **Num Trades**: Toplam işlem sayısı
- **Win Rate**: Kazanma oranı
- **Sharpe Ratio**: Risk-ayarlı getiri

## 🔍 Strategy Mantığı

### Sinyal Üretimi
1. **Trend Kontrolü**: Close > EMA (bullish trend)
2. **Momentum Kontrolü**: RSI > 50 (bullish momentum)
3. **Güç Kontrolü**: MACD > Signal (bullish power)
4. **Skor Sistemi**: 3/3 skor = AL sinyali
5. **Filtreleme**: RSI < 70 (aşırı alım değil)

### Risk Yönetimi
- **Stop Loss**: ATR tabanlı dinamik stop loss
- **Take Profit**: Sabit yüzde take profit
- **Position Sizing**: Sabit margin kullanımı
- **Commission**: %0.1 komisyon
- **Slippage**: %0.05 slippage

## 🚨 Önemli Notlar

1. **Backtest Sonuçları**: Geçmiş performans gelecek performansı garanti etmez
2. **Risk Yönetimi**: Her zaman stop loss kullanın
3. **Parametre Optimizasyonu**: Overfitting'e dikkat edin
4. **Walk-Forward**: Gerçek performans için walk-forward analizi yapın
5. **Live Trading**: Canlı trading öncesi paper trading yapın

## 📞 Destek

Herhangi bir sorun veya öneri için issue açabilirsiniz.

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.
