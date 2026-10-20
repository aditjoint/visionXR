#!/usr/bin/env bash
# VisionXR Sector 22 Daemon Starter
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=========================================================="
echo " Starting VisionXR Sector 22 Sovereign AI Command Engine"
echo " Target IP: 127.0.0.22 / Host: 0.0.0.0:8022"
echo " Domain: visionxr.adamconsult.com"
echo "=========================================================="

# Ensure directories exist
mkdir -p data/snapshots static/css static/js

# Remove pause lock if set
rm -f /tmp/visionxr_paused

# Kill existing instance on port 8022 if running
fuser -k 8022/tcp 2>/dev/null || true

# Start FastAPI Uvicorn Server
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8022 --log-level info
