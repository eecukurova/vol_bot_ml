#!/usr/bin/env python3
"""
Test Script: Duplicate ID Demo
Duplicate clientOrderId handling test
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
        self.orders = {}
        self.order_counter = 1000
        self.duplicate_count = 0
    
    def create_market_order(self, symbol, side, amount, price=None, params=None):
        """Mock market order creation"""
        client_order_id = params.get('newClientOrderId', f"mock_{self.order_counter}")
        
        # Check for duplicate
        for order in self.orders.values():
            if order.get('clientOrderId') == client_order_id:
                self.duplicate_count += 1
                log.info(f"🔄 Duplicate clientOrderId detected: {client_order_id}")
                raise ccxt.BadRequest("Duplicate clientOrderId")
        
        order_id = f"mock_{self.order_counter}"
        self.order_counter += 1
        
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
        client_order_id = params.get('newClientOrderId', f"mock_{self.order_counter}")
        
        # Check for duplicate
        for order in self.orders.values():
            if order.get('clientOrderId') == client_order_id:
                self.duplicate_count += 1
                log.info(f"🔄 Duplicate clientOrderId detected: {client_order_id}")
                raise ccxt.BadRequest("Duplicate clientOrderId")
        
        order_id = f"mock_{self.order_counter}"
        self.order_counter += 1
        
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

def test_duplicate_id():
    """Test duplicate clientOrderId handling"""
    log.info("🧪 Starting Duplicate ID Test")
    
    # Create mock exchange
    mock_exchange = MockExchange()
    
    # Test config
    config = {
        'idempotency': {
            'enabled': True,
            'state_file': 'test_duplicate_state.json',
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
        # Test 1: Create first order
        log.info("📝 Test 1: Creating first order")
        order1 = order_client.place_entry_market(
            symbol='BTC/USDT',
            side='buy',
            amount=0.001,
            extra='test_duplicate'
        )
        
        log.info(f"✅ First order: {order1}")
        
        # Test 2: Try to create duplicate order
        log.info("📝 Test 2: Attempting duplicate order")
        
        # Manually create duplicate by modifying state
        # This simulates what happens when the same order is attempted twice
        for client_id in order_client.state['orders']:
            order_client.state['orders'][client_id]['status'] = 'PENDING'
        
        order2 = order_client.place_entry_market(
            symbol='BTC/USDT',
            side='buy',
            amount=0.001,
            extra='test_duplicate'  # Same extra as before
        )
        
        log.info(f"✅ Duplicate order handled: {order2}")
        
        # Test 3: Test SL/TP duplicate handling
        log.info("📝 Test 3: Testing SL/TP duplicate handling")
        
        sl_order1 = order_client.place_stop_market_close(
            symbol='BTC/USDT',
            side='sell',
            stop_price=50000,
            intent='SL',
            extra='test_sl_duplicate'
        )
        
        log.info(f"✅ First SL order: {sl_order1}")
        
        # Try duplicate SL order
        for client_id in order_client.state['orders']:
            if 'sl' in client_id.lower():
                order_client.state['orders'][client_id]['status'] = 'PENDING'
        
        sl_order2 = order_client.place_stop_market_close(
            symbol='BTC/USDT',
            side='sell',
            stop_price=50000,
            intent='SL',
            extra='test_sl_duplicate'  # Same extra as before
        )
        
        log.info(f"✅ Duplicate SL order handled: {sl_order2}")
        
        # Check final state
        log.info("📊 Final state:")
        for client_id, order_data in order_client.state['orders'].items():
            log.info(f"  {client_id}: {order_data['status']}")
        
        log.info(f"📊 Duplicate count: {mock_exchange.duplicate_count}")
        
        log.info("✅ Duplicate ID Test Completed Successfully!")
        
    except Exception as e:
        log.error(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    test_duplicate_id()
