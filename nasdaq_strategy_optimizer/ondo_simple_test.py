#!/usr/bin/env python3
"""
ONDO Simple Test - Debug optimization issues
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ondo_data():
    """Test ONDO data loading"""
    logger.info("🔍 Testing ONDO data loading...")
    
    try:
        ticker = yf.Ticker("ONDO-USD")
        data = ticker.history(period="1mo", interval="1h")
        
        if data.empty:
            logger.error("❌ No data found")
            return None
            
        logger.info(f"✅ Data loaded: {len(data)} candles")
        logger.info(f"📅 Date range: {data.index[0]} to {data.index[-1]}")
        logger.info(f"📊 Columns: {list(data.columns)}")
        
        # Check for NaN values
        nan_counts = data.isnull().sum()
        logger.info(f"🔍 NaN values: {nan_counts.to_dict()}")
        
        # Check price range
        logger.info(f"💰 Price range: ${data['Close'].min():.4f} - ${data['Close'].max():.4f}")
        
        return data
        
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        return None

def test_simple_strategy(data):
    """Test simple strategy logic"""
    logger.info("🧪 Testing simple strategy logic...")
    
    try:
        # Simple moving average crossover
        data['sma_10'] = data['Close'].rolling(window=10).mean()
        data['sma_20'] = data['Close'].rolling(window=20).mean()
        
        # Generate signals
        data['signal'] = 0
        data.loc[data['sma_10'] > data['sma_20'], 'signal'] = 1
        data.loc[data['sma_10'] < data['sma_20'], 'signal'] = -1
        
        # Count signals
        signals = data['signal'].diff().fillna(0)
        buy_signals = (signals == 1).sum()
        sell_signals = (signals == -1).sum()
        
        logger.info(f"📈 Buy signals: {buy_signals}")
        logger.info(f"📉 Sell signals: {sell_signals}")
        
        # Simple backtest
        capital = 10000
        position = 0
        trades = []
        
        for i in range(len(data)):
            if signals.iloc[i] == 1 and position == 0:  # Buy
                position = capital * 0.2 / data['Close'].iloc[i]
                capital -= capital * 0.2
                trades.append({'type': 'buy', 'price': data['Close'].iloc[i], 'time': data.index[i]})
            elif signals.iloc[i] == -1 and position > 0:  # Sell
                pnl = position * data['Close'].iloc[i] - capital * 0.2
                capital += position * data['Close'].iloc[i]
                position = 0
                trades.append({'type': 'sell', 'price': data['Close'].iloc[i], 'pnl': pnl, 'time': data.index[i]})
        
        logger.info(f"💰 Final capital: ${capital:.2f}")
        logger.info(f"📊 Total trades: {len(trades)}")
        
        if trades:
            total_pnl = sum([t.get('pnl', 0) for t in trades])
            logger.info(f"💵 Total P&L: ${total_pnl:.2f}")
            logger.info(f"📈 Return: {(total_pnl / 10000) * 100:.2f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Strategy test error: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🚀 Starting ONDO Simple Test")
    
    # Test data loading
    data = test_ondo_data()
    if data is None:
        logger.error("❌ Data loading failed")
        return
    
    # Test strategy
    success = test_simple_strategy(data)
    if success:
        logger.info("✅ Simple strategy test passed")
    else:
        logger.error("❌ Simple strategy test failed")
    
    logger.info("🎉 Test completed")

if __name__ == "__main__":
    main()
