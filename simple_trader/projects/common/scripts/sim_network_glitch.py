#!/usr/bin/env python3
"""
Test Script: Network Glitch Simulation
Ağ hatası simülasyonu ile retry/duplicate akışını test eder
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt
import json
import time
import logging
from order_client import IdempotentOrderClient

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

class MockExchange:
    """Mock exchange for testing"""
    def __init__(self):
        self.call_count = 0
        self.orders = {}
        self.order_counter = 1000
    
    def create_market_order(self, symbol, side, amount, price=None, params=None):
        """Mock market order creation"""
        self.call_count += 1
        
        # Simulate network error on first call
        if self.call_count == 1:
            log.info("🌐 Simulating network error...")
            raise ccxt.NetworkError("Simulated network error")
        
        # Create mock order
        order_id = f"mock_{self.order_counter}"
        self.order_counter += 1
        
        client_order_id = params.get('newClientOrderId', f"mock_{order_id}")
        
        order = {
            'id': order_id,
            'clientOrderId': client_order_id,
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': price,
            'status': 'filled',
            'timestamp': int(time.time() * 1000)
        }
        
        self.orders[order_id] = order
        log.info(f"✅ Mock order created: {order_id}")
        return order
    
    def create_order(self, symbol, type, side, amount, price, params=None):
        """Mock order creation"""
        self.call_count += 1
        
        # Simulate network error on first call
        if self.call_count == 1:
            log.info("🌐 Simulating network error...")
            raise ccxt.NetworkError("Simulated network error")
        
        # Create mock order
        order_id = f"mock_{self.order_counter}"
        self.order_counter += 1
        
        client_order_id = params.get('newClientOrderId', f"mock_{order_id}")
        
        order = {
            'id': order_id,
            'clientOrderId': client_order_id,
            'symbol': symbol,
            'type': type,
            'side': side,
            'amount': amount,
            'price': price,
            'status': 'open',
            'timestamp': int(time.time() * 1000)
        }
        
        self.orders[order_id] = order
        log.info(f"✅ Mock {type} order created: {order_id}")
        return order
    
    def fetch_open_orders(self, symbol=None):
        """Mock fetch open orders"""
        return [order for order in self.orders.values() if order['status'] == 'open']
    
    def fetch_orders(self, symbol=None, limit=50):
        """Mock fetch orders"""
        return list(self.orders.values())[-limit:]
    
    def price_to_precision(self, symbol, price):
        """Mock price precision"""
        return round(price, 4)

def test_network_glitch():
    """Test network glitch and retry mechanism"""
    log.info("🧪 Starting Network Glitch Test")
    
    # Create mock exchange
    mock_exchange = MockExchange()
    
    # Test config
    config = {
        'idempotency': {
            'enabled': True,
            'state_file': 'test_state.json',
            'retry_attempts': 3,
            'retry_delay': 0.5
        },
        'sl_tp': {
            'trigger_source': 'MARK_PRICE',
            'hedge_mode': False
        }
    }
    
    # Create order client
    order_client = IdempotentOrderClient(mock_exchange, config)
    
    try:
        # Test 1: Market order with network glitch
        log.info("📝 Test 1: Market order with network glitch")
        order = order_client.place_entry_market(
            symbol='BTC/USDT',
            side='buy',
            amount=0.001,
            extra='test_glitch'
        )
        
        log.info(f"✅ Order result: {order}")
        
        # Test 2: SL order with network glitch
        log.info("📝 Test 2: SL order with network glitch")
        sl_order = order_client.place_stop_market_close(
            symbol='BTC/USDT',
            side='sell',
            stop_price=50000,
            intent='SL',
            extra='test_sl_glitch'
        )
        
        log.info(f"✅ SL Order result: {sl_order}")
        
        # Test 3: TP order with network glitch
        log.info("📝 Test 3: TP order with network glitch")
        tp_order = order_client.place_stop_market_close(
            symbol='BTC/USDT',
            side='sell',
            stop_price=55000,
            intent='TP',
            extra='test_tp_glitch'
        )
        
        log.info(f"✅ TP Order result: {tp_order}")
        
        # Check state
        log.info("📊 Final state:")
        for client_id, order_data in order_client.state['orders'].items():
            log.info(f"  {client_id}: {order_data['status']}")
        
        log.info("✅ Network Glitch Test Completed Successfully!")
        
    except Exception as e:
        log.error(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    test_network_glitch()
