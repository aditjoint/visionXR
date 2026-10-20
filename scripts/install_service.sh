#!/usr/bin/env bash
# VisionXR Systemd Service & Nginx Installer
set -e

echo "=== Installing VisionXR Sector 22 Systemd Service ==="

cat << 'EOF' | sudo tee /etc/systemd/system/visionxr.service
[Unit]
Description=VisionXR Sovereign Surveillance & Behavioral AI Engine
After=network.target

[Service]
Type=simple
User=adity
Group=adity
WorkingDirectory=/var/www22/visionXR
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8022
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload
sudo systemctl enable visionxr.service
sudo systemctl restart visionxr.service

echo "=== Linking Sector 22 Nginx Virtual Host ==="
sudo cp /var/www22/visionXR/scripts/visionxr.nginx.conf /etc/nginx/sites-available/visionxr
sudo ln -sf /etc/nginx/sites-available/visionxr /etc/nginx/sites-enabled/visionxr

# Add visionxr.adamconsult.com to /etc/hosts if absent
if ! grep -q "visionxr.adamconsult.com" /etc/hosts; then
    echo "127.0.0.22 visionxr.adamconsult.com" | sudo tee -a /etc/hosts
fi

sudo nginx -t && sudo systemctl reload nginx
echo "✓ VisionXR is permanently installed and live on http://127.0.0.22/ and http://visionxr.adamconsult.com!"
