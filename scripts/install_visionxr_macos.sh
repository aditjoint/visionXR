#!/usr/bin/env bash
set -e

echo "========================================================================"
echo "    VISIONXR ENTERPRISE PRODUCTION NODE INSTALLER (macOS)"
echo "    Sovereign AI Surveillance & Industrial Safety Governance"
echo "========================================================================"

INSTALL_DIR="/Library/VisionXR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 1. Custom Storage Directory Configuration
echo ""
echo "[1/6] CUSTOMER STORAGE CONFIGURATION:"
DEFAULT_STORAGE="/Users/Shared/VisionXR_Storage"

if [ -n "$1" ]; then
    STORAGE_PATH="$1"
else
    read -r -p "Enter custom customer storage path for CCTV archives [$DEFAULT_STORAGE]: " USER_INPUT
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
sudo mkdir -p "${INSTALL_DIR}"
sudo cp -r "${PACKAGE_ROOT}"/* "${INSTALL_DIR}/" 2>/dev/null || true

# 3. Configure client_config.json
echo ""
echo "[3/6] BINDING STORAGE & CLIENT BRANDING..."
sudo mkdir -p "${INSTALL_DIR}/config"

COMPANY_NAME="SOVEREIGN ENTERPRISE"
if [ -f "${INSTALL_DIR}/config/client_config.json" ]; then
    EXISTING_COMPANY=$(grep -o '"company_name": *"[^"]*"' "${INSTALL_DIR}/config/client_config.json" | cut -d'"' -f4 || true)
    if [ -n "$EXISTING_COMPANY" ]; then
        COMPANY_NAME="$EXISTING_COMPANY"
    fi
fi

sudo tee "${INSTALL_DIR}/config/client_config.json" > /dev/null <<EOF
{
  "company_name": "${COMPANY_NAME}",
  "storage_path": "${STORAGE_PATH}",
  "installed_at": $(date +%s),
  "platform": "darwin"
}
EOF

# 4. Hardware Lock & Developer License Validation
echo ""
echo "[4/6] VALIDATING DEVELOPER LICENSE & HARDWARE BINDING..."
cd "${INSTALL_DIR}"
python3 -c "
from app.security.hardware_lock import get_cross_platform_hardware_id
from app.engine.license_manager import license_manager
hwid = get_cross_platform_hardware_id()
print(f'[+] Detected macOS Hardware ID: {hwid}')
info = license_manager.get_license_info()
print(f'[+] Customer Name             : {info.get(\"customer_name\")}')
print(f'[+] Allowed Camera Capacity   : {info.get(\"max_cameras\")} channels')
"

# 5. Provision macOS LaunchDaemon
echo ""
echo "[5/6] PROVISIONING LAUNCHDAEMON: com.visionxr.engine.plist..."
PLIST_PATH="/Library/LaunchDaemons/com.visionxr.engine.plist"
sudo tee "${PLIST_PATH}" > /dev/null <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.visionxr.engine</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${INSTALL_DIR}/app/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>VISIONXR_STORAGE_PATH</key>
        <string>${STORAGE_PATH}</string>
        <key>VISIONXR_COMPANY_NAME</key>
        <string>${COMPANY_NAME}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

sudo launchctl load -w "${PLIST_PATH}" 2>/dev/null || true

# 6. Self-Deletion of Installation Package Media
echo ""
echo "[6/6] AUTO-DELETING INSTALLER MEDIA FROM DRIVE..."
MEDIA_ARCHIVE=$(find "${PACKAGE_ROOT}/.." -maxdepth 2 -name "visionxr-release*.tar.gz" -o -name "visionxr-release*.zip" 2>/dev/null || true)
if [ -n "$MEDIA_ARCHIVE" ]; then
    for f in $MEDIA_ARCHIVE; do
        rm -f "$f"
        echo "[+] Deleted installation archive: $(basename "$f")"
    done
fi

if [ "${PACKAGE_ROOT}" != "${INSTALL_DIR}" ]; then
    echo "[+] Auto-removing installer folder from drive: ${PACKAGE_ROOT}"
    rm -rf "${PACKAGE_ROOT}"
fi

echo ""
echo "========================================================================"
echo "✓ VISIONXR PRODUCTION INSTALLATION COMPLETE (macOS)!"
echo "  Storage Directory : ${STORAGE_PATH}"
echo "  Web Portal        : http://localhost:8022"
echo "========================================================================"
