#!/usr/bin/env python3
"""Analyze shadow mode signals and check for TP/SL hits."""

import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import ccxt
    import pandas as pd
except ImportError:
    print("⚠️  ccxt veya pandas yüklü değil. Sadece sinyal listesi gösterilecek.")

def load_shadow_state(state_file="runs/shadow_mode_state.json"):
    """Load shadow mode state."""
    state_path = Path(state_file)
    if not state_path.exists():
        print(f"❌ Shadow mode state dosyası bulunamadı: {state_file}")
        return None
    
    with open(state_path, 'r') as f:
        return json.load(f)

def check_signal_status(signal, current_price=None):
    """Check if a signal hit TP or SL."""
    side = signal.get('side', '')
    entry = signal.get('entry', 0)
    tp = signal.get('tp', 0)
    sl = signal.get('sl', 0)
    
    if not entry or not tp or not sl or not current_price:
        return 'UNKNOWN', None
    
    if side == 'LONG':
        if current_price >= tp:
            return 'TAKE_PROFIT', current_price
        elif current_price <= sl:
            return 'STOP_LOSS', current_price
        else:
            pnl_pct = ((current_price - entry) / entry) * 100
            return 'ACTIVE', pnl_pct
    elif side == 'SHORT':
        if current_price <= tp:
            return 'TAKE_PROFIT', current_price
        elif current_price >= sl:
            return 'STOP_LOSS', current_price
        else:
            pnl_pct = ((entry - current_price) / entry) * 100
            return 'ACTIVE', pnl_pct
    
    return 'UNKNOWN', None

def get_current_price():
    """Get current ETH price from Binance."""
    try:
        exchange = ccxt.binance({"options": {"defaultType": "future"}})
        ticker = exchange.fetch_ticker("ETHUSDT")
        return float(ticker['last'])
    except Exception as e:
        print(f"⚠️  Güncel fiyat alınamadı: {e}")
        return None

def main():
    print("=" * 80)
    print("📊 SHADOW MODE SİNYAL ANALİZİ")
    print("=" * 80)
    print()
    
    # Load state
    state = load_shadow_state()
    if not state:
        return
    
    signals = state.get('signals', [])
    virtual_trades = state.get('virtual_trades', [])
    
    print(f"📈 Toplam Kayıtlı Sinyal: {len(signals)}")
    print(f"💼 Virtual Trade Sayısı: {len(virtual_trades)}")
    print()
    
    if not signals:
        print("⚠️  Hiç sinyal kaydı yok!")
        return
    
    # Analyze signals
    long_signals = [s for s in signals if s.get('side') == 'LONG']
    short_signals = [s for s in signals if s.get('side') == 'SHORT']
    
    print("📊 SİNYAL DAĞILIMI:")
    print(f"   LONG: {len(long_signals)} adet")
    print(f"   SHORT: {len(short_signals)} adet")
    print()
    
    # Confidence analysis
    confidences = [s.get('confidence', 0) for s in signals if s.get('confidence', 0) > 0]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        min_conf = min(confidences)
        max_conf = max(confidences)
        print("📊 CONFIDENCE ANALİZİ:")
        print(f"   Ortalama: {avg_conf*100:.2f}%")
        print(f"   Minimum: {min_conf*100:.2f}%")
        print(f"   Maksimum: {max_conf*100:.2f}%")
        print()
    
    # Check current price
    current_price = get_current_price()
    if current_price:
        print(f"💰 Güncel ETH Fiyatı: ${current_price:.2f}")
        print()
    
    # Analyze virtual trades
    if virtual_trades:
        print("=" * 80)
        print("💼 VİRTUAL TRADE SONUÇLARI:")
        print("-" * 80)
        
        sl_trades = [t for t in virtual_trades if t.get('reason') == 'STOP_LOSS' or 'STOP_LOSS' in str(t.get('status', ''))]
        tp_trades = [t for t in virtual_trades if t.get('reason') == 'TAKE_PROFIT' or 'TAKE_PROFIT' in str(t.get('status', ''))]
        
        print(f"🟢 Take Profit: {len(tp_trades)} adet")
        print(f"🔴 Stop Loss: {len(sl_trades)} adet")
        print(f"📊 Toplam Trade: {len(virtual_trades)} adet")
        print()
        
        if virtual_trades:
            pnls = [t.get('pnl_pct', t.get('pnl', 0)) for t in virtual_trades]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]
            
            total_pnl = sum(pnls)
            avg_pnl = sum(pnls) / len(pnls) if pnls else 0
            win_rate = (len(wins) / len(virtual_trades)) * 100 if virtual_trades else 0
            
            print(f"📊 PERFORMANS:")
            print(f"   Win Rate: {win_rate:.2f}%")
            print(f"   Kazanan: {len(wins)} adet")
            print(f"   Kaybeden: {len(losses)} adet")
            print(f"   Ortalama PnL: {avg_pnl:.2f}%")
            print(f"   Toplam PnL: {total_pnl:.2f}%")
            print()
            
            # Show SL trades details
            if sl_trades:
                print("🔴 STOP LOSS TRADE DETAYLARI:")
                print("-" * 80)
                for i, trade in enumerate(sl_trades[-10:], 1):  # Last 10 SL trades
                    side = trade.get('side', 'N/A')
                    entry = trade.get('entry_price', trade.get('entry', 0))
                    exit_p = trade.get('exit_price', trade.get('exit', 0))
                    pnl = trade.get('pnl_pct', trade.get('pnl', 0))
                    ts = trade.get('timestamp', '')
                    reason = trade.get('reason', trade.get('status', 'N/A'))
                    
                    print(f"{i}. {side:5s} | Entry: ${entry:.2f} | Exit: ${exit_p:.2f} | PnL: {pnl:.2f}% | {reason}")
                    if ts:
                        try:
                            dt = datetime.fromisoformat(ts)
                            print(f"   Zaman: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                        except:
                            pass
                print()
    else:
        print("⚠️  Virtual trade kaydı bulunamadı!")
        print("   Shadow mode sadece sinyalleri kaydetmiş, trade sonuçlarını takip etmemiş.")
        print()
    
    # Check signals against current price
    if current_price and signals:
        print("=" * 80)
        print("🔍 SİNYALLERİN GÜNCEL DURUMU (TP/SL KONTROLÜ):")
        print("-" * 80)
        
        tp_hit = 0
        sl_hit = 0
        active = 0
        
        # Check last 20 signals
        for sig in signals[-20:]:
            status, value = check_signal_status(sig, current_price)
            
            if status == 'STOP_LOSS':
                sl_hit += 1
            elif status == 'TAKE_PROFIT':
                tp_hit += 1
            elif status == 'ACTIVE':
                active += 1
        
        print(f"📊 SON 20 SİNYAL ÖZET:")
        print(f"   🔴 Stop Loss: {sl_hit} adet")
        print(f"   🟢 Take Profit: {tp_hit} adet")
        print(f"   🟡 Aktif: {active} adet")
        print()
        
        # Show recent signals with status
        print("📋 SON 10 SİNYAL DETAYI:")
        print("-" * 80)
        for i, sig in enumerate(signals[-10:], 1):
            side = sig.get('side', 'N/A')
            entry = sig.get('entry', 0)
            tp = sig.get('tp', 0)
            sl = sig.get('sl', 0)
            conf = sig.get('confidence', 0)
            ts = sig.get('timestamp', '')
            
            status, value = check_signal_status(sig, current_price)
            
            status_emoji = {
                'STOP_LOSS': '🔴',
                'TAKE_PROFIT': '🟢',
                'ACTIVE': '🟡',
                'UNKNOWN': '⚪'
            }
            
            emoji = status_emoji.get(status, '⚪')
            
            if entry and tp and sl:
                if side == 'LONG':
                    tp_dist = ((tp - entry) / entry) * 100
                    sl_dist = ((entry - sl) / entry) * 100
                else:
                    tp_dist = ((entry - tp) / entry) * 100
                    sl_dist = ((sl - entry) / entry) * 100
                
                print(f"{i}. {emoji} {status:12s} | {side:5s} | Entry: ${entry:8.2f} | TP: ${tp:8.2f} (+{tp_dist:.2f}%) | SL: ${sl:8.2f} (-{sl_dist:.2f}%) | Conf: {conf*100:5.2f}%")
                
                if status == 'ACTIVE' and isinstance(value, float):
                    print(f"   Şu anki PnL: {value:+.2f}%")
                
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        print(f"   Zaman: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    except:
                        pass
            print()

if __name__ == "__main__":
    main()

