# NASDAQ Strategy Optimizer

NASDAQ hisseleri için özelleştirilmiş ATR + SuperTrend strateji optimizasyon sistemi. Yahoo Finance verisi kullanarak hisse senetleri üzerinde backtesting ve optimizasyon yapar.

## 🎯 Özellikler

- **NASDAQ Focus**: Yahoo Finance ile NASDAQ hisseleri için optimize edilmiş
- **ATR + SuperTrend**: Güçlü trend takip stratejisi
- **Heikin Ashi**: Smooth trend analizi
- **Volume Filtering**: Hacim bazlı filtreleme
- **EMA Confirmation**: EMA crossover onayı
- **Grid Search**: Parametre optimizasyonu
- **Walk-Forward Analysis**: Zaman bazlı analiz
- **Comprehensive Reporting**: Detaylı raporlama

## 📊 Desteklenen Semboller

### Technology Sector
- **AAPL** - Apple Inc. (50M vol)
- **AMD** - Advanced Micro Devices (40M vol)
- **MSFT** - Microsoft Corporation (25M vol)
- **GOOGL** - Alphabet Inc. (20M vol)
- **NVDA** - NVIDIA Corporation (35M vol)
- **META** - Meta Platforms Inc. (15M vol)
- **CRM** - Salesforce Inc. (5M vol)

### Consumer Discretionary
- **AMZN** - Amazon.com Inc. (30M vol)
- **TSLA** - Tesla Inc. (80M vol)

### Communication Services
- **NFLX** - Netflix Inc. (3M vol)

## 🚀 Hızlı Başlangıç

### 1. Kurulum

```bash
# Gerekli paketleri yükle
pip install pandas numpy yfinance typer pydantic

# NASDAQ Strategy Optimizer'ı çalıştır
cd nasdaq_strategy_optimizer
```

### 2. Mevcut Sembolleri Listele

```bash
python3 -m src.cli list-symbols --limit 10
```

### 3. Sektör Bazlı Semboller

```bash
# Technology sektörü
python3 -m src.cli list-symbols --sector Technology

# Yüksek hacimli semboller
python3 -m src.cli list-symbols --min-volume 20000000
```

### 4. NASDAQ Optimizasyonu

```bash
# Temel optimizasyon
python3 -m src.cli optimize-nasdaq --symbols "AAPL,AMD,NVDA" --timeframes "1d,1wk"

# Özel parametrelerle
python3 -m src.cli optimize-nasdaq --symbols "TSLA,MSFT" --timeframes "1d" --params-file nasdaq_params.json
```

## 📈 Strateji Parametreleri

### ATR Parameters
- **`a`**: ATR sensitivity (2, 3, 4, 5) - NASDAQ için konservatif
- **`c`**: ATR period (8, 10, 12, 14) - Kısa vadeli

### SuperTrend Parameters
- **`st_factor`**: SuperTrend multiplier (1.2, 1.5, 1.8, 2.0)

### EMA Confirmation
- **`use_ema_confirmation`**: EMA onayı (True/False)
- **`ema_fast_len`**: EMA Fast length (9, 12, 15)
- **`ema_slow_len`**: EMA Slow length (21, 26, 30)

### Volume Filtering
- **`volume_filter`**: Hacim filtreleme (True/False)
- **`min_volume_mult`**: Min hacim çarpanı (1.0, 1.5, 2.0)

### Risk Management
- **`atr_sl_mult`**: ATR stop loss çarpanı (1.5, 2.0, 2.5)
- **`atr_rr`**: Risk-reward oranı (1.5, 2.0, 3.0)

## 🎯 NASDAQ-Specific Features

### 1. Timeframe Optimization
NASDAQ için optimize edilmiş timeframe'ler:
- **1d**: Günlük analiz
- **1wk**: Haftalık analiz  
- **1mo**: Aylık analiz

### 2. Volume-Based Filtering
```python
# Yüksek hacimli semboller
high_volume_symbols = get_high_volume_symbols(min_volume=10000000)

# Sektör bazlı filtreleme
tech_symbols = get_symbols_by_sector("Technology")
```

### 3. Risk Management
NASDAQ hisseleri için özelleştirilmiş risk yönetimi:
- **Max Position Size**: %10 (varsayılan)
- **Stop Loss**: %5 (varsayılan)
- **Take Profit**: %15 (varsayılan)

## 📊 Örnek Kullanım

### Tek Sembol Testi
```bash
python3 -m src.cli test-strategy --symbol AAPL --timeframe 1d --params-string "a=3 c=10 st_factor=1.5"
```

### Sektör Optimizasyonu
```bash
python3 -m src.cli optimize-sector --sector Technology --timeframes "1d,1wk"
```

### Yüksek Hacim Optimizasyonu
```bash
python3 -m src.cli optimize-high-volume --min-volume 20000000 --timeframes "1d"
```

## 🔧 Konfigürasyon

### Environment Variables
```bash
export DATA_SOURCE="yahoo"
export DEFAULT_SYMBOLS="AAPL,AMD,NVDA,TSLA,MSFT"
export DEFAULT_TIMEFRAMES="1d,1wk,1mo"
export CACHE_DIR="./cache"
export CACHE_TTL_HOURS="24"
```

### Config Dosyası
`src/config.py` dosyasından parametreleri düzenleyebilirsin:

```python
# NASDAQ-specific parametreler
param_space = {
    "a": [2, 3, 4, 5],           # ATR sensitivity
    "c": [8, 10, 12, 14],        # ATR period
    "st_factor": [1.2, 1.5, 1.8, 2.0],  # SuperTrend multiplier
    "use_ema_confirmation": [True, False],
    "volume_filter": [True, False],
    "use_heikin_ashi": [True, False]
}
```

## 📈 Sonuçlar ve Raporlama

### Optimizasyon Sonuçları
```json
{
  "top_results": [
    {
      "symbol": "AAPL",
      "timeframe": "1d",
      "parameters": {"a": 3, "c": 10, "st_factor": 1.5},
      "total_return": 0.15,
      "sharpe_ratio": 1.2,
      "max_drawdown": -0.08,
      "win_rate": 0.65,
      "profit_factor": 1.8,
      "total_trades": 25
    }
  ]
}
```

### Performance Metrics
- **Total Return**: Toplam getiri
- **Sharpe Ratio**: Risk-ayarlı getiri
- **Max Drawdown**: Maksimum düşüş
- **Win Rate**: Kazanma oranı
- **Profit Factor**: Kar faktörü
- **Total Trades**: Toplam işlem sayısı

## 🎯 NASDAQ vs Crypto Farkları

| Özellik | NASDAQ | Crypto |
|---------|--------|--------|
| **Data Source** | Yahoo Finance | Binance API |
| **Timeframes** | 1d, 1wk, 1mo | 15m, 1h, 4h |
| **Parameters** | Konservatif | Agresif |
| **Volume Filter** | ✅ Aktif | ❌ Pasif |
| **Risk Management** | %5-15 | %1-5 |
| **Position Size** | %10 max | %100 max |

## 🚀 Gelişmiş Özellikler

### 1. Walk-Forward Analysis
```bash
python3 -m src.cli walk-forward --symbols "AAPL,AMD" --timeframes "1d" --train-days 90 --test-days 30
```

### 2. Custom Parameter Files
```json
{
  "a": [2, 3, 4],
  "c": [8, 10, 12],
  "st_factor": [1.2, 1.5],
  "use_ema_confirmation": [true],
  "volume_filter": [true]
}
```

### 3. Sector Analysis
```bash
# Technology sektörü analizi
python3 -m src.cli optimize-sector --sector Technology

# Healthcare sektörü analizi  
python3 -m src.cli optimize-sector --sector Healthcare
```

## 📊 Örnek Sonuçlar

### AAPL (1d timeframe)
- **Best Parameters**: a=3, c=10, st_factor=1.5
- **Total Return**: 15.2%
- **Sharpe Ratio**: 1.24
- **Max Drawdown**: -8.1%
- **Win Rate**: 65%

### AMD (1wk timeframe)
- **Best Parameters**: a=4, c=12, st_factor=1.8
- **Total Return**: 22.8%
- **Sharpe Ratio**: 1.45
- **Max Drawdown**: -12.3%
- **Win Rate**: 58%

## 🔍 Troubleshooting

### Common Issues

1. **Import Errors**: Module path sorunları
   ```bash
   python3 -m src.cli --help
   ```

2. **Data Issues**: Yahoo Finance API limitleri
   ```bash
   # Cache'i temizle
   rm -rf cache/*
   ```

3. **Memory Issues**: Büyük optimizasyonlar
   ```bash
   # Paralel job sayısını azalt
   python3 -m src.cli optimize-nasdaq --jobs 2
   ```

## 📚 API Reference

### NASDAQDataProvider
```python
from src.data.nasdaq_provider import NASDAQDataProvider

provider = NASDAQDataProvider()
symbols = provider.get_available_symbols()
data = provider.fetch_data("AAPL", period="2y", interval="1d")
```

### NASDAQATRSuperTrendStrategy
```python
from src.strategy.nasdaq_atr_supertrend import create_strategy

strategy = create_strategy({
    'a': 3,
    'c': 10, 
    'st_factor': 1.5,
    'use_ema_confirmation': True,
    'volume_filter': True
})

result = strategy.run_strategy(data)
```

## 🎯 Roadmap

- [ ] **Real-time Data**: Live data feed entegrasyonu
- [ ] **Portfolio Optimization**: Multi-symbol portfolio
- [ ] **Machine Learning**: ML-based parameter optimization
- [ ] **Web Interface**: Web-based dashboard
- [ ] **Alerts**: Real-time signal alerts
- [ ] **Backtesting Engine**: Advanced backtesting features

## 📄 License

MIT License - Free to use for personal and commercial projects.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## 📞 Support

For questions and support:
- Create GitHub Issue
- Check documentation
- Review examples

---

**NASDAQ Strategy Optimizer** - Professional-grade stock optimization for NASDAQ markets 🚀
