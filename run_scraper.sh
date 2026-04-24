#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_scraper.sh  — wrapper called by cron
#
# Cron setup (runs every day at 08:00):
#   1. Open terminal and run:  crontab -e
#   2. Add this line (replace the path with your actual path):
#
#      0 8 * * * /Users/javohireshonov/Desktop/Study/Projects/Tashkent\ apartment\ analysis/run_scraper.sh
#
# ---------------------------------------------------------------------------

PROJECT_DIR="/Users/javohireshonov/Desktop/Study/Projects/Tashkent apartment analysis"
SCRAPER_DIR="$PROJECT_DIR/scraper"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

echo "$(date '+%Y-%m-%d %H:%M:%S') — cron run started" >> "$LOG_DIR/cron.log"

cd "$SCRAPER_DIR" || exit 1

# Activate the environment that has the dependencies installed.
# If you used a plain pip install, just call python3 directly.
# If you used conda:  conda run -n <env_name> python scraper.py
python3 scraper.py >> "$LOG_DIR/cron.log" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') — cron run finished" >> "$LOG_DIR/cron.log"
