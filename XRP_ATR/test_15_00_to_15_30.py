#!/usr/bin/env python3
"""
15:00 - 15:30 arası tüm bar'ları test et (ATR Period = 11)
"""
import pandas as pd
import ccxt
from datetime import datetime
import pytz
from src.atr_supertrend import get_atr_supertrend_signals

def test_15_00_to_15_30():
    """15:00 - 15:30 arası tüm bar'ları test et"""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    
    tz_tr = pytz.timezone('Europe/Istanbul')
    tz_utc = pytz.UTC
    
    symbol = "XRPUSDT"
    timeframe = "15m"
    limit = 200
    
    print("=" * 80)
    print(f"15:00 - 15:30 Arası Bar'lar - TradingView Ayarları (ATR Period = 11)")
    print("=" * 80)
    
    # Veri çek
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    df.index = df.index.tz_localize(tz_utc).tz_convert(tz_tr)
    
    # 15:00 - 15:30 arası bar'ları bul
    target_date = datetime(2025, 11, 20, 15, 0, 0)
    target_date = tz_tr.localize(target_date)
    
    mask_range = (df.index.date == target_date.date()) & (df.index.hour == 15) & (df.index.minute <= 30)
    bars_range = df[mask_range].sort_index()
    
    print(f"\n15:00 - 15:30 arası bar'lar:")
    print("=" * 80)
    
    for bar_time, bar_data in bars_range.iterrows():
        df_until = df.loc[df.index <= bar_time].copy()
        
        if len(df_until) < 12:
            continue
        
        side, signal = get_atr_supertrend_signals(
            df=df_until,
            atr_period=11,  # TradingView ayarı
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=True
        )
        
        signal_marker = "🟢 BUY" if side == "LONG" else "🔴 SELL" if side == "SHORT" else "⚪ FLAT"
        
        print(f"\n{bar_time.strftime('%H:%M')} Bar:")
        print(f"  Close: {bar_data['close']:.4f}")
        print(f"  Sinyal: {signal_marker}")
        
        if signal:
            print(f"  ATR Trailing Stop: {signal.get('atr_trailing_stop', 0):.4f}")
            print(f"  Buy Signal: {signal.get('buy_signal', False)}")
            print(f"  Sell Signal: {signal.get('sell_signal', False)}")
            print(f"  Above: {signal.get('above', False)}")
            print(f"  Below: {signal.get('below', False)}")
    
    print()
    print("=" * 80)
    print("14:00 - 16:00 arası tüm bar'lar (geniş görünüm):")
    print("=" * 80)
    
    mask_wide = (df.index.date == target_date.date()) & (df.index.hour >= 14) & (df.index.hour <= 16)
    bars_wide = df[mask_wide].sort_index()
    
    for bar_time, bar_data in bars_wide.iterrows():
        df_until = df.loc[df.index <= bar_time].copy()
        if len(df_until) < 12:
            continue
        
        side, signal = get_atr_supertrend_signals(
            df=df_until,
            atr_period=11,
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=True
        )
        
        signal_marker = "🟢 BUY" if side == "LONG" else "🔴 SELL" if side == "SHORT" else "⚪"
        print(f"{bar_time.strftime('%H:%M')} | C={bar_data['close']:.4f} | {signal_marker}")

if __name__ == "__main__":
    test_15_00_to_15_30()

