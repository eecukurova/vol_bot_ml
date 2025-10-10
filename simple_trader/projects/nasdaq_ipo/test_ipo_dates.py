#!/usr/bin/env python3
from core.filters import StockFilter
from core.data import analyze_stocks
from core.utils import days_ago, parse_date
import logging
logging.basicConfig(level=logging.INFO)

# Test CLOV and SPCE only
symbols = ['CLOV', 'SPCE']
analyses = analyze_stocks(symbols)

# Add IPO dates manually
for analysis in analyses:
    if analysis['symbol'] == 'CLOV':
        analysis['ipoDate'] = '2025-11-15'
    elif analysis['symbol'] == 'SPCE':
        analysis['ipoDate'] = '2025-12-01'

print('Analyses with IPO dates:')
for analysis in analyses:
    symbol = analysis['symbol']
    close = analysis['lastClose']
    rsi = analysis['rsi14']
    adx = analysis['adx14']
    dd = analysis['drawdownFromHigh']
    ipo_date = analysis['ipoDate']
    print(f'{symbol}: Close=${close:.2f}, RSI={rsi:.1f}, ADX={adx:.1f}, DD={dd:.1f}%, IPO={ipo_date}')

# Test IPO date filter
cutoff_date = days_ago(180)
print(f'Cutoff date: {cutoff_date}')

for analysis in analyses:
    ipo_date_str = analysis.get('ipoDate', '')
    ipo_date = parse_date(ipo_date_str)
    symbol = analysis['symbol']
    print(f'{symbol}: {ipo_date_str} -> {ipo_date} (>= {cutoff_date}? {ipo_date >= cutoff_date if ipo_date else False})')

# Test filters
filter_obj = StockFilter(min_price=0.1, max_price=10.0, min_volume=100000, rsi_min=20.0, rsi_max=80.0, min_drawdown=10.0)
filtered = filter_obj.apply_filters(analyses)
print(f'Filtered: {len(filtered)} stocks')
