#!/usr/bin/env python3
"""
Regression Channel Strategy Optimizer for Crypto
Volensy - Regresyon Kanalları ve Volatilite Stratejisi (KRIPTO Optimizasyonu)
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
from itertools import product
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.strategy.regression_channel import RegressionChannelStrategy


def download_binance_futures_klines(symbol: str, interval: str, days: int = 180):
    """
    Download Binance futures klines data
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "15m", "1h", "4h")
        days: Number of days to download
        
    Returns:
        DataFrame with OHLCV data
    """
    base_url = "https://fapi.binance.com/fapi/v1/klines"
    
    # Calculate start time
    end_time = int(time.time() * 1000)
    start_time = end_time - (days * 24 * 60 * 60 * 1000)
    
    all_data = []
    current_start = start_time
    
    while current_start < end_time:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current_start,
            'limit': 1000
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break
            
            all_data.extend(data)
            
            # Update start time for next batch
            current_start = data[-1][0] + 1
            
            # Avoid rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error downloading data: {e}")
            break
    
    if not all_data:
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(all_data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    
    df.set_index('timestamp', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']]
    
    return df


def optimize_regression_channel_crypto(symbol: str = "BTCUSDT", timeframe: str = "15m"):
    """
    Optimize Regression Channel Strategy for Crypto
    
    Args:
        symbol: Trading symbol (default: BTCUSDT)
        timeframe: Timeframe (default: 15m)
    """
    print(f"\n{'='*70}")
    print(f"🚀 Regression Channel Strategy Optimizer (CRYPTO)")
    print(f"{'='*70}")
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    
    # Download data
    print(f"\n📥 Downloading {symbol} {timeframe} data...")
    df = download_binance_futures_klines(symbol, timeframe, days=180)
    if df is None or len(df) < 200:
        print("❌ Failed to download data or insufficient data")
        return
    
    print(f"✅ Downloaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Parameter ranges for optimization (crypto-focused)
    # FOCUSED ON HIGH WIN RATE - More selective parameters
    reg_lens = [100, 125, 150]  # Longer periods = more selective
    inner_mults = [1.0, 1.2]  # Wider inner bands
    outer_mults = [2.0, 2.5, 3.0]  # Much wider outer bands = more selective
    sma_lens = [20, 26, 30]  # Longer SMA = stronger trend filter
    use_trend_filters = [True, False]  # Test both
    
    stoch_lens = [14, 20]  # Longer periods = more selective
    smooth_ks = [3, 5]  # More smoothing = less noise
    smooth_ds = [3, 5]  # More smoothing = less noise
    ob_levels = [80, 85, 90]  # Higher overbought = more selective
    os_levels = [10, 15, 20]  # Lower oversold = more selective
    
    tp_pcts = [0.02, 0.025, 0.03]  # Higher TP = better R:R
    sl_pcts = [0.01, 0.012, 0.015]  # Tighter SL = better R:R
    
    total_combinations = (
        len(reg_lens) * len(inner_mults) * len(outer_mults) * 
        len(sma_lens) * len(use_trend_filters) *
        len(stoch_lens) * len(smooth_ks) * len(smooth_ds) *
        len(ob_levels) * len(os_levels) *
        len(tp_pcts) * len(sl_pcts)
    )
    
    print(f"\n📊 Testing {total_combinations:,} parameter combinations...")
    print(f"⚠️  This will take approximately {total_combinations * 0.3 / 60:.1f} minutes...")
    
    all_results = []
    best_result = None
    best_score = -float('inf')
    
    combination_count = 0
    start_time = time.time()
    
    for (reg_len, inner_mult, outer_mult, sma_len, use_trend_filter,
         stoch_len, smooth_k, smooth_d, ob_level, os_level,
         tp_pct, sl_pct) in product(
        reg_lens, inner_mults, outer_mults, sma_lens, use_trend_filters,
        stoch_lens, smooth_ks, smooth_ds, ob_levels, os_levels,
        tp_pcts, sl_pcts
    ):
        combination_count += 1
        
        if combination_count % 50 == 0:
            elapsed = time.time() - start_time
            if combination_count > 0:
                remaining = (total_combinations - combination_count) * (elapsed / combination_count)
                best_wr = best_result['results']['win_rate'] if best_result else 0
                best_pf = best_result['results']['profit_factor'] if best_result else 0
                print(f"Progress: {combination_count}/{total_combinations} ({combination_count/total_combinations*100:.1f}%) | "
                      f"Elapsed: {elapsed/60:.1f}m | Remaining: {remaining/60:.1f}m | "
                      f"Best Score: {best_score:.2f} | Best WR: {best_wr:.1f}% | Best PF: {best_pf:.2f}")
        
        params = {
            'reg_len': reg_len,
            'inner_mult': inner_mult,
            'outer_mult': outer_mult,
            'sma_len': sma_len,
            'use_trend_filter': use_trend_filter,
            'stoch_len': stoch_len,
            'smooth_k': smooth_k,
            'smooth_d': smooth_d,
            'ob_level': ob_level,
            'os_level': os_level,
            'tp_pct': tp_pct,
            'sl_pct': sl_pct,
        }
        
        backtest_params = {
            'commission': 0.0005,  # 0.05% for crypto
            'slippage': 0.0002,    # 0.02% slippage
        }
        
        try:
            strategy = RegressionChannelStrategy(params)
            results = strategy.run_backtest(df, **backtest_params)
            
            # Filter results - want reasonable number of trades
            if results['total_trades'] < 10 or results['total_trades'] > 500:
                continue
            
            # CRITICAL: Minimum win rate must be 75%+
            if results['win_rate'] < 75:
                continue
            
            # Minimum profit factor (can be lower if win rate is high)
            if results['profit_factor'] < 0.8:
                continue
            
            # Risk/reward check
            if results['avg_win_pct'] > 0 and results['avg_loss_pct'] > 0:
                risk_reward = results['avg_win_pct'] / results['avg_loss_pct']
                if risk_reward < 0.5:  # At least 0.5:1 risk/reward
                    continue
            else:
                continue
            
            # Calculate score - PRIORITIZE WIN RATE ABOVE ALL
            capped_return = min(results['total_return_pct'], 10000)
            score = (
                results['win_rate'] * 10.0 +         # Win rate is CRITICAL - highest priority
                results['profit_factor'] * 5.0 +      # Profit factor is important but secondary
                capped_return * 0.1 -                 # Return matters less
                results['max_drawdown_pct'] * 0.3 +  # Penalize drawdown
                (results['total_trades'] / 20) * 0.05  # Small bonus for more trades
            )
            
            # Extra bonus for very high win rates
            if results['win_rate'] >= 80:
                score += 50.0
            elif results['win_rate'] >= 75:
                score += 20.0
            
            result_entry = {
                'params': params,
                'results': results,
                'score': score
            }
            all_results.append(result_entry)
            
            if score > best_score:
                best_score = score
                best_result = result_entry
                print(f"\n⭐ New Best Score: {score:.2f}")
                print(f"   Trades: {results['total_trades']} | WR: {results['win_rate']:.1f}% | PF: {results['profit_factor']:.2f}")
                print(f"   Return: {results['total_return_pct']:.1f}% | DD: {results['max_drawdown_pct']:.1f}%")
                print(f"   Params: reg_len={reg_len}, outer_mult={outer_mult}, stoch_len={stoch_len}")
                print(f"   TP: {tp_pct*100:.1f}% | SL: {sl_pct*100:.1f}% | Trend Filter: {use_trend_filter}")
        
        except Exception as e:
            continue
    
    # Sort results by score
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"regression_channel_optimization_{symbol}_{timestamp}.json"
    
    # Convert to JSON-serializable format
    json_results = []
    for r in all_results[:100]:  # Top 100 results
        json_r = {
            'params': r['params'],
            'score': r['score'],
            'total_trades': r['results']['total_trades'],
            'win_rate': r['results']['win_rate'],
            'profit_factor': r['results']['profit_factor'],
            'total_return_pct': r['results']['total_return_pct'],
            'max_drawdown_pct': r['results']['max_drawdown_pct'],
            'winning_trades': r['results']['winning_trades'],
            'losing_trades': r['results']['losing_trades'],
            'avg_win_pct': r['results']['avg_win_pct'],
            'avg_loss_pct': r['results']['avg_loss_pct'],
        }
        json_results.append(json_r)
    
    with open(results_file, 'w') as f:
        json.dump(json_results, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"✅ Optimization Complete!")
    print(f"{'='*70}")
    print(f"\n📊 Top 10 Results:")
    print(f"{'='*70}")
    
    for i, result in enumerate(all_results[:10], 1):
        r = result['results']
        p = result['params']
        print(f"\n{i}. Score: {result['score']:.2f}")
        print(f"   Trades: {r['total_trades']} | WR: {r['win_rate']:.1f}% | PF: {r['profit_factor']:.2f}")
        print(f"   Return: {r['total_return_pct']:.1f}% | DD: {r['max_drawdown_pct']:.1f}%")
        print(f"   Params:")
        print(f"      reg_len: {p['reg_len']}, inner_mult: {p['inner_mult']}, outer_mult: {p['outer_mult']}")
        print(f"      sma_len: {p['sma_len']}, use_trend_filter: {p['use_trend_filter']}")
        print(f"      stoch_len: {p['stoch_len']}, smooth_k: {p['smooth_k']}, smooth_d: {p['smooth_d']}")
        print(f"      ob_level: {p['ob_level']}, os_level: {p['os_level']}")
        print(f"      tp_pct: {p['tp_pct']*100:.1f}%, sl_pct: {p['sl_pct']*100:.1f}%")
    
    print(f"\n💾 Results saved to: {results_file}")
    
    # Generate optimized Pine Script
    if best_result:
        print(f"\n{'='*70}")
        print(f"📝 Generating Optimized Pine Script...")
        print(f"{'='*70}")
        
        p = best_result['params']
        pine_script = generate_optimized_pine_script(p, symbol)
        
        pine_file = f"regression_channel_optimized_{symbol}_{timestamp}.pine"
        with open(pine_file, 'w') as f:
            f.write(pine_script)
        
        print(f"✅ Optimized Pine Script saved to: {pine_file}")
        print(f"\n📋 Optimized Parameters:")
        print(f"   reg_len: {p['reg_len']}")
        print(f"   inner_mult: {p['inner_mult']}")
        print(f"   outer_mult: {p['outer_mult']}")
        print(f"   sma_len: {p['sma_len']}")
        print(f"   use_trend_filter: {p['use_trend_filter']}")
        print(f"   stoch_len: {p['stoch_len']}")
        print(f"   smooth_k: {p['smooth_k']}")
        print(f"   smooth_d: {p['smooth_d']}")
        print(f"   ob_level: {p['ob_level']}")
        print(f"   os_level: {p['os_level']}")


def generate_optimized_pine_script(params: dict, symbol: str) -> str:
    """Generate optimized Pine Script from parameters"""
    
    pine = f"""//@version=6
strategy("Volensy – Regresyon Kanalları (Optimized for {symbol})", overlay = true,
     initial_capital = 100000,
     commission_type = strategy.commission.percent,
     commission_value = 0.05,
     default_qty_type = strategy.percent_of_equity,
     default_qty_value = 10,
     pyramiding = 0)

//═══════════════════════════════════════════════
// OPTIMIZED PARAMETERS FOR {symbol}
//═══════════════════════════════════════════════
// Optimized on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
// Win Rate: {params.get('win_rate', 'N/A')}%
// Profit Factor: {params.get('profit_factor', 'N/A')}

// Regresyon Kanalı
regLen      = input.int({params['reg_len']}, "Regresyon Periyodu", minval = 10, group = "Regresyon Kanalı")
innerMult   = input.float({params['inner_mult']}, "İç Bant StdDev Katsayısı", step = 0.1, group = "Regresyon Kanalı")
outerMultK  = input.float({params['outer_mult']}, "Dış Bant StdDev (KRIPTO)", step = 0.1, group = "Regresyon Kanalı")

// Trend Filtresi
useTrendFilterInput = input.bool({str(params['use_trend_filter']).lower()}, "Trend Filtresi (SMA) Kullan", group = "Trend Filtresi")
smaLen              = input.int({params['sma_len']}, "SMA Uzunluğu", minval = 1, group = "Trend Filtresi")

// Volatilite Osilatörü
stochLen    = input.int({params['stoch_len']}, "Volatilite Osilatörü Periyodu", minval = 3, group = "Volatilite Osilatörü")
smoothK     = input.int({params['smooth_k']},  "K Yumuşatma", minval = 1, group = "Volatilite Osilatörü")
smoothD     = input.int({params['smooth_d']},  "D Yumuşatma", minval = 1, group = "Volatilite Osilatörü")
obLevelK    = input.float({params['ob_level']}, "Aşırı Alım (KRIPTO)", minval = 50, maxval = 100, step = 1, group = "Volatilite Osilatörü")
osLevelK    = input.float({params['os_level']}, "Aşırı Satım (KRIPTO)", minval = 0,  maxval = 50,  step = 1, group = "Volatilite Osilatörü")

// Sinyal Ayarları
showBgZones = input.bool(true, "Aşırı ALIM/SATIM Bölgelerini Boya", group = "Görsellik")
showLabels  = input.bool(true, "AL / SAT Şekillerini Göster", group = "Görsellik")

// Mod parametreleri (KRIPTO)
outerMult   = outerMultK
obLevel     = obLevelK
osLevel     = osLevelK
useTrendFilter = useTrendFilterInput

//═══════════════════════════════════════════════
// REGRESYON KANALI HESAPLARI
//═══════════════════════════════════════════════
regressionLine = ta.linreg(close, regLen, 0)
regDev = ta.stdev(close, regLen)

upperInner = regressionLine + regDev * innerMult
lowerInner = regressionLine - regDev * innerMult
upperOuter = regressionLine + regDev * outerMult
lowerOuter = regressionLine - regDev * outerMult

//═══════════════════════════════════════════════
// TREND FİLTRESİ (SMA)
//═══════════════════════════════════════════════
sma = ta.sma(close, smaLen)
bullTrend = not useTrendFilter or close > sma
bearTrend = not useTrendFilter or close < sma

//═══════════════════════════════════════════════
// VOLATİLİTE OSİLATÖRÜ
//═══════════════════════════════════════════════
kRaw = ta.stoch(high, low, close, stochLen)
k    = ta.sma(kRaw, smoothK)
d    = ta.sma(k, smoothD)

plot(k, title = "Volatilite Osilatörü %K", linewidth = 2)
plot(d, title = "Volatilite Osilatörü %D", linewidth = 1)
hline(obLevel, "Aşırı Alım",  linestyle = hline.style_dotted)
hline(osLevel, "Aşırı Satım", linestyle = hline.style_dotted)

//═══════════════════════════════════════════════
// GÖRSELLİK
//═══════════════════════════════════════════════
bgCol = showBgZones ? (close > upperOuter ? color.new(color.red, 85) : close < lowerOuter ? color.new(color.green, 85) : na) : na
bgcolor(bgCol)

plot(regressionLine, title = "Regresyon Orta Hat", color = color.new(color.gray, 0), linewidth = 2)
plot(sma, title = "SMA", color = color.new(color.orange, 0), linewidth = 2)
plot(upperInner, title = "İç Üst Bant", color = color.new(color.red, 60), linewidth = 1)
plot(lowerInner, title = "İç Alt Bant", color = color.new(color.green, 60), linewidth = 1)
plot(upperOuter, title = "Dış Üst Bant", color = color.new(color.red, 0), linewidth = 1, style = plot.style_linebr)
plot(lowerOuter, title = "Dış Alt Bant", color = color.new(color.green, 0), linewidth = 1, style = plot.style_linebr)

//═══════════════════════════════════════════════
// SİNYAL KOŞULLARI (KRIPTO MODU)
//═══════════════════════════════════════════════
inExtremeLow  = close <= lowerOuter
inExtremeHigh = close >= upperOuter

// KRIPTO → K ve D kesişimi, seviye yalnızca filtre
volBuyK  = k < osLevel and ta.crossover(k, d)
volSellK = k > obLevel and ta.crossunder(k, d)

volBuy  = volBuyK
volSell = volSellK

buyCond  = inExtremeLow  and bullTrend and volBuy
sellCond = inExtremeHigh and bearTrend and volSell

//═══════════════════════════════════════════════
// STRATEJİ EMİRLERİ
//═══════════════════════════════════════════════
if buyCond and barstate.isconfirmed
    if strategy.position_size < 0
        strategy.close("Short")
    strategy.entry("Long", strategy.long)

if sellCond and barstate.isconfirmed
    if strategy.position_size > 0
        strategy.close("Long")
    strategy.entry("Short", strategy.short)

//═══════════════════════════════════════════════
// GRAFİKTE İŞARETLER
//═══════════════════════════════════════════════
plotshape(showLabels and buyCond,
     title = "AL",
     text = "AL",
     style = shape.triangleup,
     location = location.belowbar,
     color = color.lime,
     size = size.large)

plotshape(showLabels and sellCond,
     title = "SAT",
     text = "SAT",
     style = shape.triangledown,
     location = location.abovebar,
     color = color.red,
     size = size.large)
"""
    
    return pine


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Optimize Regression Channel Strategy for Crypto')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='Trading symbol (default: BTCUSDT)')
    parser.add_argument('--timeframe', type=str, default='15m', help='Timeframe (default: 15m)')
    
    args = parser.parse_args()
    
    optimize_regression_channel_crypto(symbol=args.symbol, timeframe=args.timeframe)

