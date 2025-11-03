#!/usr/bin/env python3
"""
Cleanup script to cancel all open orders on Binance Futures
"""

import ccxt
import json
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Load config
with open('pengu_ema_config.json', 'r') as f:
    config = json.load(f)

# Setup exchange
exchange = ccxt.binance({
    'apiKey': config['api_key'],
    'secret': config['secret'],
    'sandbox': config.get('sandbox', False),
    'options': {
        'defaultType': 'future',
    }
})

symbol = config['symbol']

try:
    log.info(f"📋 {symbol} için açık emirler kontrol ediliyor...")
    
    # Fetch open orders
    open_orders = exchange.fetch_open_orders(symbol)
    
    log.info(f"📊 Toplam {len(open_orders)} açık emir bulundu")
    
    if len(open_orders) > 0:
        log.info("🗑️ Açık emirler iptal ediliyor...")
        
        for order in open_orders:
            order_id = order['id']
            order_side = order['side']
            order_amount = order['amount']
            
            try:
                exchange.cancel_order(order_id, symbol)
                log.info(f"✅ Emir iptal edildi: {order_id} - {order_side} {order_amount}")
            except Exception as e:
                log.error(f"❌ Emir iptal edilemedi: {order_id} - {e}")
        
        log.info(f"✅ {len(open_orders)} emir iptal edildi")
    else:
        log.info("✅ Açık emir yok")
    
    # Check positions
    log.info(f"📊 Aktif pozisyonlar kontrol ediliyor...")
    positions = exchange.fetch_positions([symbol])
    
    for pos in positions:
        position_size = pos.get('size', pos.get('contracts', pos.get('amount', 0)))
        if pos['symbol'] == symbol and abs(float(position_size)) > 0:
            log.info(f"📊 Pozisyon: {position_size} @ {pos.get('entryPrice', 'N/A')}")
    
except Exception as e:
    log.error(f"❌ Hata: {e}")
