#!/usr/bin/env python3
"""
PENGU ML - Daha Fazla Veri ile Eğitim
Approach: Transfer Learning from similar volatile coins
"""

import ccxt
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, VotingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
import warnings
warnings.filterwarnings('ignore')

class MultiCoinMLStrategy:
    def __init__(self):
        self.exchange = ccxt.binance()
        self.scaler = StandardScaler()
        self.model = None
        
    def fetch_multiple_coins(self, symbols, limit=5000):
        """Fetch data from multiple similar coins"""
        print('📥 Fetching data from multiple coins...')
        print('='*80)
        
        all_data = {}
        
        for symbol in symbols:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, '1h', limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                all_data[symbol] = df
                print(f'✅ {symbol}: {len(df)} candles ({df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]})')
            except Exception as e:
                print(f'❌ {symbol}: {e}')
        
        print()
        return all_data
    
    def engineer_features(self, df):
        """Calculate all features"""
        # RSI variations
        for period in [7, 14, 21, 28]:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            df[f'rsi_{period}'] = 100 - (100 / (1 + gain/loss))
        
        # MACD variations
        for fast, slow in [(9, 21), (12, 26), (15, 30), (18, 39)]:
            ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
            df[f'macd_{fast}_{slow}'] = ema_fast - ema_slow
            df[f'macd_signal_{fast}_{slow}'] = df[f'macd_{fast}_{slow}'].ewm(span=9, adjust=False).mean()
            df[f'macd_hist_{fast}_{slow}'] = df[f'macd_{fast}_{slow}'] - df[f'macd_signal_{fast}_{slow}']
        
        # Bollinger Bands
        for period in [15, 20, 30, 50]:
            sma = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            df[f'bb_upper_{period}'] = sma + (std * 2)
            df[f'bb_lower_{period}'] = sma - (std * 2)
            df[f'bb_width_{period}'] = (df[f'bb_upper_{period}'] - df[f'bb_lower_{period}']) / df['close']
            df[f'bb_position_{period}'] = (df['close'] - df[f'bb_lower_{period}']) / (df[f'bb_upper_{period}'] - df[f'bb_lower_{period}'])
        
        # ATR and volatility
        for period in [10, 14, 20, 30]:
            hl = df['high'] - df['low']
            hc = abs(df['high'] - df['close'].shift())
            lc = abs(df['low'] - df['close'].shift())
            df[f'atr_{period}'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(window=period).mean()
            df[f'atr_pct_{period}'] = (df[f'atr_{period}'] / df['close']) * 100
        
        # Volume features
        for period in [10, 20, 50, 100]:
            df[f'volume_ma_{period}'] = df['volume'].rolling(window=period).mean()
            df[f'volume_ratio_{period}'] = df['volume'] / df[f'volume_ma_{period}']
            df[f'volume_trend_{period}'] = df['volume'].rolling(window=period//2).mean() / df['volume'].rolling(window=period).mean()
        
        # Moving averages
        for period in [10, 20, 50, 100, 200]:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
            df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
        
        # Momentum
        for period in [3, 5, 10, 20, 30]:
            df[f'momentum_{period}'] = df['close'].pct_change(periods=period)
            df[f'roc_{period}'] = ((df['close'] - df['close'].shift(period)) / df['close'].shift(period)) * 100
        
        # Price action
        df['high_low_pct'] = (df['high'] - df['low']) / df['close']
        df['open_close_pct'] = (df['close'] - df['open']) / df['open']
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(window=20).std()
        df['returns_long'] = df['close'].pct_change(periods=10)
        
        # Trend
        df['ema_cross_20_50'] = df['ema_20'] - df['ema_50']
        df['ema_cross_50_200'] = df['ema_50'] - df['ema_200']
        df['trend_strength'] = abs(df['ema_20'] - df['ema_50']) / df['close']
        
        # Support/Resistance
        df['price_position'] = (df['close'] - df['low'].rolling(50).min()) / (df['high'].rolling(50).max() - df['low'].rolling(50).min())
        
        # Candle patterns
        df['body'] = abs(df['close'] - df['open'])
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        
        # Fill NaN
        df = df.fillna(method='bfill').fillna(0)
        
        return df
    
    def create_labels_from_pattern(self, df, lookback=24):
        """Create labels based on immediate future price action"""
        labels = [0] * len(df)
        
        for i in range(lookback, len(df) - lookback):
            current_price = df['close'].iloc[i]
            
            # Look ahead only 24 candles max (1 day for 1h)
            future_prices = df['close'].iloc[i+1:i+lookback]
            
            if len(future_prices) == 0:
                continue
            
            # Calculate potential
            max_gain = ((future_prices.max() - current_price) / current_price) * 100
            max_loss = ((future_prices.min() - current_price) / current_price) * 100
            
            # Buy if we can make 1% without hitting 2% loss
            if max_gain >= 1.0 and max_loss > -2.0:
                labels[i] = 1
            # Sell if we would hit 2% loss quickly
            elif max_loss <= -2.0:
                labels[i] = -1
        
        return labels
    
    def combine_data(self, all_data):
        """Combine data from multiple coins"""
        print('🔄 Combining data from multiple coins...')
        
        combined_df = pd.DataFrame()
        
        for symbol, df in all_data.items():
            df_named = df.copy()
            df_named['symbol'] = symbol
            combined_df = pd.concat([combined_df, df_named], ignore_index=True)
        
        print(f'✅ Combined: {len(combined_df)} total candles')
        return combined_df
    
    def train_model(self, df, labels):
        """Train ensemble model"""
        print('🤖 Training ensemble model with more data...')
        
        # Get feature columns
        feature_cols = [c for c in df.columns if c not in ['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume', 'symbol']]
        
        X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        y = labels
        
        # Filter non-zero labels
        mask = pd.Series([y[i] != 0 for i in range(len(y))])
        X_filtered = X[mask.values]
        y_filtered = [y[i] for i in range(len(y)) if mask.iloc[i]]
        
        print(f'   Training samples: {len(X_filtered)}')
        
        # Train ensemble
        rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        gb = GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, random_state=42)
        
        ensemble = VotingClassifier(
            estimators=[('rf', rf), ('gb', gb)],
            voting='soft'
        )
        
        ensemble.fit(X_filtered, y_filtered)
        
        print(f'✅ Model trained!')
        
        return ensemble, feature_cols
    
    def backtest(self, df, model, feature_cols, tp=1.0, sl=2.0):
        """Backtest the model"""
        X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        
        signals = []
        for i in range(len(X)):
            try:
                signal = model.predict([X.iloc[i]])[0]
                signals.append(signal)
            except:
                signals.append(0)
        
        # Execute
        balance = 10000.0
        in_position = False
        entry_price = 0
        trades = []
        
        for i in range(len(signals)):
            if signals[i] == 1 and not in_position:
                in_position = True
                entry_price = df['close'].iloc[i]
            
            elif in_position:
                pnl = (df['close'].iloc[i] - entry_price) / entry_price
                
                if pnl >= tp / 100:
                    trades.append(tp / 100)
                    balance += balance * (tp / 100)
                    in_position = False
                elif pnl <= -sl / 100:
                    trades.append(-sl / 100)
                    balance += balance * (-sl / 100)
                    in_position = False
                elif signals[i] == -1:
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

def main():
    print('🎯 PENGU ML - Multi-Coin Data Approach')
    print('='*80)
    
    ml = MultiCoinMLStrategy()
    
    # Similar volatile coins (meme coins like PENGU)
    symbols = [
        'PENGU/USDT',
        'PEPE/USDT',  # Similar meme coin
        'DOGE/USDT',  # Volatile
        'SHIB/USDT',  # Volatile
        'FLOKI/USDT', # Similar pattern
    ]
    
    # Fetch data
    all_data = ml.fetch_multiple_coins(symbols, limit=3000)
    
    if 'PENGU/USDT' not in all_data:
        print('❌ PENGU data not fetched!')
        return
    
    # Combine all data
    combined_df = ml.combine_data(all_data)
    
    # Calculate features for all
    print()
    print('🔧 Engineering features...')
    combined_df = ml.engineer_features(combined_df)
    print()
    
    # Create labels using pattern recognition
    print('🏷️  Creating labels...')
    labels = []
    for symbol in combined_df['symbol'].unique():
        symbol_df = combined_df[combined_df['symbol'] == symbol].copy()
        symbol_labels = ml.create_labels_from_pattern(symbol_df)
        labels.extend(symbol_labels)
    
    buy_count = labels.count(1)
    sell_count = labels.count(-1)
    print(f'   Labels: {buy_count} buy, {sell_count} sell, {labels.count(0)} none')
    print()
    
    # Train model
    model, features = ml.train_model(combined_df, labels)
    print()
    
    # Test on PENGU only
    print('📊 Testing on PENGU...')
    pengu_df = combined_df[combined_df['symbol'] == 'PENGU/USDT'].copy()
    result = ml.backtest(pengu_df, model, features)
    
    if result:
        print()
        print('🏆 RESULTS:')
        print('='*80)
        print(f'   Total Return: {result["total_return"]:.2f}%')
        print(f'   Win Rate: {result["win_rate"]:.1f}%')
        print(f'   Trades: {result["trades"]}')
        print(f'   Final Balance: ${result["balance"]:.2f}')
    else:
        print('❌ No trades')

if __name__ == "__main__":
    main()

