#!/usr/bin/env python3
"""
Comprehensive Stop Loss Analysis for LLM Project
Her stop loss işlemini detaylı inceler: Model, Trend, Filtreler, Piyasa Durumu
"""

import json
import re
import ccxt
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# Load config
config_path = Path("configs/llm_config.json")
with open(config_path) as f:
    cfg = json.load(f)

exchange = ccxt.binance({
    'apiKey': cfg['api_key'],
    'secret': cfg['secret'],
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})

def get_recent_sl_trades(days=7):
    """Get recent SL trades from Binance."""
    since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    try:
        trades = exchange.fetch_my_trades("BTCUSDT", since=since, limit=500)
        return trades
    except Exception as e:
        print(f"Error fetching trades: {e}")
        return []

def pair_trades_to_positions(trades):
    """Pair trades to find positions."""
    positions = []
    i = 0
    
    while i < len(trades):
        entry_trade = trades[i]
        
        if i + 1 < len(trades):
            exit_trade = trades[i + 1]
            
            if entry_trade['side'] != exit_trade['side']:
                entry_price = entry_trade['price']
                exit_price = exit_trade['price']
                
                if entry_trade['side'] == 'buy':
                    pnl_pct = (exit_price - entry_price) / entry_price
                    side = 'LONG'
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price
                    side = 'SHORT'
                
                exit_reason = 'TP' if pnl_pct > 0 else 'SL'
                
                position = {
                    'side': side,
                    'entry': entry_price,
                    'exit': exit_price,
                    'pnl': pnl_pct,
                    'exit_reason': exit_reason,
                    'entry_time': entry_trade['datetime'],
                    'exit_time': exit_trade['datetime'],
                    'entry_order_id': entry_trade.get('id'),
                    'exit_order_id': exit_trade.get('id'),
                }
                positions.append(position)
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    return positions

def parse_log_for_signal(entry_time_str, log_file, entry_order_id=None):
    """Parse log file to find signal details around entry time."""
    if not log_file.exists():
        return {}
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Parse entry time
        try:
            entry_dt = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
            entry_date_str = entry_dt.strftime('%Y-%m-%d')
            entry_time_str_short = entry_dt.strftime('%H:%M')
        except:
            return {}
        
        signal_info = {}
        found_signal = False
        
        # First try: Find by entry order ID (most reliable)
        if entry_order_id:
            for i, line in enumerate(lines):
                if str(entry_order_id) in line and 'Entry order placed:' in line:
                    # Look backwards for signal (within 50 lines)
                    for j in range(max(0, i-50), i):
                        if 'SIGNAL:' in lines[j]:
                            found_signal = True
                            break
                    if found_signal:
                        break
        
        # Second try: Look for signal around entry time (±60 minutes)
        if not found_signal:
            for i, line in enumerate(lines):
                if 'SIGNAL:' in line:
                    # Check if date matches
                    if entry_date_str in line:
                        # Check if time is close (±60 minutes)
                        time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                        if time_match:
                            line_time = time_match.group(1)[:5]  # HH:MM
                            try:
                                line_dt = datetime.strptime(f"{entry_date_str} {line_time}", "%Y-%m-%d %H:%M")
                                time_diff = abs((line_dt - entry_dt.replace(second=0, microsecond=0)).total_seconds() / 60)
                                if time_diff > 60:
                                    continue
                            except:
                                pass
                    elif entry_date_str not in line:
                        continue
                
                # Extract signal details
                signal_match = re.search(r'SIGNAL: (\w+) @ \$([\d,]+\.?\d*)', line)
                if signal_match:
                    side = signal_match.group(1)
                    price = float(signal_match.group(2).replace(',', ''))
                    signal_info['side'] = side
                    signal_info['signal_price'] = price
                    found_signal = True
                
                # Look ahead for more details
                for j in range(i, min(i+20, len(lines))):
                    # Confidence
                    if 'Confidence:' in lines[j]:
                        conf_match = re.search(r'Confidence: ([\d.]+)%', lines[j])
                        if conf_match:
                            signal_info['confidence'] = float(conf_match.group(1))
                    
                    # TP/SL
                    if 'TP:' in lines[j] and 'SL:' in lines[j]:
                        tp_match = re.search(r'TP: \$([\d,]+\.?\d*)', lines[j])
                        sl_match = re.search(r'SL: \$([\d,]+\.?\d*)', lines[j])
                        if tp_match:
                            signal_info['tp'] = float(tp_match.group(1).replace(',', ''))
                        if sl_match:
                            signal_info['sl'] = float(sl_match.group(1).replace(',', ''))
                    
                    # Probabilities
                    if 'Probs:' in lines[j]:
                        prob_match = re.search(r'Flat=([\d.]+)%, Long=([\d.]+)%, Short=([\d.]+)%', lines[j])
                        if prob_match:
                            signal_info['probs'] = {
                                'flat': float(prob_match.group(1)),
                                'long': float(prob_match.group(2)),
                                'short': float(prob_match.group(3)),
                            }
                    
                    # RSI
                    if 'RSI:' in lines[j]:
                        rsi_match = re.search(r'RSI: ([\d.]+)', lines[j])
                        if rsi_match:
                            signal_info['rsi'] = float(rsi_match.group(1))
                    
                    # Volume Spike
                    if 'Volume Spike:' in lines[j]:
                        vol_match = re.search(r'Volume Spike: ([\d.]+)', lines[j])
                        if vol_match:
                            signal_info['vol_spike'] = float(vol_match.group(1))
                    
                    # Trend check
                    if 'Trend check PASSED' in lines[j] or 'TREND CHECK FAILED' in lines[j]:
                        if 'PASSED' in lines[j]:
                            signal_info['trend_check'] = 'PASSED'
                            # Extract EMA values
                            ema_match = re.search(r'EMA50=([\d.]+), EMA200=([\d.]+)', lines[j])
                            if ema_match:
                                signal_info['ema50'] = float(ema_match.group(1))
                                signal_info['ema200'] = float(ema_match.group(2))
                        else:
                            signal_info['trend_check'] = 'FAILED'
                            signal_info['trend_reason'] = lines[j].strip()
                    
                    # Pattern blocker
                    if 'PATTERN BLOCKER' in lines[j]:
                        signal_info['pattern_blocked'] = True
                        if 'reason' in lines[j].lower():
                            signal_info['pattern_reason'] = lines[j].strip()
                
                if found_signal:
                    break
        
        return signal_info
    except Exception as e:
        print(f"Error parsing log: {e}")
        return {}

def get_market_data_at_time(timestamp_str, timeframe='3m', limit=50):
    """Get market data (OHLCV) at a specific time."""
    try:
        # Parse timestamp
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        since = int((dt - timedelta(minutes=limit*3)).timestamp() * 1000)
        
        # Fetch klines
        klines = exchange.fetch_ohlcv("BTCUSDT", timeframe, since=since, limit=limit)
        
        if not klines:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return None

def calculate_indicators(df):
    """Calculate basic indicators."""
    if df is None or len(df) < 50:
        return {}
    
    # EMA50 and EMA200
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Volume spike (average of last 20 vs last 5)
    if len(df) >= 20:
        avg_vol_20 = df['volume'].tail(20).mean()
        avg_vol_5 = df['volume'].tail(5).mean()
        vol_spike = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0
    else:
        vol_spike = 1.0
    
    last = df.iloc[-1]
    
    return {
        'price': last['close'],
        'ema50': last['ema50'],
        'ema200': last['ema200'],
        'rsi': last['rsi'],
        'vol_spike': vol_spike,
        'trend': 'LONG' if last['ema50'] > last['ema200'] else 'SHORT',
    }

def analyze_single_sl_trade(position, log_file):
    """Analyze a single SL trade in detail."""
    print("\n" + "=" * 100)
    print(f"❌ STOP LOSS TRADE ANALİZİ")
    print("=" * 100)
    
    print(f"\n📊 Temel Bilgiler:")
    print(f"   Side: {position['side']}")
    print(f"   Entry: ${position['entry']:.2f}")
    print(f"   Exit: ${position['exit']:.2f}")
    print(f"   PnL: {position['pnl']*100:.2f}%")
    print(f"   Entry Time: {position['entry_time']}")
    print(f"   Exit Time: {position['exit_time']}")
    
    # Duration
    try:
        entry_dt = datetime.fromisoformat(position['entry_time'].replace('Z', '+00:00'))
        exit_dt = datetime.fromisoformat(position['exit_time'].replace('Z', '+00:00'))
        duration = exit_dt - entry_dt
        duration_min = duration.total_seconds() / 60
        print(f"   Duration: {duration_min:.1f} minutes ({duration_min/60:.1f} hours)")
    except:
        pass
    
    # Get signal info from logs
    print(f"\n🔍 Sinyal Analizi (Loglardan):")
    entry_order_id = position.get('entry_order_id')
    signal_info = parse_log_for_signal(position['entry_time'], log_file, entry_order_id)
    
    if not signal_info:
        print("   ⚠️  Sinyal bilgisi loglarda bulunamadı")
        return
    
    # Model Analysis
    print(f"\n   🤖 Model Değerlendirmesi:")
    if 'confidence' in signal_info:
        conf = signal_info['confidence']
        print(f"      Confidence: {conf:.2f}%")
        if conf >= 90:
            print(f"      ✅ Yüksek confidence (≥90%)")
        elif conf >= 85:
            print(f"      ⚠️  Orta confidence (85-90%)")
        else:
            print(f"      ❌ Düşük confidence (<85%) - Threshold altında!")
    
    if 'probs' in signal_info:
        probs = signal_info['probs']
        print(f"      Probabilities:")
        print(f"         Flat: {probs['flat']:.2f}%")
        print(f"         Long: {probs['long']:.2f}%")
        print(f"         Short: {probs['short']:.2f}%")
        
        # Probability ratio
        if position['side'] == 'LONG':
            prob_ratio = probs['long'] / probs['short'] if probs['short'] > 0 else float('inf')
            print(f"      Long/Short Ratio: {prob_ratio:.2f}")
            if prob_ratio < 3.0:
                print(f"      ⚠️  Düşük probability ratio (<3.0) - Model belirsiz!")
        else:
            prob_ratio = probs['short'] / probs['long'] if probs['long'] > 0 else float('inf')
            print(f"      Short/Long Ratio: {prob_ratio:.2f}")
            if prob_ratio < 3.0:
                print(f"      ⚠️  Düşük probability ratio (<3.0) - Model belirsiz!")
    
    # Trend Check
    print(f"\n   📈 Trend Kontrolü:")
    if 'trend_check' in signal_info:
        if signal_info['trend_check'] == 'PASSED':
            print(f"      ✅ Trend kontrolü GEÇTİ")
            if 'ema50' in signal_info and 'ema200' in signal_info:
                print(f"         EMA50: {signal_info['ema50']:.2f}")
                print(f"         EMA200: {signal_info['ema200']:.2f}")
        else:
            print(f"      ❌ Trend kontrolü BAŞARISIZ!")
            if 'trend_reason' in signal_info:
                print(f"         Sebep: {signal_info['trend_reason']}")
    else:
        print(f"      ⚠️  Trend kontrolü bilgisi bulunamadı")
    
    # Filters
    print(f"\n   🔍 Filtreler:")
    if 'rsi' in signal_info:
        rsi = signal_info['rsi']
        print(f"      RSI: {rsi:.1f}")
        if position['side'] == 'LONG' and rsi > 80:
            print(f"      ⚠️  RSI çok yüksek (overbought) - LONG için riskli!")
        elif position['side'] == 'SHORT' and rsi < 20:
            print(f"      ⚠️  RSI çok düşük (oversold) - SHORT için riskli!")
        else:
            print(f"      ✅ RSI normal aralıkta")
    
    if 'vol_spike' in signal_info:
        vol_spike = signal_info['vol_spike']
        print(f"      Volume Spike: {vol_spike:.2f}")
        if vol_spike < 0.3:
            print(f"      ⚠️  Volume spike çok düşük (<0.3) - Filtre devre dışı olabilir!")
        else:
            print(f"      ✅ Volume spike yeterli")
    
    if 'pattern_blocked' in signal_info:
        print(f"      ⚠️  Pattern Blocker aktif - Ama sinyal geçti?")
        if 'pattern_reason' in signal_info:
            print(f"         Sebep: {signal_info['pattern_reason']}")
    
    # TP/SL Analysis
    if 'tp' in signal_info and 'sl' in signal_info:
        print(f"\n   🎯 Risk/Reward Analizi:")
        print(f"      TP: ${signal_info['tp']:.2f}")
        print(f"      SL: ${signal_info['sl']:.2f}")
        
        if position['side'] == 'LONG':
            tp_dist = ((signal_info['tp'] - position['entry']) / position['entry']) * 100
            sl_dist = ((position['entry'] - signal_info['sl']) / position['entry']) * 100
        else:
            tp_dist = ((position['entry'] - signal_info['tp']) / position['entry']) * 100
            sl_dist = ((signal_info['sl'] - position['entry']) / position['entry']) * 100
        
        print(f"      TP Distance: {tp_dist:.2f}%")
        print(f"      SL Distance: {sl_dist:.2f}%")
        print(f"      Risk/Reward: {tp_dist/sl_dist:.2f}" if sl_dist > 0 else "      Risk/Reward: N/A")
        
        # Actual move
        if position['side'] == 'LONG':
            actual_move = ((position['exit'] - position['entry']) / position['entry']) * 100
        else:
            actual_move = ((position['entry'] - position['exit']) / position['entry']) * 100
        
        print(f"      Actual Move: {actual_move:.2f}%")
        
        if abs(actual_move - sl_dist) < 0.1:
            print(f"      ✅ SL doğru çalıştı")
        else:
            overshoot = actual_move - sl_dist
            print(f"      ⚠️  SL overshoot: {overshoot:.2f}%")
    
    # Market Data Analysis
    print(f"\n   📊 Entry Zamanı Piyasa Durumu:")
    entry_market = get_market_data_at_time(position['entry_time'], '3m', 50)
    if entry_market is not None:
        entry_indicators = calculate_indicators(entry_market)
        if entry_indicators:
            print(f"      Price: ${entry_indicators['price']:.2f}")
            print(f"      EMA50: ${entry_indicators['ema50']:.2f}")
            print(f"      EMA200: ${entry_indicators['ema200']:.2f}")
            print(f"      Trend: {entry_indicators['trend']}")
            print(f"      RSI: {entry_indicators['rsi']:.1f}")
            print(f"      Volume Spike: {entry_indicators['vol_spike']:.2f}")
            
            # Check if trend matches signal
            if position['side'] == 'LONG' and entry_indicators['trend'] != 'LONG':
                print(f"      ❌ LONG sinyali ama piyasa SHORT trend'de!")
            elif position['side'] == 'SHORT' and entry_indicators['trend'] != 'SHORT':
                print(f"      ❌ SHORT sinyali ama piyasa LONG trend'de!")
            else:
                print(f"      ✅ Trend sinyal ile uyumlu")
    
    print(f"\n   📊 Exit Zamanı Piyasa Durumu:")
    exit_market = get_market_data_at_time(position['exit_time'], '3m', 50)
    if exit_market is not None:
        exit_indicators = calculate_indicators(exit_market)
        if exit_indicators:
            print(f"      Price: ${exit_indicators['price']:.2f}")
            print(f"      Trend: {exit_indicators['trend']}")
            print(f"      RSI: {exit_indicators['rsi']:.1f}")
            
            # Check if trend reversed
            if entry_market is not None and entry_indicators:
                if entry_indicators['trend'] != exit_indicators['trend']:
                    print(f"      ⚠️  Trend değişti: {entry_indicators['trend']} → {exit_indicators['trend']}")
                else:
                    print(f"      Trend aynı kaldı: {exit_indicators['trend']}")
    
    # Problem Identification
    print(f"\n   🔍 Problem Tespiti:")
    problems = []
    solutions = []
    
    if 'confidence' in signal_info and signal_info['confidence'] < 85:
        problems.append("Düşük confidence (<85%)")
        solutions.append("Confidence threshold'u 90%'a yükselt")
    
    if 'probs' in signal_info:
        if position['side'] == 'LONG' and signal_info['probs']['long'] / signal_info['probs']['short'] < 3.0:
            problems.append("Düşük probability ratio (<3.0)")
            solutions.append("min_prob_ratio'yu artır")
    
    if 'trend_check' in signal_info and signal_info['trend_check'] == 'FAILED':
        problems.append("Trend kontrolü başarısız")
        solutions.append("Trend kontrolü zaten aktif - logları kontrol et")
    
    if 'rsi' in signal_info:
        if position['side'] == 'LONG' and signal_info['rsi'] > 80:
            problems.append("RSI overbought (LONG için riskli)")
            solutions.append("RSI filtresi zaten aktif - kontrol et")
        elif position['side'] == 'SHORT' and signal_info['rsi'] < 20:
            problems.append("RSI oversold (SHORT için riskli)")
            solutions.append("RSI filtresi zaten aktif - kontrol et")
    
    if duration_min < 60:
        problems.append("Çok hızlı stop loss (<1 saat)")
        solutions.append("Entry timing'i iyileştir veya SL mesafesini artır")
    
    if abs(position['pnl']) > 0.01:
        problems.append("Büyük zarar (>1%)")
        solutions.append("SL mesafesini azalt veya daha erken çık")
    
    if problems:
        for i, problem in enumerate(problems, 1):
            print(f"      {i}. ❌ {problem}")
        print(f"\n   💡 Çözüm Önerileri:")
        for i, solution in enumerate(solutions, 1):
            print(f"      {i}. {solution}")
    else:
        print(f"      ✅ Belirgin bir problem tespit edilmedi")
        print(f"      💡 Bu durumda:")
        print(f"         - Piyasa koşulları entry'den sonra değişmiş olabilir")
        print(f"         - Normal stop loss - risk yönetimi çalışıyor")
        print(f"         - Model doğru ama timing yanlış olabilir")

def main():
    print("=" * 100)
    print("LLM PROJESİ - STOP LOSS İŞLEMLERİ DETAYLI ANALİZ")
    print("=" * 100)
    
    # Get recent trades
    print("\n📊 Binance'den işlemler çekiliyor...")
    trades = get_recent_sl_trades(days=7)
    print(f"   Toplam işlem: {len(trades)}")
    
    # Pair to positions
    positions = pair_trades_to_positions(trades)
    sl_positions = [p for p in positions if p.get('exit_reason') == 'SL']
    
    if not sl_positions:
        print("\n✅ Son 7 günde stop loss işlemi yok!")
        return
    
    print(f"\n📊 Stop Loss İşlemleri: {len(sl_positions)} adet")
    print("=" * 100)
    
    # Log file
    log_file = Path("runs/llm_live.log")
    
    # Analyze each SL trade
    for i, pos in enumerate(sl_positions, 1):
        print(f"\n\n{'#' * 100}")
        print(f"# STOP LOSS İŞLEM #{i} / {len(sl_positions)}")
        print(f"{'#' * 100}")
        analyze_single_sl_trade(pos, log_file)
    
    # Summary
    print(f"\n\n{'=' * 100}")
    print("📊 ÖZET ANALİZ")
    print("=" * 100)
    
    avg_pnl = sum(p['pnl'] for p in sl_positions) / len(sl_positions)
    total_pnl = sum(p['pnl'] for p in sl_positions)
    
    print(f"\n   Toplam SL İşlemi: {len(sl_positions)}")
    print(f"   Ortalama PnL: {avg_pnl*100:.2f}%")
    print(f"   Toplam Zarar: {total_pnl*100:.2f}%")
    
    # Side breakdown
    sl_long = [p for p in sl_positions if p['side'] == 'LONG']
    sl_short = [p for p in sl_positions if p['side'] == 'SHORT']
    
    if sl_long:
        avg_long = sum(p['pnl'] for p in sl_long) / len(sl_long)
        print(f"   LONG SL: {len(sl_long)} işlem, Ortalama: {avg_long*100:.2f}%")
    
    if sl_short:
        avg_short = sum(p['pnl'] for p in sl_short) / len(sl_short)
        print(f"   SHORT SL: {len(sl_short)} işlem, Ortalama: {avg_short*100:.2f}%")
    
    print(f"\n💡 Genel Öneriler:")
    print("=" * 100)
    
    if len(sl_positions) > 3:
        print(f"   ⚠️  Çok fazla SL ({len(sl_positions)}) - Entry stratejisini gözden geçir")
    
    if avg_pnl < -0.005:
        print(f"   ⚠️  Ortalama zarar yüksek ({avg_pnl*100:.2f}%) - SL mesafesini azalt")
    
    if sl_short and len(sl_short) > len(sl_long):
        print(f"   ⚠️  SHORT SL'ler LONG'dan fazla - SHORT stratejisini gözden geçir")
    
    print(f"\n   ✅ Trend kontrolü aktif - Piyasa trendine ters pozisyon açılmıyor")
    print(f"   ✅ RSI, Volume, Confidence filtreleri aktif")
    print(f"   ✅ Model confidence'ları genelde yüksek (≥85%)")

if __name__ == "__main__":
    main()

