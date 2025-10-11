#!/usr/bin/env python3
"""
NASDAQ Post-IPO Sub-$1 Rebound Screener
Main application entry point
"""
import argparse
import logging
import sys
import csv
import os
from datetime import datetime
from typing import List, Dict

# Add current directory to path for imports
sys.path.append('.')

from core.utils import setup_logging, format_date
from core.ipo import get_ipo_symbols, IPOFetcher
from core.data import analyze_stocks
from core.filters import StockFilter, get_filter_summary
from core.rank import rank_stocks
from core.telegram import send_screener_results
from core.tracking import StockTracker


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='NASDAQ Post-IPO Sub-$1 Rebound Screener',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app.py --dry-run
  python app.py --days 90 --min_price 0.5 --top_n 10
  python app.py --min_vol 1000000 --rsi_min 25
        """
    )
    
    # Filter parameters
    parser.add_argument('--days', type=int, default=180,
                       help='Days back for IPO filter (default: 180)')
    parser.add_argument('--min_price', type=float, default=0.30,
                       help='Minimum price filter (default: 0.30)')
    parser.add_argument('--max_price', type=float, default=1.00,
                       help='Maximum price filter (default: 1.00)')
    parser.add_argument('--min_vol', type=int, default=500000,
                       help='Minimum daily volume (default: 500000)')
    parser.add_argument('--rsi_min', type=float, default=30.0,
                       help='Minimum RSI (default: 30.0)')
    parser.add_argument('--rsi_max', type=float, default=45.0,
                       help='Maximum RSI (default: 45.0)')
    parser.add_argument('--adx_max', type=float, default=25.0,
                       help='Maximum ADX (default: 25.0)')
    parser.add_argument('--max_consec_below1', type=int, default=60,
                       help='Max consecutive days below $1 (default: 60)')
    parser.add_argument('--min_drawdown', type=float, default=70.0,
                       help='Minimum drawdown from high %% (default: 70.0)')
    
    # Output parameters
    parser.add_argument('--top_n', type=int, default=20,
                       help='Number of top results to show (default: 20)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without sending Telegram messages')
    
    # Logging
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Logging level (default: INFO)')
    
    return parser.parse_args()


def print_console_summary(stocks: List[Dict], filter_summary: str):
    """Print console summary table"""
    if not stocks:
        print(f"\nNo stocks found matching filters: {filter_summary}")
        return
    
    print(f"\n{'='*80}")
    print(f"NASDAQ Post-IPO Sub-$1 Rebound Screener Results")
    print(f"Filters: {filter_summary}")
    print(f"Found: {len(stocks)} stocks")
    print(f"{'='*80}")
    
    # Header
    print(f"{'Rank':<4} {'Symbol':<8} {'Price':<8} {'Volume':<10} {'Spike':<6} "
          f"{'RSI':<6} {'ADX':<6} {'DD%':<6} {'IPO Date':<12}")
    print("-" * 80)
    
    # Data rows
    for i, stock in enumerate(stocks, 1):
        symbol = stock.get('symbol', 'N/A')
        price = stock.get('lastClose', 0.0)
        volume = stock.get('lastVolume', 0)
        vol_spike = stock.get('volSpikeRatio', 0.0)
        rsi = stock.get('rsi14', 0.0)
        adx = stock.get('adx14', 0.0)
        drawdown = stock.get('drawdownFromHigh', 0.0)
        ipo_date = stock.get('ipoDate', 'Unknown')
        
        print(f"{i:<4} {symbol:<8} ${price:<7.2f} {volume:<10,} {vol_spike:<6.1f}× "
              f"{rsi:<6.1f} {adx:<6.1f} {drawdown:<6.1f}% {ipo_date:<12}")


def main():
    """Main application function"""
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting NASDAQ Post-IPO Sub-$1 Rebound Screener")
    logger.info(f"Arguments: {vars(args)}")
    
    try:
        # Step 1: Get IPO symbols
        logger.info("Step 1: Fetching IPO symbols")
        ipo_symbols = get_ipo_symbols(args.days)
        
        if not ipo_symbols:
            logger.warning("No IPO symbols found")
            if not args.dry_run:
                filter_summary = get_filter_summary(
                    args.min_price, args.max_price, args.min_vol,
                    args.rsi_min, args.rsi_max, args.adx_max,
                    args.max_consec_below1, args.min_drawdown, args.days
                )
                send_screener_results([], filter_summary, args.top_n)
            return
        
        logger.info(f"Found {len(ipo_symbols)} IPO symbols")
        
        # Step 2: Analyze stocks
        logger.info("Step 2: Analyzing stocks")
                # Get IPO dates for symbols
        fetcher = IPOFetcher()
        ipo_data = fetcher.get_ipo_data(args.days)
        recent_ipos = fetcher.filter_recent_ipos(ipo_data, args.days)
        ipo_dates = {}
        for ipo in recent_ipos:
            ipo_dates[ipo["symbol"]] = ipo["ipoDate"]
        
        stock_analyses = analyze_stocks(ipo_symbols, ipo_dates)
        
        if not stock_analyses:
            logger.warning("No stock analyses completed")
            return
        
        logger.info(f"Analyzed {len(stock_analyses)} stocks")
        
        # Step 3: Apply filters
        logger.info("Step 3: Applying filters")
        stock_filter = StockFilter(
            min_price=args.min_price,
            max_price=args.max_price,
            min_volume=args.min_vol,
            rsi_min=args.rsi_min,
            rsi_max=args.rsi_max,
            adx_max=args.adx_max,
            max_consec_below1=args.max_consec_below1,
            min_drawdown=args.min_drawdown,
            ipo_days_back=args.days
        )
        
        filtered_stocks = stock_filter.apply_filters(stock_analyses)
        
        # Step 4: Rank stocks
        logger.info("Step 4: Ranking stocks")
        ranked_stocks = rank_stocks(filtered_stocks, args.top_n)
        
        # Step 5: Generate filter summary
        filter_summary = get_filter_summary(
            args.min_price, args.max_price, args.min_vol,
            args.rsi_min, args.rsi_max, args.adx_max,
            args.max_consec_below1, args.min_drawdown, args.days
        )
        
        # Step 6: Output results
        print_console_summary(ranked_stocks, filter_summary)
        
        # Step 6.5: Update tracking system
        logger.info("Step 6.5: Updating stock tracking")
        tracker = StockTracker()
        
        # Add new stocks to tracking
        for stock in ranked_stocks:
            symbol = stock['symbol']
            price = stock['lastClose']
            tracker.add_new_stock(symbol, price)
        
        # Update existing tracked stocks with current prices
        active_stocks = tracker.get_active_stocks()
        if active_stocks:
            logger.info(f"Updating {len(active_stocks)} tracked stocks")
            # Re-analyze tracked stocks to get current prices
            tracked_analyses = analyze_stocks(active_stocks, ipo_dates)
            for analysis in tracked_analyses:
                if analysis:
                    symbol = analysis['symbol']
                    current_price = analysis['lastClose']
                    tracker.update_stock_price(symbol, current_price)
        
        # Step 7: Save CSV report
        if ranked_stocks:
            save_csv_report(ranked_stocks, args)
        
        # Step 8: Print tracking summary
        tracking_summary = tracker.get_tracking_summary()
        print("\n" + tracking_summary)
        
        # Step 9: Send Telegram notification (if not dry-run)
        if not args.dry_run:
            logger.info("Step 8: Sending Telegram notification")
            success = send_screener_results(ranked_stocks, filter_summary, args.top_n)
            if success:
                logger.info("Telegram notification sent successfully")
            else:
                logger.error("Failed to send Telegram notification")
        else:
            logger.info("Dry-run mode: Skipping Telegram notification")
        
        logger.info("Screener completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Screener interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def save_csv_report(stocks: List[Dict], args):
    """Save results to CSV report"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not stocks:
        return
    
    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"output/nasdaq_ipo_report_{timestamp}.csv"
    
    # Define CSV columns
    fieldnames = [
        'symbol', 'lastClose', 'lastVolume', 'volSpikeRatio', 
        'rsi14', 'adx14', 'daysConsecBelow1', 'drawdownFromHigh',
        'ipoDate', 'marketCap'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for stock in stocks:
                # Prepare row data
                row = {}
                for field in fieldnames:
                    value = stock.get(field, '')
                    # Format numeric values
                    if field in ['lastClose', 'volSpikeRatio', 'rsi14', 'adx14', 'drawdownFromHigh']:
                        row[field] = f"{value:.2f}" if value else ''
                    elif field in ['lastVolume', 'marketCap']:
                        row[field] = f"{value:,.0f}" if value else ''
                    else:
                        row[field] = value
                
                writer.writerow(row)
        
        logger.info(f"CSV report saved: {filename}")
        
    except Exception as e:
        logger.error(f"Error saving CSV report: {e}")


if __name__ == "__main__":
    main()
