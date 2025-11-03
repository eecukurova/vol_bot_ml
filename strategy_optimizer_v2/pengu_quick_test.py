#!/usr/bin/env python3
"""
Quick test for PENGU ATR SuperTrend with real data
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

def calculate_heikin_ashi(df):
    """Calculate Heikin Ashi candles"""
    ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = ha_close.copy()
    
    for i in range(1, len(ha_open)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
    
    # Add to df before calculating high/low
    df['ha_close'] = ha_close
    df['ha_open'] = ha_open
    
    ha_high = df[['high', 'ha_open', 'ha_close']].max(axis=1)
    ha_low = df[['low', 'ha_open', 'ha_close']].min(axis=1)
    
    df['ha_high'] = ha_high
    df['ha_low'] = ha_low
    
    return df

def calculate_atr(df, period):
    """Calculate ATR"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    true_range = np.maximum(high_low, np.maximum(high_close, low_close))
    atr = true_range.rolling(window=period).mean()
    return atr

def test_pengu_strategy(timeframe='1h', atr_period=14, atr_multiplier=2.5):
    """Test PENGU strategy with real data"""
    print(f"\n🧪 Testing PENGU with real data ({timeframe})")
    print("="*80)
    
    try:
        exchange = ccxt.binance()
        
        # Fetch real data
        print(f"📊 Fetching PENGU/USDT data for {timeframe}...")
        ohlcv = exchange.fetch_ohlcv('PENGU/USDT', timeframe, limit=500)
        
        if not ohlcv or len(ohlcv) < 100:
            print("❌ Not enough data")
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f"✅ Fetched {len(df)} candles")
        print(f"📅 Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"💰 Price range: ${df['close'].min():.6f} - ${df['close'].max():.6f}")
        
        # Calculate Heikin Ashi
        df = calculate_heikin_ashi(df)
        
        # Calculate ATR
        atr = calculate_atr(df, atr_period)
        df['atr'] = atr
        
        # Calculate nLoss
        n_loss = atr_multiplier * atr
        
        # Calculate ATR Trailing Stop
        df['atr_trailing_stop'] = np.nan
        src = df['ha_close']
        
        # Simple position calculation
        df['position'] = 0
        
        for i in range(len(df)):
            if pd.isna(df['atr'].iloc[i]) or pd.isna(n_loss.iloc[i]):
                continue
            
            if i == 0:
                df.loc[i, 'atr_trailing_stop'] = src.iloc[i] - n_loss.iloc[i]
            else:
                prev_stop = df['atr_trailing_stop'].iloc[i-1]
                
                if src.iloc[i] > prev_stop and src.iloc[i-1] > prev_stop:
                    df.loc[i, 'atr_trailing_stop'] = max(prev_stop, src.iloc[i] - n_loss.iloc[i])
                elif src.iloc[i] < prev_stop and src.iloc[i-1] < prev_stop:
                    df.loc[i, 'atr_trailing_stop'] = min(prev_stop, src.iloc[i] + n_loss.iloc[i])
                elif src.iloc[i] > prev_stop:
                    df.loc[i, 'atr_trailing_stop'] = src.iloc[i] - n_loss.iloc[i]
                else:
                    df.loc[i, 'atr_trailing_stop'] = src.iloc[i] + n_loss.iloc[i]
            
            # Position
            if i > 0 and not pd.isna(df['atr_trailing_stop'].iloc[i-1]):
                if src.iloc[i-1] < df['atr_trailing_stop'].iloc[i-1] and src.iloc[i] > df['atr_trailing_stop'].iloc[i]:
                    df.loc[i, 'position'] = 1
                elif src.iloc[i-1] > df['atr_trailing_stop'].iloc[i-1] and src.iloc[i] < df['atr_trailing_stop'].iloc[i]:
                    df.loc[i, 'position'] = -1
                else:
                    df.loc[i, 'position'] = df['position'].iloc[i-1]
        
        # Find signals
        buy_signals = df[df['position'].diff() == 1].index.tolist()
        sell_signals = df[df['position'].diff() == -1].index.tolist()
        
        print(f"\n📊 SIGNALS FOUND:")
        print(f"   Buy signals: {len(buy_signals)}")
        print(f"   Sell signals: {len(sell_signals)}")
        
        # Calculate performance
        if len(buy_signals) > 0:
            # Simple backtest
            trades = []
            position = None
            
            for i in range(len(df)):
                if i in buy_signals and position is None:
                    position = {
                        'entry': i,
                        'price': df['close'].iloc[i],
                        'entry_date': df['date'].iloc[i]
                    }
                elif i in sell_signals and position is not None:
                    exit_price = df['close'].iloc[i]
                    pnl = (exit_price - position['price']) / position['price']
                    
                    trades.append({
                        'entry': position['entry'],
                        'exit': i,
                        'entry_date': position['entry_date'],
                        'exit_date': df['date'].iloc[i],
                        'entry_price': position['price'],
                        'exit_price': exit_price,
                        'pnl': pnl
                    })
                    position = None
            
            if trades:
                profitable = [t for t in trades if t['pnl'] > 0]
                total_return = sum(t['pnl'] for t in trades)
                win_rate = len(profitable) / len(trades) * 100
                
                print(f"\n💰 PERFORMANCE:")
                print(f"   Total Trades: {len(trades)}")
                print(f"   Win Rate: {win_rate:.1f}%")
                print(f"   Total Return: {total_return:.2%}")
                print(f"   Avg Return: {total_return/len(trades):.2%}")
                print(f"   Max Win: {max(t['pnl'] for t in trades):.2%}")
                print(f"   Max Loss: {min(t['pnl'] for t in trades):.2%}")
                
                print(f"\n📈 RECENT TRADES:")
                for i, trade in enumerate(trades[-5:], 1):
                    print(f"   {i}. Entry: ${trade['entry_price']:.6f} → Exit: ${trade['exit_price']:.6f} → PnL: {trade['pnl']:.2%}")
                
                return {
                    'trades': len(trades),
                    'win_rate': win_rate,
                    'total_return': total_return,
                    'avg_return': total_return/len(trades)
                }
        
        print("⚠️ No signals found with these parameters")
        return None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🚀 PENGU Quick Test with Real Data")
    print("="*80)
    
    # Test different timeframes
    for tf in ['15m', '30m', '1h', '4h']:
        result = test_pengu_strategy(timeframe=tf, atr_period=14, atr_multiplier=2.5)
        if result:
            print(f"✅ {tf}: {result['trades']} trades, {result['win_rate']:.1f}% WR, {result['total_return']:.2%} return")
        else:
            print(f"❌ {tf}: No profitable signals")
        
        print()
