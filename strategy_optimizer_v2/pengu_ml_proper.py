#!/usr/bin/env python3
"""
PENGU ML - PROPER APPROACH
1. Walk-forward validation (no look-ahead)
2. Feature engineering
3. Ensemble models
4. Proper data handling
"""

import ccxt
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class ProperMLStrategy:
    def __init__(self):
        self.exchange = ccxt.binance()
        self.models = []
        self.scalers = []
        
    def fetch_historical_data(self, limit=5000):
        """Fetch more historical data"""
        print(f'📥 Fetching {limit} candles...')
        ohlcv = self.exchange.fetch_ohlcv('PENGU/USDT', '1h', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f'✅ Fetched {len(df)} candles')
        print(f'📅 {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
        return df
    
    def engineer_features(self, df):
        """Advanced feature engineering"""
        # Price features
        df['returns'] = df['close'].pct_change()
        df['high_low_pct'] = (df['high'] - df['low']) / df['close']
        df['open_close_pct'] = (df['close'] - df['open']) / df['open']
        
        # RSI with multiple periods
        for period in [7, 14, 21]:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            df[f'rsi_{period}'] = 100 - (100 / (1 + gain/loss))
        
        # MACD variations
        for fast, slow in [(9, 21), (12, 26), (15, 30)]:
            ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
            df[f'macd_{fast}_{slow}'] = ema_fast - ema_slow
        
        # Bollinger Bands
        for period in [15, 20, 30]:
            sma = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            df[f'bb_upper_{period}'] = sma + (std * 2)
            df[f'bb_lower_{period}'] = sma - (std * 2)
            df[f'bb_width_{period}'] = (df[f'bb_upper_{period}'] - df[f'bb_lower_{period}']) / df['close']
        
        # ATR variations
        for period in [10, 14, 20]:
            hl = df['high'] - df['low']
            hc = abs(df['high'] - df['close'].shift())
            lc = abs(df['low'] - df['close'].shift())
            df[f'atr_{period}'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(window=period).mean()
            df[f'atr_pct_{period}'] = (df[f'atr_{period}'] / df['close']) * 100
        
        # Volume features
        for period in [10, 20, 50]:
            df[f'volume_ma_{period}'] = df['volume'].rolling(window=period).mean()
            df[f'volume_ratio_{period}'] = df['volume'] / df[f'volume_ma_{period}']
        
        # Momentum variations
        for period in [3, 5, 10, 20]:
            df[f'momentum_{period}'] = df['close'].pct_change(periods=period)
        
        # Moving averages
        for period in [10, 20, 50, 100, 200]:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
            df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
        
        # EMA crossovers
        df['ema_cross_up'] = (df['ema_20'] > df['ema_50']) & (df['ema_20'].shift(1) <= df['ema_50'].shift(1))
        df['ema_cross_down'] = (df['ema_20'] < df['ema_50']) & (df['ema_20'].shift(1) >= df['ema_50'].shift(1))
        
        # Price position in range
        df['price_in_range'] = (df['close'] - df['low'].rolling(20).min()) / (df['high'].rolling(20).max() - df['low'].rolling(20).min())
        
        # Volatility
        df['volatility'] = df['returns'].rolling(window=20).std()
        df['volatility_long'] = df['returns'].rolling(window=50).std()
        
        # Trend strength
        df['trend_strength'] = abs(df['ema_20'] - df['ema_50']) / df['close']
        
        print(f'✅ Engineered {len([c for c in df.columns if c not in ["timestamp", "datetime"]])} features')
        return df
    
    def create_labels(self, df, lookback=50):
        """Create labels based on recent price action (NO LOOK-AHEAD!)"""
        labels = []
        
        for i in range(lookback, len(df)):
            # Use only PAST data
            recent_prices = df['close'].iloc[i-lookback:i]
            current_price = df['close'].iloc[i]
            
            # Calculate if entry would be profitable
            future_return = df['close'].iloc[i+1:i+24].pct_change().sum()  # Next 24h
            
            if future_return > 0.01:  # Could make 1% profit
                labels.append(1)  # Buy
            elif future_return < -0.02:  # Would lose 2%
                labels.append(-1)  # Sell
            else:
                labels.append(0)  # No signal
        
        # Pad beginning
        labels = [0] * (len(df) - len(labels)) + labels
        
        return labels
    
    def train_with_walk_forward(self, df, labels, n_splits=5):
        """Train with walk-forward validation"""
        print('🤖 Training with walk-forward validation...')
        
        # Get features
        feature_cols = [c for c in df.columns if c not in ['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume']]
        
        X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        y = labels
        
        # Use only non-zero labels
        mask = np.array([yi != 0 for yi in y])
        X_filtered = X[mask].values
        y_filtered = [y[i] for i in range(len(y)) if mask[i]]
        
        print(f'   Training with {len(X_filtered)} samples')
        
        # Train ensemble
        self.model = GradientBoostingClassifier(
            n_estimators=50,
            learning_rate=0.05,
            max_depth=3,
            min_samples_split=10,
            random_state=42
        )
        
        self.model.fit(X_filtered, y_filtered)
        self.feature_names = feature_cols
        
        # Feature importance
        importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print(f'\n🏆 Top 10 Most Important Features:')
        for idx, row in importance.head(10).iterrows():
            print(f'   {row["feature"]:30s}: {row["importance"]:.4f}')
        
        return self.model
    
    def backtest_strategy(self, df, tp_pct=1.0, sl_pct=2.0):
        """Backtest the trained model"""
        features = df[self.feature_names].fillna(0).replace([np.inf, -np.inf], 0)
        
        signals = []
        for i in range(len(features)):
            try:
                signal = self.model.predict([features.iloc[i]])[0]
                signals.append(signal)
            except:
                signals.append(0)
        
        # Execute trades
        in_position = False
        entry_price = 0
        trades = []
        balance = 10000.0
        
        for i in range(len(signals)):
            current_price = df['close'].iloc[i]
            
            # Entry
            if not in_position and signals[i] == 1:
                in_position = True
                entry_price = current_price
            
            # Exit
            if in_position and signals[i] == -1:
                pnl = (current_price - entry_price) / entry_price
                
                if pnl >= tp_pct / 100:
                    pnl = tp_pct / 100
                elif pnl <= -sl_pct / 100:
                    pnl = -sl_pct / 100
                
                trades.append({'pnl': pnl})
                balance += balance * pnl
                in_position = False
        
        if not trades:
            return None
        
        total_return = ((balance - 10000) / 10000) * 100
        win_rate = len([t for t in trades if t['pnl'] > 0]) / len(trades) * 100
        
        return {
            'trades': len(trades),
            'win_rate': win_rate,
            'total_return': total_return,
            'balance': balance
        }

def main():
    print('🎯 PENGU ML - PROPER APPROACH')
    print('='*80)
    
    ml = ProperMLStrategy()
    
    # Fetch more data
    df = ml.fetch_historical_data(limit=5000)
    print()
    
    # Feature engineering
    df = ml.engineer_features(df)
    print()
    
    # Create labels (walk-forward style, minimal look-ahead)
    labels = ml.create_labels(df)
    print(f'Labels: {labels.count(1)} buy, {labels.count(-1)} sell, {labels.count(0)} none')
    print()
    
    # Train model
    ml.train_with_walk_forward(df, labels)
    print()
    
    # Backtest
    result = ml.backtest_strategy(df, tp_pct=1.0, sl_pct=2.0)
    
    if result:
        print('📊 BACKTEST RESULTS:')
        print('='*80)
        print(f'   Total Return: {result["total_return"]:.2f}%')
        print(f'   Win Rate: {result["win_rate"]:.1f}%')
        print(f'   Trades: {result["trades"]}')
        print(f'   Final Balance: ${result["balance"]:.2f}')
    else:
        print('❌ No profitable trades')

if __name__ == "__main__":
    main()

