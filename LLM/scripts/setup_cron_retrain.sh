#!/bin/bash
# Cron job setup script for automated retraining
# Usage: ./setup_cron_retrain.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"

# Cron job entry (runs every Sunday at 2:00 AM)
CRON_ENTRY="0 2 * * 0 cd $PROJECT_DIR && $VENV_PYTHON scripts/retrain_runner.py --config configs/train_3m.json --test-weeks 2 --min-improvement 0.05 >> runs/retrain.log 2>&1"

echo "🔧 Setting up cron job for automated retraining..."
echo ""
echo "Project directory: $PROJECT_DIR"
echo "Python path: $VENV_PYTHON"
echo ""
echo "Cron entry to add:"
echo "$CRON_ENTRY"
echo ""
echo "To add manually, run:"
echo "  crontab -e"
echo ""
echo "Then paste the line above."
echo ""
echo "Or run this command to add automatically:"
echo "  (crontab -l 2>/dev/null; echo \"$CRON_ENTRY\") | crontab -"

read -p "Add cron job automatically? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "✅ Cron job added!"
    echo ""
    echo "View current cron jobs:"
    echo "  crontab -l"
    echo ""
    echo "Check retraining logs:"
    echo "  tail -f $PROJECT_DIR/runs/retrain.log"
else
    echo "Skipped. Add manually using the instructions above."
fi

