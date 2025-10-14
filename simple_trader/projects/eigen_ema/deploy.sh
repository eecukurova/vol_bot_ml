#!/bin/bash

# Eigen EMA Multi-Timeframe Crossover Trader - Deployment Script
# This script automates the deployment process on Ubuntu servers

set -e  # Exit on any error

echo "🚀 Eigen EMA Trader Deployment Script"
echo "====================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Check if we're on Ubuntu
if ! command -v apt &> /dev/null; then
    print_error "This script is designed for Ubuntu/Debian systems"
    exit 1
fi

print_status "Starting deployment process..."

# Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and pip if not already installed
if ! command -v python3 &> /dev/null; then
    print_status "Installing Python 3..."
    sudo apt install python3 python3-pip python3-venv -y
fi

# Install system dependencies
print_status "Installing system dependencies..."
sudo apt install -y curl wget git htop nano

# Create project directory
PROJECT_DIR="/home/$USER/simple_trader/projects/eigen_ema"
print_status "Creating project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"

# Navigate to project directory
cd "$PROJECT_DIR"

# Create virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install ccxt pandas numpy requests python-telegram-bot pydantic python-dotenv

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p runs logs

# Copy configuration file if it doesn't exist
if [ ! -f "eigen_ema_multi_config.json" ]; then
    print_status "Creating configuration file..."
    cp eigen_ema_multi_config.json.example eigen_ema_multi_config.json
    print_warning "Please edit eigen_ema_multi_config.json with your API keys and settings"
fi

# Set up systemd service
print_status "Setting up systemd service..."
sudo cp eigen-ema-multi-trader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable eigen-ema-multi-trader.service

# Set proper permissions
print_status "Setting proper permissions..."
sudo chown -R $USER:$USER "$PROJECT_DIR"
chmod +x eigen_ema_multi_trader.py

# Create log rotation configuration
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/eigen-ema-trader > /dev/null <<EOF
$PROJECT_DIR/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload eigen-ema-multi-trader.service
    endscript
}
EOF

# Create monitoring script
print_status "Creating monitoring script..."
cat > monitor.sh << 'EOF'
#!/bin/bash

# Eigen EMA Trader Monitoring Script

echo "🔍 Eigen EMA Trader Status"
echo "=========================="

# Check service status
echo "📊 Service Status:"
systemctl is-active eigen-ema-multi-trader.service

# Check recent logs
echo -e "\n📋 Recent Logs (last 10 lines):"
journalctl -u eigen-ema-multi-trader.service -n 10 --no-pager

# Check for errors
echo -e "\n❌ Recent Errors:"
journalctl -u eigen-ema-multi-trader.service --since "1 hour ago" | grep -E "(ERROR|❌)" | tail -5

# Check disk usage
echo -e "\n💾 Disk Usage:"
df -h $PWD

# Check memory usage
echo -e "\n🧠 Memory Usage:"
free -h
EOF

chmod +x monitor.sh

# Create backup script
print_status "Creating backup script..."
cat > backup.sh << 'EOF'
#!/bin/bash

# Eigen EMA Trader Backup Script

BACKUP_DIR="/home/$USER/backups/eigen_ema"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="eigen_ema_backup_$DATE.tar.gz"

echo "📦 Creating backup: $BACKUP_FILE"

mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/$BACKUP_FILE" \
    --exclude='venv' \
    --exclude='*.log' \
    --exclude='__pycache__' \
    .

echo "✅ Backup created: $BACKUP_DIR/$BACKUP_FILE"
EOF

chmod +x backup.sh

# Create update script
print_status "Creating update script..."
cat > update.sh << 'EOF'
#!/bin/bash

# Eigen EMA Trader Update Script

echo "🔄 Updating Eigen EMA Trader..."

# Stop service
sudo systemctl stop eigen-ema-multi-trader.service

# Backup current version
./backup.sh

# Pull latest changes (if using git)
# git pull origin main

# Update dependencies
source venv/bin/activate
pip install --upgrade ccxt pandas numpy requests python-telegram-bot

# Restart service
sudo systemctl start eigen-ema-multi-trader.service

echo "✅ Update completed!"
EOF

chmod +x update.sh

# Create health check script
print_status "Creating health check script..."
cat > health_check.sh << 'EOF'
#!/bin/bash

# Eigen EMA Trader Health Check Script

PROJECT_DIR="/home/$USER/simple_trader/projects/eigen_ema"
cd "$PROJECT_DIR"

echo "🏥 Eigen EMA Trader Health Check"
echo "================================="

# Check if service is running
if systemctl is-active --quiet eigen-ema-multi-trader.service; then
    echo "✅ Service is running"
else
    echo "❌ Service is not running"
    exit 1
fi

# Check if config file exists
if [ -f "eigen_ema_multi_config.json" ]; then
    echo "✅ Configuration file exists"
else
    echo "❌ Configuration file missing"
    exit 1
fi

# Check if Python dependencies are installed
source venv/bin/activate
python3 -c "import ccxt, pandas, numpy, requests" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Python dependencies are installed"
else
    echo "❌ Python dependencies missing"
    exit 1
fi

# Check disk space
DISK_USAGE=$(df "$PROJECT_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 90 ]; then
    echo "✅ Disk space is sufficient ($DISK_USAGE% used)"
else
    echo "❌ Disk space is low ($DISK_USAGE% used)"
    exit 1
fi

# Check memory usage
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ "$MEMORY_USAGE" -lt 90 ]; then
    echo "✅ Memory usage is normal ($MEMORY_USAGE% used)"
else
    echo "❌ Memory usage is high ($MEMORY_USAGE% used)"
fi

echo "✅ Health check passed!"
EOF

chmod +x health_check.sh

# Final setup
print_status "Finalizing setup..."

# Create a simple start script
cat > start.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Eigen EMA Trader..."
sudo systemctl start eigen-ema-multi-trader.service
sudo systemctl status eigen-ema-multi-trader.service --no-pager
EOF

chmod +x start.sh

# Create a simple stop script
cat > stop.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping Eigen EMA Trader..."
sudo systemctl stop eigen-ema-multi-trader.service
echo "✅ Service stopped"
EOF

chmod +x stop.sh

# Create a simple restart script
cat > restart.sh << 'EOF'
#!/bin/bash
echo "🔄 Restarting Eigen EMA Trader..."
sudo systemctl restart eigen-ema-multi-trader.service
sudo systemctl status eigen-ema-multi-trader.service --no-pager
EOF

chmod +x restart.sh

print_success "Deployment completed successfully!"
echo ""
echo "📋 Next Steps:"
echo "1. Edit eigen_ema_multi_config.json with your API keys and settings"
echo "2. Run ./health_check.sh to verify everything is working"
echo "3. Run ./start.sh to start the trader"
echo "4. Run ./monitor.sh to check status"
echo ""
echo "📚 Available Scripts:"
echo "- ./start.sh      : Start the trader"
echo "- ./stop.sh       : Stop the trader"
echo "- ./restart.sh    : Restart the trader"
echo "- ./monitor.sh    : Monitor status and logs"
echo "- ./health_check.sh: Run health check"
echo "- ./backup.sh     : Create backup"
echo "- ./update.sh     : Update dependencies"
echo ""
echo "📖 Documentation:"
echo "- README.md       : Complete documentation"
echo "- QUICKSTART.md   : Quick start guide"
echo "- PERFORMANCE.md  : Performance metrics"
echo ""
print_warning "Don't forget to configure your API keys in eigen_ema_multi_config.json!"
print_success "Happy trading! 🎉"
