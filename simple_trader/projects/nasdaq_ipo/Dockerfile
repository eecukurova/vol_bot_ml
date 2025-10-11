FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs output

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN useradd -m -u 1000 nasdaq && chown -R nasdaq:nasdaq /app
USER nasdaq

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe', timeout=5)" || exit 1

# Default command
CMD ["python", "app.py", "--days", "180", "--min_price", "0.30", "--max_price", "1.00", "--min_vol", "500000", "--rsi_min", "30", "--rsi_max", "45", "--adx_max", "25", "--max_consec_below1", "60", "--min_drawdown", "70", "--top_n", "20"]
