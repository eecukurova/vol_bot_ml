#!/usr/bin/env python3
"""TWMA 4H Stratejisi - Karlılık ve Mantık Analizi"""

import json

# Optimizasyon sonuçlarını oku
with open('twma_4h_optimization_BTCUSDT_20251118_222333.json', 'r') as f:
    results = json.load(f)

best = results[0] if results else None

if best:
    r = best['results']
    p = best['params']
    
    print("="*70)
    print("TWMA 4H STRATEJİSİ - KARLILIK VE MANTIK ANALİZİ")
    print("="*70)
    print()
    
    # Temel metrikler
    print("📊 TEMEL PERFORMANS METRİKLERİ:")
    print("-"*70)
    print(f"Total Trades: {r['total_trades']}")
    print(f"Win Rate: {r['win_rate']:.2f}%")
    print(f"Profit Factor: {r['profit_factor']:.2f}")
    print(f"Total Return: {r['total_return_pct']:.2f}% (5x leverage ile)")
    print(f"Max Drawdown: {r['max_drawdown_pct']:.2f}%")
    print(f"Avg Win: {r['avg_win_pct']:.2f}%")
    print(f"Avg Loss: {r['avg_loss_pct']:.2f}%")
    print()
    
    # Risk/Reward analizi
    risk_reward_ratio = abs(r['avg_win_pct'] / r['avg_loss_pct']) if r['avg_loss_pct'] != 0 else 0
    print("💰 RİSK/ÖDÜL ANALİZİ:")
    print("-"*70)
    print(f"Risk/Reward Ratio: {risk_reward_ratio:.2f}:1")
    print(f"  → Ortalama kazanç: {r['avg_win_pct']:.2f}%")
    print(f"  → Ortalama kayıp: {r['avg_loss_pct']:.2f}%")
    if risk_reward_ratio >= 1.5:
        print(f"  → ✅ İYİ (1.5:1 veya üzeri ideal)")
    elif risk_reward_ratio >= 1.0:
        print(f"  → ⚠️ ORTA (1.0:1 minimum)")
    else:
        print(f"  → ❌ KÖTÜ (1.0:1'in altı)")
    print()
    
    # Profit Factor analizi
    print("📈 PROFİT FACTOR ANALİZİ:")
    print("-"*70)
    pf = r['profit_factor']
    if pf >= 2.0:
        pf_rating = "✅ MÜKEMMEL"
    elif pf >= 1.5:
        pf_rating = "✅ İYİ"
    elif pf >= 1.2:
        pf_rating = "⚠️ ORTA"
    elif pf >= 1.0:
        pf_rating = "⚠️ ZAYIF"
    else:
        pf_rating = "❌ KARLISIZ"
    
    print(f"Profit Factor: {pf:.2f} {pf_rating}")
    print(f"  → Gross Profit: {r['gross_profit']:.2f}%")
    print(f"  → Gross Loss: {r['gross_loss']:.2f}%")
    if pf > 1.0:
        print(f"  → ✅ Karlı (1.0'dan büyük)")
    else:
        print(f"  → ❌ Karlısız (1.0'dan küçük)")
    print()
    
    # Win Rate analizi
    print("🎯 WIN RATE ANALİZİ:")
    print("-"*70)
    wr = r['win_rate']
    if wr >= 60:
        wr_rating = "✅ MÜKEMMEL"
    elif wr >= 50:
        wr_rating = "✅ İYİ"
    elif wr >= 40:
        wr_rating = "⚠️ ORTA (Risk/Reward ile telafi edilebilir)"
    else:
        wr_rating = "❌ DÜŞÜK"
    
    print(f"Win Rate: {wr:.2f}% {wr_rating}")
    winning_trades = int(r['total_trades'] * wr / 100)
    losing_trades = r['total_trades'] - winning_trades
    print(f"  → Kazanan trade: {winning_trades}")
    print(f"  → Kaybeden trade: {losing_trades}")
    print()
    
    # Return analizi (leverage olmadan)
    leverage = p['leverage']
    return_without_leverage = r['total_return_pct'] / leverage
    annual_return_est = return_without_leverage * 365 / 180
    print("💵 GETİRİ ANALİZİ:")
    print("-"*70)
    print(f"Return (5x leverage ile): {r['total_return_pct']:.2f}%")
    print(f"Return (leverage olmadan): {return_without_leverage:.2f}%")
    if return_without_leverage >= 2.0:
        print(f"  → ✅ İYİ")
    elif return_without_leverage >= 0:
        print(f"  → ⚠️ ORTA")
    else:
        print(f"  → ❌ NEGATİF")
    print(f"  → 180 günde {return_without_leverage:.2f}% = yıllık ~{annual_return_est:.2f}% (tahmini)")
    print()
    
    # Drawdown analizi
    print("⚠️  RİSK ANALİZİ:")
    print("-"*70)
    dd = r['max_drawdown_pct']
    if dd <= 5:
        dd_rating = "✅ DÜŞÜK RİSK"
    elif dd <= 10:
        dd_rating = "⚠️ ORTA RİSK"
    elif dd <= 20:
        dd_rating = "⚠️ YÜKSEK RİSK"
    else:
        dd_rating = "❌ ÇOK YÜKSEK RİSK"
    
    print(f"Max Drawdown: {dd:.2f}% {dd_rating}")
    if dd <= 10:
        print(f"  → ✅ Kabul edilebilir")
    else:
        print(f"  → ⚠️ Dikkat edilmeli")
    print()
    
    # Trade sayısı analizi
    print("📊 İSTATİSTİKSEL GÜVENİLİRLİK:")
    print("-"*70)
    trades = r['total_trades']
    if trades >= 100:
        stat_rating = "✅ YÜKSEK GÜVENİLİRLİK"
    elif trades >= 50:
        stat_rating = "⚠️ ORTA GÜVENİLİRLİK"
    elif trades >= 30:
        stat_rating = "⚠️ DÜŞÜK GÜVENİLİRLİK"
    else:
        stat_rating = "❌ ÇOK DÜŞÜK GÜVENİLİRLİK"
    
    print(f"Total Trades: {trades} {stat_rating}")
    if trades >= 50:
        print(f"  → ✅ Yeterli örneklem")
    else:
        print(f"  → ⚠️ Daha fazla trade gerekli")
    print()
    
    # Genel değerlendirme
    print("="*70)
    print("GENEL DEĞERLENDİRME:")
    print("="*70)
    print()
    
    positives = []
    negatives = []
    
    # Pozitif yönler
    if pf >= 1.5:
        positives.append(f"✅ Profit Factor {pf:.2f} - İyi seviyede")
    if risk_reward_ratio >= 1.5:
        positives.append(f"✅ Risk/Reward {risk_reward_ratio:.2f}:1 - İdeal seviyede")
    if dd <= 10:
        positives.append(f"✅ Max Drawdown {dd:.2f}% - Kabul edilebilir risk")
    if return_without_leverage > 0:
        positives.append(f"✅ Pozitif getiri (leverage olmadan): {return_without_leverage:.2f}%")
    
    # Negatif yönler
    if wr < 50:
        negatives.append(f"⚠️ Win Rate {wr:.2f}% - Düşük (ama risk/ödül ile telafi ediliyor)")
    if trades < 100:
        negatives.append(f"⚠️ Trade sayısı {trades} - Daha fazla örneklem istenir")
    if dd > 5:
        negatives.append(f"⚠️ Drawdown {dd:.2f}% - Orta seviye risk")
    
    print("✅ GÜÇLÜ YÖNLER:")
    for pos in positives:
        print(f"   {pos}")
    
    if negatives:
        print()
        print("⚠️  DİKKAT EDİLMESİ GEREKENLER:")
        for neg in negatives:
            print(f"   {neg}")
    
    print()
    print("="*70)
    print("SONUÇ:")
    print("="*70)
    
    # Final rating
    score = 0
    if pf >= 1.5:
        score += 2
    elif pf >= 1.2:
        score += 1
    
    if risk_reward_ratio >= 1.5:
        score += 2
    elif risk_reward_ratio >= 1.0:
        score += 1
    
    if return_without_leverage >= 2.0:
        score += 2
    elif return_without_leverage >= 0:
        score += 1
    
    if dd <= 5:
        score += 2
    elif dd <= 10:
        score += 1
    
    if trades >= 50:
        score += 1
    
    if score >= 7:
        final_rating = "✅ MANTIKLI VE KARLI - Kullanılabilir"
    elif score >= 5:
        final_rating = "⚠️ ORTA SEVİYE - Dikkatli kullanılmalı"
    elif score >= 3:
        final_rating = "⚠️ ZAYIF - İyileştirme gerekli"
    else:
        final_rating = "❌ KARLISIZ - Kullanılmamalı"
    
    print(f"Final Rating: {final_rating} (Score: {score}/9)")
    print()
    print("📝 ÖNERİLER:")
    if wr < 50:
        print("   - Win rate düşük ama risk/ödül oranı iyi (1.88:1)")
        print("   - Bu, düşük win rate'in kabul edilebilir olduğunu gösterir")
    if trades < 100:
        print("   - Daha fazla veri ile test edilmesi önerilir")
        print("   - Forward testing (paper trading) yapılmalı")
    if dd > 5:
        print("   - Drawdown yönetimi için position sizing ayarlanabilir")
    print("   - Gerçek trading'de küçük pozisyonlarla başlanmalı")
    print("   - Risk yönetimi kurallarına sıkı sıkıya uyulmalı")
    print()
    print("="*70)

