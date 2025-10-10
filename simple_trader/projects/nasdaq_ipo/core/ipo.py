"""
IPO data fetching from Finnhub API and CSV fallback
"""
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import os
from dotenv import load_dotenv

from .utils import parse_date, days_ago

load_dotenv()

logger = logging.getLogger(__name__)


class IPOFetcher:
    """Fetch IPO data from Finnhub API or CSV fallback"""
    
    def __init__(self):
        self.finnhub_token = os.getenv('FINNHUB_TOKEN', '')
        self.base_url = 'https://finnhub.io/api/v1'
        
    def fetch_from_finnhub(self, days_back: int = 180) -> List[Dict]:
        """Fetch IPO data from Finnhub API"""
        if not self.finnhub_token:
            logger.warning("FINNHUB_TOKEN not provided, falling back to CSV")
            return []
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = days_ago(days_back)
            
            # Format dates for API
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            url = f"{self.base_url}/calendar/ipo"
            params = {
                'from': start_str,
                'to': end_str,
                'token': self.finnhub_token
            }
            
            logger.info(f"Fetching IPO data from Finnhub: {start_str} to {end_str}")
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            ipos = data.get('ipoCalendar', [])
            
            # Filter for NASDAQ only
            nasdaq_ipos = [
                ipo for ipo in ipos 
                if ipo.get('exchange', '').upper() == 'NASDAQ'
            ]
            
            logger.info(f"Found {len(nasdaq_ipos)} NASDAQ IPOs from Finnhub")
            
            # Convert to standard format
            result = []
            for ipo in nasdaq_ipos:
                result.append({
                    'symbol': ipo.get('symbol', ''),
                    'ipoDate': ipo.get('date', ''),
                    'exchange': 'NASDAQ'
                })
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Finnhub API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching from Finnhub: {e}")
            return []
    
    def fetch_from_csv(self, csv_path: str = 'ipos.csv') -> List[Dict]:
        """Fetch IPO data from CSV fallback"""
        try:
            if not os.path.exists(csv_path):
                logger.warning(f"CSV file {csv_path} not found")
                return []
            
            df = pd.read_csv(csv_path)
            
            # Validate required columns
            required_cols = ['symbol', 'ipoDate', 'exchange']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"CSV missing required columns: {required_cols}")
                return []
            
            # Filter for NASDAQ only
            nasdaq_df = df[df['exchange'].str.upper() == 'NASDAQ']
            
            # Convert to list of dicts
            result = nasdaq_df.to_dict('records')
            
            logger.info(f"Loaded {len(result)} NASDAQ IPOs from CSV")
            
            return result
            
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            return []
    
    def get_ipo_data(self, days_back: int = 180) -> List[Dict]:
        """Get IPO data with fallback logic"""
        # Try Finnhub first
        if self.finnhub_token:
            ipo_data = self.fetch_from_finnhub(days_back)
            if ipo_data:
                return ipo_data
        
        # Fallback to CSV
        logger.info("Using CSV fallback for IPO data")
        return self.fetch_from_csv()
    
    def filter_recent_ipos(self, ipo_data: List[Dict], days_back: int = 180) -> List[Dict]:
        """Filter IPOs from the last N days"""
        cutoff_date = days_ago(days_back)
        
        filtered = []
        for ipo in ipo_data:
            ipo_date = parse_date(ipo.get('ipoDate', ''))
            if ipo_date and ipo_date >= cutoff_date:
                filtered.append(ipo)
        
        logger.info(f"Filtered to {len(filtered)} IPOs from last {days_back} days")
        return filtered


def get_ipo_symbols(days_back: int = 180) -> List[str]:
    """Get list of IPO symbols from last N days"""
    fetcher = IPOFetcher()
    ipo_data = fetcher.get_ipo_data(days_back)
    recent_ipos = fetcher.filter_recent_ipos(ipo_data, days_back)
    
    symbols = [ipo['symbol'] for ipo in recent_ipos if ipo.get('symbol')]
    logger.info(f"Retrieved {len(symbols)} IPO symbols")
    
    return symbols
