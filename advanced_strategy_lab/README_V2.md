# Advanced Strategy Lab - PENGU Strategy V2 Yaklaşımı

## 🎯 Proje Hedefi

V2'de farklı yaklaşım: **PEMBDU için hibrit multi-timeframe strategy**

### Önceki Projede (V1)
- Tek indikatör bazlı stratejiler
- CCI: +25.99%
- Head & Shoulders: +32%
- Heikin Ashi Hybrid: +7.72%

### V2'de Değişiklikler

#### 1. **Multi-Timeframe Analysis**
- 5dk: Entry signals
- 1h: Trend confirmation
- 4h: Overall direction

#### 2. **Dynamic Position Sizing**
- Volatilite bazlı position size
- ATR bazlı risk calculation
- Kelly Criterion

#### 3. **Machine Learning Features**
- RSI divergence detection
- Volume profile analysis
- Support/Resistance breakout confirmation

#### 4. **Risk Management**
- Trailing stop
- Partial profit taking
- Adaptive TP/SL based on volatility

## 📁 Dosya Yapısı

```
advanced_strategy_lab/
├── README_V2.md (bu dosya)
├── pengu_multi_timeframe.pine
├── pengu_ml_features.py
├── pengu_dynamic_risk.py
├── pengu_backtest_comprehensive.py
└── results/
```

## 🚀 Yaklaşımlar

### A. Multi-Timeframe Strategy
```pine
// 4h: Trend
// 1h: Entry timing
// 5m: Precise entry
```

### B. Volume + Price Action
```pine
// Volume spikes + RSI
// Breakout confirmation
// False signal filtering
```

### C. Adaptive Parameters
```pine
// ATR-based TP/SL
// Volatility-adjusted position size
// Market regime detection
```

### D. Divergence Trading
```pine
// RSI divergence
// MACD divergence
// Volume divergence
```

## 🎯 Başlangıç

Şimdi bu yaklaşımları tek tek test edeceğiz!

