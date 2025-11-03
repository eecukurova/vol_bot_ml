#!/usr/bin/env python3
"""
PENGU - Comprehensive Indicator Testing
Test ALL possible indicators to find working strategy
"""

import ccxt
import pandas as pd
import numpy as np

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    """Stochastic Oscillator"""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    d_percent = k_percent.rolling(window=d_period).mean()
    return k_percent, d_percent

def calculate_williams_r(high, low, close, period=14):
    """Williams %R"""
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    wr = -100 * ((highest_high - close) / (highest_high - lowest_low))
    return wr

def calculate_adx(high, low, close, period=14):
    """ADX - Average Directional Index"""
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr_list = [
        high - low,
        abs(high - close.shift()),
        abs(low - close.shift())
    ]
    tr = pd.concat(tr_list, axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx, plus_di, minus_di

def calculate_momentum(prices, period=10):
    """Momentum"""
    return prices.diff(period)

def calculate_roc(prices, period=12):
    """Rate of Change"""
    return ((prices - prices.shift(period)) / prices.shift(period)) * 100

def backtest_indicator(df, name, signals):
    """Backtest any indicator strategy"""
    if not signals or sum(signals) == 0:
        return None
    
    in_position = False
    entry_price = 0
    trades = []
    balance = 10000.0
    
    for i in range(len(signals)):
        if signals[i] == 1 and not in_position:
            in_position = True
            entry_price = df['close'].iloc[i]
        elif signals[i] == -1 and in_position:
            exit_price = df['close'].iloc[i]
            pnl = (exit_price - entry_price) / entry_price
            
            # Apply TP/SL
            if pnl >= 0.01:
                pnl = 0.01
            elif pnl <= -0.02:
                pnl = -0.02
            
            trades.append({'pnl': pnl})
            balance += balance * pnl
            in_position = False
    
    if not trades or balance < 0:
        return None
    
    total_return = ((balance - 10000) / 10000) * 100
    win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades) * 100
    
    return {
        'name': name,
        'trades': len(trades),
        'win_rate': win_rate,
        'total_return': total_return,
        'balance': balance
    }

def main():
    print('🎯 PENGU - ALL INDICATORS COMPREHENSIVE TEST')
    print('='*80)
    
    # Fetch data
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=2000)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    print(f'✅ {len(df)} candles')
    print(f'📅 {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
    print()
    
    results = []
    
    # 1. Bollinger Bands
    upper, middle, lower = calculate_bollinger_bands(df['close'], 20)
    bb_signals = [0] * len(df)
    for i in range(1, len(df)):
        if df['close'].iloc[i-1] <= lower.iloc[i-1] and df['close'].iloc[i] > lower.iloc[i]:
            bb_signals[i] = 1
        elif df['close'].iloc[i-1] >= upper.iloc[i-1] and df['close'].iloc[i] < upper.iloc[i]:
            bb_signals[i] = -1
    result = backtest_indicator(df, 'Bollinger Bands', bb_signals)
    if result:
        results.append(result)
    
    # 2. Stochastic
    k, d = calculate_stochastic(df['high'], df['low'], df['close'], 14)
    stoch_signals = [0] * len(df)
    for i in range(1, len(df)):
        if k.iloc[i-1] <= 20 and k.iloc[i] > 20:
            stoch_signals[i] = 1
        elif k.iloc[i-1] >= 80 and k.iloc[i] < 80:
            stoch_signals[i] = -1
    result = backtest_indicator(df, 'Stochastic 14', stoch_signals)
    if result:
        results.append(result)
    
    # 3. Williams %R
    wr = calculate_williams_r(df['high'], df['low'], df['close'], 14)
    wr_signals = [0] * len(df)
    for i in range(1, len(df)):
        if wr.iloc[i-1] <= -80 and wr.iloc[i] > -80:
            wr_signals[i] = 1
        elif wr.iloc[i-1] >= -20 and wr.iloc[i] < -20:
            wr_signals[i] = -1
    result = backtest_indicator(df, 'Williams %R', wr_signals)
    if result:
        results.append(result)
    
    # 4. ADX + DI
    adx, plus_di, minus_di = calculate_adx(df['high'], df['low'], df['close'], 14)
    adx_signals = [0] * len(df)
    for i in range(1, len(df)):
        if adx.iloc[i] > 25 and plus_di.iloc[i] > minus_di.iloc[i]:
            adx_signals[i] = 1
        elif adx.iloc[i] > 25 and minus_di.iloc[i] > plus_di.iloc[i]:
            adx_signals[i] = -1
    result = backtest_indicator(df, 'ADX + DI', adx_signals)
    if result:
        results.append(result)
    
    # 5. Momentum
    momentum = calculate_momentum(df['close'], 10)
    mom_signals = [0] * len(df)
    for i in range(1, len(df)):
        if momentum.iloc[i-1] <= 0 and momentum.iloc[i] > 0:
            mom_signals[i] = 1
        elif momentum.iloc[i-1] >= 0 and momentum.iloc[i] < 0:
            mom_signals[i] = -1
    result = backtest_indicator(df, 'Momentum', mom_signals)
    if result:
        results.append(result)
    
    # 6. ROC (Rate of Change)
    roc = calculate_roc(df['close'], 12)
    roc_signals = [0] * len(df)
    for i in range(1, len(df)):
        if roc.iloc[i-1] <= -5 and roc.iloc[i] > -5:
            roc_signals[i] = 1
        elif roc.iloc[i-1] >= 5 and roc.iloc[i] < 5:
            roc_signals[i] = -1
    result = backtest_indicator(df, 'ROC', roc_signals)
    if result:
        results.append(result)
    
    # 7. BB Squeeze
    bb_width = (upper - lower) / middle
    bb_narrow = bb_width < bb_width.rolling(window=20).quantile(0.25)
    squeeze_signals = [0] * len(df)
    for i in range(1, len(df)):
        if bb_narrow.iloc[i] and df['close'].iloc[i] > middle.iloc[i]:
            squeeze_signals[i] = 1
        elif bb_narrow.iloc[i] and df['close'].iloc[i] < middle.iloc[i]:
            squeeze_signals[i] = -1
    result = backtest_indicator(df, 'BB Squeeze', squeeze_signals)
    if result:
        results.append(result)
    
    # Display results
    if results:
        results.sort(key=lambda x: x['total_return'], reverse=True)
        
        print('🏆 TOP INDICATORS:')
        print('='*80)
        
        for i, r in enumerate(results[:15], 1):
            print(f'{i:2d}. {r["name"]:20s} | Trades={r["trades"]:3d} | '
                  f'WR={r["win_rate"]:5.1f}% | Return={r["total_return"]:6.2f}% | '
                  f'Balance=${r["balance"]:.2f}')
    else:
        print('❌ No profitable indicators found')
    
    print()
    print('✅ Test completed!')
    print()
    if results and results[0]['total_return'] > 0:
        print(f'🏆 WINNER: {results[0]["name"]} with {results[0]["total_return"]:.2f}% return')

if __name__ == "__main__":
    main()

