#!/usr/bin/env bash
# =============================================================================
# VisionXR Keep-Alive Script (Called by infra_stabilizer & crontab)
# Ensures port 8022 is responsive; restarts uvicorn daemon if unresponsive.
# =============================================================================

DIR="/var/www22/visionXR"
LOG_FILE="$DIR/data/keep_alive.log"
mkdir -p "$DIR/data"

if [ -f /tmp/visionxr_paused ]; then
    exit 0
fi

if ! curl -s -m 3 http://127.0.0.1:8022/api/health >/dev/null 2>&1 && \
   ! curl -s -m 3 http://127.0.0.1:8022/api/stream/cameras >/dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [KEEP-ALIVE] VisionXR unresponsive on port 8022. Reviving..." >> "$LOG_FILE"
    fuser -k 8022/tcp 2>/dev/null || true
    pkill -f "uvicorn app.main:app --host 0.0.0.0 --port 8022" 2>/dev/null || true
    sleep 1
    cd "$DIR"
    nohup /usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8022 >> "$DIR/data/visionxr.log" 2>&1 &
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [KEEP-ALIVE] VisionXR process launched." >> "$LOG_FILE"
fi

# Ensure watchdog daemon is running
if ! pgrep -f "auto_heal_watchdog.sh" >/dev/null 2>&1; then
    nohup /bin/bash "$DIR/scripts/auto_heal_watchdog.sh" >> "$DIR/data/watchdog_runner.log" 2>&1 &
fi
