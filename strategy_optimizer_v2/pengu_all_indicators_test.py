#!/usr/bin/env python3
"""
PENGU - Comprehensive Indicator Tester
Test ALL popular financial indicators to find the best strategy for PENGU
Rules: Frequent, Profitable, Safe
"""

import ccxt
import pandas as pd
import numpy as np

def calculate_heikin_ashi(df):
    """Calculate Heikin Ashi"""
    df = df.copy()
    df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    df['ha_open'] = df['ha_close'].copy()
    
    for i in range(1, len(df)):
        df.loc[df.index[i], 'ha_open'] = (df['ha_open'].iloc[i-1] + df['ha_close'].iloc[i-1]) / 2
    
    df['ha_high'] = df[['high', 'ha_open', 'ha_close']].max(axis=1)
    df['ha_low'] = df[['low', 'ha_open', 'ha_close']].min(axis=1)
    
    return df

def calculate_sma(prices, period):
    """Simple Moving Average"""
    return prices.rolling(window=period).mean()

def calculate_ema(prices, period):
    """Exponential Moving Average"""
    return prices.ewm(span=period, adjust=False).mean()

def calculate_wma(prices, period):
    """Weighted Moving Average"""
    weights = np.arange(1, period + 1)
    def wma_func(x):
        return np.dot(x, weights) / weights.sum()
    return prices.rolling(window=period).apply(wma_func, raw=True)

def calculate_rsi(prices, period=14):
    """Relative Strength Index"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_stoch(high, low, close, k_period=14, d_period=3):
    """Stochastic Oscillator"""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    d_percent = k_percent.rolling(window=d_period).mean()
    return k_percent, d_percent

def calculate_cci(high, low, close, period=20):
    """Commodity Channel Index"""
    tp = (high + low + close) / 3  # Typical Price
    sma = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
    cci = (tp - sma) / (0.015 * mad)
    return cci

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """MACD"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_adx(high, low, close, period=14):
    """Average Directional Index"""
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr = pd.concat([
        high - low,
        abs(high - close.shift()),
        abs(low - close.shift())
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx, plus_di, minus_di

def calculate_bb(prices, period=20, std_dev=2):
    """Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_momentum(prices, period=10):
    """Momentum Oscillator"""
    return prices.diff(period)

def calculate_roc(prices, period=12):
    """Rate of Change"""
    return ((prices - prices.shift(period)) / prices.shift(period)) * 100

def calculate_williams_r(high, low, close, period=14):
    """Williams %R"""
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    wr = -100 * ((highest_high - close) / (highest_high - lowest_low))
    return wr

def backtest_strategy(df, signals, name, tp=0.01, sl=0.02):
    """Backtest any strategy with TP/SL"""
    position = None
    trades = []
    balance = 10000.0
    
    for i in range(len(signals)):
        signal = signals[i]
        
        if signal == 1 and position is None:  # Buy signal
            position = {'entry_idx': i, 'entry_price': df['close'].iloc[i]}
            
        elif signal == -1 and position is not None:  # Sell signal
            exit_price = df['close'].iloc[i]
            pnl_pct = (exit_price - position['entry_price']) / position['entry_price']
            
            # Apply TP/SL
            if pnl_pct >= tp:
                pnl_pct = tp
            elif pnl_pct <= -sl:
                pnl_pct = -sl
            
            trades.append({
                'entry': position['entry_idx'],
                'exit': i,
                'pnl': pnl_pct,
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'name': name
            })
            
            balance += balance * pnl_pct
            position = None
    
    if not trades:
        return None
    
    profitable = [t for t in trades if t['pnl'] > 0]
    total_return = sum(t['pnl'] for t in trades)
    win_rate = len(profitable) / len(trades) * 100
    avg_return = total_return / len(trades)
    
    # Calculate max drawdown
    equity = [10000.0]
    for trade in trades:
        equity.append(equity[-1] * (1 + trade['pnl']))
    
    peak = equity[0]
    max_dd = 0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak
        if dd > max_dd:
            max_dd = dd
    
    return {
        'name': name,
        'trades': len(trades),
        'win_rate': win_rate,
        'total_return': total_return * 100,
        'avg_return': avg_return,
        'profitable': len(profitable),
        'balance': balance,
        'max_drawdown': max_dd * 100
    }

def generate_signals_from_indicator(df, indicator_name, params):
    """Generate buy/sell signals from various indicators"""
    signals = [0] * len(df)
    
    if 'sma' in indicator_name.lower():
        period = params.get('period', 20)
        sma = calculate_sma(df['close'], period)
        df[f'{indicator_name}'] = sma
        
        for i in range(1, len(df)):
            if not pd.isna(sma.iloc[i]) and not pd.isna(sma.iloc[i-1]):
                if df['close'].iloc[i-1] <= sma.iloc[i-1] and df['close'].iloc[i] > sma.iloc[i]:
                    signals[i] = 1  # Buy
                elif df['close'].iloc[i-1] >= sma.iloc[i-1] and df['close'].iloc[i] < sma.iloc[i]:
                    signals[i] = -1  # Sell
    
    elif 'ema' in indicator_name.lower():
        period = params.get('period', 20)
        ema = calculate_ema(df['close'], period)
        
        for i in range(1, len(df)):
            if not pd.isna(ema.iloc[i]) and not pd.isna(ema.iloc[i-1]):
                if df['close'].iloc[i-1] <= ema.iloc[i-1] and df['close'].iloc[i] > ema.iloc[i]:
                    signals[i] = 1
                elif df['close'].iloc[i-1] >= ema.iloc[i-1] and df['close'].iloc[i] < ema.iloc[i]:
                    signals[i] = -1
    
    elif 'rsi' in indicator_name.lower():
        period = params.get('period', 14)
        rsi = calculate_rsi(df['close'], period)
        overbought = params.get('overbought', 70)
        oversold = params.get('oversold', 30)
        
        for i in range(1, len(df)):
            if not pd.isna(rsi.iloc[i]) and not pd.isna(rsi.iloc[i-1]):
                if rsi.iloc[i-1] <= oversold and rsi.iloc[i] > oversold:
                    signals[i] = 1
                elif rsi.iloc[i-1] >= overbought and rsi.iloc[i] < overbought:
                    signals[i] = -1
    
    elif 'macd' in indicator_name.lower():
        fast = params.get('fast', 12)
        slow = params.get('slow', 26)
        signal_period = params.get('signal', 9)
        
        macd, signal_line, histogram = calculate_macd(df['close'], fast, slow, signal_period)
        
        for i in range(1, len(df)):
            if not pd.isna(histogram.iloc[i]) and not pd.isna(histogram.iloc[i-1]):
                if histogram.iloc[i-1] <= 0 and histogram.iloc[i] > 0:
                    signals[i] = 1  # MACD crossover
                elif histogram.iloc[i-1] >= 0 and histogram.iloc[i] < 0:
                    signals[i] = -1
    
    elif 'stoch' in indicator_name.lower():
        k_period = params.get('k_period', 14)
        d_period = params.get('d_period', 3)
        
        k, d = calculate_stoch(df['high'], df['low'], df['close'], k_period, d_period)
        
        for i in range(1, len(df)):
            if not pd.isna(k.iloc[i]) and not pd.isna(k.iloc[i-1]):
                if k.iloc[i-1] <= 20 and d.iloc[i-1] <= 20 and k.iloc[i] > 20:
                    signals[i] = 1
                elif k.iloc[i-1] >= 80 and d.iloc[i-1] >= 80 and k.iloc[i] < 80:
                    signals[i] = -1
    
    elif 'cci' in indicator_name.lower():
        period = params.get('period', 20)
        cci = calculate_cci(df['high'], df['low'], df['close'], period)
        
        for i in range(1, len(df)):
            if not pd.isna(cci.iloc[i]) and not pd.isna(cci.iloc[i-1]):
                if cci.iloc[i-1] <= -100 and cci.iloc[i] > -100:
                    signals[i] = 1
                elif cci.iloc[i-1] >= 100 and cci.iloc[i] < 100:
                    signals[i] = -1
    
    elif 'williams' in indicator_name.lower():
        period = params.get('period', 14)
        wr = calculate_williams_r(df['high'], df['low'], df['close'], period)
        
        for i in range(1, len(df)):
            if not pd.isna(wr.iloc[i]) and not pd.isna(wr.iloc[i-1]):
                if wr.iloc[i-1] <= -80 and wr.iloc[i] > -80:
                    signals[i] = 1
                elif wr.iloc[i-1] >= -20 and wr.iloc[i] < -20:
                    signals[i] = -1
    
    elif 'adx' in indicator_name.lower():
        period = params.get('period', 14)
        adx, plus_di, minus_di = calculate_adx(df['high'], df['low'], df['close'], period)
        
        for i in range(1, len(df)):
            if not pd.isna(adx.iloc[i]) and not pd.isna(plus_di.iloc[i]) and not pd.isna(minus_di.iloc[i]):
                if adx.iloc[i] > 25 and plus_di.iloc[i] > minus_di.iloc[i] and plus_di.iloc[i-1] <= minus_di.iloc[i-1]:
                    signals[i] = 1
                elif adx.iloc[i] > 25 and minus_di.iloc[i] > plus_di.iloc[i] and minus_di.iloc[i-1] <= plus_di.iloc[i-1]:
                    signals[i] = -1
    
    return signals

def main():
    print('🎯 PENGU - Comprehensive Indicator Tester')
    print('🎯 Rules: Frequent ✅ | Profitable ✅ | Safe ✅')
    print('='*100)
    
    try:
        exchange = ccxt.binance()
        
        print('📥 Fetching PENGU/USDT data from Binance...')
        ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=1000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f'✅ Fetched {len(df)} candles')
        print(f'📅 From: {df["datetime"].iloc[0]}')
        print(f'📅 To: {df["datetime"].iloc[-1]}')
        print()
        
        # Calculate Heikin Ashi
        df = calculate_heikin_ashi(df)
        
        # Define all strategies to test
        strategies = [
            # Moving Averages
            {'name': 'SMA_20', 'type': 'sma', 'params': {'period': 20}},
            {'name': 'SMA_50', 'type': 'sma', 'params': {'period': 50}},
            {'name': 'SMA_100', 'type': 'sma', 'params': {'period': 100}},
            {'name': 'EMA_20', 'type': 'ema', 'params': {'period': 20}},
            {'name': 'EMA_50', 'type': 'ema', 'params': {'period': 50}},
            {'name': 'EMA_100', 'type': 'ema', 'params': {'period': 100}},
            {'name': 'EMA_12_26', 'type': 'ema', 'params': {'period': 12}},
            
            # Oscillators
            {'name': 'RSI_14', 'type': 'rsi', 'params': {'period': 14, 'overbought': 70, 'oversold': 30}},
            {'name': 'RSI_9', 'type': 'rsi', 'params': {'period': 9, 'overbought': 70, 'oversold': 30}},
            {'name': 'RSI_21', 'type': 'rsi', 'params': {'period': 21, 'overbought': 70, 'oversold': 30}},
            {'name': 'RSI_7', 'type': 'rsi', 'params': {'period': 7, 'overbought': 70, 'oversold': 30}},
            {'name': 'RSI_14_40_60', 'type': 'rsi', 'params': {'period': 14, 'overbought': 60, 'oversold': 40}},
            
            # MACD
            {'name': 'MACD_12_26_9', 'type': 'macd', 'params': {'fast': 12, 'slow': 26, 'signal': 9}},
            {'name': 'MACD_8_18_9', 'type': 'macd', 'params': {'fast': 8, 'slow': 18, 'signal': 9}},
            
            # Stochastic
            {'name': 'STOCH_14_3', 'type': 'stoch', 'params': {'k_period': 14, 'd_period': 3}},
            {'name': 'STOCH_9_3', 'type': 'stoch', 'params': {'k_period': 9, 'd_period': 3}},
            
            # CCI
            {'name': 'CCI_20', 'type': 'cci', 'params': {'period': 20}},
            {'name': 'CCI_14', 'type': 'cci', 'params': {'period': 14}},
            
            # Williams %R
            {'name': 'WILLIAMS_14', 'type': 'williams', 'params': {'period': 14}},
            
            # ADX
            {'name': 'ADX_14', 'type': 'adx', 'params': {'period': 14}},
            {'name': 'ADX_10', 'type': 'adx', 'params': {'period': 10}},
        ]
        
        print(f'🧪 Testing {len(strategies)} strategies...')
        print()
        
        results = []
        
        for strategy in strategies:
            signals = generate_signals_from_indicator(df, strategy['name'], strategy['params'])
            result = backtest_strategy(df, signals, strategy['name'], tp=0.01, sl=0.02)
            
            if result:
                results.append(result)
        
        if not results:
            print('❌ No results found!')
            return
        
        # Sort by total return
        results.sort(key=lambda x: x['total_return'], reverse=True)
        
        print('🏆 TOP 15 STRATEGIES (Ranked by Total Return):')
        print('='*100)
        
        for i, r in enumerate(results[:15], 1):
            print(f'{i:2d}. {r["name"]:20s} | '
                  f'Trades={r["trades"]:3d} | '
                  f'WR={r["win_rate"]:5.1f}% | '
                  f'Return={r["total_return"]:6.2f}% | '
                  f'Avg={r["avg_return"]*100:6.3f}% | '
                  f'DD={r["max_drawdown"]:5.2f}%')
        
        print()
        print('='*100)
        
        # Find best by each criterion
        best_frequent = max(results, key=lambda x: x['trades'])
        best_profitable = max(results, key=lambda x: x['total_return'])
        best_safe = min(results, key=lambda x: x['max_drawdown']) if results else None
        
        print('🏅 BEST BY CATEGORY:')
        print('='*100)
        print(f'🎯 Most Frequent: {best_frequent["name"]} with {best_frequent["trades"]} trades')
        print(f'💰 Most Profitable: {best_profitable["name"]} with {best_profitable["total_return"]:.2f}% return')
        if best_safe:
            print(f'🛡️  Safest: {best_safe["name"]} with {best_safe["max_drawdown"]:.2f}% max drawdown')
        
        print()
        print('🎯 RECOMMENDED STRATEGY (Best Balance):')
        print('='*100)
        
        # Calculate composite score: (frequent * 0.3) + (profitable * 0.4) + (safe * 0.3)
        for r in results:
            freq_score = (r['trades'] / best_frequent['trades']) * 100 if best_frequent['trades'] > 0 else 0
            prof_score = (r['total_return'] / 100) * 100 if best_profitable['total_return'] > 0 else 0
            safe_score = (1 - (r['max_drawdown'] / 100)) * 100 if r['max_drawdown'] < 100 else 0
            
            composite = (freq_score * 0.3) + (prof_score * 0.4) + (safe_score * 0.3)
            r['composite_score'] = composite
        
        results.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
        
        best_composite = results[0] if results else None
        if best_composite:
            print(f'🏆 {best_composite["name"]}')
            print(f'   Composite Score: {best_composite["composite_score"]:.2f}')
            print(f'   Trades: {best_composite["trades"]}')
            print(f'   Win Rate: {best_composite["win_rate"]:.1f}%')
            print(f'   Total Return: {best_composite["total_return"]:.2f}%')
            print(f'   Max Drawdown: {best_composite["max_drawdown"]:.2f}%')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

