#!/usr/bin/env bash
# =============================================================================
# stop_visionxr.sh — Instantly Pause / Stop VisionXR Daemon & Watchdogs
# Sets /tmp/visionxr_paused so auto-heal won't restart until started again.
# =============================================================================

touch /tmp/visionxr_paused
fuser -k 8022/tcp 2>/dev/null || true
pkill -f "uvicorn app.main:app.*8022" 2>/dev/null || true

echo "✓ VisionXR stopped. Port 8022 released."
echo "✓ Watchdog & keep-alive are paused. Server will remain cooled."
echo "To resume: run bash /var/www22/visionXR/scripts/start_visionxr.sh"
