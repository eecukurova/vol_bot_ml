#!/usr/bin/env python3
"""
LLM Projesi - Stop Loss ve Take Profit İşlemleri Kapsamlı Analiz
Son işlemleri analiz eder, SL/TP oranlarını hesaplar ve öneriler sunar
"""

import json
import ccxt
from datetime import datetime, timedelta
from pathlib import Path
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

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

def get_recent_trades(days=30):
    """Get recent trades from Binance."""
    since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    try:
        trades = exchange.fetch_my_trades("BTCUSDT", since=since, limit=1000)
        return trades
    except Exception as e:
        print(f"❌ Hata: {e}")
        return []

def get_recent_orders(days=30):
    """Get recent orders from Binance."""
    since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    try:
        orders = exchange.fetch_orders("BTCUSDT", since=since, limit=1000)
        return orders
    except Exception as e:
        print(f"❌ Hata: {e}")
        return []

def analyze_positions_from_orders(orders):
    """Analyze positions from orders (entry, TP, SL)."""
    positions = []
    
    # Group orders by clientOrderId or timestamp proximity
    entry_orders = {}
    sl_orders = {}
    tp_orders = {}
    
    for order in orders:
        if order.get('status') != 'closed':
            continue
            
        client_id = order.get('clientOrderId', '')
        order_type = order.get('type', '').lower()
        side = order.get('side', '').upper()
        
        # Entry orders (market orders)
        if order_type == 'market' and side in ['BUY', 'SELL']:
            # Try to extract position ID from clientOrderId
            pos_id = client_id.split('-')[0] if '-' in client_id else str(order['timestamp'])
            entry_orders[pos_id] = {
                'order': order,
                'side': 'LONG' if side == 'BUY' else 'SHORT',
                'price': float(order.get('price', 0) or order.get('average', 0)),
                'time': datetime.fromtimestamp(order['timestamp'] / 1000),
                'amount': float(order.get('amount', 0) or order.get('filled', 0))
            }
        
        # SL orders
        if 'stop' in order_type or 'sl' in client_id.lower():
            # Try to match with entry
            for pos_id, entry in entry_orders.items():
                if abs(order['timestamp'] - entry['order']['timestamp']) < 300000:  # 5 dakika içinde
                    sl_orders[pos_id] = {
                        'order': order,
                        'price': float(order.get('stopPrice', 0) or order.get('price', 0)),
                        'time': datetime.fromtimestamp(order['timestamp'] / 1000)
                    }
                    break
        
        # TP orders
        if 'take' in order_type or 'tp' in client_id.lower():
            for pos_id, entry in entry_orders.items():
                if abs(order['timestamp'] - entry['order']['timestamp']) < 300000:
                    tp_orders[pos_id] = {
                        'order': order,
                        'price': float(order.get('price', 0) or order.get('stopPrice', 0)),
                        'time': datetime.fromtimestamp(order['timestamp'] / 1000)
                    }
                    break
    
    # Match entry with exit (TP or SL)
    for pos_id, entry in entry_orders.items():
        position = {
            'id': pos_id,
            'side': entry['side'],
            'entry_price': entry['price'],
            'entry_time': entry['time'],
            'entry_amount': entry['amount'],
            'exit_reason': None,
            'exit_price': None,
            'exit_time': None,
            'pnl_pct': None
        }
        
        # Check if SL triggered
        if pos_id in sl_orders:
            sl = sl_orders[pos_id]
            position['exit_reason'] = 'SL'
            position['exit_price'] = sl['price']
            position['exit_time'] = sl['time']
            
            if entry['side'] == 'LONG':
                position['pnl_pct'] = (sl['price'] - entry['price']) / entry['price']
            else:
                position['pnl_pct'] = (entry['price'] - sl['price']) / entry['price']
        
        # Check if TP triggered
        elif pos_id in tp_orders:
            tp = tp_orders[pos_id]
            position['exit_reason'] = 'TP'
            position['exit_price'] = tp['price']
            position['exit_time'] = tp['time']
            
            if entry['side'] == 'LONG':
                position['pnl_pct'] = (tp['price'] - entry['price']) / entry['price']
            else:
                position['pnl_pct'] = (entry['price'] - tp['price']) / entry['price']
        
        # Only add if position was closed
        if position['exit_reason']:
            positions.append(position)
    
    return positions

def analyze_trades_directly(trades):
    """Analyze trades directly by pairing buy/sell."""
    positions = []
    i = 0
    
    while i < len(trades):
        entry_trade = trades[i]
        
        # Look for exit trade (opposite side)
        exit_trade = None
        for j in range(i + 1, min(i + 10, len(trades))):  # Check next 10 trades
            if trades[j]['side'] != entry_trade['side']:
                exit_trade = trades[j]
                break
        
        if exit_trade:
            entry_price = float(entry_trade['price'])
            exit_price = float(exit_trade['price'])
            
            if entry_trade['side'] == 'buy':
                pnl_pct = (exit_price - entry_price) / entry_price
                side = 'LONG'
            else:
                pnl_pct = (entry_price - exit_price) / entry_price
                side = 'SHORT'
            
            # Determine exit reason based on PnL and expected SL/TP
            sl_pct = cfg.get('trading_params', {}).get('sl_pct', 0.006)
            tp_pct = cfg.get('trading_params', {}).get('tp_pct', 0.008)
            
            if pnl_pct < -sl_pct * 0.9:  # Close to SL
                exit_reason = 'SL'
            elif pnl_pct > tp_pct * 0.9:  # Close to TP
                exit_reason = 'TP'
            else:
                exit_reason = 'MANUAL'  # Unknown
            
            position = {
                'side': side,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_pct': pnl_pct,
                'exit_reason': exit_reason,
                'entry_time': datetime.fromtimestamp(entry_trade['timestamp'] / 1000),
                'exit_time': datetime.fromtimestamp(exit_trade['timestamp'] / 1000),
                'entry_order_id': entry_trade.get('id'),
                'exit_order_id': exit_trade.get('id'),
            }
            positions.append(position)
            i += 2  # Skip both trades
        else:
            i += 1
    
    return positions

def main():
    print("=" * 100)
    print("LLM PROJESİ - STOP LOSS VE TAKE PROFIT KAPSAMLI ANALİZ")
    print("=" * 100)
    print()
    
    # Get data
    print("📊 Veriler çekiliyor...")
    trades = get_recent_trades(days=30)
    orders = get_recent_orders(days=30)
    
    print(f"   Toplam Trade: {len(trades)}")
    print(f"   Toplam Order: {len(orders)}")
    print()
    
    # Analyze positions
    print("🔍 Pozisyonlar analiz ediliyor...")
    positions_from_orders = analyze_positions_from_orders(orders)
    positions_from_trades = analyze_trades_directly(trades)
    
    # Combine and deduplicate
    all_positions = positions_from_trades
    if positions_from_orders:
        # Add unique positions from orders
        for pos_ord in positions_from_orders:
            # Check if already exists
            exists = False
            for pos_tr in all_positions:
                if (abs((pos_ord['entry_time'] - pos_tr['entry_time']).total_seconds()) < 60 and
                    abs(pos_ord['entry_price'] - pos_tr['entry_price']) / pos_tr['entry_price'] < 0.001):
                    exists = True
                    break
            if not exists:
                all_positions.append(pos_ord)
    
    if not all_positions:
        print("⚠️ Analiz edilecek pozisyon bulunamadı!")
        return
    
    # Filter recent positions (last 30 days)
    cutoff_date = datetime.now() - timedelta(days=30)
    recent_positions = [p for p in all_positions if p['entry_time'] >= cutoff_date]
    
    print(f"   Toplam Pozisyon: {len(recent_positions)}")
    print()
    
    # Categorize
    sl_positions = [p for p in recent_positions if p['exit_reason'] == 'SL']
    tp_positions = [p for p in recent_positions if p['exit_reason'] == 'TP']
    manual_positions = [p for p in recent_positions if p['exit_reason'] == 'MANUAL']
    
    print("=" * 100)
    print("📊 GENEL İSTATİSTİKLER")
    print("=" * 100)
    print()
    
    total = len(recent_positions)
    if total == 0:
        print("⚠️ Son 30 günde pozisyon bulunamadı!")
        return
    
    print(f"📈 Toplam Pozisyon: {total}")
    print(f"   ✅ Take Profit: {len(tp_positions)} ({len(tp_positions)/total*100:.1f}%)")
    print(f"   ❌ Stop Loss: {len(sl_positions)} ({len(sl_positions)/total*100:.1f}%)")
    print(f"   🔄 Manuel: {len(manual_positions)} ({len(manual_positions)/total*100:.1f}%)")
    print()
    
    # Win rate
    closed_positions = sl_positions + tp_positions
    if closed_positions:
        win_rate = len(tp_positions) / len(closed_positions) * 100
        print(f"🎯 Win Rate: {win_rate:.1f}%")
        print()
    
    # PnL Analysis
    print("=" * 100)
    print("💰 KAR/ZARAR ANALİZİ")
    print("=" * 100)
    print()
    
    if tp_positions:
        avg_tp_pnl = sum(p['pnl_pct'] for p in tp_positions) / len(tp_positions)
        total_tp_pnl = sum(p['pnl_pct'] for p in tp_positions)
        print(f"✅ Take Profit:")
        print(f"   Adet: {len(tp_positions)}")
        print(f"   Ortalama PnL: {avg_tp_pnl*100:.2f}%")
        print(f"   Toplam PnL: {total_tp_pnl*100:.2f}%")
        print()
    
    if sl_positions:
        avg_sl_pnl = sum(p['pnl_pct'] for p in sl_positions) / len(sl_positions)
        total_sl_pnl = sum(p['pnl_pct'] for p in sl_positions)
        print(f"❌ Stop Loss:")
        print(f"   Adet: {len(sl_positions)}")
        print(f"   Ortalama PnL: {avg_sl_pnl*100:.2f}%")
        print(f"   Toplam PnL: {total_sl_pnl*100:.2f}%")
        print()
    
    # Side breakdown
    print("=" * 100)
    print("📊 YÖN ANALİZİ")
    print("=" * 100)
    print()
    
    sl_long = [p for p in sl_positions if p['side'] == 'LONG']
    sl_short = [p for p in sl_positions if p['side'] == 'SHORT']
    tp_long = [p for p in tp_positions if p['side'] == 'LONG']
    tp_short = [p for p in tp_positions if p['side'] == 'SHORT']
    
    print(f"LONG Pozisyonlar:")
    print(f"   TP: {len(tp_long)} ({len(tp_long)/(len(tp_long)+len(sl_long))*100:.1f}% win rate)" if (tp_long or sl_long) else "   TP: 0")
    print(f"   SL: {len(sl_long)}")
    print()
    
    print(f"SHORT Pozisyonlar:")
    print(f"   TP: {len(tp_short)} ({len(tp_short)/(len(tp_short)+len(sl_short))*100:.1f}% win rate)" if (tp_short or sl_short) else "   TP: 0")
    print(f"   SL: {len(sl_short)}")
    print()
    
    # Time analysis
    print("=" * 100)
    print("⏰ ZAMAN ANALİZİ")
    print("=" * 100)
    print()
    
    if sl_positions:
        sl_durations = [(p['exit_time'] - p['entry_time']).total_seconds() / 60 for p in sl_positions]
        avg_sl_duration = sum(sl_durations) / len(sl_durations)
        print(f"❌ Stop Loss:")
        print(f"   Ortalama Süre: {avg_sl_duration:.1f} dakika")
        print(f"   En Kısa: {min(sl_durations):.1f} dakika")
        print(f"   En Uzun: {max(sl_durations):.1f} dakika")
        print()
    
    if tp_positions:
        tp_durations = [(p['exit_time'] - p['entry_time']).total_seconds() / 60 for p in tp_positions]
        avg_tp_duration = sum(tp_durations) / len(tp_durations)
        print(f"✅ Take Profit:")
        print(f"   Ortalama Süre: {avg_tp_duration:.1f} dakika")
        print(f"   En Kısa: {min(tp_durations):.1f} dakika")
        print(f"   En Uzun: {max(tp_durations):.1f} dakika")
        print()
    
    # Recent SL positions details
    if sl_positions:
        print("=" * 100)
        print("❌ SON STOP LOSS İŞLEMLERİ (Detay)")
        print("=" * 100)
        print()
        
        recent_sl = sorted(sl_positions, key=lambda x: x['entry_time'], reverse=True)[:10]
        for i, pos in enumerate(recent_sl, 1):
            duration = (pos['exit_time'] - pos['entry_time']).total_seconds() / 60
            print(f"{i}. {pos['side']} - Entry: ${pos['entry_price']:.2f} → Exit: ${pos['exit_price']:.2f}")
            print(f"   PnL: {pos['pnl_pct']*100:.2f}% | Süre: {duration:.1f} dk")
            print(f"   Entry: {pos['entry_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Exit: {pos['exit_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            print()
    
    # Recommendations
    print("=" * 100)
    print("💡 ÖNERİLER VE ÇÖZÜMLER")
    print("=" * 100)
    print()
    
    sl_rate = len(sl_positions) / total * 100 if total > 0 else 0
    
    if sl_rate > 50:
        print("⚠️ KRİTİK: Stop Loss oranı %50'nin üzerinde!")
        print("   Öneriler:")
        print("   1. Confidence threshold'u yükselt (şu an: 0.85)")
        print("   2. Probability ratio filtresini sıkılaştır (şu an: 5.0)")
        print("   3. Volume spike threshold'u yükselt (şu an: 0.4)")
        print("   4. RSI filtrelerini sıkılaştır")
        print("   5. Minimum bar kontrolünü artır")
        print()
    
    if sl_positions:
        quick_sl = [p for p in sl_positions if (p['exit_time'] - p['entry_time']).total_seconds() < 300]  # 5 dakikadan kısa
        if len(quick_sl) > len(sl_positions) * 0.3:
            print("⚠️ UYARI: Stop Loss işlemlerinin %30'undan fazlası 5 dakikadan kısa sürede gerçekleşmiş!")
            print("   Öneriler:")
            print("   1. Entry timing'i iyileştir (daha iyi fiyat seviyesi bekle)")
            print("   2. SL seviyesini biraz genişlet (şu an: 0.6%)")
            print("   3. Sinyal confirmation süresini artır")
            print()
    
    if sl_long and sl_short:
        long_sl_rate = len(sl_long) / (len(tp_long) + len(sl_long)) * 100 if (tp_long or sl_long) else 0
        short_sl_rate = len(sl_short) / (len(tp_short) + len(sl_short)) * 100 if (tp_short or sl_short) else 0
        
        if long_sl_rate > short_sl_rate * 1.5:
            print("⚠️ UYARI: LONG pozisyonlarda SL oranı SHORT'a göre çok yüksek!")
            print("   Öneriler:")
            print("   1. LONG sinyalleri için daha sıkı filtreler uygula")
            print("   2. LONG için confidence threshold'u artır")
            print()
        elif short_sl_rate > long_sl_rate * 1.5:
            print("⚠️ UYARI: SHORT pozisyonlarda SL oranı LONG'a göre çok yüksek!")
            print("   Öneriler:")
            print("   1. SHORT sinyalleri için daha sıkı filtreler uygula")
            print("   2. SHORT için confidence threshold'u artır")
            print()
    
    # Current config summary
    print("=" * 100)
    print("⚙️ MEVCUT AYARLAR")
    print("=" * 100)
    print()
    
    trading_params = cfg.get('trading_params', {})
    print(f"Stop Loss: {trading_params.get('sl_pct', 0)*100:.2f}%")
    print(f"Take Profit: {trading_params.get('tp_pct', 0)*100:.2f}%")
    print(f"Confidence Threshold (LONG): {trading_params.get('thr_long', 0)*100:.0f}%")
    print(f"Confidence Threshold (SHORT): {trading_params.get('thr_short', 0)*100:.0f}%")
    print()
    
    regime_filter = cfg.get('regime_filter', {})
    print(f"Volume Spike Threshold: {regime_filter.get('vol_spike_threshold', 0)}")
    print()
    
    multi_timeframe = cfg.get('multi_timeframe', {})
    print(f"Multi-Timeframe: {'Aktif' if multi_timeframe.get('enabled', False) else 'Pasif'}")
    if multi_timeframe.get('enabled'):
        print(f"   Signal Timeframe: {multi_timeframe.get('signal_timeframe', 'N/A')}")
        print(f"   Trend Timeframe: {multi_timeframe.get('trend_timeframe', 'N/A')}")
    print()
    
    print("=" * 100)

if __name__ == "__main__":
    main()

