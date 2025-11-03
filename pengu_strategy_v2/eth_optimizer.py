#!/usr/bin/env python3
"""
ETH Bollinger Bands Strategy Optimizer
Optimized for ETH USDT with focus on frequent signals and high profitability
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from itertools import product
import warnings
warnings.filterwarnings('ignore')

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from data.data_fetcher import DataFetcher
from strategy.bollinger_strategy import BollingerStrategy
from optimize.optimizer import StrategyOptimizer
from reporting.reporter import StrategyReporter

class ETHBollingerOptimizer:
    def __init__(self, config_file: str = "eth_params.json"):
        """Initialize ETH Bollinger Bands Optimizer"""
        self.config_file = config_file
        self.config = self.load_config()
        self.setup_logging()
        
        # Initialize components
        self.data_fetcher = DataFetcher()
        self.strategy = BollingerStrategy()
        self.optimizer = StrategyOptimizer()
        self.reporter = StrategyReporter()
        
        self.log.info("🚀 ETH Bollinger Bands Optimizer initialized")
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            self.log.error(f"❌ Config file not found: {self.config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.log.error(f"❌ Invalid JSON in config file: {e}")
            sys.exit(1)
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('eth_optimization.log'),
                logging.StreamHandler()
            ]
        )
        self.log = logging.getLogger(__name__)
    
    def fetch_eth_data(self):
        """Fetch ETH USDT data for optimization"""
        symbol = self.config['symbol']
        timeframes = self.config['timeframes']
        
        self.log.info(f"📊 Fetching ETH data for timeframes: {timeframes}")
        
        data = {}
        for timeframe in timeframes:
            try:
                df = self.data_fetcher.fetch_crypto_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=self.config['start_date'],
                    end_date=self.config['end_date']
                )
                
                if df is not None and not df.empty:
                    data[timeframe] = df
                    self.log.info(f"✅ {timeframe} data: {len(df)} candles")
                else:
                    self.log.warning(f"⚠️ No data for {timeframe}")
                    
            except Exception as e:
                self.log.error(f"❌ Error fetching {timeframe} data: {e}")
        
        return data
    
    def generate_parameter_combinations(self):
        """Generate parameter combinations for optimization"""
        params = self.config['parameters']
        combinations = []
        
        # Generate all parameter combinations
        param_names = list(params.keys())
        param_values = [self.generate_range(params[name]) for name in param_names]
        
        for combo in product(*param_values):
            param_dict = dict(zip(param_names, combo))
            combinations.append(param_dict)
        
        self.log.info(f"🔢 Generated {len(combinations)} parameter combinations")
        return combinations
    
    def generate_range(self, param_config):
        """Generate range of values for a parameter"""
        min_val = param_config['min']
        max_val = param_config['max']
        step = param_config['step']
        
        return np.arange(min_val, max_val + step, step)
    
    def optimize_timeframe(self, data, timeframe):
        """Optimize strategy for a specific timeframe"""
        self.log.info(f"🎯 Optimizing for {timeframe} timeframe")
        
        df = data[timeframe]
        combinations = self.generate_parameter_combinations()
        
        results = []
        best_result = None
        best_score = -float('inf')
        
        for i, params in enumerate(combinations):
            try:
                # Run backtest with current parameters
                result = self.run_backtest(df, params, timeframe)
                
                if result:
                    # Calculate optimization score
                    score = self.calculate_optimization_score(result)
                    result['optimization_score'] = score
                    result['timeframe'] = timeframe
                    result['parameters'] = params
                    
                    results.append(result)
                    
                    if score > best_score:
                        best_score = score
                        best_result = result
                    
                    if (i + 1) % 100 == 0:
                        self.log.info(f"📈 Processed {i + 1}/{len(combinations)} combinations")
                        
            except Exception as e:
                self.log.error(f"❌ Error in optimization {i}: {e}")
                continue
        
        self.log.info(f"✅ {timeframe} optimization completed: {len(results)} valid results")
        return results, best_result
    
    def run_backtest(self, df, params, timeframe):
        """Run backtest with given parameters"""
        try:
            # Set strategy parameters
            self.strategy.set_parameters(params)
            
            # Run backtest
            trades = self.strategy.backtest(df)
            
            if not trades or len(trades) == 0:
                return None
            
            # Calculate metrics
            metrics = self.calculate_metrics(trades, df)
            
            return {
                'trades': trades,
                'metrics': metrics,
                'total_trades': len(trades)
            }
            
        except Exception as e:
            self.log.error(f"❌ Backtest error: {e}")
            return None
    
    def calculate_metrics(self, trades, df):
        """Calculate trading metrics"""
        if not trades:
            return {}
        
        # Convert trades to DataFrame for easier calculation
        trades_df = pd.DataFrame(trades)
        
        # Basic metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # PnL metrics
        total_pnl = trades_df['pnl'].sum()
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        # Risk metrics
        max_drawdown = self.calculate_max_drawdown(trades_df)
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else float('inf')
        
        # Time metrics
        avg_trade_duration = trades_df['duration'].mean() if 'duration' in trades_df.columns else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'avg_trade_duration': avg_trade_duration
        }
    
    def calculate_max_drawdown(self, trades_df):
        """Calculate maximum drawdown"""
        if 'pnl' not in trades_df.columns:
            return 0
        
        cumulative_pnl = trades_df['pnl'].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        max_drawdown = abs(drawdown.min())
        
        return max_drawdown
    
    def calculate_optimization_score(self, result):
        """Calculate optimization score based on goals"""
        metrics = result['metrics']
        goals = self.config['optimization_goals']
        
        # Primary goal: profit factor
        profit_factor_score = min(metrics.get('profit_factor', 0), 5.0) / 5.0
        
        # Secondary goal: total trades (more trades = better for ETH)
        total_trades = metrics.get('total_trades', 0)
        min_trades = goals.get('min_trades', 50)
        trades_score = min(total_trades / min_trades, 2.0) / 2.0
        
        # Penalty for high drawdown
        max_drawdown = metrics.get('max_drawdown', 0)
        max_allowed_dd = goals.get('max_drawdown', 0.15)
        drawdown_penalty = max(0, 1 - max_drawdown / max_allowed_dd)
        
        # Win rate bonus
        win_rate = metrics.get('win_rate', 0)
        min_win_rate = goals.get('min_win_rate', 0.45)
        win_rate_bonus = max(0, (win_rate - min_win_rate) / (1 - min_win_rate))
        
        # Combined score
        score = (profit_factor_score * 0.4 + 
                trades_score * 0.3 + 
                drawdown_penalty * 0.2 + 
                win_rate_bonus * 0.1)
        
        return score
    
    def run_optimization(self):
        """Run complete optimization process"""
        self.log.info("🚀 Starting ETH Bollinger Bands Optimization")
        
        # Fetch data
        data = self.fetch_eth_data()
        if not data:
            self.log.error("❌ No data available for optimization")
            return
        
        # Optimize each timeframe
        all_results = []
        best_results = {}
        
        for timeframe in self.config['timeframes']:
            if timeframe in data:
                results, best_result = self.optimize_timeframe(data, timeframe)
                all_results.extend(results)
                best_results[timeframe] = best_result
        
        # Save results
        self.save_results(all_results, best_results)
        
        # Generate reports
        self.generate_reports(all_results, best_results)
        
        self.log.info("✅ ETH optimization completed successfully!")
    
    def save_results(self, all_results, best_results):
        """Save optimization results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save all results
        results_file = f"eth_optimization_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        # Save best results
        best_file = f"eth_best_results_{timestamp}.json"
        with open(best_file, 'w') as f:
            json.dump(best_results, f, indent=2, default=str)
        
        self.log.info(f"💾 Results saved: {results_file}, {best_file}")
    
    def generate_reports(self, all_results, best_results):
        """Generate optimization reports"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create reports directory
        reports_dir = Path("reports") / "eth_optimization"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate summary report
        summary_file = reports_dir / f"eth_summary_{timestamp}.md"
        self.generate_summary_report(summary_file, all_results, best_results)
        
        # Generate detailed report
        detailed_file = reports_dir / f"eth_detailed_{timestamp}.json"
        with open(detailed_file, 'w') as f:
            json.dump({
                'all_results': all_results,
                'best_results': best_results,
                'config': self.config
            }, f, indent=2, default=str)
        
        self.log.info(f"📊 Reports generated: {summary_file}, {detailed_file}")
    
    def generate_summary_report(self, file_path, all_results, best_results):
        """Generate summary report"""
        with open(file_path, 'w') as f:
            f.write("# ETH Bollinger Bands Optimization Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Configuration\n")
            f.write(f"- **Symbol:** {self.config['symbol']}\n")
            f.write(f"- **Timeframes:** {', '.join(self.config['timeframes'])}\n")
            f.write(f"- **Period:** {self.config['start_date']} to {self.config['end_date']}\n")
            f.write(f"- **Initial Capital:** ${self.config['initial_capital']:,}\n\n")
            
            f.write("## Best Results by Timeframe\n\n")
            
            for timeframe, result in best_results.items():
                if result:
                    metrics = result['metrics']
                    params = result['parameters']
                    
                    f.write(f"### {timeframe.upper()} Timeframe\n")
                    f.write(f"- **Total Trades:** {metrics.get('total_trades', 0)}\n")
                    f.write(f"- **Win Rate:** {metrics.get('win_rate', 0):.2%}\n")
                    f.write(f"- **Total PnL:** ${metrics.get('total_pnl', 0):.2f}\n")
                    f.write(f"- **Profit Factor:** {metrics.get('profit_factor', 0):.2f}\n")
                    f.write(f"- **Max Drawdown:** {metrics.get('max_drawdown', 0):.2%}\n")
                    f.write(f"- **Optimization Score:** {result.get('optimization_score', 0):.3f}\n\n")
                    
                    f.write("**Best Parameters:**\n")
                    for param, value in params.items():
                        f.write(f"- {param}: {value}\n")
                    f.write("\n")
            
            f.write("## Optimization Summary\n")
            f.write(f"- **Total Combinations Tested:** {len(all_results)}\n")
            f.write(f"- **Valid Results:** {len([r for r in all_results if r])}\n")
            
            if all_results:
                avg_trades = np.mean([r['metrics'].get('total_trades', 0) for r in all_results])
                avg_win_rate = np.mean([r['metrics'].get('win_rate', 0) for r in all_results])
                avg_profit_factor = np.mean([r['metrics'].get('profit_factor', 0) for r in all_results])
                
                f.write(f"- **Average Trades:** {avg_trades:.1f}\n")
                f.write(f"- **Average Win Rate:** {avg_win_rate:.2%}\n")
                f.write(f"- **Average Profit Factor:** {avg_profit_factor:.2f}\n")

def main():
    """Main function"""
    optimizer = ETHBollingerOptimizer()
    optimizer.run_optimization()

if __name__ == "__main__":
    main()
