#!/usr/bin/env python3
"""
Pine Editor Stratejilerini Test Et
"""

import os
import re
import pandas as pd
from src.data.nasdaq_provider import NASDAQDataProvider
from typing import Dict, List, Any

class PineStrategyTester:
    def __init__(self):
        self.provider = NASDAQDataProvider()
        self.results = []
        
    def parse_pine_file(self, file_path: str) -> Dict[str, Any]:
        """Pine Script dosyasını parse et ve parametreleri çıkar"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parametreleri çıkar
        params = {}
        
        # Strategy adı
        strategy_match = re.search(r'strategy\("([^"]+)"', content)
        if strategy_match:
            params['strategy_name'] = strategy_match.group(1)
        else:
            # Study adı da olabilir
            study_match = re.search(r'study\("([^"]+)"', content)
            if study_match:
                params['strategy_name'] = study_match.group(1)
        
        # ATR Sensitivity (farklı formatlar)
        atr_patterns = [
            r'a\s*=\s*input\.float\(([^,]+)',
            r'ATR\s*Sensitivity.*?defval=([0-9.]+)',
            r'Multiplier.*?defval=([0-9.]+)',
            r'ATR\s*Multiplier.*?defval=([0-9.]+)'
        ]
        for pattern in atr_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    params['a'] = float(match.group(1))
                    break
                except:
                    continue
        
        # ATR Period (farklı formatlar)
        atr_period_patterns = [
            r'c\s*=\s*input\.int\(([^,]+)',
            r'ATR\s*Period.*?defval=([0-9]+)',
            r'Periods.*?defval=([0-9]+)',
            r'Period.*?defval=([0-9]+)'
        ]
        for pattern in atr_period_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    params['c'] = int(match.group(1))
                    break
                except:
                    continue
        
        # SuperTrend Factor
        st_factor_patterns = [
            r'st_factor\s*=\s*input\.float\(([^,]+)',
            r'SuperTrend.*?Factor.*?defval=([0-9.]+)',
            r'Factor.*?defval=([0-9.]+)'
        ]
        for pattern in st_factor_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    params['st_factor'] = float(match.group(1))
                    break
                except:
                    continue
        
        # Stop Loss
        sl_patterns = [
            r'stop_loss_pct\s*=\s*input\.float\(([^,]+)',
            r'Stop\s*Loss.*?defval=([0-9.]+)',
            r'SL.*?defval=([0-9.]+)'
        ]
        for pattern in sl_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    params['stop_loss_pct'] = float(match.group(1))
                    break
                except:
                    continue
        
        # Take Profit
        tp_patterns = [
            r'take_profit_pct\s*=\s*input\.float\(([^,]+)',
            r'Take\s*Profit.*?defval=([0-9.]+)',
            r'TP.*?defval=([0-9.]+)'
        ]
        for pattern in tp_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    params['take_profit_pct'] = float(match.group(1))
                    break
                except:
                    continue
        
        return params
    
    def test_strategy_with_params(self, params: Dict[str, Any], symbol: str = 'MSFT') -> Dict[str, Any]:
        """Parametrelerle strateji test et"""
        try:
            # MSFT verisi al
            data = self.provider.fetch_data(symbol, period='1y', interval='1d')
            
            # Fix data format
            data = data.reset_index()
            if 'date' in data.columns:
                data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
                data.set_index('date', inplace=True)
            
            # Strategy parametrelerini hazırla
            strategy_params = {
                'a': params.get('a', 0.5),
                'c': params.get('c', 2),
                'st_factor': params.get('st_factor', 0.4),
                'use_ema_confirmation': False,
                'volume_filter': False,
                'stop_loss_pct': params.get('stop_loss_pct', 0.5),
                'take_profit_pct': params.get('take_profit_pct', 1.0)
            }
            
            # Strategy oluştur
            from src.strategy.nasdaq_atr_supertrend import create_strategy
            strategy = create_strategy(strategy_params)
            data_with_indicators = strategy.calculate_indicators(data)
            
            # TÜM sinyalleri bul
            all_signals = []
            for i in range(1, len(data_with_indicators)):
                current = data_with_indicators.iloc[i]
                previous = data_with_indicators.iloc[i-1]
                
                # BUY sinyali
                if current['close'] > current['super_trend'] and previous['close'] <= previous['super_trend']:
                    all_signals.append({
                        'timestamp': current.name,
                        'signal_type': 'BUY',
                        'price': current['close']
                    })
                
                # SELL sinyali
                if current['close'] < current['super_trend'] and previous['close'] >= previous['super_trend']:
                    all_signals.append({
                        'timestamp': current.name,
                        'signal_type': 'SELL',
                        'price': current['close']
                    })
            
            # Backtest simülasyonu
            position = None
            trades = []
            
            for signal in all_signals:
                if signal['signal_type'] == 'BUY' and position is None:
                    position = {
                        'side': 'BUY',
                        'entry_price': signal['price'],
                        'entry_time': signal['timestamp'],
                        'stop_loss': signal['price'] * (1 - strategy_params['stop_loss_pct'] / 100),
                        'take_profit': signal['price'] * (1 + strategy_params['take_profit_pct'] / 100)
                    }
                
                elif signal['signal_type'] == 'SELL' and position is not None:
                    exit_price = signal['price']
                    pnl = (exit_price - position['entry_price']) / position['entry_price']
                    
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': signal['timestamp'],
                        'side': position['side'],
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'pnl': pnl
                    })
                    position = None
            
            # Metrikleri hesapla
            if trades:
                profitable = sum(1 for t in trades if t['pnl'] > 0)
                win_rate = profitable / len(trades) * 100
                total_return = sum(t['pnl'] for t in trades)
                
                return {
                    'strategy_name': params.get('strategy_name', 'Unknown'),
                    'params': strategy_params,
                    'total_trades': len(trades),
                    'win_rate': win_rate,
                    'total_return': total_return,
                    'signals_count': len(all_signals),
                    'success': True
                }
            else:
                return {
                    'strategy_name': params.get('strategy_name', 'Unknown'),
                    'params': strategy_params,
                    'total_trades': 0,
                    'win_rate': 0,
                    'total_return': 0,
                    'signals_count': len(all_signals),
                    'success': False
                }
                
        except Exception as e:
            return {
                'strategy_name': params.get('strategy_name', 'Unknown'),
                'params': params,
                'error': str(e),
                'success': False
            }
    
    def test_all_strategies(self, folder_path: str = 'pine_strategies_to_test'):
        """Klasördeki tüm Pine Script dosyalarını test et"""
        print('🚀 PINE EDITOR STRATEJİLERİNİ TEST ET')
        print('='*60)
        
        if not os.path.exists(folder_path):
            print(f'❌ Klasör bulunamadı: {folder_path}')
            return
        
        pine_files = [f for f in os.listdir(folder_path) if f.endswith('.pine') or f.endswith('.txt')]
        
        if not pine_files:
            print(f'❌ {folder_path} klasöründe Pine Script dosyası bulunamadı')
            print('📁 Lütfen .pine uzantılı dosyaları bu klasöre yükleyin')
            return
        
        print(f'📊 Bulunan Pine Script dosyaları: {len(pine_files)}')
        for i, file in enumerate(pine_files, 1):
            print(f'   {i}. {file}')
        
        print(f'\n🔬 Test başlıyor...')
        
        for i, file in enumerate(pine_files, 1):
            file_path = os.path.join(folder_path, file)
            print(f'\n📋 {i}/{len(pine_files)} - {file}')
            print('-'*50)
            
            try:
                # Pine dosyasını parse et
                params = self.parse_pine_file(file_path)
                print(f'🔧 Parametreler: {params}')
                
                # Stratejiyi test et
                result = self.test_strategy_with_params(params)
                
                if result['success']:
                    print(f'✅ Başarılı!')
                    print(f'   İşlem sayısı: {result["total_trades"]}')
                    print(f'   Win Rate: {result["win_rate"]:.1f}%')
                    print(f'   Total Return: {result["total_return"]:.2%}')
                    print(f'   Sinyal sayısı: {result["signals_count"]}')
                else:
                    print(f'❌ Başarısız: {result.get("error", "Bilinmeyen hata")}')
                
                self.results.append(result)
                
            except Exception as e:
                print(f'❌ Hata: {e}')
                self.results.append({
                    'strategy_name': file,
                    'error': str(e),
                    'success': False
                })
        
        # Sonuçları özetle
        self.print_summary()
    
    def print_summary(self):
        """Test sonuçlarını özetle"""
        print(f'\n🏆 TEST SONUÇLARI ÖZETİ')
        print('='*80)
        
        successful_results = [r for r in self.results if r['success']]
        
        if not successful_results:
            print('❌ Başarılı test sonucu bulunamadı!')
            return
        
        # En iyi sonuçları sırala
        successful_results.sort(key=lambda x: x['total_return'], reverse=True)
        
        print(f'📊 Toplam test: {len(self.results)}')
        print(f'✅ Başarılı: {len(successful_results)}')
        print(f'❌ Başarısız: {len(self.results) - len(successful_results)}')
        
        print(f'\n🥇 EN İYİ 5 SONUÇ:')
        print('-'*80)
        for i, result in enumerate(successful_results[:5], 1):
            print(f'{i}. {result["strategy_name"]}')
            print(f'   Win Rate: {result["win_rate"]:.1f}% | Return: {result["total_return"]:.2%} | Trades: {result["total_trades"]}')
            print(f'   Params: a={result["params"]["a"]}, c={result["params"]["c"]}, st_factor={result["params"]["st_factor"]}')
            print()
        
        # En iyi stratejiyi öner
        if successful_results:
            best = successful_results[0]
            print(f'🎯 EN İYİ STRATEJİ: {best["strategy_name"]}')
            print(f'   Win Rate: {best["win_rate"]:.1f}%')
            print(f'   Total Return: {best["total_return"]:.2%}')
            print(f'   Total Trades: {best["total_trades"]}')

def main():
    tester = PineStrategyTester()
    tester.test_all_strategies()

if __name__ == "__main__":
    main()
