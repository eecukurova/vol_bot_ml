#!/bin/bash
# NASDAQ IPO Screener - Log Rotation Script
# Run weekly to clean up old logs and CSV reports

cd /root/simple_trader/projects/nasdaq_ipo

# Create archive directory if it doesn't exist
mkdir -p archive

# Move CSV reports older than 30 days to archive
find output/ -name "nasdaq_ipo_report_*.csv" -mtime +30 -exec mv {} archive/ \;

# Compress old CSV reports (older than 90 days)
find archive/ -name "nasdaq_ipo_report_*.csv" -mtime +90 -exec gzip {} \;

# Clean up old log files (keep last 30 days)
find logs/ -name "nasdaq_ipo_*.log" -mtime +30 -delete

# Clean up old compressed logs (keep last 90 days)
find logs/ -name "nasdaq_ipo_*.log.gz" -mtime +90 -delete

# Log rotation completion
echo "$(date): Log rotation completed" >> logs/rotation.log
