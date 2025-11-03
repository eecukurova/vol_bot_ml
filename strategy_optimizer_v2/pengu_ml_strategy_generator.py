#!/usr/bin/env python3
"""
PENGU ML + LLM Strategy Generator
3 Hedef: Kar sürekliliği, İşlem sürekliliği, Güvenlik
"""

import ccxt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class PENGUMLStrategyGenerator:
    def __init__(self, symbol='PENGU/USDT', timeframe='1h'):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = ccxt.binance()
        self.model = None
        self.features_list = []
        
    def fetch_data(self, limit=5000):
        """Fetch historical data"""
        print(f'📥 Fetching {self.symbol} data...')
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        print(f'✅ Fetched {len(df)} candles')
        print(f'📅 {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
        return df
    
    def calculate_features(self, df):
        """Calculate technical indicators as features"""
        print('🔧 Calculating features...')
        
        # Price features
        df['returns'] = df['close'].pct_change()
        df['high_low_pct'] = (df['high'] - df['low']) / df['close']
        df['open_close_pct'] = (df['close'] - df['open']) / df['open']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Bollinger Bands
        bb_period = 20
        df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
        bb_std = df['close'].rolling(window=bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        df['atr'] = ranges.max(axis=1).rolling(window=14).mean()
        
        # Volume features
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        df['volume_trend'] = df['volume'].rolling(window=5).mean() / df['volume'].rolling(window=20).mean()
        
        # Moving averages
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        
        # Momentum
        df['momentum'] = df['close'].pct_change(periods=4)
        df['price_change'] = df['close'].pct_change(periods=1)
        
        # Volatility
        df['volatility'] = df['returns'].rolling(window=20).std()
        
        # Stochastic
        period = 14
        df['stoch_low'] = df['low'].rolling(window=period).min()
        df['stoch_high'] = df['high'].rolling(window=period).max()
        df['stoch_k'] = 100 * ((df['close'] - df['stoch_low']) / (df['stoch_high'] - df['stoch_low']))
        df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()
        
        # ADX
        df['plus_dm'] = df['high'].diff()
        df['minus_dm'] = -df['low'].diff()
        df['plus_dm'][df['plus_dm'] < 0] = 0
        df['minus_dm'][df['minus_dm'] < 0] = 0
        
        tr_list = [
            df['high'] - df['low'],
            abs(df['high'] - df['close'].shift()),
            abs(df['low'] - df['close'].shift())
        ]
        tr = pd.concat(tr_list, axis=1).max(axis=1)
        df['tr'] = tr
        df['atr_adx'] = tr.rolling(window=14).mean()
        
        plus_di = 100 * (df['plus_dm'].rolling(window=14).mean() / df['atr_adx'])
        minus_di = 100 * (df['minus_dm'].rolling(window=14).mean() / df['atr_adx'])
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.rolling(window=14).mean()
        
        print(f'✅ Calculated {len([c for c in df.columns if c not in ["timestamp", "datetime"]])} features')
        return df
    
    def generate_labels(self, df, tp_pct=1.0, sl_pct=2.0, lookahead=100):
        """Generate labels based on future price action"""
        print('🏷️  Generating labels...')
        
        labels = [0] * len(df)  # 0: No signal, 1: Buy, -1: Sell
        
        for i in range(len(df) - lookahead):
            current_price = df['close'].iloc[i]
            
            # Look ahead
            future_prices = df['close'].iloc[i+1:i+lookahead]
            
            # Calculate max profit/loss
            max_gain = ((future_prices.max() - current_price) / current_price) * 100
            max_loss = ((future_prices.min() - current_price) / current_price) * 100
            
            # Check if TP or SL would be hit
            if max_gain >= tp_pct and max_loss > -sl_pct:
                # Take profit possible
                tp_idx = i + 1 + np.argmax(future_prices)
                sl_before_tp = future_prices.iloc[:np.argmax(future_prices)].min()
                if ((sl_before_tp - current_price) / current_price) * 100 > -sl_pct:
                    labels[i] = 1  # Buy signal
            elif max_loss <= -sl_pct:
                # Stop loss would hit
                labels[i] = -1 if max_loss < -sl_pct * 1.5 else 0  # Avoid bad entries
        
        # Ensure we have some balance
        buy_signals = labels.count(1)
        sell_signals = labels.count(-1)
        
        print(f'   Labels: {buy_signals} buy signals, {sell_signals} sell signals')
        return labels
    
    def train_model(self, df, labels):
        """Train ML model"""
        print('🤖 Training ML model...')
        
        # Select features
        feature_cols = [
            'returns', 'high_low_pct', 'open_close_pct',
            'rsi', 'macd', 'macd_signal', 'macd_hist',
            'bb_width', 'atr', 'volume_ratio', 'volume_trend',
            'momentum', 'volatility', 'stoch_k', 'stoch_d', 'adx'
        ]
        
        X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        y = labels
        
        # Remove rows with 0 label for now (could use for balancing)
        mask = pd.Series([yi != 0 for yi in y])
        X_filtered = X[mask.values]
        y_filtered = [y[i] for i in range(len(y)) if mask.iloc[i]]
        
        if len(X_filtered) == 0:
            print('❌ No valid labels!')
            return None
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_filtered, y_filtered, test_size=0.2, random_state=42
        )
        
        # Train model
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        self.model.fit(X_train, y_train)
        self.features_list = feature_cols
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f'✅ Model trained! Accuracy: {accuracy:.2%}')
        print(f'\n{classification_report(y_test, y_pred)}')
        
        return self.model
    
    def generate_strategy(self, df, tp_pct=1.0, sl_pct=2.0):
        """Generate trading strategy"""
        print('📊 Generating strategy...')
        
        if self.model is None:
            print('❌ Model not trained!')
            return None
        
        # Generate signals
        signals = []
        features = df[self.features_list].fillna(0).replace([np.inf, -np.inf], 0)
        
        for i in range(len(df)):
            if features.iloc[i].notna().all():
                signal = self.model.predict([features.iloc[i]])[0]
                signals.append(signal)
            else:
                signals.append(0)
        
        # Backtest
        trades = []
        balance = 10000.0
        in_position = False
        entry_price = 0
        is_long = False
        
        for i in range(len(signals)):
            current_price = df['close'].iloc[i]
            
            # Entry
            if not in_position and signals[i] == 1:
                in_position = True
                is_long = True
                entry_price = current_price
            elif not in_position and signals[i] == -1:
                in_position = True
                is_long = False
                entry_price = current_price
            
            # Exit
            if in_position:
                if is_long:
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
                
                # TP
                if pnl_pct >= tp_pct / 100:
                    trades.append({'pnl': tp_pct / 100, 'type': 'TP'})
                    balance += balance * (tp_pct / 100)
                    in_position = False
                # SL
                elif pnl_pct <= -sl_pct / 100:
                    trades.append({'pnl': -sl_pct / 100, 'type': 'SL'})
                    balance += balance * (-sl_pct / 100)
                    in_position = False
                # Opposite signal
                elif (is_long and signals[i] == -1) or (not is_long and signals[i] == 1):
                    trades.append({'pnl': pnl_pct, 'type': 'Signal'})
                    balance += balance * pnl_pct
                    in_position = False
        
        # Results
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
    
    def optimize_parameters(self, df):
        """Optimize TP/SL parameters"""
        print('🎯 Optimizing TP/SL parameters...')
        
        results = []
        for tp in [0.5, 1.0, 1.5, 2.0, 3.0]:
            for sl in [1.0, 2.0, 3.0, 4.0]:
                if tp < sl:  # TP should be smaller than SL for risk management
                    result = self.generate_strategy(df, tp, sl)
                    if result:
                        result['tp'] = tp
                        result['sl'] = sl
                        result['risk_reward'] = tp / sl
                        results.append(result)
        
        if results:
            results.sort(key=lambda x: x['total_return'] / x['trades'] * x['win_rate'], reverse=True)
            return results[0]
        
        return None

def main():
    print('🎯 PENGU ML + LLM STRATEGY GENERATOR')
    print('🎯 Hedef: Kar + İşlem + Güvenlik Sürekliliği')
    print('='*80)
    
    generator = PENGUMLStrategyGenerator(symbol='PENGU/USDT', timeframe='1h')
    
    # Fetch data
    df = generator.fetch_data(limit=3000)
    
    # Calculate features
    df = generator.calculate_features(df)
    
    # Generate labels
    labels = generator.generate_labels(df, tp_pct=1.0, sl_pct=2.0)
    
    # Train model
    generator.train_model(df, labels)
    
    # Optimize parameters
    best_params = generator.optimize_parameters(df)
    
    if best_params:
        print('\n🏆 BEST STRATEGY PARAMETERS:')
        print('='*80)
        print(f'   TP: {best_params["tp"]}%')
        print(f'   SL: {best_params["sl"]}%')
        print(f'   Risk/Reward: {best_params["risk_reward"]:.2f}')
        print(f'   Total Return: {best_params["total_return"]:.2f}%')
        print(f'   Win Rate: {best_params["win_rate"]:.1f}%')
        print(f'   Trades: {best_params["trades"]}')
        print(f'   Final Balance: ${best_params["balance"]:.2f}')
        
        # Save model
        model_file = f'pengu_ml_model_{datetime.now().strftime("%Y%m%d_%H%M%S")}.joblib'
        joblib.dump(generator.model, model_file)
        print(f'\n💾 Model saved: {model_file}')
    else:
        print('\n❌ No profitable strategy found')

if __name__ == "__main__":
    main()

