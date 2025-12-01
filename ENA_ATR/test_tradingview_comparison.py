#!/usr/bin/env python3
"""
TradingView Pine Script ile Python kodumuzun karşılaştırması
"""
import sys
import pandas as pd
import ccxt
from datetime import datetime
import pytz
from src.atr_supertrend import get_atr_supertrend_signals

def fetch_and_test(symbol="ENAUSDT", timeframe="15m", limit=200):
    """Binance'den veri çek ve sinyalleri test et"""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    
    # Veri çek
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    
    # Türkiye saatine çevir
    tz_utc = pytz.UTC
    tz_tr = pytz.timezone('Europe/Istanbul')
    df.index = df.index.tz_localize(tz_utc).tz_convert(tz_tr)
    
    print("=" * 80)
    print(f"TradingView Pine Script vs Python Kod Karşılaştırması")
    print("=" * 80)
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Parametreler:")
    print(f"  - Key Value (a): 3.0")
    print(f"  - ATR Period (c): 10")
    print(f"  - Heikin Ashi (h): false")
    print(f"  - Super Trend Factor: 1.5")
    print()
    
    # Son 10 bar'ı göster
    print("Son 10 Bar (Türkiye Saati):")
    print(df[['open', 'high', 'low', 'close']].tail(10))
    print()
    
    # Her bar için sinyal kontrolü
    print("Bar Bazında Sinyal Analizi (Son 10 Bar):")
    print("-" * 80)
    
    for i in range(max(0, len(df) - 10), len(df)):
        df_until = df.iloc[:i+1]
        
        if len(df_until) < 12:  # ATR için minimum veri
            continue
        
        side, signal_info = get_atr_supertrend_signals(
            df=df_until,
            atr_period=10,
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=False  # TradingView'de false
        )
        
        bar_time = df_until.index[-1]
        bar_data = df_until.iloc[-1]
        
        signal_marker = ""
        if side == "LONG":
            signal_marker = "🟢 BUY"
        elif side == "SHORT":
            signal_marker = "🔴 SELL"
        else:
            signal_marker = "⚪ FLAT"
        
        print(f"{bar_time.strftime('%Y-%m-%d %H:%M:%S')} | "
              f"O={bar_data['open']:.4f} H={bar_data['high']:.4f} "
              f"L={bar_data['low']:.4f} C={bar_data['close']:.4f} | "
              f"{signal_marker}")
        
        if signal_info:
            print(f"  ATR Trailing Stop: {signal_info.get('atr_trailing_stop', 0):.4f}")
            print(f"  Current Price: {signal_info.get('current_price', 0):.4f}")
            print(f"  Position: {signal_info.get('position', 0)}")
            print(f"  Buy Signal: {signal_info.get('buy_signal', False)}")
            print(f"  Sell Signal: {signal_info.get('sell_signal', False)}")
            print(f"  Above: {signal_info.get('above', False)}")
            print(f"  Below: {signal_info.get('below', False)}")
            print()
    
    # Son bar için detaylı analiz
    print("=" * 80)
    print("Son Bar Detaylı Analiz:")
    print("-" * 80)
    
    side, signal_info = get_atr_supertrend_signals(
        df=df,
        atr_period=10,
        key_value=3.0,
        super_trend_factor=1.5,
        use_heikin_ashi=False
    )
    
    last_bar = df.iloc[-1]
    last_time = df.index[-1]
    
    print(f"Bar Zamanı: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"OHLC: O={last_bar['open']:.4f} H={last_bar['high']:.4f} "
          f"L={last_bar['low']:.4f} C={last_bar['close']:.4f}")
    print()
    
    if signal_info:
        print(f"Sinyal: {side if side else 'FLAT'}")
        print(f"ATR Trailing Stop: {signal_info.get('atr_trailing_stop', 0):.4f}")
        print(f"Current Price: {signal_info.get('current_price', 0):.4f}")
        print(f"Super Trend: {signal_info.get('super_trend', 0):.4f}")
        print(f"Position: {signal_info.get('position', 0)}")
        print(f"Buy Signal: {signal_info.get('buy_signal', False)}")
        print(f"Sell Signal: {signal_info.get('sell_signal', False)}")
        print(f"Buy Super Trend: {signal_info.get('buy_super_trend', False)}")
        print(f"Sell Super Trend: {signal_info.get('sell_super_trend', False)}")
        print(f"Above (crossover): {signal_info.get('above', False)}")
        print(f"Below (crossover): {signal_info.get('below', False)}")
    
    print()
    print("=" * 80)
    print("TradingView Pine Script Mantığı:")
    print("  buy = src > xATRTrailingStop and above (crossover(ema, xATRTrailingStop))")
    print("  sell = src < xATRTrailingStop and below (crossover(xATRTrailingStop, ema))")
    print("=" * 80)

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "ENAUSDT"
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "15m"
    
    fetch_and_test(symbol=symbol, timeframe=timeframe)

