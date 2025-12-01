#!/usr/bin/env python3
"""
14:30 bar'ını detaylı test et - SELL sinyali var!
"""
import pandas as pd
import ccxt
from datetime import datetime
import pytz
from src.atr_supertrend import get_atr_supertrend_signals

def test_14_30_detailed():
    """14:30 bar'ını detaylı test et"""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    
    tz_tr = pytz.timezone('Europe/Istanbul')
    tz_utc = pytz.UTC
    
    symbol = "ENAUSDT"
    timeframe = "15m"
    limit = 200
    
    print("=" * 80)
    print(f"14:30 Bar Detaylı Analizi - SELL Sinyali")
    print("=" * 80)
    
    # Veri çek
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    df.index = df.index.tz_localize(tz_utc).tz_convert(tz_tr)
    
    # 14:30 bar'ını bul
    target_date = datetime(2025, 11, 20, 14, 30, 0)
    target_date = tz_tr.localize(target_date)
    
    mask_14_30 = (df.index.date == target_date.date()) & (df.index.hour == 14) & (df.index.minute == 30)
    bar_14_30 = df[mask_14_30]
    
    if len(bar_14_30) == 0:
        print("⚠️ 14:30 bar'ı bulunamadı!")
        return
    
    bar_14_30_data = bar_14_30.iloc[0]
    bar_14_30_time = bar_14_30_data.name
    
    print(f"\n14:30 Bar (Türkiye Saati): {bar_14_30_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  OHLC: O={bar_14_30_data['open']:.4f} H={bar_14_30_data['high']:.4f} "
          f"L={bar_14_30_data['low']:.4f} C={bar_14_30_data['close']:.4f}")
    print()
    
    # UTC zamanını da göster
    bar_14_30_utc = bar_14_30_time.astimezone(tz_utc)
    print(f"14:30 Bar (UTC): {bar_14_30_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()
    
    df_until = df.loc[df.index <= bar_14_30_time].copy()
    
    if len(df_until) < 12:
        print("⚠️ Yeterli veri yok")
        return
    
    # Sinyal üret
    side, signal = get_atr_supertrend_signals(
        df=df_until,
        atr_period=11,
        key_value=3.0,
        super_trend_factor=1.5,
        use_heikin_ashi=True
    )
    
    print("=" * 80)
    print(f"📊 SİNYAL: {side if side else 'FLAT'}")
    print("=" * 80)
    
    if signal:
        print("\nDetaylı Bilgiler:")
        print(f"  ATR Trailing Stop: {signal.get('atr_trailing_stop', 0):.4f}")
        print(f"  Current Price: {signal.get('current_price', 0):.4f}")
        print(f"  Super Trend: {signal.get('super_trend', 0):.4f}")
        print(f"  Position: {signal.get('position', 0)}")
        print()
        print("Sinyal Koşulları:")
        print(f"  Buy Signal: {signal.get('buy_signal', False)}")
        print(f"  Sell Signal: {signal.get('sell_signal', False)} ✅")
        print(f"  Above: {signal.get('above', False)}")
        print(f"  Below: {signal.get('below', False)} ✅")
        print()
        print("Pine Script Mantığı:")
        print("  sell = src < xATRTrailingStop and below")
        print(f"    - src < Stop: {signal.get('current_price', 0):.4f} < {signal.get('atr_trailing_stop', 0):.4f} = {signal.get('current_price', 0) < signal.get('atr_trailing_stop', 0)}")
        print(f"    - below (crossover): {signal.get('below', False)}")
    
    print()
    print("=" * 80)
    print("Önceki ve Sonraki Bar'lar:")
    print("=" * 80)
    
    # Önceki ve sonraki birkaç bar'ı göster
    mask_range = (df.index.date == target_date.date()) & (df.index.hour >= 14) & (df.index.hour <= 15)
    bars_range = df[mask_range].sort_index()
    
    for bar_time, bar_data in bars_range.iterrows():
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
        
        signal_marker = "🟢 BUY" if side == "LONG" else "🔴 SELL" if side == "SHORT" else "⚪ FLAT"
        highlight = " ⭐" if side == "SHORT" else ""
        print(f"{bar_time.strftime('%H:%M')} | C={bar_data['close']:.4f} | {signal_marker}{highlight}")

if __name__ == "__main__":
    test_14_30_detailed()

