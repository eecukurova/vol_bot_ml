#!/usr/bin/env python3
"""Compare performance of SOL, LLM (BTC), and ETH projects."""

import json
import ccxt
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import sys

# Load configs
llm_config_path = Path("LLM/configs/llm_config.json")
eth_config_path = Path("ETH/configs/llm_config.json")
sol_config_path = Path("SOL/configs/llm_config.json")

with open(llm_config_path) as f:
    llm_cfg = json.load(f)
with open(eth_config_path) as f:
    eth_cfg = json.load(f)
with open(sol_config_path) as f:
    sol_cfg = json.load(f)

exchange = ccxt.binance({
    'apiKey': llm_cfg['api_key'],
    'secret': llm_cfg['secret'],
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})

def get_recent_trades(symbol, days=7):
    """Get recent trades from Binance."""
    print(f"📊 Fetching {symbol} trades (last {days} days)...")
    
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    
    try:
        trades = exchange.fetch_my_trades(symbol, since=since, limit=500)
        print(f"   Found {len(trades)} trades")
        return trades
    except Exception as e:
        print(f"   Error: {e}")
        return []

def pair_trades_to_positions(trades):
    """Pair trades to find entry/exit positions."""
    if not trades:
        return []
    
    positions = []
    i = 0
    
    while i < len(trades):
        entry_trade = trades[i]
        
        # Find corresponding exit trade
        if i + 1 < len(trades):
            exit_trade = trades[i + 1]
            
            # Check if it's a position pair (entry + exit)
            if entry_trade['side'] != exit_trade['side']:
                # Calculate PnL
                entry_price = entry_trade['price']
                exit_price = exit_trade['price']
                
                if entry_trade['side'] == 'buy':  # LONG
                    pnl_pct = (exit_price - entry_price) / entry_price
                    side = 'LONG'
                else:  # SHORT
                    pnl_pct = (entry_price - exit_price) / entry_price
                    side = 'SHORT'
                
                # Get realized PnL if available
                realized_pnl = None
                if 'info' in entry_trade and 'realizedPnl' in entry_trade['info']:
                    realized_pnl = float(entry_trade['info']['realizedPnl'])
                elif 'info' in exit_trade and 'realizedPnl' in exit_trade['info']:
                    realized_pnl = float(exit_trade['info']['realizedPnl'])
                
                # Determine exit reason (approximate)
                exit_reason = 'TP' if pnl_pct > 0 else 'SL'
                
                position = {
                    'side': side,
                    'entry': entry_price,
                    'exit': exit_price,
                    'pnl': pnl_pct,
                    'realized_pnl': realized_pnl,
                    'exit_reason': exit_reason,
                    'entry_time': entry_trade['datetime'],
                    'exit_time': exit_trade['datetime'],
                }
                positions.append(position)
                i += 2
            else:
                i += 1
        else:
            i += 1
    
    return positions

def analyze_project(symbol, project_name, days=7):
    """Analyze a project's performance."""
    print(f"\n{'='*100}")
    print(f"📊 {project_name} ({symbol}) - Son {days} Gün Analizi")
    print(f"{'='*100}")
    
    trades = get_recent_trades(symbol, days=days)
    if not trades:
        print(f"❌ No trades found for {symbol}")
        return None
    
    positions = pair_trades_to_positions(trades)
    if not positions:
        print(f"❌ No positions found for {symbol}")
        return None
    
    # Separate TP and SL
    tp_positions = [p for p in positions if p.get('exit_reason') == 'TP']
    sl_positions = [p for p in positions if p.get('exit_reason') == 'SL']
    
    # Calculate metrics
    total_positions = len(positions)
    tp_count = len(tp_positions)
    sl_count = len(sl_positions)
    win_rate = (tp_count / total_positions * 100) if total_positions > 0 else 0
    
    # PnL
    total_pnl = sum(p['pnl'] for p in positions)
    tp_pnl = sum(p['pnl'] for p in tp_positions) if tp_positions else 0
    sl_pnl = sum(p['pnl'] for p in sl_positions) if sl_positions else 0
    
    # Average PnL
    avg_pnl = total_pnl / total_positions if total_positions > 0 else 0
    avg_tp = tp_pnl / tp_count if tp_count > 0 else 0
    avg_sl = sl_pnl / sl_count if sl_count > 0 else 0
    
    # Profit factor
    gross_profit = abs(tp_pnl) if tp_pnl > 0 else 0
    gross_loss = abs(sl_pnl) if sl_pnl < 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
    
    # Long vs Short
    long_positions = [p for p in positions if p['side'] == 'LONG']
    short_positions = [p for p in positions if p['side'] == 'SHORT']
    
    long_tp = len([p for p in long_positions if p.get('exit_reason') == 'TP'])
    long_sl = len([p for p in long_positions if p.get('exit_reason') == 'SL'])
    short_tp = len([p for p in short_positions if p.get('exit_reason') == 'TP'])
    short_sl = len([p for p in short_positions if p.get('exit_reason') == 'SL'])
    
    print(f"\n📈 Genel İstatistikler:")
    print(f"   Toplam Pozisyon: {total_positions}")
    print(f"   ✅ Take Profit: {tp_count} ({tp_count/total_positions*100:.1f}%)")
    print(f"   ❌ Stop Loss: {sl_count} ({sl_count/total_positions*100:.1f}%)")
    print(f"   📊 Win Rate: {win_rate:.1f}%")
    
    print(f"\n💰 PnL İstatistikleri:")
    print(f"   Toplam PnL: {total_pnl*100:+.2f}%")
    print(f"   TP PnL: {tp_pnl*100:+.2f}%")
    print(f"   SL PnL: {sl_pnl*100:.2f}%")
    print(f"   Ortalama PnL: {avg_pnl*100:+.2f}%")
    print(f"   Ortalama TP: {avg_tp*100:+.2f}%")
    print(f"   Ortalama SL: {avg_sl*100:.2f}%")
    print(f"   📈 Profit Factor: {profit_factor:.2f}")
    
    print(f"\n📊 Long vs Short:")
    print(f"   LONG: {len(long_positions)} pozisyon (TP: {long_tp}, SL: {long_sl})")
    print(f"   SHORT: {len(short_positions)} pozisyon (TP: {short_tp}, SL: {short_sl})")
    
    # Recent performance (last 3 days)
    cutoff = datetime.now() - timedelta(days=3)
    recent_positions = []
    for pos in positions:
        try:
            exit_time = datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00'))
            if exit_time.replace(tzinfo=None) > cutoff:
                recent_positions.append(pos)
        except:
            pass
    
    if recent_positions:
        recent_tp = len([p for p in recent_positions if p.get('exit_reason') == 'TP'])
        recent_sl = len([p for p in recent_positions if p.get('exit_reason') == 'SL'])
        recent_pnl = sum(p['pnl'] for p in recent_positions)
        recent_win_rate = (recent_tp / len(recent_positions) * 100) if recent_positions else 0
        
        print(f"\n📅 Son 3 Gün:")
        print(f"   Pozisyon: {len(recent_positions)}")
        print(f"   TP: {recent_tp}, SL: {recent_sl}")
        print(f"   Win Rate: {recent_win_rate:.1f}%")
        print(f"   PnL: {recent_pnl*100:+.2f}%")
    
    return {
        'project_name': project_name,
        'symbol': symbol,
        'total_positions': total_positions,
        'tp_count': tp_count,
        'sl_count': sl_count,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'tp_pnl': tp_pnl,
        'sl_pnl': sl_pnl,
        'avg_pnl': avg_pnl,
        'profit_factor': profit_factor,
        'recent_pnl': recent_pnl if recent_positions else 0,
        'recent_win_rate': recent_win_rate if recent_positions else 0,
    }

def main():
    print("="*100)
    print("📊 SOL, LLM (BTC), ETH PROJELERİ KARŞILAŞTIRMASI")
    print("="*100)
    
    results = []
    
    # Analyze each project
    results.append(analyze_project("SOLUSDT", "SOL", days=7))
    results.append(analyze_project("BTCUSDT", "LLM (BTC)", days=7))
    results.append(analyze_project("ETHUSDT", "ETH", days=7))
    
    # Filter out None results
    results = [r for r in results if r is not None]
    
    if not results:
        print("\n❌ No data available for comparison")
        return
    
    # Summary comparison
    print(f"\n{'='*100}")
    print("📊 ÖZET KARŞILAŞTIRMA")
    print(f"{'='*100}")
    
    print(f"\n{'Proje':<15} {'Pozisyon':>10} {'TP':>6} {'SL':>6} {'Win Rate':>10} {'PnL':>12} {'PF':>8} {'Son 3 Gün':>12}")
    print("-"*100)
    
    for r in results:
        print(f"{r['project_name']:<15} {r['total_positions']:>10} {r['tp_count']:>6} {r['sl_count']:>6} "
              f"{r['win_rate']:>9.1f}% {r['total_pnl']*100:>+11.2f}% {r['profit_factor']:>7.2f} "
              f"{r['recent_pnl']*100:>+11.2f}%")
    
    # Find best performer
    print(f"\n{'='*100}")
    print("🏆 EN BAŞARILI PROJE")
    print(f"{'='*100}")
    
    # Sort by multiple criteria
    # 1. Total PnL
    best_pnl = max(results, key=lambda x: x['total_pnl'])
    print(f"\n💰 En Yüksek Toplam PnL: {best_pnl['project_name']} ({best_pnl['total_pnl']*100:+.2f}%)")
    
    # 2. Win Rate
    best_wr = max(results, key=lambda x: x['win_rate'])
    print(f"📊 En Yüksek Win Rate: {best_wr['project_name']} ({best_wr['win_rate']:.1f}%)")
    
    # 3. Profit Factor
    best_pf = max(results, key=lambda x: x['profit_factor'])
    print(f"📈 En Yüksek Profit Factor: {best_pf['project_name']} ({best_pf['profit_factor']:.2f})")
    
    # 4. Recent Performance (last 3 days)
    best_recent = max(results, key=lambda x: x['recent_pnl'])
    print(f"📅 Son 3 Gün En İyi: {best_recent['project_name']} ({best_recent['recent_pnl']*100:+.2f}%)")
    
    # Overall recommendation
    print(f"\n{'='*100}")
    print("💡 ÖNERİ")
    print(f"{'='*100}")
    
    # Score each project
    scores = {}
    for r in results:
        score = 0
        # PnL score (40%)
        score += (r['total_pnl'] * 100) * 0.4
        # Win rate score (30%)
        score += (r['win_rate'] / 100) * 30 * 0.3
        # Profit factor score (20%)
        score += min(r['profit_factor'], 5.0) * 4 * 0.2  # Cap at 5.0, scale to 0-4
        # Recent performance (10%)
        score += (r['recent_pnl'] * 100) * 0.1
        
        scores[r['project_name']] = score
    
    best_overall = max(scores.items(), key=lambda x: x[1])
    print(f"\n🏆 EN BAŞARILI PROJE (Genel Skor): {best_overall[0]}")
    print(f"   Skor: {best_overall[1]:.2f}")
    
    # Show all scores
    print(f"\n📊 Tüm Projelerin Skorları:")
    for project, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        print(f"   {project}: {score:.2f}")
    
    # Recommendation
    best_project = best_overall[0]
    best_result = next(r for r in results if r['project_name'] == best_project)
    
    print(f"\n✅ ÖNERİ: {best_project} projesi ile devam edilmeli")
    print(f"   Nedenler:")
    print(f"   - Toplam PnL: {best_result['total_pnl']*100:+.2f}%")
    print(f"   - Win Rate: {best_result['win_rate']:.1f}%")
    print(f"   - Profit Factor: {best_result['profit_factor']:.2f}")
    print(f"   - Son 3 Gün: {best_result['recent_pnl']*100:+.2f}%")
    
    # Warning if all projects are losing
    if all(r['total_pnl'] < 0 for r in results):
        print(f"\n⚠️ UYARI: Tüm projeler zarar ediyor!")
        print(f"   En az zarar eden: {min(results, key=lambda x: x['total_pnl'])['project_name']}")
        print(f"   Öneri: Tüm projeleri durdur ve stratejileri gözden geçir")

if __name__ == "__main__":
    main()

