# Regression Channel Strategy Optimizer

## Açıklama

Volensy Regresyon Kanalları ve Volatilite Stratejisi için kripto optimizasyon aracı.

## Sorun

Orijinal Pine Script stratejisi kripto için hiç sinyal üretmiyordu. Bu optimizer:
- Parametreleri kripto piyasasına göre optimize eder
- Daha geniş bantlar test eder (crypto volatilitesi için)
- Trend filtresini opsiyonel yapar
- Volatilite osilatörü parametrelerini optimize eder

## Kullanım

### Temel Kullanım

```bash
cd strategy_optimizer
python optimize_regression_channel_crypto.py --symbol BTCUSDT --timeframe 15m
```

### Parametreler

- `--symbol`: Trading symbol (default: BTCUSDT)
- `--timeframe`: Timeframe (default: 15m)

### Örnekler

```bash
# BTC için optimize et
python optimize_regression_channel_crypto.py --symbol BTCUSDT --timeframe 15m

# ETH için optimize et
python optimize_regression_channel_crypto.py --symbol ETHUSDT --timeframe 15m

# 1 saatlik timeframe
python optimize_regression_channel_crypto.py --symbol BTCUSDT --timeframe 1h
```

## Optimize Edilen Parametreler

1. **Regresyon Kanalı**
   - `reg_len`: Regresyon periyodu (50-150)
   - `inner_mult`: İç bant çarpanı (0.8-1.2)
   - `outer_mult`: Dış bant çarpanı (1.0-2.0) - **Kripto için daha geniş**

2. **Trend Filtresi**
   - `sma_len`: SMA uzunluğu (10-26)
   - `use_trend_filter`: Trend filtresi kullan (True/False)

3. **Volatilite Osilatörü**
   - `stoch_len`: Stochastic periyodu (10-20)
   - `smooth_k`: K yumuşatma (2-5)
   - `smooth_d`: D yumuşatma (2-5)
   - `ob_level`: Aşırı alım seviyesi (70-85)
   - `os_level`: Aşırı satım seviyesi (15-30)

4. **Risk Yönetimi**
   - `tp_pct`: Take profit yüzdesi (0.5%-2.5%)
   - `sl_pct`: Stop loss yüzdesi (0.5%-2%)

## Çıktılar

1. **JSON Sonuçları**: `regression_channel_optimization_{SYMBOL}_{TIMESTAMP}.json`
   - Top 100 sonuç
   - Parametreler ve performans metrikleri

2. **Optimize Edilmiş Pine Script**: `regression_channel_optimized_{SYMBOL}_{TIMESTAMP}.pine`
   - TradingView'da kullanıma hazır
   - Optimize edilmiş parametrelerle

## Performans Metrikleri

- **Win Rate**: Kazanan işlem yüzdesi
- **Profit Factor**: Toplam kâr / Toplam zarar
- **Total Return**: Toplam getiri yüzdesi
- **Max Drawdown**: Maksimum düşüş yüzdesi
- **Risk/Reward**: Ortalama kâr / Ortalama zarar

## Öneriler

1. **İlk Optimizasyon**: Parametreleri geniş tutun, sonra daraltın
2. **Timeframe Seçimi**: 15m-1h arası kripto için ideal
3. **Sembol Seçimi**: BTC, ETH gibi likit coinler için daha iyi sonuçlar
4. **Backtest Süresi**: En az 180 gün veri kullanın

## Notlar

- Optimizasyon uzun sürebilir (binlerce kombinasyon test edilir)
- Sonuçlar geçmiş verilere dayanır, gelecek performansı garanti etmez
- Overfitting riski var - out-of-sample test yapın

