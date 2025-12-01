#!/usr/bin/env python3
"""
16:00 bar'ını test et - 2025-11-20 16:00 Türkiye saati
"""
import pandas as pd
import ccxt
from datetime import datetime
import pytz
from src.atr_supertrend import get_atr_supertrend_signals

def test_16_00_bar():
    """16:00 bar'ını test et"""
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    
    # Türkiye saati 16:00 = UTC 13:00 (kış saati)
    # 2025-11-20 16:00 TR = 2025-11-20 13:00 UTC
    tz_tr = pytz.timezone('Europe/Istanbul')
    tz_utc = pytz.UTC
    
    # 16:00 bar'ını bulmak için yeterli veri çek (200 bar)
    symbol = "ENAUSDT"
    timeframe = "15m"
    limit = 200
    
    print("=" * 80)
    print(f"16:00 Bar Testi - {symbol} {timeframe}")
    print("=" * 80)
    
    # Veri çek
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('time', inplace=True)
    
    # UTC'den Türkiye saatine çevir
    df.index = df.index.tz_localize(tz_utc).tz_convert(tz_tr)
    
    # 16:00 bar'ını bul (2025-11-20 16:00)
    target_date = datetime(2025, 11, 20, 16, 0, 0)
    target_date = tz_tr.localize(target_date)
    
    print(f"\nAranan Bar: {target_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Toplam Bar Sayısı: {len(df)}")
    print(f"İlk Bar: {df.index[0].strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Son Bar: {df.index[-1].strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()
    
    # 16:00 civarındaki bar'ları bul
    mask = (df.index.date == target_date.date()) & (df.index.hour == 16)
    bars_16_00 = df[mask]
    
    if len(bars_16_00) == 0:
        print("⚠️ 16:00 bar'ı bulunamadı!")
        print("\n16:00 civarındaki bar'lar:")
        mask_near = (df.index.date == target_date.date()) & (df.index.hour >= 15) & (df.index.hour <= 17)
        bars_near = df[mask_near]
        if len(bars_near) > 0:
            print(bars_near[['open', 'high', 'low', 'close']])
        return
    
    print(f"✅ 16:00 bar'ı bulundu: {len(bars_16_00)} bar")
    print()
    
    # Her 16:00 bar'ını test et
    for bar_time, bar_data in bars_16_00.iterrows():
        print("=" * 80)
        print(f"Bar Zamanı: {bar_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"OHLC: O={bar_data['open']:.4f} H={bar_data['high']:.4f} "
              f"L={bar_data['low']:.4f} C={bar_data['close']:.4f}")
        print()
        
        # Bu bar'a kadar olan veriyi al
        df_until = df.loc[df.index <= bar_time].copy()
        
        if len(df_until) < 12:  # ATR için minimum veri
            print("⚠️ Yeterli veri yok (minimum 12 bar gerekli)")
            continue
        
        # Sinyal üret
        side, signal_info = get_atr_supertrend_signals(
            df=df_until,
            atr_period=10,
            key_value=3.0,
            super_trend_factor=1.5,
            use_heikin_ashi=True  # Config'de true
        )
        
        print(f"📊 Sinyal: {side if side else 'FLAT'}")
        print()
        
        if signal_info:
            print("Detaylı Bilgiler:")
            print(f"  ATR Trailing Stop: {signal_info.get('atr_trailing_stop', 0):.4f}")
            print(f"  Current Price (Close): {signal_info.get('current_price', 0):.4f}")
            print(f"  Super Trend: {signal_info.get('super_trend', 0):.4f}")
            print(f"  Position: {signal_info.get('position', 0)}")
            print()
            print("Sinyal Koşulları:")
            print(f"  Buy Signal (ATR): {signal_info.get('buy_signal', False)}")
            print(f"    - src > xATRTrailingStop: {bar_data['close']:.4f} > {signal_info.get('atr_trailing_stop', 0):.4f} = {bar_data['close'] > signal_info.get('atr_trailing_stop', 0)}")
            print(f"    - above (crossover): {signal_info.get('above', False)}")
            print()
            print(f"  Sell Signal (ATR): {signal_info.get('sell_signal', False)}")
            print(f"    - src < xATRTrailingStop: {bar_data['close']:.4f} < {signal_info.get('atr_trailing_stop', 0):.4f} = {bar_data['close'] < signal_info.get('atr_trailing_stop', 0)}")
            print(f"    - below (crossover): {signal_info.get('below', False)}")
            print()
            print(f"  Buy Super Trend (Alert): {signal_info.get('buy_super_trend', False)}")
            print(f"  Sell Super Trend (Alert): {signal_info.get('sell_super_trend', False)}")
            print()
            
            # Önceki bar'ı da göster
            if len(df_until) >= 2:
                prev_bar = df_until.iloc[-2]
                prev_time = df_until.index[-2]
                print(f"Önceki Bar ({prev_time.strftime('%H:%M')}):")
                print(f"  Close: {prev_bar['close']:.4f}")
                print()
    
    print("=" * 80)
    print("Pine Script Mantığı:")
    print("  buy = src > xATRTrailingStop and above")
    print("  sell = src < xATRTrailingStop and below")
    print("=" * 80)

if __name__ == "__main__":
    test_16_00_bar()

