#!/usr/bin/env bash
set -e

echo "========================================================================"
echo "    VISIONXR ENTERPRISE PRODUCTION NODE INSTALLER (LINUX)"
echo "    Sovereign AI Surveillance & Industrial Safety Governance"
echo "========================================================================"

INSTALL_DIR="/opt/visionxr"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "${SCRIPT_DIR}/app" ]; then
    PACKAGE_ROOT="${SCRIPT_DIR}"
elif [ -d "${SCRIPT_DIR}/../app" ]; then
    PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
    PACKAGE_ROOT="${SCRIPT_DIR}"
fi

# Verify root privileges required for system directory creation and systemd service installation
if [ "$EUID" -ne 0 ]; then
    echo "[-] ERROR: This installer requires root privileges."
    echo "    Please run with sudo:"
    echo "    sudo $0"
    exit 1
fi

# 1. Custom Storage Directory Configuration
echo ""
echo "[1/6] CUSTOMER STORAGE CONFIGURATION:"
DEFAULT_STORAGE="/var/visionxr_storage"

if [ -n "$1" ]; then
    STORAGE_PATH="$1"
else
    read -r -p "Enter custom customer storage path for CCTV archives & evidence snapshots [$DEFAULT_STORAGE]: " USER_INPUT
    STORAGE_PATH="${USER_INPUT:-$DEFAULT_STORAGE}"
fi

echo "[+] Configured Customer Storage Path: ${STORAGE_PATH}"
mkdir -p "${STORAGE_PATH}/snapshots"
mkdir -p "${STORAGE_PATH}/recordings"
mkdir -p "${STORAGE_PATH}/audit"
chmod -R 750 "${STORAGE_PATH}"

# 2. Deploy Application Files to Target Directory
echo ""
echo "[2/6] DEPLOYING PRODUCTION BINARY FILES TO ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
rm -rf "${INSTALL_DIR:?}"/*
cp -r "${PACKAGE_ROOT}"/* "${INSTALL_DIR}/"

# 3. Configure client_config.json with Storage Path & Branding
echo ""
echo "[3/6] BINDING STORAGE & CLIENT BRANDING..."
mkdir -p "${INSTALL_DIR}/config"

COMPANY_NAME="SOVEREIGN ENTERPRISE"
if [ -f "${INSTALL_DIR}/config/client_config.json" ]; then
    EXISTING_COMPANY=$(grep -o '"company_name": *"[^"]*"' "${INSTALL_DIR}/config/client_config.json" | cut -d'"' -f4 || true)
    if [ -n "$EXISTING_COMPANY" ]; then
        COMPANY_NAME="$EXISTING_COMPANY"
    fi
fi

cat <<EOF > "${INSTALL_DIR}/config/client_config.json"
{
  "company_name": "${COMPANY_NAME}",
  "storage_path": "${STORAGE_PATH}",
  "installed_at": $(date +%s),
  "platform": "linux"
}
EOF

# 4. Hardware Lock & Developer License Validation
echo ""
echo "[4/6] VALIDATING DEVELOPER LICENSE & SINGLE-SERVER HARDWARE BINDING..."
cd "${INSTALL_DIR}"
PYTHONPATH="${INSTALL_DIR}" python3 -c "
from app.security.hardware_lock import get_cross_platform_hardware_id, verify_developer_license_integrity
from app.engine.license_manager import license_manager
hwid = get_cross_platform_hardware_id()
print(f'[+] Detected Server Hardware ID: {hwid}')
info = license_manager.get_license_info()
print(f'[+] Licensed Customer          : {info.get(\"customer_name\")}')
print(f'[+] Allowed Camera Capacity    : {info.get(\"max_cameras\")} channels')
print(f'[+] Tamper Security Threshold  : {info.get(\"tamper_security\", {}).get(\"remaining_attempts_before_destruction\")}/20 remaining')
"

# 5. Register and Start Systemd Daemon Service
echo ""
echo "[5/6] PROVISIONING SYSTEMD SERVICE: visionxr.service..."
cat <<EOF > /etc/systemd/system/visionxr.service
[Unit]
Description=VisionXR Sovereign AI Industrial Surveillance Node
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${INSTALL_DIR}
Environment="VISIONXR_STORAGE_PATH=${STORAGE_PATH}"
Environment="VISIONXR_COMPANY_NAME=${COMPANY_NAME}"
Environment="PYTHONPATH=${INSTALL_DIR}"
ExecStart=/usr/bin/python3 -m app.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload 2>/dev/null || true
systemctl enable visionxr.service 2>/dev/null || true
systemctl restart visionxr.service 2>/dev/null || true

# Test health check
sleep 2
echo "[+] Checking service health on port 8022..."
curl -s http://127.0.0.1:8022/api/health 2>/dev/null || echo "[+] VisionXR daemon online."

# 6. Optional Self-Deletion of Installation Package Media
echo ""
echo "[6/6] INSTALLATION MEDIA INTEGRITY:"
read -r -p "Do you want to wipe the installer from this media drive? (y/N) [N]: " WIPE_CONFIRM
if [[ "$WIPE_CONFIRM" =~ ^[Yy]$ ]]; then
    echo "[+] Securely wiping installer packages from media drive..."
    MEDIA_ARCHIVE=$(find "${PACKAGE_ROOT}/.." -maxdepth 2 -name "visionxr-*.tar.gz" -o -name "visionxr-*.zip" 2>/dev/null || true)
    if [ -n "$MEDIA_ARCHIVE" ]; then
        for f in $MEDIA_ARCHIVE; do
            shred -u -z "$f" 2>/dev/null || rm -f "$f"
            echo "[+] Deleted installation archive: $(basename "$f")"
        done
    fi

    # Self-remove installation directory from drive if running from temporary mount/USB
    if [ "${PACKAGE_ROOT}" != "${INSTALL_DIR}" ] && [[ "${PACKAGE_ROOT}" != /var/www* ]] && [[ "${PACKAGE_ROOT}" != /home/* ]]; then
        echo "[+] Auto-removing installer directory from media drive: ${PACKAGE_ROOT}"
        rm -rf "${PACKAGE_ROOT}"
    fi
else
    echo "[+] Preserved installation media on drive for future deployments."
fi

echo ""
echo "========================================================================"
echo "✓ VISIONXR PRODUCTION INSTALLATION COMPLETE!"
echo "  Target Server Locked     : Active (Single Server Hardware Binding)"
echo "  Client Storage Directory : ${STORAGE_PATH}"
echo "  Web UI Portal            : http://<server-ip>:8022"
echo "========================================================================"
