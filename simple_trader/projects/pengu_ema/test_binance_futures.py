#!/usr/bin/env python3
import ccxt
import json

# Binance futures exchange
exchange = ccxt.binance({
    "sandbox": False,
    "apiKey": "test",
    "secret": "test",
    "options": {
        "defaultType": "future"
    }
})

try:
    print("🔍 Binance futures markets yükleniyor...")
    markets = exchange.load_markets()
    
    # BTC futures marketini bul
    btc_futures = None
    for symbol, market in markets.items():
        if "BTC" in symbol and "USDT" in symbol and market.get("type") == "swap":
            btc_futures = market
            print(f"✅ BTC Futures bulundu: {symbol}")
            print(f"   Type: {market.get(\"type\")}")
            print(f"   Contract: {market.get(\"contract\")}")
            print(f"   Quote: {market.get(\"quote\")}")
            print(f"   Settle: {market.get(\"settle\")}")
            print(f"   Active: {market.get(\"active\")}")
            print(f"   ID: {market.get(\"id\")}")
            break
    
    if not btc_futures:
        print("❌ BTC Futures bulunamadı")
        
        # Tüm swap marketleri listele
        print("
📊 Tüm swap marketleri:")
        swap_markets = [s for s, m in markets.items() if m.get("type") == "swap"]
        for market in swap_markets[:10]:  # İlk 10u göster
            print(f"   {market}")
            
except Exception as e:
    print(f"❌ Hata: {e}")
