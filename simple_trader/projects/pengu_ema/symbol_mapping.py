#!/usr/bin/env python3
"""
Pengu EMA Trading Bot - Symbol/Market Mapping Helper V2
Binance Futures (USDT-M) için sembol haritalama ve doğrulama
"""

import ccxt
import logging
import sys
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class SymbolMapping:
    """Sembol haritalama sonucu"""
    rest_symbol: str          # REST API için (örn: BTCUSDT)
    order_symbol: str         # Order API için (örn: BTC/USDT:USDT)
    market_type: str          # market type (swap)
    quote: str                # quote asset (USDT)
    settle: str               # settle asset (USDT)
    amount_step: float        # lot size step
    price_tick: float         # price tick size
    min_amount: float         # minimum order amount
    max_amount: float         # maximum order amount
    min_price: float          # minimum price
    max_price: float          # maximum price
    active: bool              # market active status


class SymbolMappingHelper:
    """Binance Futures (USDT-M) için sembol haritalama ve doğrulama yardımcısı"""
    
    def __init__(self, exchange: ccxt.binance, logger: logging.Logger):
        self.exchange = exchange
        self.log = logger
        self.markets = None
        self.symbol_mapping: Optional[SymbolMapping] = None
        
    def load_and_validate_markets(self, symbol: str) -> SymbolMapping:
        """
        Pazar verilerini yükle ve sembolü doğrula
        
        Args:
            symbol: Config'ten gelen sembol (örn: BTC/USDT:USDT)
            
        Returns:
            SymbolMapping: Doğrulanmış sembol haritalama
            
        Raises:
            SystemExit: Sembol doğrulama başarısız
        """
        try:
            # Markets yükle
            self.log.info("📊 Markets yükleniyor...")
            self.markets = self.exchange.load_markets()
            self.log.info(f"✅ {len(self.markets)} market yüklendi")
            
            # Sembol doğrulama
            return self._validate_symbol(symbol)
            
        except Exception as e:
            self.log.error(f"❌ Market yükleme hatası: {e}")
            raise SystemExit(1)
    
    def _validate_symbol(self, symbol: str) -> SymbolMapping:
        """
        Sembol doğrulama ve haritalama
        
        Args:
            symbol: Doğrulanacak sembol
            
        Returns:
            SymbolMapping: Doğrulanmış haritalama
            
        Raises:
            SystemExit: Doğrulama başarısız
        """
        # 1. Sembol var mı?
        if symbol not in self.markets:
            self.log.error(f"❌ symbol_map_fail reason=\"Symbol not found\" symbol=\"{symbol}\"")
            raise SystemExit(1)
        
        market = self.markets[symbol]
        
        # 2. Market türü kontrolü (swap/futures olmalı)
        if market.get('type') != 'swap':
            self.log.error(f"❌ symbol_map_fail reason=\"Not a swap/futures market\" symbol=\"{symbol}\" market_type=\"{market.get('type')}\"")
            raise SystemExit(1)
        
        # 3. Contract kontrolü (perpetual olmalı)
        if not market.get('contract', False):
            self.log.error(f"❌ symbol_map_fail reason=\"Not a perpetual contract\" symbol=\"{symbol}\"")
            raise SystemExit(1)
        
        # 4. Quote asset kontrolü (USDT olmalı)
        quote = market.get('quote', '')
        if quote != 'USDT':
            self.log.error(f"❌ symbol_map_fail reason=\"Wrong quote asset\" symbol=\"{symbol}\" quote=\"{quote}\" expected=\"USDT\"")
            raise SystemExit(1)
        
        # 5. Settle asset kontrolü (USDT-M olmalı)
        settle = market.get('settle', '')
        if settle != 'USDT':
            self.log.error(f"❌ symbol_map_fail reason=\"Expected USDT-M\" symbol=\"{symbol}\" settle=\"{settle}\" expected=\"USDT\"")
            raise SystemExit(1)
        
        # 6. Market aktif mi?
        if not market.get('active', True):
            self.log.error(f"❌ symbol_map_fail reason=\"Market inactive or frozen\" symbol=\"{symbol}\"")
            raise SystemExit(1)
        
        # 7. Lot/Price step kontrolü
        amount_step = market.get('amount', {}).get('step', 0.001)
        price_tick = market.get('price', {}).get('step', 0.01)
        
        if amount_step <= 0:
            self.log.error(f"❌ symbol_map_fail reason=\"Amount step invalid\" symbol=\"{symbol}\" amount_step=\"{amount_step}\"")
            raise SystemExit(1)
        
        if price_tick <= 0:
            self.log.error(f"❌ symbol_map_fail reason=\"Price tick invalid\" symbol=\"{symbol}\" price_tick=\"{price_tick}\"")
            raise SystemExit(1)
        
        # 8. Sembol haritalama oluştur
        mapping = self._create_symbol_mapping(symbol, market)
        
        # 9. Başarılı log
        self.log.info(f"✅ symbol_map_ok market={mapping.market_type} quote={mapping.quote} settle={mapping.settle} "
                     f"rest=\"{mapping.rest_symbol}\" order=\"{mapping.order_symbol}\" "
                     f"amount_step={mapping.amount_step} price_tick={mapping.price_tick} "
                     f"min_amount={mapping.min_amount} max_amount={mapping.max_amount}")
        
        self.symbol_mapping = mapping
        return mapping
    
    def _create_symbol_mapping(self, symbol: str, market: Dict) -> SymbolMapping:
        """
        Sembol haritalama oluştur
        
        Args:
            symbol: Orijinal sembol
            market: Market verisi
            
        Returns:
            SymbolMapping: Haritalama sonucu
        """
        # REST API sembolü (genelde BTCUSDT)
        rest_symbol = market.get('id', symbol.replace('/', '').replace(':', ''))
        
        # Order API sembolü - market objesinden al
        order_symbol = symbol  # Zaten doğru formatta geliyor
        
        return SymbolMapping(
            rest_symbol=rest_symbol,
            order_symbol=order_symbol,
            market_type=market.get('type', 'unknown'),
            quote=market.get('quote', ''),
            settle=market.get('settle', ''),
            amount_step=market.get('amount', {}).get('step', 0.001),
            price_tick=market.get('price', {}).get('step', 0.01),
            min_amount=market.get('amount', {}).get('min', 0),
            max_amount=market.get('amount', {}).get('max', 0),
            min_price=market.get('price', {}).get('min', 0),
            max_price=market.get('price', {}).get('max', 0),
            active=market.get('active', False)
        )
    
    def get_symbol_for_endpoint(self, endpoint: str) -> str:
        """
        Endpoint'e göre doğru sembol string'i döndür
        
        Args:
            endpoint: API endpoint adı
            
        Returns:
            str: Endpoint'e uygun sembol string'i
            
        Raises:
            ValueError: Sembol haritalama yapılmamış
        """
        if not self.symbol_mapping:
            raise ValueError("Symbol mapping not initialized. Call load_and_validate_markets() first.")
        
        # Endpoint'e göre sembol seçimi
        endpoint_lower = endpoint.lower()
        
        if endpoint_lower in ['fetch_positions', 'fetch_balance', 'fetch_account']:
            # REST API için
            return self.symbol_mapping.rest_symbol
            
        elif endpoint_lower in ['create_order', 'cancel_order', 'fetch_open_orders', 
                               'fetch_my_trades', 'fetch_order', 'fetch_orders', 'fetch_ohlcv']:
            # Order API için
            return self.symbol_mapping.order_symbol
            
        else:
            # Varsayılan olarak order symbol
            self.log.warning(f"⚠️ Unknown endpoint '{endpoint}', using order symbol")
            return self.symbol_mapping.order_symbol
    
    def get_market_info(self) -> Optional[SymbolMapping]:
        """
        Market bilgilerini döndür
        
        Returns:
            SymbolMapping: Market bilgileri
        """
        return self.symbol_mapping
    
    def validate_order_amount(self, amount: float) -> bool:
        """
        Order amount'unu doğrula
        
        Args:
            amount: Doğrulanacak amount
            
        Returns:
            bool: Geçerli mi?
        """
        if not self.symbol_mapping:
            return False
        
        return (self.symbol_mapping.min_amount <= amount <= self.symbol_mapping.max_amount and
                amount % self.symbol_mapping.amount_step == 0)
    
    def validate_order_price(self, price: float) -> bool:
        """
        Order price'ını doğrula
        
        Args:
            price: Doğrulanacak price
            
        Returns:
            bool: Geçerli mi?
        """
        if not self.symbol_mapping:
            return False
        
        return (self.symbol_mapping.min_price <= price <= self.symbol_mapping.max_price and
                price % self.symbol_mapping.price_tick == 0)
    
    def format_amount(self, amount: float) -> float:
        """
        Amount'u market step'ine göre formatla
        
        Args:
            amount: Formatlanacak amount
            
        Returns:
            float: Formatlanmış amount
        """
        if not self.symbol_mapping:
            return amount
        
        step = self.symbol_mapping.amount_step
        return round(amount / step) * step
    
    def format_price(self, price: float) -> float:
        """
        Price'ı market tick'ine göre formatla
        
        Args:
            price: Formatlanacak price
            
        Returns:
            float: Formatlanmış price
        """
        if not self.symbol_mapping:
            return price
        
        tick = self.symbol_mapping.price_tick
        return round(price / tick) * tick


if __name__ == "__main__":
    # Test fonksiyonu
    import json
    
    # Test config
    test_configs = [
        {"symbol": "BTC/USDT:USDT", "expected": "valid"},
        {"symbol": "NOPE/USDT", "expected": "not_found"},
        {"symbol": "BTC/USDT", "expected": "valid"},
        {"symbol": "ETH/USDT:USDT", "expected": "valid"},
    ]
    
    # Exchange setup
    exchange = ccxt.binance({
        'sandbox': False,
        'options': {
            'defaultType': 'future'
        }
    })
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    helper = SymbolMappingHelper(exchange, logger)
    
    for config in test_configs:
        symbol = config['symbol']
        expected = config['expected']
        
        print(f"\n🧪 Testing symbol: {symbol}")
        
        try:
            mapping = helper.load_and_validate_markets(symbol)
            print(f"✅ Success: {mapping.rest_symbol} / {mapping.order_symbol}")
            
            # Endpoint testleri
            rest_symbol = helper.get_symbol_for_endpoint('fetch_positions')
            order_symbol = helper.get_symbol_for_endpoint('create_order')
            print(f"📊 REST: {rest_symbol}, Order: {order_symbol}")
            
        except SystemExit:
            print(f"❌ Expected failure for {symbol}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
