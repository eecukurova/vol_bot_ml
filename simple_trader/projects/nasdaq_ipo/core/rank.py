"""
Ranking logic for NASDAQ Post-IPO Sub-$1 Rebound Screener
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def safe_mcap(market_cap):
    """Safe market cap handling for sorting"""
    if market_cap is None or market_cap <= 0:
        return float('inf')  # Put None/zero market cap at the end
    return float(market_cap)


class StockRanker:
    """Rank stocks based on multiple criteria"""
    
    def __init__(self):
        pass
    
    def rank_stocks(self, stocks: List[Dict], top_n: int = 20) -> List[Dict]:
        """Rank stocks and return top N"""
        if not stocks:
            logger.warning("No stocks to rank")
            return []
        
        logger.info(f"Ranking {len(stocks)} stocks")
        
        # Sort by multiple criteria
        ranked_stocks = sorted(
            stocks,
            key=lambda x: self._get_sort_key(x),
            reverse=True  # Descending order
        )
        
        # Return top N
        result = ranked_stocks[:top_n]
        logger.info(f"Returning top {len(result)} stocks")
        
        return result
    
    def _get_sort_key(self, stock: Dict) -> tuple:
        """Get sort key for ranking (higher is better)"""
        # Primary: Volume spike ratio (descending)
        vol_spike = stock.get('volSpikeRatio', 0.0)
        
        # Secondary: Drawdown from high (descending - higher drawdown = better opportunity)
        drawdown = stock.get('drawdownFromHigh', 0.0)
        
        # Tertiary: Market cap (ascending - smaller cap = better opportunity)
        market_cap = stock.get('marketCap')
        market_cap_safe = safe_mcap(market_cap)
        
        # Quaternary: RSI (lower is better for oversold recovery)
        rsi = stock.get('rsi14', 50.0)
        
        return (vol_spike, drawdown, -market_cap_safe, -rsi)  # Negative RSI for lower=better
    
    def get_ranking_explanation(self) -> str:
        """Get explanation of ranking criteria"""
        return ("Ranking by: 1) Volume Spike Ratio (desc), 2) Drawdown from High (desc), "
                "3) Market Cap (asc), 4) RSI (lower=better)")


def rank_stocks(stocks: List[Dict], top_n: int = 20) -> List[Dict]:
    """Convenience function to rank stocks"""
    ranker = StockRanker()
    return ranker.rank_stocks(stocks, top_n)
