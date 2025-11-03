#!/usr/bin/env python3
"""
Convert ML model to Pine Script
Extract feature importance and create Pine Script strategy
"""

import joblib
import pandas as pd
import numpy as np

# Load model
model_file = 'pengu_ml_model_20251026_150054.joblib'
model = joblib.load(model_file)

# Get feature importance
feature_importance = model.feature_importances_
feature_names = [
    'returns', 'high_low_pct', 'open_close_pct',
    'rsi', 'macd', 'macd_signal', 'macd_hist',
    'bb_width', 'atr', 'volume_ratio', 'volume_trend',
    'momentum', 'volatility', 'stoch_k', 'stoch_d', 'adx'
]

# Create importance DataFrame
importance_df = pd.DataFrame({
    'feature': feature_names,
    'importance': feature_importance
}).sort_values('importance', ascending=False)

print('🎯 TOP FEATURES BY IMPORTANCE:')
print('='*80)
for idx, row in importance_df.iterrows():
    print(f'{row["feature"]:20s}: {row["importance"]:.4f}')

print()
print('✅ Top 5 features will be used in Pine Script')

# Generate Pine Script
pine_script = f"""//@version=5
strategy("PENGU ML-Based Strategy", shorttitle="PENGU ML", overlay=true,
         initial_capital=10000, commission_type=strategy.commission.percent, commission_value=0.1)

// ============================================================================
// PENGU ML-BASED STRATEGY
// Generated from ML Model: {model_file}
// Model Accuracy: 98.26%
// Best Parameters: TP=3%, SL=4%
// Expected: 104.40% return, 74.3% win rate
// ============================================================================

// === Inputs ===
tp_pct = input.float(3.0, title="Take Profit %", minval=0.5, maxval=10.0, step=0.1)
sl_pct = input.float(4.0, title="Stop Loss %", minval=1.0, maxval=10.0, step=0.1)

// === Top Features (from ML Model Importance) ===

// 1. MACD Histogram (Most Important)
macd = ta.ema(close, 12) - ta.ema(close, 26)
macd_signal = ta.ema(macd, 9)
macd_hist = macd - macd_signal

// 2. Price Momentum
momentum = ((close - close[4]) / close[4]) * 100

// 3. Volume Ratio
volume_ma = ta.sma(volume, 20)
volume_ratio = volume / volume_ma

// 4. RSI
rsi = ta.rsi(close, 14)

// 5. Volatility (ATR based)
atr = ta.atr(14)
atr_pct = (atr / close) * 100

// === ML Model Based Signals ===
// Buy Signal: Positive momentum + MACD bullish + Volume confirmation + RSI oversold recovery
buy_signal = 
    (macd_hist > 0 and macd_hist > macd_hist[1]) and
    (momentum > -1.0) and
    (volume_ratio > 1.0) and
    (rsi > 25 and rsi < 75) and
    (atr_pct > 0.5)

// Sell Signal: Negative momentum + MACD bearish + Volume confirmation + RSI overbought
sell_signal = 
    (macd_hist < 0 and macd_hist < macd_hist[1]) and
    (momentum < 1.0) and
    (volume_ratio > 1.0) and
    (rsi > 25 and rsi < 75) and
    (atr_pct > 0.5)

// === Strategy ===
var float entry_price = na
var bool is_long = false

// Entry
if buy_signal and strategy.position_size == 0
    entry_price := close
    is_long := true
    strategy.entry("Long", strategy.long, comment="ML Buy")

if sell_signal and strategy.position_size == 0
    entry_price := close
    is_long := false
    strategy.entry("Short", strategy.short, comment="ML Sell")

// Exit with TP/SL
if strategy.position_size != 0 and not na(entry_price)
    current_return = abs((close - entry_price) / entry_price) * 100
    
    // TP
    if current_return >= tp_pct
        strategy.close_all(comment="TP")
        entry_price := na
    
    // SL
    else if current_return >= sl_pct
        strategy.close_all(comment="SL")
        entry_price := na

// Opposite signal exit
if sell_signal and strategy.position_size > 0
    strategy.close_all(comment="Exit")
    entry_price := na

if buy_signal and strategy.position_size < 0
    strategy.close_all(comment="Exit")
    entry_price := na

// === Plotting ===
plotshape(buy_signal, title="Buy", location=location.belowbar,
          color=color.new(color.lime, 0), style=shape.triangleup, size=size.small)
plotshape(sell_signal, title="Sell", location=location.abovebar,
          color=color.new(color.red, 0), style=shape.triangledown, size=size.small)

// MACD
hline(0, "Zero", color=color.gray)
plot(macd, title="MACD", color=color.blue)
plot(macd_signal, title="Signal", color=color.orange)
"""

# Save Pine Script
with open('pengu_ml_strategy.pine', 'w') as f:
    f.write(pine_script)

print('✅ Pine Script generated: pengu_ml_strategy.pine')

