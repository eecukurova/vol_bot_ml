#!/usr/bin/env python3
"""
Pengu EMA Trading Bot - Configuration Schema Validation
Yüzde birimi standardı: 0.01 = %1 (ondalık format)
"""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional
import json
import logging


class DynamicTPLevel(BaseModel):
    """Dinamik TP seviyesi"""
    threshold: float = Field(..., ge=0.001, le=0.1, description="Threshold yüzdesi (0.01 = %1)")
    tp_pct: float = Field(..., ge=0.001, le=0.1, description="TP yüzdesi (0.01 = %1)")


class DynamicTPConfig(BaseModel):
    """Dinamik TP konfigürasyonu"""
    enabled: bool = True
    levels: List[DynamicTPLevel] = Field(..., min_items=1, max_items=5)
    
    @field_validator('levels')
    @classmethod
    def validate_levels_order(cls, v):
        """Dinamik TP seviyelerinin artan threshold sırasında olduğunu kontrol et"""
        thresholds = [level.threshold for level in v]
        if thresholds != sorted(thresholds):
            raise ValueError(f"Dinamik TP seviyeleri artan threshold sırasında olmalı: {thresholds}")
        
        # Eşit threshold kontrolü
        if len(set(thresholds)) != len(thresholds):
            raise ValueError(f"Dinamik TP seviyelerinde eşit threshold değerleri olamaz: {thresholds}")
        
        return v


class TimeframeConfig(BaseModel):
    """Tek zaman dilimi konfigürasyonu"""
    enabled: bool = True
    take_profit: float = Field(..., ge=0.001, le=0.1, description="Take profit yüzdesi (0.01 = %1)")
    stop_loss: float = Field(..., ge=0.001, le=0.1, description="Stop loss yüzdesi (0.01 = %1)")
    priority: int = Field(..., ge=1, le=10, description="Öncelik sırası (1=en yüksek)")
    trailing_activation: float = Field(..., ge=0.001, le=0.1, description="Trailing aktivasyon yüzdesi (0.01 = %1)")
    trailing_step: float = Field(..., ge=0.001, le=0.1, description="Trailing step yüzdesi (0.01 = %1)")
    trailing_distance: float = Field(..., ge=0.001, le=0.1, description="Trailing distance yüzdesi (0.01 = %1)")
    dynamic_tp: DynamicTPConfig
    
    @field_validator('take_profit', 'stop_loss', 'trailing_activation', 'trailing_step', 'trailing_distance')
    @classmethod
    def validate_percentage_range(cls, v):
        """Yüzde değerlerinin makul aralıkta olduğunu kontrol et"""
        if v < 0.001:
            raise ValueError(f"Yüzde değeri çok küçük: {v} (minimum 0.001 = %0.1)")
        if v > 0.1:
            raise ValueError(f"Yüzde değeri çok büyük: {v} (maksimum 0.1 = %10)")
        return v


class MultiTimeframeConfig(BaseModel):
    """Çoklu zaman dilimi konfigürasyonu"""
    enabled: bool = True
    timeframes: Dict[str, TimeframeConfig]


class EMAConfig(BaseModel):
    """EMA indikatör konfigürasyonu"""
    fast_period: int = Field(..., ge=5, le=50, description="Hızlı EMA periyodu")
    slow_period: int = Field(..., ge=10, le=100, description="Yavaş EMA periyodu")
    
    @field_validator('slow_period')
    @classmethod
    def validate_slow_period(cls, v, info):
        """Yavaş periyodun hızlı periyoddan büyük olduğunu kontrol et"""
        if hasattr(info, 'data') and 'fast_period' in info.data and v <= info.data['fast_period']:
            raise ValueError(f"Yavaş EMA periyodu ({v}) hızlı EMA periyodundan ({info.data['fast_period']}) büyük olmalı")
        return v


class PineScriptParams(BaseModel):
    """Pine Script parametreleri"""
    rsi: Dict[str, float]
    bollinger_bands: Dict[str, float]
    volume: Dict[str, float]
    momentum: Dict[str, float]


class TimeframeValidation(BaseModel):
    """Zaman dilimi validasyon ayarları"""
    enabled: bool = True
    min_candles_for_signal: int = Field(..., ge=10, le=200)
    require_confirmed_candle: bool = True


class SignalManagement(BaseModel):
    """Sinyal yönetimi ayarları"""
    single_position_only: bool = True
    cooldown_after_exit: int = Field(..., ge=0, le=3600, description="Çıkış sonrası bekleme süresi (saniye)")
    priority_order: List[str] = Field(..., min_items=1, max_items=10)
    timeframe_validation: TimeframeValidation


class RiskManagement(BaseModel):
    """Risk yönetimi ayarları - Yüzde birimi: 0.01 = %1"""
    break_even_enabled: bool = True
    break_even_percentage: float = Field(..., ge=0.001, le=0.1, description="Break even yüzdesi (0.01 = %1)")
    trailing_stop_enabled: bool = True
    trailing_stop_percentage: float = Field(..., ge=0.001, le=0.1, description="Trailing stop yüzdesi (0.01 = %1)")
    dynamic_tp_enabled: bool = True
    tp_increment_percentage: float = Field(..., ge=0.001, le=0.1, description="TP artış yüzdesi (0.01 = %1)")
    max_tp_percentage: float = Field(..., ge=0.001, le=0.1, description="Maksimum TP yüzdesi (0.01 = %1)")
    trailing_update_threshold: float = Field(..., ge=0.001, le=0.1, description="Trailing güncelleme eşiği (0.01 = %1)")
    max_positions: int = Field(..., ge=1, le=10, description="Maksimum pozisyon sayısı")
    
    @field_validator('break_even_percentage', 'trailing_stop_percentage', 'tp_increment_percentage', 
              'max_tp_percentage', 'trailing_update_threshold')
    @classmethod
    def validate_percentage_values(cls, v):
        """Risk yönetimi yüzde değerlerini kontrol et"""
        if v < 0.001:
            raise ValueError(f"Risk yönetimi yüzdesi çok küçük: {v} (minimum 0.001 = %0.1)")
        if v > 0.1:
            raise ValueError(f"Risk yönetimi yüzdesi çok büyük: {v} (maksimum 0.1 = %10)")
        return v


class IdempotencyConfig(BaseModel):
    """İdempotent işlem ayarları"""
    enabled: bool = True
    state_file: str = Field(..., min_length=1)
    retry_attempts: int = Field(..., ge=1, le=10)
    retry_delay: float = Field(..., ge=0.1, le=10.0)


class SLTPConfig(BaseModel):
    """Stop Loss / Take Profit ayarları"""
    trigger_source: str = Field(..., pattern="^(MARK_PRICE|LAST_PRICE)$")
    hedge_mode: bool = False


class LoggingConfig(BaseModel):
    """Logging ayarları"""
    level: str = Field(..., pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    file: str = Field(..., min_length=1)
    detailed_signals: bool = True
    detailed_positions: bool = True
    detailed_timeframes: bool = True


class TelegramConfig(BaseModel):
    """Telegram bildirim ayarları"""
    bot_token: str = Field(..., min_length=10)
    chat_id: str = Field(..., min_length=1)
    enabled: bool = True


class PenguEMAConfig(BaseModel):
    """Pengu EMA Trading Bot Ana Konfigürasyon Şeması"""
    
    # API Ayarları
    api_key: str = Field(..., min_length=10)
    secret: str = Field(..., min_length=10)
    sandbox: bool = False
    
    # Trading Ayarları
    symbol: str = Field(..., pattern="^[A-Z]+/[A-Z]+(:[A-Z]+)?$")
    trade_amount_usd: float = Field(..., ge=1.0, le=10000.0)
    leverage: int = Field(..., ge=1, le=125)
    
    # Konfigürasyon Bileşenleri
    multi_timeframe: MultiTimeframeConfig
    ema: EMAConfig
    pine_script_params: PineScriptParams
    heikin_ashi: Dict[str, bool]
    signal_management: SignalManagement
    risk_management: RiskManagement
    idempotency: IdempotencyConfig
    sl_tp: SLTPConfig
    logging: LoggingConfig
    telegram: TelegramConfig
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol_format(cls, v):
        """Symbol formatını kontrol et"""
        if '/' not in v:
            raise ValueError(f"Symbol formatı hatalı: {v} (örn: PENGU/USDT)")
        parts = v.split('/')
        if len(parts) != 2 or not all(part.isalpha() for part in parts):
            raise ValueError(f"Symbol formatı hatalı: {v} (örn: PENGU/USDT)")
        return v
    
    @field_validator('trade_amount_usd')
    @classmethod
    def validate_trade_amount(cls, v):
        """Trade amount kontrolü"""
        if v < 1.0:
            raise ValueError(f"Trade amount çok küçük: {v} (minimum 1.0 USDT)")
        if v > 10000.0:
            raise ValueError(f"Trade amount çok büyük: {v} (maksimum 10000.0 USDT)")
        return v


def load_and_validate_config(config_file: str) -> PenguEMAConfig:
    """
    Config dosyasını yükle ve doğrula
    
    Args:
        config_file: Config dosyası yolu
        
    Returns:
        PenguEMAConfig: Doğrulanmış konfigürasyon
        
    Raises:
        ValueError: Config doğrulama hatası
        FileNotFoundError: Config dosyası bulunamadı
        json.JSONDecodeError: JSON parse hatası
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # Pydantic ile doğrulama
        config = PenguEMAConfig(**config_data)
        
        logging.info("✅ Config doğrulaması başarılı")
        logging.info(f"📊 Symbol: {config.symbol}")
        logging.info(f"💰 Trade Amount: {config.trade_amount_usd} USDT")
        logging.info(f"⚡ Leverage: {config.leverage}x")
        logging.info(f"🎯 Yüzde birimi standardı: 0.01 = %1")
        
        return config
        
    except FileNotFoundError:
        error_msg = f"❌ Config dosyası bulunamadı: {config_file}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
        
    except json.JSONDecodeError as e:
        error_msg = f"❌ JSON parse hatası: {e}"
        logging.error(error_msg)
        raise json.JSONDecodeError(error_msg)
        
    except Exception as e:
        error_msg = f"❌ Config doğrulama hatası: {e}"
        logging.error(error_msg)
        raise ValueError(error_msg)


def validate_percentage_standard(config_data: dict) -> bool:
    """
    Yüzde birimi standardını kontrol et (0.01 = %1)
    
    Args:
        config_data: Config verisi
        
    Returns:
        bool: Standarda uygun mu
        
    Raises:
        ValueError: Standarda uymayan değerler
    """
    percentage_fields = [
        'multi_timeframe.timeframes.15m.take_profit',
        'multi_timeframe.timeframes.15m.stop_loss',
        'multi_timeframe.timeframes.30m.take_profit',
        'multi_timeframe.timeframes.30m.stop_loss',
        'multi_timeframe.timeframes.1h.take_profit',
        'multi_timeframe.timeframes.1h.stop_loss',
        'risk_management.break_even_percentage',
        'risk_management.trailing_stop_percentage',
        'risk_management.tp_increment_percentage',
        'risk_management.max_tp_percentage',
        'risk_management.trailing_update_threshold'
    ]
    
    errors = []
    
    for field_path in percentage_fields:
        try:
            # Nested field'a erişim
            value = config_data
            for key in field_path.split('.'):
                value = value[key]
            
            # Yüzde değeri kontrolü (0.01 = %1 standardı)
            if isinstance(value, (int, float)):
                if value > 1.0:
                    errors.append(f"❌ {field_path}: {value} - Yüzde değeri 1.0'dan büyük (0.01 = %1 standardı)")
                elif value < 0.001:
                    errors.append(f"❌ {field_path}: {value} - Yüzde değeri çok küçük (minimum 0.001 = %0.1)")
                    
        except KeyError:
            # Field bulunamadı, devam et
            continue
    
    if errors:
        error_msg = "Yüzde birimi standardı hatası (0.01 = %1):\n" + "\n".join(errors)
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    logging.info("✅ Yüzde birimi standardı kontrolü başarılı")
    return True


if __name__ == "__main__":
    # Test için
    import sys
    
    if len(sys.argv) != 2:
        print("Kullanım: python config_schema.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        config = load_and_validate_config(config_file)
        print("✅ Config doğrulaması başarılı!")
        print(f"📊 Symbol: {config.symbol}")
        print(f"💰 Trade Amount: {config.trade_amount_usd} USDT")
        print(f"⚡ Leverage: {config.leverage}x")
        
    except Exception as e:
        print(f"❌ Config doğrulama hatası: {e}")
        sys.exit(1)
