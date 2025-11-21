#!/usr/bin/env python3
"""
15:30 bar'ını TradingView ayarlarıyla test et:
- ATR Period: 11 (bizim kodda 10 kullanıyorduk!)
- Key Value: 3
- Heikin Ashi: True
- Multiplier: 1.5
"""
import pandas as pd
import ccxt
from datetime import datetime
import pytz
from src.atr_supertrend import get_atr_supertrend_signals

def test_15_30_with_tradingview_settings():
    """15:30 bar'ını TradingView ayarlarıyla test et"""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    
    tz_tr = pytz.timezone('Europe/Istanbul')
    tz_utc = pytz.UTC
    
    symbol = "XRPUSDT"
    timeframe = "15m"
    limit = 200
    
    print("=" * 80)
    print(f"15:30 Bar Testi - TradingView Ayarlarıyla")
    print("=" * 80)
    print("TradingView Ayarları:")
    print("  - Key Value: 3")
    print("  - ATR Period: 11 ⚠️ (Bizim kodda 10 kullanıyorduk!)")
    print("  - Heikin Ashi: True")
    print("  - Multiplier: 1.5")
    print("=" * 80)
    
    # Veri çek
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    df.index = df.index.tz_localize(tz_utc).tz_convert(tz_tr)
    
    # 15:30 bar'ını bul
    target_date = datetime(2025, 11, 20, 15, 30, 0)
    target_date = tz_tr.localize(target_date)
    
    mask_15_30 = (df.index.date == target_date.date()) & (df.index.hour == 15) & (df.index.minute == 30)
    bar_15_30 = df[mask_15_30]
    
    if len(bar_15_30) == 0:
        print("⚠️ 15:30 bar'ı bulunamadı!")
        return
    
    bar_15_30_data = bar_15_30.iloc[0]
    bar_15_30_time = bar_15_30_data.name
    
    print(f"\n15:30 Bar: {bar_15_30_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  OHLC: O={bar_15_30_data['open']:.4f} H={bar_15_30_data['high']:.4f} "
          f"L={bar_15_30_data['low']:.4f} C={bar_15_30_data['close']:.4f}")
    print()
    
    df_until = df.loc[df.index <= bar_15_30_time].copy()
    
    if len(df_until) < 12:
        print("⚠️ Yeterli veri yok")
        return
    
    # ÖNCE ATR Period = 10 ile test et (eski ayar)
    print("📊 ATR Period = 10 (Eski Ayar):")
    side_10, signal_10 = get_atr_supertrend_signals(
        df=df_until,
        atr_period=10,
        key_value=3.0,
        super_trend_factor=1.5,
        use_heikin_ashi=True
    )
    print(f"  Sinyal: {side_10 if side_10 else 'FLAT'}")
    if signal_10:
        print(f"  Buy Signal: {signal_10.get('buy_signal', False)}")
        print(f"  Sell Signal: {signal_10.get('sell_signal', False)}")
        print(f"  ATR Trailing Stop: {signal_10.get('atr_trailing_stop', 0):.4f}")
    print()
    
    # SONRA ATR Period = 11 ile test et (TradingView ayarı)
    print("📊 ATR Period = 11 (TradingView Ayarı):")
    side_11, signal_11 = get_atr_supertrend_signals(
        df=df_until,
        atr_period=11,  # ⚠️ TradingView'de 11!
        key_value=3.0,
        super_trend_factor=1.5,
        use_heikin_ashi=True
    )
    print(f"  Sinyal: {side_11 if side_11 else 'FLAT'}")
    if signal_11:
        print(f"  Buy Signal: {signal_11.get('buy_signal', False)}")
        print(f"  Sell Signal: {signal_11.get('sell_signal', False)}")
        print(f"  ATR Trailing Stop: {signal_11.get('atr_trailing_stop', 0):.4f}")
        print(f"  Current Price: {signal_11.get('current_price', 0):.4f}")
        print(f"  Above: {signal_11.get('above', False)}")
        print(f"  Below: {signal_11.get('below', False)}")
    print()
    
    # 16:00 bar'ını da test et
    mask_16_00 = (df.index.date == target_date.date()) & (df.index.hour == 16) & (df.index.minute == 0)
    bar_16_00 = df[mask_16_00]
    
    if len(bar_16_00) > 0:
        bar_16_00_data = bar_16_00.iloc[0]
        bar_16_00_time = bar_16_00_data.name
        df_until_16 = df.loc[df.index <= bar_16_00_time].copy()
        
        print("=" * 80)
        print(f"16:00 Bar: {bar_16_00_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  OHLC: O={bar_16_00_data['open']:.4f} H={bar_16_00_data['high']:.4f} "
              f"L={bar_16_00_data['low']:.4f} C={bar_16_00_data['close']:.4f}")
        print()
        
        print("📊 ATR Period = 11 (TradingView Ayarı):")
        side_16, signal_16 = get_atr_supertrend_signals(
            df=df_until_16,
            atr_period=11,
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=True
        )
        print(f"  Sinyal: {side_16 if side_16 else 'FLAT'}")
        if signal_16:
            print(f"  Buy Signal: {signal_16.get('buy_signal', False)}")
            print(f"  Sell Signal: {signal_16.get('sell_signal', False)}")
            print(f"  ATR Trailing Stop: {signal_16.get('atr_trailing_stop', 0):.4f}")
            print(f"  Current Price: {signal_16.get('current_price', 0):.4f}")
    
    print()
    print("=" * 80)
    print("SONUÇ:")
    print("=" * 80)
    if side_11 == "SHORT":
        print("✅ 15:30'da SELL sinyali bulundu (ATR Period = 11 ile)")
    else:
        print("❌ 15:30'da sinyal bulunamadı")
    print("=" * 80)

if __name__ == "__main__":
    test_15_30_with_tradingview_settings()

