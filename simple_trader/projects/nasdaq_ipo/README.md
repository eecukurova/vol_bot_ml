# NASDAQ Post-IPO Sub-$1 Rebound Screener

A comprehensive screener for identifying potential rebound opportunities in NASDAQ stocks that have recently gone public and are trading below $1.

## Features

- **IPO Data Sources**: Finnhub API with CSV fallback
- **Symbol Hygiene**: Excludes warrants, units, ETFs, SPACs, and other non-common stocks
- **Technical Analysis**: RSI, ADX, Volume analysis with custom implementations
- **Smart Filtering**: Multiple criteria for identifying rebound potential
- **Delist Risk Protection**: Tracks consecutive days below $1 to avoid delisting risks
- **Telegram Notifications**: Automated alerts with auto-splitting for long messages
- **Robust Error Handling**: Continues processing even with API failures
- **Comprehensive Testing**: Unit tests for all core functionality

## Quick Start

### 1. Installation

```bash
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Finnhub API Token (optional - falls back to ipos.csv if empty)
FINNHUB_TOKEN=your_finnhub_token_here

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Run the Screener

**Dry run (console output only):**
```bash
python app.py --dry-run
```

**Send to Telegram:**
```bash
python app.py
```

## Filter Criteria

### Security Type Exclusions
The screener automatically excludes non-common stocks:
- **Warrants** (symbols ending with W, WS, or containing "WARRANT")
- **Units** (symbols ending with U or containing "UNIT") 
- **Rights** (symbols ending with R or containing "RIGHT")
- **ETFs** (containing "ETF", "TRUST", "FUND")
- **SPACs** (containing "SPAC", "SPECIAL PURPOSE ACQUISITION")
- **ADRs** (containing "ADR", "ADS")

### Financial Filters
- **IPO Date**: Last 180 days (configurable)
- **Price Range**: $0.30 - $1.00 (configurable)
- **Daily Volume**: > 500,000 shares (configurable)
- **RSI(14)**: 30-45 (oversold recovery zone)
- **ADX(14)**: < 25 (weak trend = reversal potential)
- **Delist Risk**: ≤ 60 consecutive days below $1
- **Drawdown**: ≥ 70% from IPO high

### Ranking Criteria
1. **Volume Spike Ratio** (descending) - Higher volume = more interest
2. **Drawdown from High** (descending) - Higher drawdown = better opportunity  
3. **Market Cap** (ascending) - Smaller cap = more upside potential
4. **RSI** (ascending) - Lower RSI = more oversold

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/test_indicators.py    # RSI, ADX calculations
pytest tests/test_filters.py       # Filter logic and symbol hygiene
pytest tests/test_utils.py         # Utility functions
pytest tests/test_rank.py          # Ranking logic
```

### Test Coverage
- **Technical Indicators**: RSI and ADX calculations with deterministic test cases
- **Filter Logic**: Price, volume, RSI, ADX, consecutive days, and drawdown filters
- **Symbol Hygiene**: Warrant, unit, ETF, SPAC, and ADR exclusions
- **Utility Functions**: Safe division, consecutive days calculation, drawdown calculation
- **Ranking Logic**: Multi-criteria sorting with tie-breakers

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--days` | 180 | Days back for IPO filter |
| `--min_price` | 0.30 | Minimum price filter |
| `--max_price` | 1.00 | Maximum price filter |
| `--min_vol` | 500000 | Minimum daily volume |
| `--rsi_min` | 30.0 | Minimum RSI |
| `--rsi_max` | 45.0 | Maximum RSI |
| `--adx_max` | 25.0 | Maximum ADX |
| `--max_consec_below1` | 60 | Max consecutive days below $1 |
| `--min_drawdown` | 70.0 | Minimum drawdown from high % |
| `--top_n` | 20 | Number of top results to show |
| `--dry-run` | False | Run without sending Telegram messages |
| `--log-level` | INFO | Logging level |

## Filter Criteria

The screener applies the following filters to identify potential rebound opportunities:

1. **IPO Date**: Last 180 days (configurable)
2. **Price Range**: $0.30 - $1.00 (configurable)
3. **Volume**: > 500,000 daily volume (configurable)
4. **RSI**: 30-45 (oversold recovery band)
5. **ADX**: < 25 (weak trend → reversal potential)
6. **Delist Risk**: Max 60 consecutive days below $1
7. **Drawdown**: ≥ 70% from IPO high

## Ranking System

Stocks are ranked by:
1. **Volume Spike Ratio** (descending) - Higher volume activity
2. **Drawdown from High** (descending) - More oversold = better opportunity
3. **Market Cap** (ascending) - Smaller cap = more potential
4. **RSI** (lower = better) - More oversold = better recovery potential

## Known Limitations

- **Reverse Splits**: The screener doesn't account for reverse stock splits, which can affect price history
- **News Flow**: No integration with news sentiment or earnings announcements
- **Market Hours**: Data is based on daily closes, not intraday movements
- **IPO Data Accuracy**: Relies on Finnhub or manual CSV data for IPO dates
- **Rate Limits**: Respects API rate limits but may take longer for large symbol lists
- **Market Cap**: Some stocks may not have market cap data available

## Example Output

### Console Output
```
================================================================================
NASDAQ Post-IPO Sub-$1 Rebound Screener Results
Filters: IPO≤180d, Px 0.30–1.00, Vol>500,000, RSI 30–45, ADX<25, ≤60d <$1, DD≥70%
Found: 5 stocks
================================================================================
Rank Symbol   Price    Volume     Spike  RSI    ADX    DD%    IPO Date    
--------------------------------------------------------------------------------
1    REBND    $0.62    3.1M       2.8×   33.4   18.1   81%    2025-07-18  
2    RECOV    $0.45    2.2M       1.9×   31.2   22.3   75%    2025-08-15  
```

### Telegram Message
```
NASDAQ Post-IPO Sub-$1 Screener (2025-10-10)
Filters: IPO≤180d, Px 0.30–1.00, Vol>500,000, RSI 30–45, ADX<25, ≤60d <$1, DD≥70%
Top 5 by VolSpike & Drawdown

1) REBND  Px:$0.62  Vol:3.1M  Spike:2.8×  RSI:33.4  ADX:18.1  DD:81%  IPO:2025-07-18
2) RECOV  Px:$0.45  Vol:2.2M  Spike:1.9×  RSI:31.2  ADX:22.3  DD:75%  IPO:2025-08-15
```

## Project Structure

```
nasdaq_ipo/
├── app.py                 # Main application
├── requirements.txt       # Dependencies
├── .env.example          # Environment template
├── ipos.csv              # Fallback IPO data
├── core/                 # Core modules
│   ├── __init__.py
│   ├── utils.py          # Utility functions
│   ├── ipo.py            # IPO data fetching
│   ├── data.py           # Market data & indicators
│   ├── filters.py        # Filter logic
│   ├── rank.py           # Ranking logic
│   └── telegram.py       # Telegram notifications
├── tests/                # Unit tests
│   └── test_indicators.py
└── output/               # Generated reports
```

## Testing

Run the test suite:

```bash
pytest tests/
```

## Error Handling

The application is designed to be resilient:

- **API Failures**: Continues processing other symbols
- **Missing Data**: Logs warnings and skips problematic symbols
- **Rate Limiting**: Built-in delays and batching
- **Network Issues**: Retry logic with exponential backoff

## Fallback Mode

If Finnhub API is not available or token is not provided, the screener automatically falls back to using the included `ipos.csv` file with sample IPO data.

## Rate Limits

- **Finnhub API**: Respects rate limits with built-in delays
- **Yahoo Finance**: Batched requests with delays to avoid blocking
- **Telegram**: Single message per run to avoid spam

## Logging

The application provides detailed logging at different levels:

- **INFO**: General progress and results
- **WARNING**: Non-critical issues (missing data, API fallbacks)
- **ERROR**: Critical failures that stop processing
- **DEBUG**: Detailed technical information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is for educational and research purposes. Please ensure compliance with all applicable terms of service for the data sources used.

## Disclaimer

This screener is for informational purposes only and does not constitute financial advice. Always conduct your own research and consider consulting with a financial advisor before making investment decisions.
