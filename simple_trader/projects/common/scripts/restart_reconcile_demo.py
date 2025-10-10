#!/usr/bin/env python3
"""
Test Script: Restart Reconcile Demo
Servis restart simülasyonu ile reconcile mekanizmasını test eder
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
        self.reconcile_mode = False
    
    def create_market_order(self, symbol, side, amount, price=None, params=None):
        """Mock market order creation"""
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

def test_restart_reconcile():
    """Test restart and reconcile mechanism"""
    log.info("🧪 Starting Restart Reconcile Test")
    
    # Create mock exchange
    mock_exchange = MockExchange()
    
    # Test config
    config = {
        'idempotency': {
            'enabled': True,
            'state_file': 'test_restart_state.json',
            'retry_attempts': 3,
            'retry_delay': 0.5
        },
        'sl_tp': {
            'trigger_source': 'MARK_PRICE',
            'hedge_mode': False
        }
    }
    
    # Phase 1: Create orders and simulate service crash
    log.info("📝 Phase 1: Creating orders and simulating crash")
    
    order_client1 = IdempotentOrderClient(mock_exchange, config)
    
    # Create some orders
    order1 = order_client1.place_entry_market(
        symbol='BTC/USDT',
        side='buy',
        amount=0.001,
        extra='test_restart_1'
    )
    
    order2 = order_client1.place_stop_market_close(
        symbol='BTC/USDT',
        side='sell',
        stop_price=50000,
        intent='SL',
        extra='test_restart_sl'
    )
    
    log.info("💥 Simulating service crash...")
    
    # Phase 2: Restart service and reconcile
    log.info("📝 Phase 2: Restarting service and reconciling")
    
    # Create new order client (simulating service restart)
    order_client2 = IdempotentOrderClient(mock_exchange, config)
    
    # Reconcile pending orders
    reconciled_count = order_client2.reconcile_pending('BTC/USDT')
    
    log.info(f"✅ Reconciled {reconciled_count} orders")
    
    # Check final state
    log.info("📊 Final state after reconcile:")
    for client_id, order_data in order_client2.state['orders'].items():
        log.info(f"  {client_id}: {order_data['status']}")
    
    # Phase 3: Test duplicate order handling
    log.info("📝 Phase 3: Testing duplicate order handling")
    
    try:
        # Try to create the same order again
        duplicate_order = order_client2.place_entry_market(
            symbol='BTC/USDT',
            side='buy',
            amount=0.001,
            extra='test_restart_1'  # Same extra as before
        )
        
        log.info(f"✅ Duplicate order handled: {duplicate_order}")
        
    except Exception as e:
        log.error(f"❌ Duplicate order test failed: {e}")
    
    log.info("✅ Restart Reconcile Test Completed Successfully!")

if __name__ == "__main__":
    test_restart_reconcile()
