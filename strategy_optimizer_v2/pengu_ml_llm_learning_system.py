#!/usr/bin/env python3
"""
PENGU ML + LLM Learning System
Self-improving strategy with ML model and LLM analysis
"""

import ccxt
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
import joblib
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class PENGULLMLearningSystem:
    """ML + LLM Self-Learning Trading System"""
    
    def __init__(self, symbol='PENGU/USDT'):
        self.exchange = ccxt.binance()
        self.symbol = symbol
        self.model = None
        self.feature_names = []
        self.strategy_params = {
            'tp': 1.0,
            'sl': 2.0,
            'min_win_rate': 0.60
        }
        
    def fetch_more_data(self):
        """Fetch comprehensive historical data"""
        print('📥 Fetching historical data...')
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, '1h', limit=2000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        print(f'✅ {len(df)} candles: {df["datetime"].iloc[0]} to {df["datetime"].iloc[-1]}')
        return df
    
    def engineer_features(self, df):
        """Comprehensive feature engineering"""
        print('🔧 Engineering features...')
        
        # Price features
        df['returns'] = df['close'].pct_change()
        df['high_low_pct'] = (df['high'] - df['low']) / df['close']
        df['open_close_pct'] = (df['close'] - df['open']) / df['open']
        
        # Multiple RSI periods
        for period in [7, 14, 21]:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            df[f'rsi_{period}'] = 100 - (100 / (1 + gain/loss))
        
        # MACD variations
        for fast, slow in [(9, 21), (12, 26)]:
            ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
            df[f'macd_{fast}_{slow}'] = ema_fast - ema_slow
            df[f'macd_signal_{fast}_{slow}'] = df[f'macd_{fast}_{slow}'].ewm(span=9, adjust=False).mean()
            df[f'macd_hist_{fast}_{slow}'] = df[f'macd_{fast}_{slow}'] - df[f'macd_signal_{fast}_{slow}']
        
        # Bollinger Bands
        for period in [20]:
            sma = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            df[f'bb_upper_{period}'] = sma + (std * 2)
            df[f'bb_lower_{period}'] = sma - (std * 2)
            df[f'bb_width_{period}'] = (df[f'bb_upper_{period}'] - df[f'bb_lower_{period}']) / sma
        
        # Volume
        df['volume_ma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio_20'] = df['volume'] / df['volume_ma_20']
        
        # Momentum
        df['momentum_5'] = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) * 100
        
        # Moving averages
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        print(f'✅ Created {len([c for c in df.columns if c not in ["timestamp", "datetime"]])} features')
        return df
    
    def create_proper_labels(self, df, tp_pct=1.0, sl_pct=2.0, lookahead=24):
        """Create labels WITHOUT look-ahead bias"""
        print('🏷️  Creating labels (no look-ahead)...')
        
        labels = []
        
        for i in range(50, len(df) - lookahead):
            current_price = df['close'].iloc[i]
            future_prices = df['close'].iloc[i+1:i+lookahead+1]
            
            # Calculate if trade would hit TP before SL
            if len(future_prices) > 0:
                max_profit = ((future_prices.max() - current_price) / current_price) * 100
                min_loss = ((future_prices.min() - current_price) / current_price) * 100
                
                # Buy if can make TP without hitting SL first
                if max_profit >= tp_pct and min_loss > -sl_pct:
                    labels.append(1)
                # Sell if would hit SL
                elif min_loss <= -sl_pct:
                    labels.append(-1)
                else:
                    labels.append(0)
            else:
                labels.append(0)
        
        # Pad beginning
        labels = [0] * (len(df) - len(labels)) + labels
        
        print(f'   Labels: {labels.count(1)} buy, {labels.count(-1)} sell, {labels.count(0)} none')
        return labels
    
    def train_with_validation(self, df, labels):
        """Train model with proper validation"""
        print('🤖 Training ML model...')
        
        # Get features
        feature_cols = [
            'rsi_7', 'rsi_14', 'rsi_21',
            'macd_9_21', 'macd_signal_9_21', 'macd_hist_9_21',
            'macd_12_26', 'macd_signal_12_26', 'macd_hist_12_26',
            'bb_width_20', 'volume_ratio_20', 'momentum_5',
            'ema_20', 'ema_50', 'returns'
        ]
        
        X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        y = labels
        
        # Filter non-zero
        mask = pd.Series([y[i] != 0 for i in range(len(y))])
        X_filtered = X[mask.values]
        y_filtered = [y[i] for i in range(len(y)) if mask.iloc[i]]
        
        if len(X_filtered) < 50:
            print('❌ Not enough training data!')
            return None
        
        print(f'   Training with {len(X_filtered)} samples')
        
        # Time series split validation
        tscv = TimeSeriesSplit(n_splits=3)
        scores = []
        
        for train_idx, test_idx in tscv.split(X_filtered):
            X_train, X_test = X_filtered.iloc[train_idx], X_filtered.iloc[test_idx]
            y_train, y_test = [y_filtered[i] for i in train_idx], [y_filtered[i] for i in test_idx]
            
            model = GradientBoostingClassifier(
                n_estimators=50,
                learning_rate=0.05,
                max_depth=3,
                min_samples_split=10,
                random_state=42
            )
            
            model.fit(X_train, y_train)
            score = model.score(X_test, y_test)
            scores.append(score)
        
        print(f'   Cross-validation scores: {[f"{s:.2%}" for s in scores]}')
        avg_score = np.mean(scores)
        print(f'   Average score: {avg_score:.2%}')
        print()
        
        # Train final model on all data
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
        
        print('🏆 Top 5 Important Features:')
        for idx, row in importance.head(5).iterrows():
            print(f'   {row["feature"]:20s}: {row["importance"]:.4f}')
        
        return self.model
    
    def backtest_strategy(self, df, tp_pct, sl_pct):
        """Backtest the ML strategy"""
        features = df[self.feature_names].fillna(0).replace([np.inf, -np.inf], 0)
        
        signals = []
        for i in range(len(features)):
            try:
                signal = self.model.predict([features.iloc[i]])[0]
                signals.append(signal)
            except:
                signals.append(0)
        
        # Execute
        balance = 10000.0
        in_position = False
        entry_price = 0
        is_long = False
        trades = []
        
        for i in range(len(signals)):
            if signals[i] == 1 and not in_position:
                in_position = True
                is_long = True
                entry_price = df['close'].iloc[i]
            
            elif signals[i] == -1 and not in_position:
                in_position = True
                is_long = False
                entry_price = df['close'].iloc[i]
            
            elif in_position:
                if is_long:
                    pnl = (df['close'].iloc[i] - entry_price) / entry_price
                else:
                    pnl = (entry_price - df['close'].iloc[i]) / entry_price
                
                if pnl >= tp_pct / 100:
                    trades.append(tp_pct / 100)
                    balance += balance * (tp_pct / 100)
                    in_position = False
                elif pnl <= -sl_pct / 100:
                    trades.append(-sl_pct / 100)
                    balance += balance * (-sl_pct / 100)
                    in_position = False
                elif (is_long and signals[i] == -1) or (not is_long and signals[i] == 1):
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
    
    def llm_analyze_strategy(self, results):
        """LLM analyzes and recommends improvements"""
        print()
        print('🤖 LLM Strategy Analysis:')
        print('='*80)
        
        if results['total_return'] > 5:
            print('✅ GOOD: Strategy is profitable')
            print('💡 Recommendation: Continue with current parameters')
        elif results['total_return'] > 0:
            print('⚠️  MARGINAL: Small positive return')
            print('💡 Recommendation: Optimize parameters or add filters')
        else:
            print('❌ POOR: Strategy is losing money')
            print('💡 Recommendation: Re-train model or change approach')
        
        if results['win_rate'] < 50:
            print('⚠️  Win rate below 50% - too risky!')
        
        print()

def main():
    print('🎯 PENGU ML + LLM Learning System')
    print('🎯 Goal: Self-improving, TradingView-compatible strategy')
    print('='*80)
    print()
    
    system = PENGULLMLearningSystem('PENGU/USDT')
    
    # 1. Fetch data
    df = system.fetch_more_data()
    print()
    
    # 2. Engineer features
    df = system.engineer_features(df)
    print()
    
    # 3. Create proper labels
    labels = system.create_proper_labels(df, tp_pct=1.0, sl_pct=2.0)
    print()
    
    # 4. Train with validation
    model = system.train_with_validation(df, labels)
    print()
    
    if model:
        # 5. Backtest
        result = system.backtest_strategy(df, tp_pct=1.0, sl_pct=2.0)
        
        if result:
            print('📊 STRATEGY RESULTS:')
            print('='*80)
            print(f'   Total Return: {result["total_return"]:.2f}%')
            print(f'   Win Rate: {result["win_rate"]:.1f}%')
            print(f'   Trades: {result["trades"]}')
            print(f'   Final Balance: ${result["balance"]:.2f}')
            print()
            
            # 6. LLM Analysis
            system.llm_analyze_strategy(result)
            
            # 7. Save model
            model_file = f'pengu_ml_proper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.joblib'
            joblib.dump(model, model_file)
            print(f'💾 Model saved: {model_file}')
        else:
            print('❌ No trades generated')
    else:
        print('❌ Model training failed')

if __name__ == "__main__":
    main()

