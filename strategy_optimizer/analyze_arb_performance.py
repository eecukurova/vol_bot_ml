#!/usr/bin/env python3
"""
ARB Strateji Performans Analizi
Win rate ve risk/reward analizi
"""

def analyze_performance():
    """Win rate ve risk/reward analizi"""
    print("="*70)
    print("📊 ARB Strateji Performans Analizi")
    print("="*70)
    
    # Mevcut durum
    total_trades = 99
    winning_trades = 45
    win_rate = (winning_trades / total_trades) * 100
    
    tp_pct = 0.5
    sl_pct = 1.5
    risk_reward_ratio = sl_pct / tp_pct
    
    print(f"\n🔴 MEVCUT DURUM:")
    print(f"  Total Trades: {total_trades}")
    print(f"  Winning Trades: {winning_trades}")
    print(f"  Win Rate: {win_rate:.2f}%")
    print(f"  TP: {tp_pct}%")
    print(f"  SL: {sl_pct}%")
    print(f"  Risk/Reward: 1:{risk_reward_ratio:.2f}")
    
    # Gerekli win rate hesaplama
    required_win_rate = (risk_reward_ratio / (1 + risk_reward_ratio)) * 100
    
    print(f"\n⚠️  SORUN:")
    print(f"  Mevcut Win Rate: {win_rate:.2f}%")
    print(f"  Gerekli Win Rate: {required_win_rate:.2f}%")
    print(f"  Eksik: {required_win_rate - win_rate:.2f}%")
    
    # Farklı senaryolar
    print(f"\n{'='*70}")
    print("💡 ÇÖZÜM ÖNERİLERİ")
    print("="*70)
    
    scenarios = [
        {"tp": 0.6, "sl": 0.5, "name": "Senaryo 1: TP artır, SL azalt"},
        {"tp": 0.8, "sl": 0.6, "name": "Senaryo 2: Dengeli"},
        {"tp": 1.0, "sl": 0.6, "name": "Senaryo 3: TP odaklı"},
        {"tp": 0.6, "sl": 0.4, "name": "Senaryo 4: SL çok düşük"},
        {"tp": 1.2, "sl": 0.8, "name": "Senaryo 5: Her ikisi de büyük"},
    ]
    
    for scenario in scenarios:
        rr = scenario["sl"] / scenario["tp"]
        req_wr = (rr / (1 + rr)) * 100
        print(f"\n{scenario['name']}:")
        print(f"  TP: {scenario['tp']}% | SL: {scenario['sl']}%")
        print(f"  Risk/Reward: 1:{rr:.2f}")
        print(f"  Gerekli Win Rate: {req_wr:.2f}%")
        if win_rate >= req_wr:
            print(f"  ✅ Mevcut win rate ({win_rate:.2f}%) YETERLİ!")
        else:
            print(f"  ❌ Win rate artırılmalı: +{req_wr - win_rate:.2f}%")
    
    print(f"\n{'='*70}")
    print("🎯 ÖNERİLER")
    print("="*70)
    print("1. Risk/Reward oranını düzelt (TP artır, SL azalt)")
    print("2. Win rate'i artırmak için daha seçici entry conditions")
    print("3. Ek indikatörler/osilatörler ekle (MACD, Bollinger, ATR)")
    print("4. Volume confirmation güçlendir")
    print("5. Trend filtreleri ekle")
    print("6. Multi-timeframe confirmation")


if __name__ == "__main__":
    analyze_performance()

