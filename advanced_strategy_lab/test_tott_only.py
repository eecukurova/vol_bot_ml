#!/usr/bin/env python3
"""
TOTT Strategy - Only Original Logic (No SUPERTREND/ATR combination)
"""

import pandas as pd
import numpy as np
from src.data.nasdaq_provider import NASDAQDataProvider

def calculate_var(src, length):
    """Variable Adaptive Rate moving average"""
    valpha = 2 / (length + 1)
    
    # Price changes
    vud1 = np.where(src > src.shift(1), src - src.shift(1), 0)
    vdd1 = np.where(src < src.shift(1), src.shift(1) - src, 0)
    
    # Sum over 9 periods
    vUD = pd.Series(vud1).rolling(window=9).sum()
    vDD = pd.Series(vdd1).rolling(window=9).sum()
    
    # CMO calculation
    vCMO = (vUD - vDD) / (vUD + vDD)
    vCMO = vCMO.fillna(0)
    
    # VAR calculation
    VAR = pd.Series(index=src.index, dtype=float)
    VAR.iloc[0] = src.iloc[0]
    
    for i in range(1, len(src)):
        VAR.iloc[i] = valpha * abs(vCMO.iloc[i]) * src.iloc[i] + (1 - valpha * abs(vCMO.iloc[i])) * VAR.iloc[i-1]
    
    return VAR

def test_tott_only():
    print('🚀 TOTT STRATEJİSİ - SADECE ORİJİNAL MANTIK')
    print('='*60)

    # TOTT parametreleri (Pine Script'ten)
    params = {
        'length': 40,
        'percent': 1.0,
        'coeff': 0.001,
        'mav': 'VAR'  # Variable Adaptive Rate
    }

    print(f'📊 TOTT Parametreleri:')
    print(f'   Length: {params["length"]}')
    print(f'   Percent: {params["percent"]}')
    print(f'   Coeff: {params["coeff"]}')
    print(f'   MA Type: {params["mav"]}')
    print()

    # MSFT verisi al
    provider = NASDAQDataProvider()
    data = provider.fetch_data('MSFT', period='1y', interval='1d')

    # Fix data format
    data = data.reset_index()
    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
        data.set_index('date', inplace=True)

    print(f'📊 MSFT Veri: {len(data)} gün')
    print(f'📅 Tarih aralığı: {data.index[0].strftime("%Y-%m-%d")} - {data.index[-1].strftime("%Y-%m-%d")}')
    print()

    # Calculate VAR
    data['VAR'] = calculate_var(data['close'], params['length'])

    # Calculate fark (difference)
    data['fark'] = data['VAR'] * params['percent'] * 0.01

    # Calculate long and short stops
    data['longStop'] = data['VAR'] - data['fark']
    data['shortStop'] = data['VAR'] + data['fark']

    # Calculate trailing stops
    data['longStopPrev'] = data['longStop'].shift(1)
    data['shortStopPrev'] = data['shortStop'].shift(1)

    # Update stops based on trend
    for i in range(1, len(data)):
        if data['VAR'].iloc[i] > data['longStopPrev'].iloc[i]:
            data['longStop'].iloc[i] = max(data['longStop'].iloc[i], data['longStopPrev'].iloc[i])
        if data['VAR'].iloc[i] < data['shortStopPrev'].iloc[i]:
            data['shortStop'].iloc[i] = min(data['shortStop'].iloc[i], data['shortStopPrev'].iloc[i])

    # Calculate direction
    data['dir'] = 1
    for i in range(1, len(data)):
        prev_dir = data['dir'].iloc[i-1]
        if prev_dir == -1 and data['VAR'].iloc[i] > data['shortStopPrev'].iloc[i]:
            data['dir'].iloc[i] = 1
        elif prev_dir == 1 and data['VAR'].iloc[i] < data['longStopPrev'].iloc[i]:
            data['dir'].iloc[i] = -1
        else:
            data['dir'].iloc[i] = prev_dir

    # Calculate MT (Moving Trend)
    data['MT'] = np.where(data['dir'] == 1, data['longStop'], data['shortStop'])

    # Calculate OTT (Optimized Trend Tracker)
    data['OTT'] = np.where(
        data['VAR'] > data['MT'],
        data['MT'] * (200 + params['percent']) / 200,
        data['MT'] * (200 - params['percent']) / 200
    )

    # Calculate OTT up and down
    data['OTTup'] = data['OTT'] * (1 + params['coeff'])
    data['OTTdn'] = data['OTT'] * (1 - params['coeff'])

    # Shift OTT for signal calculation (2 periods)
    data['OTTup_shifted'] = data['OTTup'].shift(2)
    data['OTTdn_shifted'] = data['OTTdn'].shift(2)

    print('🔍 TOTT İNDİKATÖRLERİ HESAPLANDI')
    print(f'   VAR: {data["VAR"].iloc[-1]:.2f}')
    print(f'   OTT: {data["OTT"].iloc[-1]:.2f}')
    print(f'   OTTup: {data["OTTup"].iloc[-1]:.2f}')
    print(f'   OTTdn: {data["OTTdn"].iloc[-1]:.2f}')
    print(f'   Direction: {data["dir"].iloc[-1]}')
    print()

    # Generate signals
    signals = []
    for i in range(1, len(data)):
        current = data.iloc[i]
        previous = data.iloc[i-1]
        
        # Buy signal: VAR crosses above OTTup
        if (current['VAR'] > current['OTTup_shifted'] and 
            previous['VAR'] <= previous['OTTup_shifted']):
            signals.append({
                'timestamp': current.name,
                'signal_type': 'BUY',
                'price': current['close'],
                'var': current['VAR'],
                'ottup': current['OTTup_shifted']
            })
        
        # Sell signal: VAR crosses below OTTdn
        elif (current['VAR'] < current['OTTdn_shifted'] and 
              previous['VAR'] >= previous['OTTdn_shifted']):
            signals.append({
                'timestamp': current.name,
                'signal_type': 'SELL',
                'price': current['close'],
                'var': current['VAR'],
                'ottdn': current['OTTdn_shifted']
            })

    print(f'📊 TOTT SİNYALLERİ: {len(signals)} adet')
    for i, signal in enumerate(signals[-5:], 1):  # Son 5 sinyal
        print(f'   {i}. {signal["timestamp"].strftime("%Y-%m-%d")} - {signal["signal_type"]} @ ${signal["price"]:.2f}')
    print()

    # Backtest
    trades = []
    position = None

    for signal in signals:
        if signal['signal_type'] == 'BUY' and position is None:
            position = {
                'side': 'BUY',
                'entry_price': signal['price'],
                'entry_time': signal['timestamp']
            }
        elif signal['signal_type'] == 'SELL' and position is not None:
            exit_price = signal['price']
            pnl = (exit_price - position['entry_price']) / position['entry_price']
            
            trades.append({
                'entry_time': position['entry_time'],
                'exit_time': signal['timestamp'],
                'side': position['side'],
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'pnl': pnl
            })
            position = None

    print(f'📈 TOTT BACKTEST SONUÇLARI:')
    if trades:
        profitable = sum(1 for t in trades if t['pnl'] > 0)
        win_rate = profitable / len(trades) * 100
        total_return = sum(t['pnl'] for t in trades)
        
        print(f'   ✅ İşlem sayısı: {len(trades)}')
        print(f'   📈 Win Rate: {win_rate:.1f}%')
        print(f'   💰 Total Return: {total_return:.2%}')
        print(f'   📊 Sinyal sayısı: {len(signals)}')
        
        print(f'\n📋 İŞLEM DETAYLARI:')
        for i, trade in enumerate(trades, 1):
            print(f'   {i}. {trade["entry_time"].strftime("%Y-%m-%d")} -> {trade["exit_time"].strftime("%Y-%m-%d")}')
            print(f'      Entry: ${trade["entry_price"]:.2f} -> Exit: ${trade["exit_price"]:.2f}')
            print(f'      PnL: {trade["pnl"]:.2%}')
            print()
    else:
        print(f'   ❌ İşlem yapılamadı')
        print(f'   📊 Sinyal sayısı: {len(signals)}')

    print(f'🎯 TOTT STRATEJİSİ SONUCU:')
    if trades:
        if total_return > 0:
            print(f'   ✅ KARLI: {total_return:.2%}')
        else:
            print(f'   ❌ ZARARLI: {total_return:.2%}')
    else:
        print(f'   ⚠️ SİNYAL YOK')

if __name__ == "__main__":
    test_tott_only()
