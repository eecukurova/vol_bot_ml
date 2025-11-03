"""
NASDAQ ATR SuperTrend Optimizer
NASDAQ hisseleri için ATR SuperTrend parametrelerini optimize eden modül
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import itertools
from datetime import datetime

from ..strategy.atr_supertrend_nasdaq import ATRSuperTrendStrategy, ATRSuperTrendConfig, NASDAQ_OPTIMIZED_PARAMS
from ..data.nasdaq_provider import NASDAQDataProvider, get_nasdaq_data, get_high_volume_symbols
from ..optimize.metrics import calculate_all_metrics
from ..reporting.reporter import create_reporter

logger = logging.getLogger(__name__)

@dataclass
class OptimizationResult:
    """Optimizasyon sonucu"""
    symbol: str
    best_params: Dict
    best_score: float
    all_results: List[Dict]
    execution_time: float
    total_tests: int

class NASDAQOptimizer:
    """
    NASDAQ hisseleri için ATR SuperTrend optimizasyonu
    """
    
    def __init__(self, data_provider: NASDAQDataProvider = None):
        self.data_provider = data_provider or NASDAQDataProvider()
        self.logger = logging.getLogger(__name__)
        
        # Optimizasyon parametreleri
        self.param_ranges = {
            'key_value': np.arange(1.5, 4.5, 0.5),      # 1.5, 2.0, 2.5, 3.0, 3.5, 4.0
            'atr_period': range(5, 21, 2),               # 5, 7, 9, 11, 13, 15, 17, 19
            'multiplier': np.arange(1.0, 2.5, 0.2),     # 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4
            'use_heikin_ashi': [False, True]             # Normal ve Heikin Ashi
        }
        
        # Optimizasyon metrikleri
        self.metrics = ['sharpe_ratio', 'max_drawdown', 'total_return', 'win_rate']
        
    def optimize_single_symbol(self, 
                              symbol: str,
                              period: str = "2y",
                              interval: str = "1d",
                              max_workers: int = 4) -> OptimizationResult:
        """
        Tek sembol için optimizasyon
        
        Args:
            symbol: Hisse senedi sembolü
            period: Veri periyodu
            interval: Veri aralığı
            max_workers: Paralel işlem sayısı
        """
        self.logger.info(f"Optimizasyon başlatılıyor: {symbol}")
        start_time = datetime.now()
        
        # Veri çek
        df = self.data_provider.fetch_data(symbol, period, interval)
        if df is None:
            self.logger.error(f"Veri çekilemedi: {symbol}")
            return None
        
        self.logger.info(f"Veri yüklendi: {symbol} ({len(df)} kayıt)")
        
        # Parametre kombinasyonları oluştur
        param_combinations = list(itertools.product(
            self.param_ranges['key_value'],
            self.param_ranges['atr_period'],
            self.param_ranges['multiplier'],
            self.param_ranges['use_heikin_ashi']
        ))
        
        total_tests = len(param_combinations)
        self.logger.info(f"Toplam test sayısı: {total_tests}")
        
        # Paralel optimizasyon
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Görevleri gönder
            future_to_params = {
                executor.submit(self._test_parameters, symbol, df, params): params
                for params in param_combinations
            }
            
            # Sonuçları topla
            for i, future in enumerate(as_completed(future_to_params)):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                    
                    if (i + 1) % 50 == 0:
                        self.logger.info(f"İlerleme: {i + 1}/{total_tests}")
                        
                except Exception as e:
                    params = future_to_params[future]
                    self.logger.error(f"Test hatası {params}: {e}")
        
        # En iyi sonucu bul
        if not results:
            self.logger.error(f"Hiç sonuç bulunamadı: {symbol}")
            return None
        
        # Sharpe ratio'ya göre sırala
        results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
        best_result = results[0]
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        self.logger.info(f"Optimizasyon tamamlandı: {symbol}")
        self.logger.info(f"En iyi Sharpe Ratio: {best_result['sharpe_ratio']:.4f}")
        self.logger.info(f"En iyi parametreler: {best_result['params']}")
        self.logger.info(f"Toplam süre: {execution_time:.2f} saniye")
        
        return OptimizationResult(
            symbol=symbol,
            best_params=best_result['params'],
            best_score=best_result['sharpe_ratio'],
            all_results=results,
            execution_time=execution_time,
            total_tests=total_tests
        )
    
    def _test_parameters(self, symbol: str, df: pd.DataFrame, params: Tuple) -> Optional[Dict]:
        """Parametre kombinasyonunu test et"""
        try:
            key_value, atr_period, multiplier, use_heikin_ashi = params
            
            # Strateji konfigürasyonu
            config = ATRSuperTrendConfig(
                symbol=symbol,
                key_value=key_value,
                atr_period=atr_period,
                multiplier=multiplier,
                use_heikin_ashi=use_heikin_ashi
            )
            
            # Strateji oluştur
            strategy = ATRSuperTrendStrategy(config)
            
            # Sinyalleri üret
            signals_df = strategy.generate_signals(df)
            
            # Metrikleri hesapla
            metrics = self._calculate_simple_metrics(signals_df)
            
            # Sonuç
            result = {
                'params': {
                    'key_value': key_value,
                    'atr_period': atr_period,
                    'multiplier': multiplier,
                    'use_heikin_ashi': use_heikin_ashi
                },
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'max_drawdown': metrics.get('max_drawdown', 0),
                'total_return': metrics.get('total_return', 0),
                'win_rate': metrics.get('win_rate', 0),
                'total_trades': metrics.get('total_trades', 0)
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Test hatası {params}: {e}")
            return None
    
    def optimize_multiple_symbols(self, 
                                 symbols: List[str],
                                 period: str = "2y",
                                 interval: str = "1d",
                                 max_workers: int = 4) -> Dict[str, OptimizationResult]:
        """Birden fazla sembol için optimizasyon"""
        results = {}
        
        for symbol in symbols:
            try:
                result = self.optimize_single_symbol(symbol, period, interval, max_workers)
                if result:
                    results[symbol] = result
            except Exception as e:
                self.logger.error(f"Optimizasyon hatası {symbol}: {e}")
        
        return results
    
    def optimize_high_volume_symbols(self, 
                                    min_volume: int = 10000000,
                                    period: str = "2y",
                                    interval: str = "1d",
                                    max_workers: int = 4) -> Dict[str, OptimizationResult]:
        """Yüksek hacimli hisseler için optimizasyon"""
        symbols = get_high_volume_symbols(min_volume)
        self.logger.info(f"Yüksek hacimli semboller: {symbols}")
        
        return self.optimize_multiple_symbols(symbols, period, interval, max_workers)
    
    def optimize_sector(self, 
                       sector: str,
                       period: str = "2y",
                       interval: str = "1d",
                       max_workers: int = 4) -> Dict[str, OptimizationResult]:
        """Sektör için optimizasyon"""
        symbols = self.data_provider.get_symbols_by_sector(sector)
        self.logger.info(f"{sector} sektörü sembolleri: {symbols}")
        
        return self.optimize_multiple_symbols(symbols, period, interval, max_workers)
    
    def compare_with_predefined(self, symbol: str, period: str = "2y") -> Dict:
        """Önceden tanımlı parametrelerle karşılaştır"""
        # Önceden tanımlı parametreler
        predefined_config = NASDAQ_OPTIMIZED_PARAMS.get(symbol)
        if not predefined_config:
            self.logger.warning(f"Önceden tanımlı parametre bulunamadı: {symbol}")
            return None
        
        # Veri çek
        df = self.data_provider.fetch_data(symbol, period)
        if df is None:
            return None
        
        # Önceden tanımlı parametrelerle test
        predefined_strategy = ATRSuperTrendStrategy(predefined_config)
        predefined_signals = predefined_strategy.generate_signals(df)
        predefined_metrics = self._calculate_simple_metrics(predefined_signals)
        
        # Optimize edilmiş parametrelerle test
        optimization_result = self.optimize_single_symbol(symbol, period)
        if not optimization_result:
            return None
        
        # Karşılaştırma
        comparison = {
            'symbol': symbol,
            'predefined': {
                'params': predefined_config.__dict__,
                'metrics': predefined_metrics
            },
            'optimized': {
                'params': optimization_result.best_params,
                'metrics': {
                    'sharpe_ratio': optimization_result.best_score,
                    'max_drawdown': optimization_result.all_results[0]['max_drawdown'],
                    'total_return': optimization_result.all_results[0]['total_return'],
                    'win_rate': optimization_result.all_results[0]['win_rate']
                }
            },
            'improvement': {
                'sharpe_ratio': optimization_result.best_score - predefined_metrics.get('sharpe_ratio', 0),
                'max_drawdown': predefined_metrics.get('max_drawdown', 0) - optimization_result.all_results[0]['max_drawdown'],
                'total_return': optimization_result.all_results[0]['total_return'] - predefined_metrics.get('total_return', 0)
            }
        }
        
    def _calculate_simple_metrics(self, signals_df: pd.DataFrame) -> Dict[str, float]:
        """Basit metrikler hesapla"""
        try:
            # Buy/Sell sinyallerini say
            buy_signals = signals_df['buy_signal'].sum()
            sell_signals = signals_df['sell_signal'].sum()
            total_trades = buy_signals + sell_signals
            
            if total_trades == 0:
                return {
                    'sharpe_ratio': 0,
                    'max_drawdown': 0,
                    'total_return': 0,
                    'win_rate': 0,
                    'total_trades': 0
                }
            
            # Fiyat değişimi
            price_change = (signals_df['close'].iloc[-1] - signals_df['close'].iloc[0]) / signals_df['close'].iloc[0]
            
            # Basit Sharpe ratio (fiyat değişimi / volatilite)
            returns = signals_df['close'].pct_change().dropna()
            volatility = returns.std() if len(returns) > 1 else 0
            sharpe_ratio = returns.mean() / volatility if volatility > 0 else 0
            
            # Drawdown hesaplama
            peak = signals_df['close'].expanding().max()
            drawdown = (signals_df['close'] - peak) / peak
            max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
            
            # Win rate (basit hesaplama)
            win_rate = 0.5  # Varsayılan
            
            return {
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'total_return': price_change,
                'win_rate': win_rate,
                'total_trades': total_trades
            }
            
        except Exception as e:
            self.logger.error(f"Metrics hesaplama hatası: {e}")
            return {
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'total_return': 0,
                'win_rate': 0,
                'total_trades': 0
            }
    
    def generate_report(self, results: Dict[str, OptimizationResult], output_dir: str = "reports/nasdaq"):
        """Optimizasyon raporu oluştur"""
        reporter = create_reporter(output_dir)
        
        # Genel rapor
        summary_data = []
        for symbol, result in results.items():
            summary_data.append({
                'Symbol': symbol,
                'Best_Sharpe_Ratio': result.best_score,
                'Best_Params': str(result.best_params),
                'Execution_Time': result.execution_time,
                'Total_Tests': result.total_tests
            })
        
        summary_df = pd.DataFrame(summary_data)
        reporter.save_dataframe(summary_df, "nasdaq_optimization_summary.csv")
        
        # Detaylı raporlar
        for symbol, result in results.items():
            # En iyi 10 sonuç
            top_results = result.all_results[:10]
            top_df = pd.DataFrame(top_results)
            reporter.save_dataframe(top_df, f"nasdaq_{symbol}_top_results.csv")
            
            # Grafik oluştur
            self._create_optimization_plots(symbol, result, reporter)
        
        self.logger.info(f"Raporlar oluşturuldu: {output_dir}")
    
    def _create_optimization_plots(self, symbol: str, result: OptimizationResult, reporter):
        """Optimizasyon grafikleri oluştur"""
        try:
            # Sharpe ratio dağılımı
            sharpe_ratios = [r['sharpe_ratio'] for r in result.all_results]
            
            # Parametre etkisi analizi
            param_analysis = {}
            for param_name in ['key_value', 'atr_period', 'multiplier']:
                param_values = []
                param_sharpe = []
                
                for r in result.all_results:
                    param_values.append(r['params'][param_name])
                    param_sharpe.append(r['sharpe_ratio'])
                
                param_analysis[param_name] = {
                    'values': param_values,
                    'sharpe_ratios': param_sharpe
                }
            
            # Grafik oluştur
            reporter.create_optimization_plots(symbol, sharpe_ratios, param_analysis)
            
        except Exception as e:
            self.logger.error(f"Grafik oluşturma hatası {symbol}: {e}")

# Global instance
nasdaq_optimizer = NASDAQOptimizer()

def optimize_nasdaq_symbol(symbol: str, **kwargs) -> OptimizationResult:
    """Hızlı optimizasyon fonksiyonu"""
    return nasdaq_optimizer.optimize_single_symbol(symbol, **kwargs)

def optimize_high_volume_nasdaq(**kwargs) -> Dict[str, OptimizationResult]:
    """Yüksek hacimli hisseler için hızlı optimizasyon"""
    return nasdaq_optimizer.optimize_high_volume_symbols(**kwargs)
