#!/usr/bin/env python3
"""
Idempotent Order Client for Binance Futures
Güvenli, çift emir korumalı ve state yönetimli order sistemi
"""

import ccxt
import json
import hashlib
import time
import logging
import os
from datetime import datetime
from typing import Dict, Optional, Any, Tuple
from pathlib import Path

class IdempotentOrderClient:
    """
    Idempotent order client for Binance Futures
    - Deterministik clientOrderId üretimi
    - State persistence (JSON)
    - Retry mekanizması
    - Duplicate detection
    - Reconcile mekanizması
    """
    
    def __init__(self, exchange: ccxt.binance, config: Dict[str, Any]):
        """
        Initialize IdempotentOrderClient
        
        Args:
            exchange: ccxt.binance instance
            config: Configuration dict with idempotency settings
        """
        self.exchange = exchange
        self.config = config
        
        # Idempotency settings
        self.idempotency_config = config.get('idempotency', {})
        self.enabled = self.idempotency_config.get('enabled', True)
        self.state_file = self.idempotency_config.get('state_file', 'runs/state.json')
        self.retry_attempts = self.idempotency_config.get('retry_attempts', 3)
        self.retry_delay = self.idempotency_config.get('retry_delay', 1.0)
        
        # SL/TP settings
        self.sl_tp_config = config.get('sl_tp', {})
        self.trigger_source = self.sl_tp_config.get('trigger_source', 'MARK_PRICE')
        self.hedge_mode = self.sl_tp_config.get('hedge_mode', False)
        
        # Logging
        self.log = logging.getLogger(__name__)
        
        # State management
        self.state = {'orders': {}}
        self._load_state()
        
        self.log.info(f"🚀 IdempotentOrderClient initialized")
        self.log.info(f"📁 State file: {self.state_file}")
        self.log.info(f"🔄 Retry attempts: {self.retry_attempts}")
        self.log.info(f"🎯 Trigger source: {self.trigger_source}")
        self.log.info(f"🔀 Hedge mode: {self.hedge_mode}")
        self.log.info(f"📊 Last signal: {self.state.get('last_signal', 'None')}")
        
        # Market metadata cache
        self._market_cache = {}
    
    def _load_state(self):
        """Load state from JSON file"""
        try:
            state_path = Path(self.state_file)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            
            if state_path.exists():
                with open(state_path, 'r') as f:
                    self.state = json.load(f)
                self.log.info(f"📂 State loaded: {len(self.state.get('orders', {}))} orders")
            else:
                self.log.info("📂 No existing state file, starting fresh")
        except Exception as e:
            self.log.error(f"❌ Failed to load state: {e}")
            self.state = {'orders': {}}
        
        # Ensure required keys exist
        if 'orders' not in self.state:
            self.state['orders'] = {}
        if 'last_signal' not in self.state:
            self.state['last_signal'] = None
        if 'last_signal_time' not in self.state:
            self.state['last_signal_time'] = None
    
    def _save_state(self):
        """Save state to JSON file atomically"""
        try:
            state_path = Path(self.state_file)
            temp_path = state_path.with_suffix('.tmp')
            
            with open(temp_path, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            # Atomic replace
            temp_path.replace(state_path)
            self.log.debug(f"💾 State saved: {len(self.state.get('orders', {}))} orders")
        except Exception as e:
            self.log.error(f"❌ Failed to save state: {e}")
    
    def _generate_deterministic_client_order_id(self, intent_type: str, symbol: str, side: str, 
                                             qty: float, price: Optional[float] = None, 
                                             reduce_only: bool = False, extra: str = "") -> str:
        """
        Deterministik clientOrderId üretimi
        
        Format: EMA::<symbol_narrow>::<side>::<intent_type>::<epoch_bucket>::<hash>
        """
        try:
            # Symbol'ü daralt (BTC/USDT:USDT -> BTCUSDT)
            symbol_narrow = symbol.replace('/', '').replace(':', '').replace('USDT', '')
            
            # Epoch bucket (5 dakikalık gruplar)
            epoch_bucket = int(time.time() // 300) * 300
            
            # Essential fields hash (timestamp ekleyerek unique yap)
            current_time = int(time.time())
            essential_fields = f"{symbol_narrow}:{side}:{intent_type}:{qty:.6f}:{current_time}"
            if price:
                essential_fields += f":{price:.6f}"
            if reduce_only:
                essential_fields += ":reduceOnly"
            if extra:
                essential_fields += f":{extra}"
            
            # Hash oluştur (ilk 8 karakter)
            hash_obj = hashlib.md5(essential_fields.encode())
            hash_suffix = hash_obj.hexdigest()[:8]
            
            # Deterministik clientOrderId (kısa format)
            side_short = side[0].upper()  # B veya S
            intent_short = intent_type.lower()[:2]  # en, sl, tp
            client_order_id = f"EMA-{symbol_narrow}-{side_short}-{intent_short}-{hash_suffix}"
            
            return client_order_id
            
        except Exception as e:
            self.log.error(f"❌ Deterministik clientOrderId üretim hatası: {e}")
            # Fallback to original method
            return self._generate_client_order_id(intent_type, symbol, side, extra)
    
    def _register_intent(self, intent_id: str, symbol: str, side: str, intent_type: str, 
                        qty: float, price: Optional[float] = None, reduce_only: bool = False) -> str:
        """
        Intent kaydı ve deterministik clientOrderId üretimi
        """
        try:
            # Deterministik clientOrderId üret
            client_order_id = self._generate_deterministic_client_order_id(
                intent_type, symbol, side, qty, price, reduce_only, intent_id
            )
            
            # Intent kaydı
            intent_record = {
                'intent_id': intent_id,
                'symbol': symbol,
                'side': side,
                'type': intent_type,
                'qty': qty,
                'price': price,
                'reduceOnly': reduce_only,
                'timeInForce': 'GTC',
                'created_at': int(time.time()),
                'state': 'PENDING',
                'client_order_id': client_order_id
            }
            
            # State'e kaydet
            if 'intents' not in self.state:
                self.state['intents'] = {}
            
            self.state['intents'][intent_id] = intent_record
            self._save_state()
            
            self.log.info(f"🔄 INTENT NEW id={intent_id} client_oid={client_order_id} type={intent_type} reduceOnly={reduce_only}")
            
            # QA Tracking - S6 Idempotent Retry
            if hasattr(self, 'qa_tracker'):
                self.qa_track_log('idempotent', f"INTENT NEW id={intent_id} client_oid={client_order_id} type={intent_type} reduceOnly={reduce_only}")
            
            return client_order_id
            
        except Exception as e:
            self.log.error(f"❌ Intent kayıt hatası: {e}")
            return self._generate_client_order_id(intent_type, symbol, side, intent_id)
    
    def _check_intent_duplicate(self, intent_id: str) -> bool:
        """Intent duplikasyon kontrolü"""
        try:
            if 'intents' not in self.state:
                return False
            
            existing_intent = self.state['intents'].get(intent_id)
            if existing_intent and existing_intent['state'] in ['PENDING', 'SENT']:
                self.log.warning(f"🔄 INTENT DEDUP removed_stale client_oid={existing_intent['client_order_id']} keep={intent_id}")
                
                # QA Tracking - S6 Idempotent Retry
                if hasattr(self, 'qa_tracker'):
                    self.qa_track_log('idempotent', f"INTENT DEDUP removed_stale client_oid={existing_intent['client_order_id']} keep={intent_id}")
                
                return True
            
            return False
            
        except Exception as e:
            self.log.error(f"❌ Intent duplikasyon kontrol hatası: {e}")
            return False
    
    def _link_intent_to_exchange_order(self, intent_id: str, exchange_order_id: str):
        """Intent'i exchange order ile eşleştir"""
        try:
            if 'intents' not in self.state or intent_id not in self.state['intents']:
                return
            
            self.state['intents'][intent_id]['state'] = 'LINKED'
            self.state['intents'][intent_id]['exchange_order_id'] = exchange_order_id
            self._save_state()
            
            self.log.info(f"🔄 INTENT LINKED id={intent_id} exchange_order_id={exchange_order_id}")
            
            # QA Tracking - S6 Idempotent Retry
            if hasattr(self, 'qa_tracker'):
                self.qa_track_log('idempotent', f"INTENT LINKED id={intent_id} exchange_order_id={exchange_order_id}")
            
        except Exception as e:
            self.log.error(f"❌ Intent link hatası: {e}")
    
    def _generate_client_order_id(self, intent: str, symbol: str, side: str, extra: str = "") -> str:
        """
        Generate deterministic clientOrderId
        
        Format: EMA::{symbol_narrow}::{side}::{intent_type}::{epoch_bucket}::{hash}
        
        Args:
            intent: ENTRY, SL, TP
            symbol: Trading symbol (e.g., EIGEN/USDT)
            side: buy, sell
            extra: Additional data for uniqueness
            
        Returns:
            Deterministic clientOrderId
        """
        try:
            # Symbol'ü daralt (SOL/USDT:USDT -> SOL)
            symbol_narrow = symbol.replace('/', '').replace(':', '').replace('USDT', '')
            
            # Epoch bucket (5 dakikalık gruplar)
            epoch_bucket = int(time.time() // 300) * 300
            
            # Essential fields hash (timestamp ekleyerek unique yap)
            current_time = int(time.time())
            essential_fields = f"{symbol_narrow}:{side}:{intent.lower()}:{extra}:{current_time}"
            
            # Hash oluştur (ilk 8 karakter)
            hash_obj = hashlib.md5(essential_fields.encode())
            hash_suffix = hash_obj.hexdigest()[:8]
            
            # Deterministik clientOrderId (çok kısa format - max 35 karakter)
            side_short = side[0].upper()  # B veya S
            intent_short = intent.lower()[:2]  # en, sl, tp
            client_id = f"EMA-{symbol_narrow}-{side_short}-{intent_short}-{hash_suffix}"
            
        except Exception as e:
            self.log.error(f"❌ Deterministik clientOrderId üretim hatası: {e}")
            # Fallback to simple format
            hash_obj = hashlib.sha1(f"{intent.lower()}-{symbol}-{side}-{extra}".encode())
            hash_hex = hash_obj.hexdigest()[:8]
            client_id = f"EMA-{intent.lower()[:2]}-{hash_hex}"
        
        self.log.debug(f"🔑 Generated clientOrderId: {client_id}")
        return client_id
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable"""
        retryable_errors = (
            ccxt.NetworkError,
            ccxt.DDoSProtection,
            ccxt.ExchangeNotAvailable,
            ccxt.RequestTimeout
        )
        
        return isinstance(error, retryable_errors)
    
    def _is_duplicate_error(self, error: Exception) -> bool:
        """Check if error is duplicate clientOrderId"""
        error_msg = str(error).lower()
        return 'duplicate' in error_msg and 'clientorderid' in error_msg
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """Retry function with exponential backoff + jitter"""
        for attempt in range(self.retry_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not self._is_retryable_error(e):
                    raise  # Non-retryable error
                
                if attempt == self.retry_attempts - 1:
                    raise  # Last attempt failed
                
                # Calculate delay with exponential backoff + jitter
                delay = min(self.retry_delay * (2 ** attempt), 4.0)
                jitter = delay * 0.1 * (0.5 - time.time() % 1)  # ±10% jitter
                total_delay = delay + jitter
                
                self.log.warning(f"🔄 ORDER_RETRY attempt {attempt + 1}/{self.retry_attempts}, retrying in {total_delay:.2f}s: {e}")
                time.sleep(total_delay)
    
    def _reconcile_order(self, client_order_id: str, symbol: str) -> bool:
        """
        Reconcile order with exchange
        
        Args:
            client_order_id: Order ID to reconcile
            symbol: Trading symbol
            
        Returns:
            True if order found and reconciled
        """
        try:
            # First check open orders
            open_orders = self.exchange.fetch_open_orders(symbol)
            for order in open_orders:
                if order.get('clientOrderId') == client_order_id:
                    self.log.info(f"✅ RECONCILE_RESOLVED: Found open order {client_order_id}")
                    return True
            
            # Then check recent orders (last 50)
            recent_orders = self.exchange.fetch_orders(symbol, limit=50)
            for order in recent_orders:
                if order.get('clientOrderId') == client_order_id:
                    self.log.info(f"✅ RECONCILE_RESOLVED: Found recent order {client_order_id}")
                    return True
            
            self.log.warning(f"⚠️ Order {client_order_id} not found on exchange")
            return False
            
        except Exception as e:
            self.log.error(f"❌ Reconcile error for {client_order_id}: {e}")
            return False
    
    def place_entry_market(self, symbol: str, side: str, amount: float, 
                          position_side: Optional[str] = None, extra: str = "", 
                          reduce_only: bool = False) -> Dict[str, Any]:
        """
        Place market entry order with idempotency
        
        Args:
            symbol: Trading symbol
            side: buy/sell
            amount: Order amount
            position_side: LONG/SHORT (for hedge mode)
            extra: Additional data for uniqueness
            
        Returns:
            Order result dict
        """
        if not self.enabled:
            # Fallback to direct order
            return self.exchange.create_market_order(symbol, side, amount)
        
        # Intent ID oluştur
        intent_id = f"entry_{int(time.time())}_{side}_{amount:.6f}"
        
        # Duplikasyon kontrolü
        if self._check_intent_duplicate(intent_id):
            existing_intent = self.state['intents'].get(intent_id)
            return {'id': existing_intent['client_order_id'], 'status': 'duplicate'}
        
        # Intent kaydı ve deterministik clientOrderId
        client_order_id = self._register_intent(
            intent_id, symbol, side, 'ENTRY', amount, reduce_only=reduce_only
        )
        
        # Check if order already exists
        if client_order_id in self.state['orders']:
            existing_order = self.state['orders'][client_order_id]
            if existing_order['status'] == 'SENT':
                self.log.info(f"🔄 ORDER_DUPLICATE: Order {client_order_id} already sent")
                return {'id': client_order_id, 'status': 'duplicate'}
        
        # Create order params
        params = {'newClientOrderId': client_order_id}
        if self.hedge_mode and position_side:
            params['positionSide'] = position_side
        if reduce_only:
            params['reduceOnly'] = True
        
        # Save as PENDING
        self.state['orders'][client_order_id] = {
            'status': 'PENDING',
            'symbol': symbol,
            'type': 'market',
            'side': side,
            'amount': amount,
            'price': None,
            'params': params,
            'ts': int(time.time() * 1000)
        }
        self._save_state()
        
        self.log.info(f"📝 ORDER_CREATE: {client_order_id} - {side} {amount} {symbol}")
        
        try:
            # Place order with retry
            order_result = self._retry_with_backoff(
                self.exchange.create_market_order,
                symbol, side, amount, None, params
            )
            
            # Update status to SENT
            self.state['orders'][client_order_id]['status'] = 'SENT'
            self.state['orders'][client_order_id]['exchange_id'] = order_result['id']
            self._save_state()
            
            # Intent'i exchange order ile link et
            self._link_intent_to_exchange_order(intent_id, order_result['id'])
            
            self.log.info(f"✅ ORDER_SENT: {client_order_id} -> {order_result['id']}")
            return order_result
            
        except Exception as e:
            if self._is_duplicate_error(e):
                # Try to reconcile
                if self._reconcile_order(client_order_id, symbol):
                    self.state['orders'][client_order_id]['status'] = 'SENT'
                    self._save_state()
                    self.log.info(f"✅ ORDER_DUPLICATE: {client_order_id} reconciled")
                    return {'id': client_order_id, 'status': 'duplicate_resolved'}
            
            # Mark as FAILED
            self.state['orders'][client_order_id]['status'] = 'FAILED'
            self.state['orders'][client_order_id]['error'] = str(e)
            self._save_state()
            
            self.log.error(f"❌ ORDER_FAILED: {client_order_id} - {e}")
            raise
    
    def place_stop_market_close(self, symbol: str, side: str, stop_price: float,
                               position_side: Optional[str] = None, intent: str = "SL", 
                               extra: str = "", amount: Optional[float] = None, 
                               reduce_only: bool = True) -> Dict[str, Any]:
        """
        Place stop market close order (SL/TP) with idempotency
        
        Args:
            symbol: Trading symbol
            side: buy/sell
            stop_price: Stop price
            position_side: LONG/SHORT (for hedge mode)
            intent: SL or TP
            extra: Additional data for uniqueness
            
        Returns:
            Order result dict
        """
        if not self.enabled:
            # Fallback to direct order - PENGU/USDT format
            order_type = 'STOP_MARKET' if intent == 'SL' else 'TAKE_PROFIT_MARKET'
            params = {
                'stopPrice': self.exchange.price_to_precision(symbol, stop_price),
                'closePosition': True,  # PENGU/USDT için gerekli
                'workingType': 'MARK_PRICE',  # PENGU/USDT için gerekli
                'priceProtect': True  # PENGU/USDT için gerekli
            }
            if self.hedge_mode and position_side:
                params['positionSide'] = position_side
            
            # PENGU/USDT için amount parametresi None olmalı (closePosition kullanılıyor)
            return self.exchange.create_order(symbol, order_type, side, None, None, params)
        
        client_order_id = self._generate_client_order_id(intent, symbol, side, extra)
        
        # Check if order already exists
        if client_order_id in self.state['orders']:
            existing_order = self.state['orders'][client_order_id]
            if existing_order['status'] == 'SENT':
                self.log.info(f"🔄 ORDER_DUPLICATE: {intent} order {client_order_id} already sent")
                return {'id': client_order_id, 'status': 'duplicate'}
        
        # Determine order type
        order_type = 'STOP_MARKET' if intent == 'SL' else 'TAKE_PROFIT_MARKET'
        
        # Adjust stop price against current mark to avoid -2021
        safe_stop = self._adjust_stop_price_safely(symbol, side, intent, stop_price)

        # Create order params - PENGU/USDT format
        params = {
            'newClientOrderId': client_order_id,
            'stopPrice': self.exchange.price_to_precision(symbol, safe_stop),
            'closePosition': True,  # PENGU/USDT için gerekli
            'workingType': 'MARK_PRICE',  # PENGU/USDT için gerekli
            'priceProtect': True  # PENGU/USDT için gerekli
            # NOT: closePosition=True varsa reduceOnly gönderilmez (Binance API kuralı)
        }
        if self.hedge_mode and position_side:
            params['positionSide'] = position_side
        
        # Save as PENDING
        self.state['orders'][client_order_id] = {
            'status': 'PENDING',
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'amount': None,  # PENGU/USDT için None (closePosition kullanılıyor)
            'price': stop_price,
            'params': params,
            'ts': int(time.time() * 1000)
        }
        self._save_state()
        
        self.log.info(f"📝 ORDER_CREATE: {intent} {client_order_id} - {side} @ {stop_price} {symbol}")
        
        try:
            # Place order with retry - PENGU/USDT için amount None
            try:
                order_result = self._retry_with_backoff(
                    self.exchange.create_order,
                    symbol, order_type, side, None, None, params
                )
            except Exception as e:
                if self._is_immediate_trigger_error(e):
                    safer = self._adjust_stop_price_safely(symbol, side, intent, safe_stop)
                    params['stopPrice'] = self.exchange.price_to_precision(symbol, safer)
                    self.log.warning(f"🔧 -2021 retry with adjusted stopPrice={params['stopPrice']}")
                    order_result = self._retry_with_backoff(
                        self.exchange.create_order,
                        symbol, order_type, side, None, None, params
                    )
                else:
                    raise
            
            # Update status to SENT
            self.state['orders'][client_order_id]['status'] = 'SENT'
            self.state['orders'][client_order_id]['exchange_id'] = order_result['id']
            self._save_state()
            
            self.log.info(f"✅ ORDER_SENT: {intent} {client_order_id} -> {order_result['id']}")
            return order_result
            
        except Exception as e:
            if self._is_duplicate_error(e):
                # Try to reconcile
                if self._reconcile_order(client_order_id, symbol):
                    self.state['orders'][client_order_id]['status'] = 'SENT'
                    self._save_state()
                    self.log.info(f"✅ ORDER_DUPLICATE: {intent} {client_order_id} reconciled")
                    return {'id': client_order_id, 'status': 'duplicate_resolved'}
            
            # Mark as FAILED
            self.state['orders'][client_order_id]['status'] = 'FAILED'
            self.state['orders'][client_order_id]['error'] = str(e)
            self._save_state()
            
            self.log.error(f"❌ ORDER_FAILED: {intent} {client_order_id} - {e}")
            raise
    
    def place_take_profit_market_close(self, symbol: str, side: str, price: float,
                                     position_side: Optional[str] = None, intent: str = "TP", 
                                     extra: str = "", amount: Optional[float] = None,
                                     reduce_only: bool = True) -> Dict[str, Any]:
        """
        Place take profit market close order (TP) with idempotency
        
        Args:
            symbol: Trading symbol
            side: buy/sell
            price: Take profit price
            position_side: LONG/SHORT (for hedge mode)
            intent: TP
            extra: Additional data for uniqueness
            
        Returns:
            Order result dict
        """
        if not self.enabled:
            # Fallback to direct order - PENGU/USDT format
            params = {
                'stopPrice': self.exchange.price_to_precision(symbol, price),
                'closePosition': True,  # PENGU/USDT için gerekli
                'workingType': 'MARK_PRICE',  # PENGU/USDT için gerekli
                'priceProtect': True,  # PENGU/USDT için gerekli
                # NOT: closePosition=True varsa reduceOnly gönderilmez
            }
            if self.hedge_mode and position_side:
                params['positionSide'] = position_side
            
            # PENGU/USDT için amount parametresi None olmalı (closePosition kullanılıyor)
            return self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', side, None, None, params)
        
        client_order_id = self._generate_client_order_id(intent, symbol, side, extra)
        
        # Check if order already exists
        if client_order_id in self.state['orders']:
            existing_order = self.state['orders'][client_order_id]
            if existing_order['status'] == 'SENT':
                self.log.info(f"🔄 ORDER_DUPLICATE: {intent} order {client_order_id} already sent")
                return {'id': client_order_id, 'status': 'duplicate'}
        
        # Adjust stop price against current mark to avoid -2021
        safe_price = self._adjust_stop_price_safely(symbol, side, intent, price)

        # Prepare order data
        order_data = {
            'symbol': symbol,
            'type': 'TAKE_PROFIT_MARKET',
            'side': side,
            'price': safe_price,
            'amount': None,  # PENGU/USDT için None (closePosition kullanılıyor)
            'params': {
                'stopPrice': self.exchange.price_to_precision(symbol, safe_price),
                'closePosition': True,  # PENGU/USDT için gerekli
                'workingType': 'MARK_PRICE',  # PENGU/USDT için gerekli
                'priceProtect': True,  # PENGU/USDT için gerekli
                # NOT: closePosition=True varsa reduceOnly gönderilmez
            },
            'status': 'PENDING',
            'ts': int(time.time() * 1000),
            'intent': intent,
            'extra': extra
        }
        
        if self.hedge_mode and position_side:
            order_data['params']['positionSide'] = position_side
        
        # Store order in state
        self.state['orders'][client_order_id] = order_data
        self._save_state()
        
        self.log.info(f"📝 ORDER_CREATE: {intent} {client_order_id} - {side} @ {price} {symbol}")
        
        try:
            # Place the order - PENGU/USDT için amount None
            try:
                order_result = self._retry_with_backoff(
                    self.exchange.create_order,
                    symbol, 'TAKE_PROFIT_MARKET', side, None, None, order_data['params']
                )
            except Exception as e:
                if self._is_immediate_trigger_error(e):
                    safer = self._adjust_stop_price_safely(symbol, side, intent, safe_price)
                    order_data['params']['stopPrice'] = self.exchange.price_to_precision(symbol, safer)
                    self.log.warning(f"🔧 -2021 retry with adjusted stopPrice={order_data['params']['stopPrice']}")
                    order_result = self._retry_with_backoff(
                        self.exchange.create_order,
                        symbol, 'TAKE_PROFIT_MARKET', side, None, None, order_data['params']
                    )
                else:
                    raise
            
            # Update status to SENT
            self.state['orders'][client_order_id]['status'] = 'SENT'
            self.state['orders'][client_order_id]['exchange_id'] = order_result['id']
            self._save_state()
            
            self.log.info(f"✅ ORDER_SENT: {intent} {client_order_id} -> {order_result['id']}")
            return order_result
            
        except Exception as e:
            if self._is_duplicate_error(e):
                # Try to reconcile
                if self._reconcile_order(client_order_id, symbol):
                    self.state['orders'][client_order_id]['status'] = 'SENT'
                    self._save_state()
                    self.log.info(f"✅ ORDER_DUPLICATE: {intent} {client_order_id} reconciled")
                    return {'id': client_order_id, 'status': 'duplicate_resolved'}
            
            # Mark as FAILED
            self.state['orders'][client_order_id]['status'] = 'FAILED'
            self.state['orders'][client_order_id]['error'] = str(e)
            self._save_state()
            
            self.log.error(f"❌ ORDER_FAILED: {intent} {client_order_id} - {e}")
            raise
    
    def reconcile_pending(self, symbol: str) -> int:
        """
        Reconcile all PENDING orders for a symbol
        
        Args:
            symbol: Trading symbol to reconcile
            
        Returns:
            Number of reconciled orders
        """
        if not self.enabled:
            return 0
        
        reconciled_count = 0
        pending_orders = []
        
        # Find PENDING orders for this symbol
        for client_id, order_data in self.state['orders'].items():
            if (order_data['status'] == 'PENDING' and 
                order_data['symbol'] == symbol):
                pending_orders.append(client_id)
        
        if not pending_orders:
            self.log.info(f"✅ No PENDING orders to reconcile for {symbol}")
            return 0
        
        self.log.info(f"🔄 RECONCILE_PENDING: {len(pending_orders)} orders for {symbol}")
        
        for client_id in pending_orders:
            try:
                if self._reconcile_order(client_id, symbol):
                    self.state['orders'][client_id]['status'] = 'SENT'
                    reconciled_count += 1
                    self.log.info(f"✅ RECONCILE_RESOLVED: {client_id}")
                else:
                    # Try to recreate the order
                    order_data = self.state['orders'][client_id]
                    try:
                        if order_data['type'] == 'market':
                            # Recreate market order
                            order_result = self._retry_with_backoff(
                                self.exchange.create_market_order,
                                symbol, order_data['side'], order_data['amount'], 
                                None, order_data['params']
                            )
                        else:
                            # Recreate SL/TP order
                            order_result = self._retry_with_backoff(
                                self.exchange.create_order,
                                symbol, order_data['type'], order_data['side'],
                                order_data['amount'], None, order_data['params']
                            )
                        
                        self.state['orders'][client_id]['status'] = 'SENT'
                        self.state['orders'][client_id]['exchange_id'] = order_result['id']
                        reconciled_count += 1
                        self.log.info(f"✅ RECONCILE_RESOLVED: {client_id} recreated")
                        
                    except Exception as recreate_error:
                        self.state['orders'][client_id]['status'] = 'FAILED'
                        self.state['orders'][client_id]['error'] = str(recreate_error)
                        self.log.error(f"❌ RECONCILE_FAILED: {client_id} - {recreate_error}")
                        
            except Exception as e:
                self.log.error(f"❌ Reconcile error for {client_id}: {e}")
        
        self._save_state()
        self.log.info(f"✅ RECONCILE_COMPLETE: {reconciled_count}/{len(pending_orders)} orders reconciled")
        return reconciled_count
    
    def get_order_status(self, client_order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status from state"""
        return self.state['orders'].get(client_order_id)
    
    def cleanup_old_orders(self, max_age_hours: int = 24):
        """Clean up old orders from state"""
        current_time = int(time.time() * 1000)
        max_age_ms = max_age_hours * 60 * 60 * 1000
        
        old_orders = []
        for client_id, order_data in self.state['orders'].items():
            if current_time - order_data['ts'] > max_age_ms:
                old_orders.append(client_id)
        
        for client_id in old_orders:
            del self.state['orders'][client_id]
        
        if old_orders:
            self._save_state()
            self.log.info(f"🧹 Cleaned up {len(old_orders)} old orders")
    
    def sync_with_exchange(self, symbol: str):
        """Sync state with actual exchange orders"""
        try:
            # Get active orders from exchange
            open_orders = self.exchange.fetch_open_orders(symbol)
            active_client_ids = set()
            
            for order in open_orders:
                client_id = order.get('clientOrderId')
                if client_id and (client_id.startswith('vlsy-') or client_id.startswith('EMA-')):
                    active_client_ids.add(client_id)
            
            # Remove orders from state that are not active on exchange
            stale_orders = []
            for client_id in list(self.state['orders'].keys()):
                if client_id not in active_client_ids:
                    stale_orders.append(client_id)
            
            for client_id in stale_orders:
                del self.state['orders'][client_id]
            
            if stale_orders:
                self._save_state()
                self.log.info(f"🔄 Synced with exchange: removed {len(stale_orders)} stale orders")
                
        except Exception as e:
            self.log.error(f"❌ Sync with exchange failed: {e}")
    
    def _get_mark_price(self, symbol: str) -> Optional[float]:
        """Fetch current mark price with fallbacks."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            mark = None
            if isinstance(ticker, dict):
                info = ticker.get('info')
                if isinstance(info, dict) and info.get('markPrice') is not None:
                    mark = float(info.get('markPrice'))
            if mark is None and isinstance(ticker, dict):
                mark = ticker.get('last') or ticker.get('close')
            return float(mark) if mark is not None else None
        except Exception as e:
            self.log.warning(f"⚠️ Mark price alınamadı: {e}")
            return None
    
    def _get_tick_size(self, symbol: str) -> Optional[float]:
        """Extract tickSize from market filters or precision."""
        try:
            market = self._market_cache.get(symbol)
            if not market:
                market = self.exchange.market(symbol)
                self._market_cache[symbol] = market
            info = market.get('info', {}) if isinstance(market, dict) else {}
            filters = info.get('filters') or []
            for f in filters:
                if f.get('filterType') in ('PRICE_FILTER', 'PERCENT_PRICE_BY_SIDE'):
                    ts = f.get('tickSize')
                    if ts is not None:
                        ts = float(ts)
                        if ts > 0:
                            return ts
            precision = market.get('precision', {}) if isinstance(market, dict) else {}
            price_prec = precision.get('price')
            if isinstance(price_prec, int) and price_prec >= 0:
                return 10 ** (-price_prec) if price_prec <= 8 else None
            return None
        except Exception as e:
            self.log.warning(f"⚠️ tickSize alınamadı: {e}")
            return None
    
    def _align_price(self, symbol: str, price: float) -> float:
        try:
            return float(self.exchange.price_to_precision(symbol, price))
        except Exception:
            return price
    
    def _adjust_stop_price_safely(self, symbol: str, side: str, intent: str, stop_price: float) -> float:
        """
        Ensure stopPrice will not immediately trigger against current mark.
        intent 'TP' uses TAKE_PROFIT_MARKET, others use STOP_MARKET.
        Closing side defines inequality:
          - TP sell: stop > mark; TP buy: stop < mark
          - SL sell: stop < mark; SL buy: stop > mark
        """
        mark = self._get_mark_price(symbol)
        if mark is None:
            return self._align_price(symbol, stop_price)
        tick = self._get_tick_size(symbol) or 0.0
        buffer = tick * 2 if tick else abs(mark) * 1e-6
        adjusted = stop_price
        s = (side or '').lower()
        is_tp = (intent or '').upper() == 'TP'
        if is_tp:
            if s == 'sell' and adjusted <= mark:
                adjusted = mark + buffer
            elif s == 'buy' and adjusted >= mark:
                adjusted = mark - buffer
        else:
            if s == 'sell' and adjusted >= mark:
                adjusted = mark - buffer
            elif s == 'buy' and adjusted <= mark:
                adjusted = mark + buffer
        return self._align_price(symbol, adjusted)
    
    def _is_immediate_trigger_error(self, error: Exception) -> bool:
        msg = str(error)
        return ('-2021' in msg) or ('immediately trigger' in msg.lower())
    
    def get_last_signal(self) -> Optional[str]:
        """Get last signal from state"""
        return self.state.get('last_signal')
    
    def get_last_signal_time(self) -> Optional[datetime]:
        """Get last signal time from state"""
        signal_time_str = self.state.get('last_signal_time')
        if signal_time_str:
            try:
                return datetime.fromisoformat(signal_time_str)
            except ValueError:
                return None
        return None
    
    def set_last_signal(self, signal: str, signal_time: Optional[datetime] = None):
        """Set last signal in state"""
        self.state['last_signal'] = signal
        if signal_time:
            self.state['last_signal_time'] = signal_time.isoformat()
        else:
            self.state['last_signal_time'] = datetime.now().isoformat()
        self._save_state()
        self.log.info(f"📊 Signal state updated: {signal} @ {self.state['last_signal_time']}")
    
    def cancel_tp_sl_orders(self, symbol: str, order_type: Optional[str] = None) -> int:
        """
        Cancel TP/SL orders for a symbol.
        
        Args:
            symbol: Trading symbol
            order_type: "TP" or "SL" or None for both
            
        Returns:
            Number of orders cancelled
        """
        try:
            # Get all open orders from exchange
            open_orders = self.exchange.fetch_open_orders(symbol)
            
            cancelled_count = 0
            
            for order in open_orders:
                order_info = order.get('info', {})
                order_type_exchange = order_info.get('type', '').upper()
                
                # Check if this is a TP or SL order
                is_tp = 'TAKE_PROFIT' in order_type_exchange
                is_sl = 'STOP_MARKET' in order_type_exchange and 'TAKE_PROFIT' not in order_type_exchange
                
                should_cancel = False
                if order_type is None:
                    should_cancel = is_tp or is_sl
                elif order_type.upper() == "TP":
                    should_cancel = is_tp
                elif order_type.upper() == "SL":
                    should_cancel = is_sl
                
                if should_cancel:
                    try:
                        self.exchange.cancel_order(order['id'], symbol)
                        cancelled_count += 1
                        self.log.info(f"🔄 Cancelled {order_type or 'TP/SL'} order: {order['id']}")
                    except Exception as e:
                        self.log.warning(f"⚠️ Failed to cancel order {order['id']}: {e}")
            
            # Also remove from state
            if cancelled_count > 0:
                orders_to_remove = []
                for client_id, order_data in self.state['orders'].items():
                    if order_data.get('symbol') == symbol:
                        order_intent = order_data.get('params', {}).get('intent', '')
                        if order_type is None:
                            if order_intent in ('TP', 'SL'):
                                orders_to_remove.append(client_id)
                        elif order_type.upper() == order_intent:
                            orders_to_remove.append(client_id)
                
                for client_id in orders_to_remove:
                    del self.state['orders'][client_id]
                
                if orders_to_remove:
                    self._save_state()
            
            return cancelled_count
            
        except Exception as e:
            self.log.error(f"❌ Failed to cancel TP/SL orders: {e}")
            return 0
    
    def update_sl_order(
        self,
        symbol: str,
        new_sl_price: float,
        side: str,
        position_side: Optional[str] = None,
        extra: str = "",
        reason: str = "TRAILING_STOP_UPDATE"
    ) -> Dict[str, Any]:
        """
        Update stop loss order by cancelling old and placing new.
        
        Args:
            symbol: Trading symbol
            new_sl_price: New stop loss price
            side: "buy" to close LONG, "sell" to close SHORT
            position_side: LONG/SHORT (for hedge mode)
            extra: Additional data for uniqueness
            reason: Update reason
            
        Returns:
            Order result dict for new SL order
        """
        try:
            # First, cancel existing SL orders
            sl_cancelled = self.cancel_tp_sl_orders(symbol, order_type="SL")
            
            if sl_cancelled > 0:
                self.log.info(f"🔄 Cancelled {sl_cancelled} old SL order(s), placing new one")
            
            # Place new SL order
            return self.place_stop_market_close(
                symbol=symbol,
                side=side,
                stop_price=new_sl_price,
                position_side=position_side,
                intent="SL",
                extra=extra
            )
            
        except Exception as e:
            self.log.error(f"❌ Failed to update SL order: {e}")
            raise