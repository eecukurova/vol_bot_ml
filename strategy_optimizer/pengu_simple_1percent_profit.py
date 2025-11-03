#!/usr/bin/env python3
"""
PENGU Simple 1% Profit Strategy
Test different indicators to find simple 1% profit strategy
"""

import ccxt
import pandas as pd
import numpy as np

def calculate_heikin_ashi(df):
    """Calculate Heikin Ashi"""
    df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    df['ha_open'] = df['ha_close'].copy()
    for i in range(1, len(df)):
        df.loc[i, 'ha_open'] = (df['ha_open'].iloc[i-1] + df['ha_close'].iloc[i-1]) / 2
    return df

def calculate_sma(prices, period):
    """Calculate SMA"""
    return prices.rolling(window=period).mean()

def calculate_ema(prices, period):
    """Calculate EMA"""
    return prices.ewm(span=period, adjust=False).mean()

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def backtest_strategy(df, indicator_type, period, tp=0.01, sl=0.02):
    """Backtest strategy with different indicators"""
    src = df['close']  # Use regular close for now
    
    # Calculate indicator
    if indicator_type == 'SMA':
        indicator = calculate_sma(src, period)
    elif indicator_type == 'EMA':
        indicator = calculate_ema(src, period)
    elif indicator_type == 'RSI':
        indicator = calculate_rsi(src, period)
    else:
        return None
    
    # Find signals
    signals = []
    
    if indicator_type == 'RSI':
        # RSI signals
        for i in range(1, len(df)):
            if df[indicator_type].iloc[i-1] <= 40 and df[indicator_type].iloc[i] > 40:
                signals.append({'type': 'buy', 'idx': i, 'price': src.iloc[i]})
            elif df[indicator_type].iloc[i-1] >= 60 and df[indicator_type].iloc[i] < 60:
                signals.append({'type': 'sell', 'idx': i, 'price': src.iloc[i]})
    else:
        # Moving average signals
        for i in range(1, len(df)):
            if not pd.isna(indicator.iloc[i]) and not pd.isna(indicator.iloc[i-1]):
                if indicator.iloc[i-1] <= src.iloc[i-1] and indicator.iloc[i] > src.iloc[i]:
                    signals.append({'type': 'buy', 'idx': i, 'price': src.iloc[i]})
                elif indicator.iloc[i-1] >= src.iloc[i-1] and indicator.iloc[i] < src.iloc[i]:
                    signals.append({'type': 'sell', 'idx': i, 'price': src.iloc[i]})
    
    # Execute trades
    position = None
    trades = []
    
    for signal in signals:
        if signal['type'] == 'buy' and position is None:
            position = {'entry': signal['idx'], 'price': signal['price'], 'type': 'long'}
        elif signal['type'] == 'sell' and position is not None:
            exit_price = signal['price']
            pnl = (exit_price - position['price']) / position['price']
            
            # Apply TP/SL
            if pnl >= tp:
                pnl = tp
            elif pnl <= -sl:
                pnl = -sl
            
            trades.append({
                'entry': position['entry'],
                'exit': signal['idx'],
                'pnl': pnl,
                'entry_price': position['price'],
                'exit_price': exit_price
            })
            position = None
    
    # Close open position
    if position:
        exit_price = df['close'].iloc[-1]
        pnl = (exit_price - position['price']) / position['price']
        if pnl >= tp:
            pnl = tp
        elif pnl <= -sl:
            pnl = -sl
        trades.append({'pnl': pnl})
    
    if trades:
        profitable = [t for t in trades if t['pnl'] > 0]
        total_return = sum(t['pnl'] for t in trades)
        win_rate = len(profitable) / len(trades) * 100
        avg_return = total_return / len(trades)
        
        return {
            'indicator': indicator_type,
            'period': period,
            'trades': len(trades),
            'win_rate': win_rate,
            'total_return': total_return,
            'avg_return': avg_return,
            'profitable': len(profitable)
        }
    
    return None

def test_all_strategies():
    """Test all combinations"""
    print('🚀 PENGU Simple 1% Profit Strategy Tester')
    print('='*80)
    
    try:
        exchange = ccxt.binance()
        
        # Fetch REAL data
        print('📊 Fetching PENGU/USDT data from Binance...')
        ohlcv = exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=500)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f'✅ Fetched {len(df)} candles')
        print(f'📅 Date: {df["date"].min()} to {df["date"].max()}')
        print()
        
        # Test configurations
        configs = [
            # RSI strategies
            {'type': 'RSI', 'period': 14, 'tp': 0.01, 'sl': 0.02},
            {'type': 'RSI', 'period': 9, 'tp': 0.01, 'sl': 0.02},
            {'type': 'RSI', 'period': 21, 'tp': 0.01, 'sl': 0.02},
            
            # SMA strategies
            {'type': 'SMA', 'period': 20, 'tp': 0.01, 'sl': 0.02},
            {'type': 'SMA', 'period': 50, 'tp': 0.01, 'sl': 0.02},
            {'type': 'SMA', 'period': 100, 'tp': 0.01, 'sl': 0.02},
            
            # EMA strategies
            {'type': 'EMA', 'period': 20, 'tp': 0.01, 'sl': 0.02},
            {'type': 'EMA', 'period': 50, 'tp': 0.01, 'sl': 0.02},
            {'type': 'EMA', 'period': 100, 'tp': 0.01, 'sl': 0.02},
        ]
        
        results = []
        
        for config in configs:
            src = df['close']
            
            if config['type'] == 'RSI':
                indicator = calculate_rsi(src, config['period'])
                df['RSI'] = indicator
            elif config['type'] == 'SMA':
                indicator = calculate_sma(src, config['period'])
            elif config['type'] == 'EMA':
                indicator = calculate_ema(src, config['period'])
            
            # Find buy/sell signals
            buy_signals = []
            sell_signals = []
            
            if config['type'] == 'RSI':
                for i in range(1, len(df)):
                    if df['RSI'].iloc[i-1] <= 40 and df['RSI'].iloc[i] > 40:
                        buy_signals.append(i)
                    elif df['RSI'].iloc[i-1] >= 60 and df['RSI'].iloc[i] < 60:
                        sell_signals.append(i)
            else:
                for i in range(1, len(df)):
                    if not pd.isna(indicator.iloc[i]) and not pd.isna(indicator.iloc[i-1]):
                        if indicator.iloc[i-1] <= src.iloc[i-1] and indicator.iloc[i] > src.iloc[i]:
                            buy_signals.append(i)
                        elif indicator.iloc[i-1] >= src.iloc[i-1] and indicator.iloc[i] < src.iloc[i]:
                            sell_signals.append(i)
            
            # Backtest
            position = None
            trades = []
            
            for i in range(1, len(df)):
                if i in buy_signals and position is None:
                    position = {'type': 'long', 'entry': i, 'price': df['close'].iloc[i]}
                elif i in sell_signals and position is not None:
                    exit_price = df['close'].iloc[i]
                    pnl = (exit_price - position['price']) / position['price']
                    
                    if pnl >= config['tp']:
                        pnl = config['tp']
                    elif pnl <= -config['sl']:
                        pnl = -config['sl']
                    
                    trades.append({'pnl': pnl})
                    position = None
            
            if position:
                exit_price = df['close'].iloc[-1]
                pnl = (exit_price - position['price']) / position['price']
                if pnl >= config['tp']:
                    pnl = config['tp']
                elif pnl <= -config['sl']:
                    pnl = -config['sl']
                trades.append({'pnl': pnl})
            
            if trades:
                profitable = [t for t in trades if t['pnl'] > 0]
                total_return = sum(t['pnl'] for t in trades)
                win_rate = len(profitable) / len(trades) * 100
                
                results.append({
                    'indicator': config['type'],
                    'period': config['period'],
                    'trades': len(trades),
                    'win_rate': win_rate,
                    'total_return': total_return,
                    'avg_return': total_return/len(trades)
                })
        
        # Display results
        if results:
            # Sort by total return
            results.sort(key=lambda x: x['total_return'], reverse=True)
            
            print('📊 BEST STRATEGIES (by Total Return):')
            print('='*80)
            
            for i, r in enumerate(results[:10], 1):
                indicator_name = f'{r["indicator"]}{r["period"]}'
                print(f'{i}. {indicator_name}: '
                      f'WR={r["win_rate"]:.1f}%, '
                      f'Return={r["total_return"]:.2%}, '
                      f'Trades={r["trades"]}, '
                      f'Avg={r["avg_return"]:.3%}')
            
            # Show most profitable
            if results[0]['total_return'] > 0:
                print()
                best_indicator = f'{results[0]["indicator"]}{results[0]["period"]}'
                print(f'🏆 BEST: {best_indicator} with {results[0]["total_return"]:.2%} return!')
                print(f'   Win Rate: {results[0]["win_rate"]:.1f}%')
                print(f'   Trades: {results[0]["trades"]}')
            else:
                print()
                print('⚠️ None of the strategies are profitable with 1% TP target')
                print(f'Best result: {results[0]["total_return"]:.2%}')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_all_strategies()
