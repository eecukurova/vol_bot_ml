# Dockerfile for ATR + SuperTrend Strategy Optimizer

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy source code
COPY . .

# Create necessary directories
RUN mkdir -p /app/cache /app/reports

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN useradd -m -u 1000 optimizer && \
    chown -R optimizer:optimizer /app
USER optimizer

# Default command
CMD ["python", "-m", "strategy_optimizer.cli", "--help"]
