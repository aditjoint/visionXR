#!/usr/bin/env bash
# VisionXR Autonomous Process Watchdog & Auto-Healer
# Continuously monitors port 8022 and auto-revives VisionXR if unreachable

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$DIR/data/watchdog.log"
mkdir -p "$DIR/data"

while true; do
    if [ -f /tmp/visionxr_paused ]; then
        sleep 5
        continue
    fi
    if ! curl -s -m 2 http://127.0.0.1:8022/api/stream/cameras > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [AUTO-HEAL WATCHDOG] VisionXR unreachable on port 8022. Resurrecting daemon..." >> "$LOG_FILE"
        fuser -k 8022/tcp 2>/dev/null || true
        cd "$DIR"
        nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8022 --log-level info >> "$DIR/data/visionxr.log" 2>&1 &
        sleep 4
    fi
    sleep 5
done
