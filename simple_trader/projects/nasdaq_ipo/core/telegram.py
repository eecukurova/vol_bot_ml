"""
Telegram notification functionality
"""
import logging
import requests
import os
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv

from .utils import format_currency, format_percentage, format_volume

load_dotenv()

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications to Telegram"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not configured")
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram (auto-split if too long)"""
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram credentials not configured")
            return False
        
        # Telegram message limit is 4096 characters
        if len(message) <= 4096:
            return self._send_single_message(message, parse_mode)
        else:
            return self._send_split_messages(message, parse_mode)
    
    def _send_single_message(self, message: str, parse_mode: str) -> bool:
        """Send single message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            logger.info("Telegram message sent successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False
    
    def _send_split_messages(self, message: str, parse_mode: str) -> bool:
        """Split long message into multiple parts"""
        # Split by lines to preserve formatting
        lines = message.split('\n')
        current_message = ""
        message_parts = []
        
        for line in lines:
            # Check if adding this line would exceed limit
            if len(current_message + line + '\n') > 4000:  # Leave some buffer
                if current_message:
                    message_parts.append(current_message.strip())
                    current_message = line + '\n'
                else:
                    # Single line is too long, truncate it
                    message_parts.append(line[:4000])
                    current_message = ""
            else:
                current_message += line + '\n'
        
        # Add remaining content
        if current_message.strip():
            message_parts.append(current_message.strip())
        
        # Send all parts
        success = True
        for i, part in enumerate(message_parts):
            if i > 0:
                part = f"<i>(Part {i+1}/{len(message_parts)})</i>\n\n" + part
            
            if not self._send_single_message(part, parse_mode):
                success = False
        
        return success
    
    def send_screener_results(self, 
                            stocks: List[Dict], 
                            filter_summary: str,
                            top_n: int = 20) -> bool:
        """Send screener results to Telegram"""
        if not stocks:
            return self._send_no_results_message(filter_summary)
        
        # Send header message
        header_sent = self._send_header_message(len(stocks), filter_summary, top_n)
        
        # Send stock list
        if header_sent:
            return self._send_stock_list(stocks[:top_n])
        
        return False
    
    def _send_header_message(self, total_found: int, filter_summary: str, top_n: int) -> bool:
        """Send header message with summary"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        message = f"""<b>NASDAQ Post-IPO Sub-$1 Screener</b> ({today})
Filters: {filter_summary}
Top {min(total_found, top_n)} by VolSpike & Drawdown"""
        
        return self.send_message(message)
    
    def _send_stock_list(self, stocks: List[Dict]) -> bool:
        """Send formatted stock list"""
        if not stocks:
            return True
        
        message_lines = []
        
        for i, stock in enumerate(stocks, 1):
            line = self._format_stock_line(i, stock)
            message_lines.append(line)
        
        # Split into chunks if message is too long
        max_length = 4000  # Telegram message limit
        current_message = ""
        
        for line in message_lines:
            if len(current_message + line + "\n") > max_length:
                # Send current message
                if current_message:
                    if not self.send_message(current_message):
                        return False
                    current_message = ""
            
            current_message += line + "\n"
        
        # Send remaining message
        if current_message:
            return self.send_message(current_message)
        
        return True
    
    def _format_stock_line(self, rank: int, stock: Dict) -> str:
        """Format individual stock line"""
        symbol = stock.get('symbol', 'N/A')
        price = stock.get('lastClose', 0.0)
        volume = stock.get('lastVolume', 0)
        vol_spike = stock.get('volSpikeRatio', 0.0)
        rsi = stock.get('rsi14', 0.0)
        adx = stock.get('adx14', 0.0)
        drawdown = stock.get('drawdownFromHigh', 0.0)
        ipo_date = stock.get('ipoDate', 'Unknown')
        
        # Format values
        price_str = format_currency(price, 2)
        volume_str = format_volume(volume)
        vol_spike_str = f"{vol_spike:.1f}×"
        rsi_str = f"{rsi:.1f}"
        adx_str = f"{adx:.1f}"
        drawdown_str = format_percentage(drawdown, 0)
        
        return (f"{rank}) <b>{symbol}</b>  "
                f"Px:{price_str}  "
                f"Vol:{volume_str}  "
                f"Spike:{vol_spike_str}  "
                f"RSI:{rsi_str}  "
                f"ADX:{adx_str}  "
                f"DD:{drawdown_str}  "
                f"IPO:{ipo_date}")
    
    def _send_no_results_message(self, filter_summary: str) -> bool:
        """Send message when no results found"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        message = f"""<b>NASDAQ Post-IPO Sub-$1 Screener</b> ({today})
No matches for today (filters: {filter_summary})"""
        
        return self.send_message(message)


def send_screener_results(stocks: List[Dict], 
                         filter_summary: str,
                         top_n: int = 20) -> bool:
    """Convenience function to send screener results"""
    notifier = TelegramNotifier()
    return notifier.send_screener_results(stocks, filter_summary, top_n)
