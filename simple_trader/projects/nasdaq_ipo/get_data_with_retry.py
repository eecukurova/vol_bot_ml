def get_nasdaq_data_with_retry(self, symbol, max_retries=5, retry_delay=60):
    """Yahoo Finance'dan NASDAQ verisi çek - Retry ile"""
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period='5d', interval='15m')
            
            if df.empty:
                self.log.warning(f"⚠️ {symbol} için veri alınamadı. Deneme {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    self.log.info(f"⏰ {retry_delay} saniye bekleniyor...")
                    time.sleep(retry_delay)
                continue
            
            # Son mumun zamanını kontrol et
            last_candle_time = df.index[-1]
            current_time = datetime.now(self.timezone)
            
            self.log.info(f"📊 {symbol}: Son mum zamanı: {last_candle_time.strftime('%H:%M:%S')}")
            self.log.info(f"📊 {symbol}: Mevcut zaman: {current_time.strftime('%H:%M:%S')}")
            
            return df
            
        except Exception as e:
            self.log.error(f"❌ {symbol} veri çekme hatası (deneme {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                self.log.info(f"⏰ {retry_delay} saniye bekleniyor...")
                time.sleep(retry_delay)
    
    self.log.error(f"❌ {symbol} için {max_retries} deneme sonunda veri alınamadı")
    return None
