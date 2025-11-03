#!/usr/bin/env python3
"""
Test telegram notification
"""

import json
import requests
from datetime import datetime

# Load config
with open('pengu_ema_config.json', 'r') as f:
    config = json.load(f)

# Telegram settings
bot_token = config['telegram']['bot_token']
chat_id = config['telegram']['chat_id']
base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

# Test message - Confirmation Start
telegram_msg = f"""
🔍 <b>PENGU EMA - Sinyal Confirmation Başladı</b>

📊 <b>Symbol:</b> PENGU/USDT
🎯 <b>Sinyal:</b> SHORT
💰 <b>Fiyat:</b> $0.020791
📈 <b>EMA Fast:</b> 0.021074
📉 <b>EMA Slow:</b> 0.021095

⏰ <b>Confirmation Süresi:</b> 121 saniye
🔄 <b>Kontrol Aralığı:</b> 60 saniye
📊 <b>Min Confirmation:</b> 2 kez

⏰ <b>Zaman:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

print("📱 TEST MESSAGE 1: Confirmation Start")
print("="*60)
print(telegram_msg)
print("="*60)
print()

# Test message - Position Opened
telegram_msg2 = f"""
🚀 <b>PENGU EMA - SHORT Pozisyon Açıldı</b>

📊 <b>Symbol:</b> PENGU/USDT
💰 <b>Fiyat:</b> $0.020791
📈 <b>EMA Fast:</b> 0.021074
📉 <b>EMA Slow:</b> 0.021095
🕯️ <b>Heikin Ashi:</b> Aktif

🎯 <b>Take Profit:</b> $0.020687 (0.5%)
🛡️ <b>Stop Loss:</b> $0.021103 (1.5%)
⚡ <b>Leverage:</b> 10x
💰 <b>Amount:</b> $100

⏰ <b>Zaman:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

print("📱 TEST MESSAGE 2: Position Opened")
print("="*60)
print(telegram_msg2)
print("="*60)

# Send test message
print(f"\n📤 Telegram'a gönderiliyor...")
print(f"Chat ID: {chat_id}")

try:
    data = {
        'chat_id': chat_id,
        'text': telegram_msg,
        'parse_mode': 'HTML'
    }
    response = requests.post(base_url, data=data, timeout=10)
    
    if response.status_code == 200:
        print("✅ Telegram mesajı başarıyla gönderildi!")
    else:
        print(f"❌ Telegram hatası: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"❌ Telegram gönderme hatası: {e}")

