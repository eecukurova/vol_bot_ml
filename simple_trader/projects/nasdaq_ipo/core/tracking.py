#!/usr/bin/env python3
"""
NASDAQ IPO Tracking Module
Simple CSV-based tracking system for recommended stocks
"""

import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from .utils import calculate_deficiency_risk_metrics, format_deficiency_warning, get_compliance_deadline_warning

logger = logging.getLogger(__name__)

class StockTracker:
    def __init__(self, csv_file: str = "tracked_stocks.csv"):
        self.csv_file = csv_file
        self.tracked_stocks = self._load_tracked_stocks()
    
    def _load_tracked_stocks(self) -> Dict[str, Dict]:
        """Load existing tracked stocks from CSV"""
        tracked = {}
        if not os.path.exists(self.csv_file):
            return tracked
        
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    symbol = row['symbol']
                    tracked[symbol] = {
                        'first_recommended_date': row['first_recommended_date'],
                        'first_price': float(row['first_price']),
                        'last_price': float(row['last_price']),
                        'max_price': float(row['max_price']),
                        'min_price': float(row['min_price']),
                        'days_tracked': int(row['days_tracked']),
                        'status': row['status'],
                        'performance_pct': float(row['performance_pct']),
                        'consecutive_below_1': int(row.get('consecutive_below_1', 0)),
                        'deficiency_risk_flag': row.get('deficiency_risk_flag', 'False').lower() == 'true',
                        'deficiency_risk_level': row.get('deficiency_risk_level', 'NONE'),
                        'days_since_deficiency_start': int(row.get('days_since_deficiency_start', 0)),
                        'compliance_deadline': row.get('compliance_deadline', '') or None,
                        'compliance_status': row.get('compliance_status', 'COMPLIANT')
                    }
        except Exception as e:
            logger.error(f"Error loading tracked stocks: {e}")
        
        return tracked
    
    def _save_tracked_stocks(self):
        """Save tracked stocks to CSV"""
        try:
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'symbol', 'first_recommended_date', 'first_price', 
                    'last_price', 'max_price', 'min_price', 
                    'days_tracked', 'status', 'performance_pct',
                    'consecutive_below_1', 'deficiency_risk_flag', 
                    'deficiency_risk_level', 'days_since_deficiency_start',
                    'compliance_deadline', 'compliance_status'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for symbol, data in self.tracked_stocks.items():
                    writer.writerow({
                        'symbol': symbol,
                        'first_recommended_date': data['first_recommended_date'],
                        'first_price': f"{data['first_price']:.4f}",
                        'last_price': f"{data['last_price']:.4f}",
                        'max_price': f"{data['max_price']:.4f}",
                        'min_price': f"{data['min_price']:.4f}",
                        'days_tracked': data['days_tracked'],
                        'status': data['status'],
                        'performance_pct': f"{data['performance_pct']:.2f}",
                        'consecutive_below_1': data.get('consecutive_below_1', 0),
                        'deficiency_risk_flag': data.get('deficiency_risk_flag', False),
                        'deficiency_risk_level': data.get('deficiency_risk_level', 'NONE'),
                        'days_since_deficiency_start': data.get('days_since_deficiency_start', 0),
                        'compliance_deadline': data.get('compliance_deadline', ''),
                        'compliance_status': data.get('compliance_status', 'COMPLIANT')
                    })
        except Exception as e:
            logger.error(f"Error saving tracked stocks: {e}")
    
    def add_new_stock(self, symbol: str, price: float, prices: List[float] = None, dates: List[str] = None):
        """Add a new stock to tracking"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if symbol not in self.tracked_stocks:
            # Calculate deficiency metrics if price history available
            deficiency_metrics = calculate_deficiency_risk_metrics(symbol, prices or [price], dates or [today])
            
            self.tracked_stocks[symbol] = {
                'first_recommended_date': today,
                'first_price': price,
                'last_price': price,
                'max_price': price,
                'min_price': price,
                'days_tracked': 1,
                'status': 'ACTIVE',
                'performance_pct': 0.0,
                'consecutive_below_1': deficiency_metrics['consecutive_below_1'],
                'deficiency_risk_flag': deficiency_metrics['deficiency_risk_flag'],
                'deficiency_risk_level': deficiency_metrics['deficiency_risk_level'],
                'days_since_deficiency_start': deficiency_metrics['days_since_deficiency_start'],
                'compliance_deadline': deficiency_metrics['compliance_deadline'],
                'compliance_status': deficiency_metrics['compliance_status']
            }
            logger.info(f"📈 Added new stock to tracking: {symbol} @ ${price:.4f}")
            if deficiency_metrics['deficiency_risk_flag']:
                logger.warning(f"⚠️ {symbol}: Deficiency risk detected - {deficiency_metrics['consecutive_below_1']} days below $1")
        else:
            logger.info(f"📊 Stock already tracked: {symbol}")
        
        self._save_tracked_stocks()
    
    def update_stock_price(self, symbol: str, current_price: float, prices: List[float] = None, dates: List[str] = None):
        """Update stock price and performance metrics"""
        if symbol not in self.tracked_stocks:
            logger.warning(f"Stock {symbol} not found in tracking")
            return
        
        stock = self.tracked_stocks[symbol]
        
        # Update prices
        stock['last_price'] = current_price
        stock['max_price'] = max(stock['max_price'], current_price)
        stock['min_price'] = min(stock['min_price'], current_price)
        
        # Calculate performance
        stock['performance_pct'] = ((current_price - stock['first_price']) / stock['first_price']) * 100
        
        # Update days tracked
        first_date = datetime.strptime(stock['first_recommended_date'], '%Y-%m-%d')
        days_tracked = (datetime.now() - first_date).days + 1
        stock['days_tracked'] = days_tracked
        
        # Update deficiency metrics if price history available
        if prices and dates:
            deficiency_metrics = calculate_deficiency_risk_metrics(symbol, prices, dates)
            stock['consecutive_below_1'] = deficiency_metrics['consecutive_below_1']
            stock['deficiency_risk_flag'] = deficiency_metrics['deficiency_risk_flag']
            stock['deficiency_risk_level'] = deficiency_metrics['deficiency_risk_level']
            stock['days_since_deficiency_start'] = deficiency_metrics['days_since_deficiency_start']
            stock['compliance_deadline'] = deficiency_metrics['compliance_deadline']
            stock['compliance_status'] = deficiency_metrics['compliance_status']
        
        # Update status based on performance
        if stock['performance_pct'] >= 20.0:
            stock['status'] = 'HIT_TARGET'
        elif stock['performance_pct'] <= -20.0:
            stock['status'] = 'STOPPED_OUT'
        else:
            stock['status'] = 'ACTIVE'
        
        self._save_tracked_stocks()
        logger.info(f"📊 Updated {symbol}: ${current_price:.4f} ({stock['performance_pct']:+.2f}%)")
        
        # Log deficiency warnings
        if stock.get('deficiency_risk_flag', False):
            risk_level = stock.get('deficiency_risk_level', 'NONE')
            days_below = stock.get('consecutive_below_1', 0)
            days_since_start = stock.get('days_since_deficiency_start', 0)
            warning_msg = format_deficiency_warning(symbol, days_below, days_since_start, risk_level)
            logger.warning(warning_msg)
    
    def get_tracking_summary(self) -> str:
        """Generate tracking summary report"""
        if not self.tracked_stocks:
            return "No stocks currently being tracked."
        
        # Calculate statistics
        total_stocks = len(self.tracked_stocks)
        active_stocks = sum(1 for s in self.tracked_stocks.values() if s['status'] == 'ACTIVE')
        hit_target = sum(1 for s in self.tracked_stocks.values() if s['status'] == 'HIT_TARGET')
        stopped_out = sum(1 for s in self.tracked_stocks.values() if s['status'] == 'STOPPED_OUT')
        
        avg_performance = sum(s['performance_pct'] for s in self.tracked_stocks.values()) / total_stocks
        avg_days = sum(s['days_tracked'] for s in self.tracked_stocks.values()) / total_stocks
        
        # Calculate deficiency risk statistics
        deficiency_risk_stocks = sum(1 for s in self.tracked_stocks.values() if s.get('deficiency_risk_flag', False))
        critical_risk_stocks = sum(1 for s in self.tracked_stocks.values() if s.get('deficiency_risk_level', 'NONE') == 'CRITICAL')
        
        # Generate report
        report = f"""📊 NASDAQ IPO Tracking Summary - {datetime.now().strftime('%Y-%m-%d')}
================================================================================
Total Tracked: {total_stocks} | Active: {active_stocks} | Hit Target: {hit_target} | Stopped Out: {stopped_out}
Average Performance: {avg_performance:+.2f}% | Average Days Tracked: {avg_days:.1f}
Deficiency Risk: {deficiency_risk_stocks} stocks | Critical Risk: {critical_risk_stocks} stocks
================================================================================
Symbol    First Date   Current   Change%   Days   Status    Deficiency Risk
--------------------------------------------------------------------------------"""
        
        # Sort by performance (descending)
        sorted_stocks = sorted(
            self.tracked_stocks.items(), 
            key=lambda x: x[1]['performance_pct'], 
            reverse=True
        )
        
        for symbol, data in sorted_stocks:
            # Format deficiency risk status
            deficiency_status = ""
            if data.get('deficiency_risk_flag', False):
                risk_level = data.get('deficiency_risk_level', 'NONE')
                days_below = data.get('consecutive_below_1', 0)
                if risk_level == 'CRITICAL':
                    deficiency_status = f"💀 {days_below}d"
                elif risk_level == 'HIGH':
                    deficiency_status = f"🔥 {days_below}d"
                elif risk_level == 'MEDIUM':
                    deficiency_status = f"🚨 {days_below}d"
                else:
                    deficiency_status = f"⚠️ {days_below}d"
            else:
                deficiency_status = "✅ OK"
            
            report += f"""
{symbol:<8} {data['first_recommended_date']}   ${data['last_price']:<8.4f} {data['performance_pct']:+6.2f}%   {data['days_tracked']:<4} {data['status']:<12} {deficiency_status}"""
        
        return report
    
    def get_active_stocks(self) -> List[str]:
        """Get list of currently active stocks"""
        return [symbol for symbol, data in self.tracked_stocks.items() if data['status'] == 'ACTIVE']
