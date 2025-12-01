#!/usr/bin/env python3
"""
16:00 bar'ını EMA crossover detayıyla test et
"""
import pandas as pd
import numpy as np
import ccxt
from datetime import datetime
import pytz
from src.atr_supertrend import get_atr_supertrend_signals, calculate_atr_trailing_stop, calculate_heikin_ashi

def test_16_00_crossover():
    """16:00 bar'ını EMA crossover detayıyla test et"""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    
    tz_tr = pytz.timezone('Europe/Istanbul')
    tz_utc = pytz.UTC
    
    symbol = "ENAUSDT"
    timeframe = "15m"
    limit = 200
    
    print("=" * 80)
    print(f"16:00 Bar EMA Crossover Detaylı Analizi")
    print("=" * 80)
    
    # Veri çek
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    df.index = df.index.tz_localize(tz_utc).tz_convert(tz_tr)
    
    # 16:00 ve sonraki birkaç bar'ı test et
    target_date = datetime(2025, 11, 20, 16, 0, 0)
    target_date = tz_tr.localize(target_date)
    
    mask_range = (df.index.date == target_date.date()) & (df.index.hour >= 15) & (df.index.hour <= 17)
    bars_range = df[mask_range].sort_index()
    
    print(f"\n15:00 - 17:00 arası bar'lar:")
    print("=" * 80)
    
    for i, (bar_time, bar_data) in enumerate(bars_range.iterrows()):
        df_until = df.loc[df.index <= bar_time].copy()
        
        if len(df_until) < 12:
            continue
        
        # Heikin Ashi hesapla
        ha_df = calculate_heikin_ashi(df_until)
        src = ha_df['ha_close']
        
        # ATR Trailing Stop hesapla
        xATRTrailingStop, pos, src_series = calculate_atr_trailing_stop(
            df=df_until,
            atr_period=10,
            key_value=3.0,
            use_heikin_ashi=True
        )
        
        # EMA(1) hesapla
        ema_src = src.ewm(span=1, adjust=False).mean()
        
        # Mevcut ve önceki değerler
        curr_src = src.iloc[-1]
        prev_src = src.iloc[-2] if len(src) > 1 else src.iloc[-1]
        
        curr_stop = xATRTrailingStop.iloc[-1]
        prev_stop = xATRTrailingStop.iloc[-2] if len(xATRTrailingStop) > 1 else xATRTrailingStop.iloc[-1]
        
        curr_ema = ema_src.iloc[-1]
        prev_ema = ema_src.iloc[-2] if len(ema_src) > 1 else ema_src.iloc[-1]
        
        # Crossover kontrolü
        above = curr_ema > curr_stop and prev_ema <= prev_stop
        below = curr_stop > curr_ema and prev_stop <= prev_ema
        
        # Sinyal koşulları
        buy_signal = curr_src > curr_stop and above
        sell_signal = curr_src < curr_stop and below
        
        # Sinyal üret
        side, signal_info = get_atr_supertrend_signals(
            df=df_until,
            atr_period=10,
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=True
        )
        
        signal_marker = "🟢 BUY" if side == "LONG" else "🔴 SELL" if side == "SHORT" else "⚪ FLAT"
        
        print(f"\n{bar_time.strftime('%H:%M')} Bar:")
        print(f"  Close: {bar_data['close']:.4f} | HA Close (src): {curr_src:.4f}")
        print(f"  ATR Trailing Stop: {curr_stop:.4f}")
        print(f"  EMA(1): {curr_ema:.4f}")
        print(f"  Position: {int(pos.iloc[-1])}")
        print()
        print(f"  Önceki Bar:")
        print(f"    EMA: {prev_ema:.4f}, Stop: {prev_stop:.4f}")
        print(f"    EMA > Stop: {prev_ema > prev_stop}")
        print(f"    EMA <= Stop: {prev_ema <= prev_stop}")
        print()
        print(f"  Mevcut Bar:")
        print(f"    EMA: {curr_ema:.4f}, Stop: {curr_stop:.4f}")
        print(f"    EMA > Stop: {curr_ema > curr_stop}")
        print(f"    EMA <= Stop: {curr_ema <= curr_stop}")
        print()
        print(f"  Crossover:")
        print(f"    Above (EMA crosses above Stop): {above}")
        print(f"    Below (Stop crosses above EMA): {below}")
        print()
        print(f"  Sinyal Koşulları:")
        print(f"    src > Stop: {curr_src:.4f} > {curr_stop:.4f} = {curr_src > curr_stop}")
        print(f"    src < Stop: {curr_src:.4f} < {curr_stop:.4f} = {curr_src < curr_stop}")
        print(f"    Buy Signal: {buy_signal}")
        print(f"    Sell Signal: {sell_signal}")
        print()
        print(f"  📊 SONUÇ: {signal_marker}")
        print("-" * 80)

if __name__ == "__main__":
    test_16_00_crossover()

