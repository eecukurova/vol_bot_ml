#!/usr/bin/env python3
"""
16:00 bar'ını detaylı test et - Heikin Ashi ile
"""
import pandas as pd
import ccxt
from datetime import datetime
import pytz
from src.atr_supertrend import get_atr_supertrend_signals, calculate_heikin_ashi

def test_16_00_detailed():
    """16:00 bar'ını detaylı test et"""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    
    tz_tr = pytz.timezone('Europe/Istanbul')
    tz_utc = pytz.UTC
    
    symbol = "XRPUSDT"
    timeframe = "15m"
    limit = 200
    
    print("=" * 80)
    print(f"16:00 Bar Detaylı Testi - {symbol} {timeframe}")
    print("=" * 80)
    
    # Veri çek
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    df.index = df.index.tz_localize(tz_utc).tz_convert(tz_tr)
    
    # 15:45 ve 16:00 bar'larını bul
    target_date = datetime(2025, 11, 20, 16, 0, 0)
    target_date = tz_tr.localize(target_date)
    
    mask_15_45 = (df.index.date == target_date.date()) & (df.index.hour == 15) & (df.index.minute == 45)
    mask_16_00 = (df.index.date == target_date.date()) & (df.index.hour == 16) & (df.index.minute == 0)
    
    bar_15_45 = df[mask_15_45]
    bar_16_00 = df[mask_16_00]
    
    if len(bar_15_45) == 0 or len(bar_16_00) == 0:
        print("⚠️ Bar'lar bulunamadı!")
        return
    
    bar_15_45 = bar_15_45.iloc[0]
    bar_16_00 = bar_16_00.iloc[0]
    
    bar_15_45_time = bar_15_45.name
    bar_16_00_time = bar_16_00.name
    
    print(f"\n15:45 Bar: {bar_15_45_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  OHLC: O={bar_15_45['open']:.4f} H={bar_15_45['high']:.4f} "
          f"L={bar_15_45['low']:.4f} C={bar_15_45['close']:.4f}")
    print(f"\n16:00 Bar: {bar_16_00_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  OHLC: O={bar_16_00['open']:.4f} H={bar_16_00['high']:.4f} "
          f"L={bar_16_00['low']:.4f} C={bar_16_00['close']:.4f}")
    print()
    
    # Her iki bar için test et (Hem normal hem Heikin Ashi)
    for bar_name, bar_time, bar_data in [("15:45", bar_15_45_time, bar_15_45), 
                                          ("16:00", bar_16_00_time, bar_16_00)]:
        print("=" * 80)
        print(f"{bar_name} Bar Testi")
        print("=" * 80)
        
        df_until = df.loc[df.index <= bar_time].copy()
        
        if len(df_until) < 12:
            continue
        
        # Normal (Heikin Ashi olmadan)
        print("\n📊 NORMAL CANDLES (Heikin Ashi = False):")
        side_normal, signal_normal = get_atr_supertrend_signals(
            df=df_until,
            atr_period=10,
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=False
        )
        
        print(f"  Sinyal: {side_normal if side_normal else 'FLAT'}")
        if signal_normal:
            print(f"  Buy Signal: {signal_normal.get('buy_signal', False)}")
            print(f"  Sell Signal: {signal_normal.get('sell_signal', False)}")
            print(f"  ATR Trailing Stop: {signal_normal.get('atr_trailing_stop', 0):.4f}")
            print(f"  Close: {bar_data['close']:.4f}")
            print(f"  Above: {signal_normal.get('above', False)}")
            print(f"  Below: {signal_normal.get('below', False)}")
        
        # Heikin Ashi ile
        print("\n📊 HEIKIN ASHI CANDLES (Heikin Ashi = True):")
        side_ha, signal_ha = get_atr_supertrend_signals(
            df=df_until,
            atr_period=10,
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=True
        )
        
        print(f"  Sinyal: {side_ha if side_ha else 'FLAT'}")
        if signal_ha:
            print(f"  Buy Signal: {signal_ha.get('buy_signal', False)}")
            print(f"  Sell Signal: {signal_ha.get('sell_signal', False)}")
            print(f"  ATR Trailing Stop: {signal_ha.get('atr_trailing_stop', 0):.4f}")
            
            # Heikin Ashi close değerini göster
            ha_df = calculate_heikin_ashi(df_until)
            ha_close = ha_df['ha_close'].iloc[-1]
            print(f"  HA Close (src): {ha_close:.4f}")
            print(f"  Normal Close: {bar_data['close']:.4f}")
            print(f"  Above: {signal_ha.get('above', False)}")
            print(f"  Below: {signal_ha.get('below', False)}")
        
        print()
    
    # Önceki birkaç bar'ı da göster
    print("=" * 80)
    print("Önceki Bar'lar (15:00 - 16:00 arası):")
    print("=" * 80)
    mask_range = (df.index.date == target_date.date()) & (df.index.hour >= 15) & (df.index.hour <= 16)
    bars_range = df[mask_range].sort_index()
    
    for bar_time, bar_data in bars_range.iterrows():
        df_until = df.loc[df.index <= bar_time].copy()
        if len(df_until) < 12:
            continue
        
        side, signal = get_atr_supertrend_signals(
            df=df_until,
            atr_period=10,
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=True
        )
        
        signal_marker = "🟢 BUY" if side == "LONG" else "🔴 SELL" if side == "SHORT" else "⚪ FLAT"
        print(f"{bar_time.strftime('%H:%M')} | C={bar_data['close']:.4f} | {signal_marker}")

if __name__ == "__main__":
    test_16_00_detailed()

