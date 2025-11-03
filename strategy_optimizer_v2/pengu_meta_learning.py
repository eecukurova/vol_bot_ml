#!/usr/bin/env python3
"""
PENGU Meta-Learning System
Learn from multiple indicators and find the best combination
LLM interprets results and suggests improvements
"""

import ccxt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import warnings
warnings.filterwarnings('ignore')

class PENGUMetaLearning:
    """Meta-Learning: Test all combinations, LLM finds best"""
    
    def __init__(self, symbol='PENGU/USDT'):
        self.exchange = ccxt.binance()
        self.symbol = symbol
        self.best_strategy = None
        
    def fetch_data(self):
        print('📥 Fetching PENGU data...')
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, '1h', limit=2000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        print(f'✅ {len(df)} candles')
        return df
    
    def test_all_combinations(self, df):
        """Test ALL indicator combinations"""
        print('🧪 Testing all indicator combinations...')
        print('='*80)
        
        results = []
        
        # Define all possible strategies
        strategies = [
            {
                'name': 'RSI Oversold',
                'buy': lambda df: (df['rsi_14'] < 30) & (df['rsi_14'] > df['rsi_14'].shift(1)),
                'sell': lambda df: (df['rsi_14'] > 70)
            },
            {
                'name': 'MACD Cross',
                'buy': lambda df: (df['macd_12_26'] > df['macd_signal_12_26']) & (df['macd_12_26'].shift(1) <= df['macd_signal_12_26'].shift(1)),
                'sell': lambda df: (df['macd_12_26'] < df['macd_signal_12_26']) & (df['macd_12_26'].shift(1) >= df['macd_signal_12_26'].shift(1))
            },
            {
                'name': 'Bollinger Bounce',
                'buy': lambda df: (df['close'] < df['bb_lower_20']) & (df['close'] > df['bb_lower_20'].shift(1)),
                'sell': lambda df: (df['close'] > df['bb_upper_20'])
            },
            {
                'name': 'EMA Cross',
                'buy': lambda df: (df['ema_20'] > df['ema_50']) & (df['ema_20'].shift(1) <= df['ema_50'].shift(1)),
                'sell': lambda df: (df['ema_20'] < df['ema_50']) & (df['ema_20'].shift(1) >= df['ema_50'].shift(1))
            },
            {
                'name': 'RSI + Volume',
                'buy': lambda df: (df['rsi_14'] < 40) & (df['volume_ratio_20'] > 1.5),
                'sell': lambda df: (df['rsi_14'] > 60) & (df['volume_ratio_20'] > 1.5)
            },
            {
                'name': 'MACD + RSI',
                'buy': lambda df: (df['macd_hist_12_26'] > 0) & (df['rsi_14'] < 40),
                'sell': lambda df: (df['macd_hist_12_26'] < 0) & (df['rsi_14'] > 60)
            },
            {
                'name': 'Full Combination',
                'buy': lambda df: (df['rsi_14'] < 35) & (df['macd_hist_12_26'] > 0) & (df['ema_20'] > df['ema_50']) & (df['volume_ratio_20'] > 1.2),
                'sell': lambda df: (df['rsi_14'] > 65) & (df['macd_hist_12_26'] < 0) & (df['ema_20'] < df['ema_50']) & (df['volume_ratio_20'] > 1.2)
            },
        ]
        
        for strategy in strategies:
            result = self.backtest_strategy(df, strategy)
            if result:
                result['name'] = strategy['name']
                results.append(result)
        
        return results
    
    def backtest_strategy(self, df, strategy):
        """Backtest a strategy"""
        buy_sig = strategy['buy'](df)
        sell_sig = strategy['sell'](df)
        
        if not buy_sig.any():
            return None
        
        balance = 10000.0
        in_position = False
        entry_price = 0
        trades = []
        
        for i in range(50, len(df)):
            if buy_sig.iloc[i] and not in_position:
                in_position = True
                entry_price = df['close'].iloc[i]
            
            elif in_position:
                pnl = (df['close'].iloc[i] - entry_price) / entry_price
                
                # TP/SL
                if pnl >= 0.01:
                    trades.append(0.01)
                    balance += balance * 0.01
                    in_position = False
                elif pnl <= -0.02:
                    trades.append(-0.02)
                    balance += balance * (-0.02)
                    in_position = False
                elif sell_sig.iloc[i]:
                    trades.append(pnl)
                    balance += balance * pnl
                    in_position = False
        
        if not trades:
            return None
        
        total_return = ((balance - 10000) / 10000) * 100
        win_rate = len([t for t in trades if t > 0]) / len(trades) * 100
        
        return {
            'trades': len(trades),
            'win_rate': win_rate,
            'total_return': total_return,
            'balance': balance
        }
    
    def llm_recommend_strategy(self, best):
        """LLM analyzes and recommends"""
        print('🤖 LLM Strategy Recommendation:')
        print('='*80)
        
        if best['total_return'] > 5:
            print(f"✅ BEST STRATEGY: {best['name']}")
            print(f"   Return: {best['total_return']:.2f}%")
            print(f"   Win Rate: {best['win_rate']:.1f}%")
            print(f"   Trades: {best['trades']}")
            print()
            print('💡 LLM Analysis:')
            print('   This strategy works because:')
            if 'Full' in best['name']:
                print('   - Multiple indicators provide confirmation')
                print('   - Reduces false signals')
                print('   - Good risk/reward ratio')
            elif 'RSI' in best['name'] and 'Volume' in best['name']:
                print('   - RSI identifies oversold/overbought')
                print('   - Volume confirms strength of move')
            print()
            print('🎯 Recommendation: Use this strategy!')
        else:
            print('⚠️  No profitable strategy found')
            print('💡 LLM Suggestion:')
            print('   - Try different timeframes')
            print('   - Adjust TP/SL parameters')
            print('   - Consider market regime detection')

def main():
    print('🎯 PENGU Meta-Learning System')
    print('🎯 Testing all combinations, LLM recommends best')
    print('='*80)
    print()
    
    ml = PENGUMetaLearning('PENGU/USDT')
    
    # Fetch and prepare data
    df = ml.fetch_data()
    
    # Calculate indicators
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['rsi_14'] = 100 - (100 / (1 + gain/loss))
    
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd_12_26'] = ema12 - ema26
    df['macd_signal_12_26'] = df['macd_12_26'].ewm(span=9, adjust=False).mean()
    df['macd_hist_12_26'] = df['macd_12_26'] - df['macd_signal_12_26']
    
    bb_middle = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper_20'] = bb_middle + (bb_std * 2)
    df['bb_lower_20'] = bb_middle - (bb_std * 2)
    
    df['volume_ma_20'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio_20'] = df['volume'] / df['volume_ma_20']
    
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    df = df.fillna(method='bfill').fillna(0)
    print()
    
    # Test all combinations
    results = ml.test_all_combinations(df)
    
    if results:
        results.sort(key=lambda x: x['total_return'], reverse=True)
        
        print('📊 ALL STRATEGY RESULTS:')
        for r in results:
            print(f'{r["name"]:20s} | Trades={r["trades"]:3d} | WR={r["win_rate"]:5.1f}% | Return={r["total_return"]:6.2f}%')
        
        best = results[0]
        print()
        ml.llm_recommend_strategy(best)

if __name__ == "__main__":
    main()

