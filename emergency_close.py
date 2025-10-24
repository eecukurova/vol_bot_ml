#!/usr/bin/env python3
import ccxt
import json

# Config yükle
with open('sol_macd_config.json', 'r') as f:
    config = json.load(f)

# Exchange bağlantısı
exchange = ccxt.binance({
    'apiKey': config['api_key'],
    'secret': config['secret'],
    'sandbox': config['sandbox'],
    'options': {'defaultType': 'future'}
})

print("🚨 ACİL: TÜM POZİSYONLARI KAPATIYORUM!")

# Mevcut pozisyonları kontrol et
positions = exchange.fetch_positions(['SOL/USDT'])
for pos in positions:
    if pos['contracts'] > 0:
        print(f"Pozisyon bulundu: {pos['contracts']} {pos['symbol']} @ {pos['entryPrice']}")
        
        # Pozisyonu kapat
        try:
            if pos['side'] == 'long':
                # Long pozisyonu kapat (sell)
                result = exchange.create_market_sell_order('SOL/USDT', pos['contracts'])
                print(f"✅ Long pozisyon kapatıldı: {result['id']}")
            else:
                # Short pozisyonu kapat (buy)
                result = exchange.create_market_buy_order('SOL/USDT', pos['contracts'])
                print(f"✅ Short pozisyon kapatıldı: {result['id']}")
        except Exception as e:
            print(f"❌ Pozisyon kapatma hatası: {e}")

# Açık order'ları iptal et
print("\n🚨 AÇIK ORDERLARI İPTAL EDİYORUM!")
open_orders = exchange.fetch_open_orders('SOL/USDT')
for order in open_orders:
    try:
        exchange.cancel_order(order['id'], 'SOL/USDT')
        print(f"✅ Order iptal edildi: {order['id']} ({order['type']})")
    except Exception as e:
        print(f"❌ Order iptal hatası: {order['id']} - {e}")

print("\n✅ TÜM POZİSYONLAR VE ORDERLAR TEMİZLENDİ!")
