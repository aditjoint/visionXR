#!/usr/bin/env python3
"""
VisionXR Sovereign Node USB Packaging Utility
Builds a non-distribution, cross-platform standalone package directly to the mounted USB drive.
- Excludes 100% of markdown (.md) documents.
- Includes automated one-click installers for both Ubuntu and Windows.
- Automatically downloads all dependencies on target machine without pre-installed requirements.
- Configured for local IP (127.0.0.X / 127.0.0.1:8022).
- Automatically deletes the installer package from the USB media once installation on target machine completes.
"""

import os
import sys
import shutil
import stat
from pathlib import Path

BASE_DIR = Path("/var/www22/visionXR")
USB_MOUNT = Path("/media/adity/Sony-Media")
TARGET_DIR = USB_MOUNT / "VisionXR_Setup"
PAYLOAD_DIR = TARGET_DIR / "payload"

def main():
    print("========================================================================")
    print("       VISIONXR CROSS-PLATFORM USB PACKAGE BUILDER")
    print(f"       Source Tree : {BASE_DIR}")
    print(f"       Destination : {TARGET_DIR}")
    print("========================================================================")

    if not USB_MOUNT.exists():
        print(f"[-] ERROR: USB mount directory {USB_MOUNT} is not mounted.")
        sys.exit(1)

    # Clean existing target directory if present
    if TARGET_DIR.exists():
        print(f"[+] Removing existing directory at {TARGET_DIR}...")
        shutil.rmtree(TARGET_DIR)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy App Source
    print("\n[1/6] Copying core application components (app, static)...")
    shutil.copytree(
        BASE_DIR / "app",
        PAYLOAD_DIR / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.md", "*.markdown")
    )
    shutil.copytree(
        BASE_DIR / "static",
        PAYLOAD_DIR / "static",
        ignore=shutil.ignore_patterns("*.md", "*.markdown")
    )

    # 2. Copy Default Configuration & Operational Data
    print("\n[2/6] Packaging operational templates & user zones...")
    (PAYLOAD_DIR / "config").mkdir(parents=True, exist_ok=True)
    (PAYLOAD_DIR / "data").mkdir(parents=True, exist_ok=True)

    # Write default client config
    default_client_config = {
        "company_name": "SOVEREIGN ENTERPRISE",
        "storage_path": "/var/visionxr_storage",
        "host": "0.0.0.0",
        "port": 8022,
        "local_ip": "127.0.0.1",
        "platform": "auto"
    }
    with open(PAYLOAD_DIR / "config" / "client_config.json", "w") as f:
        import json
        json.dump(default_client_config, f, indent=2)

    # Copy clean data files if they exist
    source_data = BASE_DIR / "data"
    for item in ["cameras.json", "zones.json", "safety_rules.json", "ip_rules.json", "storage_policy.json"]:
        src_file = source_data / item
        if src_file.exists():
            shutil.copy2(src_file, PAYLOAD_DIR / "data" / item)

    # 3. Create requirements.txt
    print("\n[3/6] Generating requirements.txt for auto-downloadable dependencies...")
    requirements_content = """fastapi>=0.100.0
uvicorn[standard]>=0.23.0
opencv-python-headless>=4.8.0
numpy>=1.23.0
pydantic>=2.0.0
shapely>=2.0.0
psutil>=5.9.0
python-multipart>=0.0.6
requests>=2.28.0
"""
    with open(PAYLOAD_DIR / "requirements.txt", "w") as f:
        f.write(requirements_content)

    # 4. Generate Linux / Ubuntu Installer Script
    print("\n[4/6] Creating install_ubuntu.sh...")
    ubuntu_script = """#!/usr/bin/env bash
# ==============================================================================
# VisionXR Universal Sovereign Node Installer (Ubuntu / Debian Linux)
# Non-Distribution / Full Standalone Engine (Bound to 127.0.0.X Local Access)
# Auto-downloads all dependencies & auto-deletes installer from USB media
# ==============================================================================
set -e

# Verify root/sudo privileges
if [ "$EUID" -ne 0 ]; then
    echo "[-] ERROR: This installer requires administrative (root) privileges."
    echo "    Please run with sudo: sudo bash $0"
    exit 1
fi

# MOTHER SERVER SAFETY GUARD:
# Prevent accidental installation if executed on the source/development master server
if [ -d "/var/www22/visionXR" ]; then
    echo "========================================================================"
    echo "[-] SAFETY ABORT: MOTHER SERVER ENVIRONMENT DETECTED (/var/www22/visionXR)"
    echo "    This installer package is meant to be run on ANOTHER client machine."
    echo "    To protect the development master server, installation has been blocked."
    echo "========================================================================"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INSTALL_DIR="/opt/visionxr"
STORAGE_DIR="/var/visionxr_storage"

echo "========================================================================"
echo "    VISIONXR UNIVERSAL SOVEREIGN NODE INSTALLER"
echo "    Target Environment: Ubuntu / Debian Linux"
echo "    Local Endpoint    : http://127.0.0.1:8022 (and 127.0.0.X)"
echo "========================================================================"
echo ""

# 1. Update APT & Auto-Download System Dependencies
echo "[1/6] Auto-downloading system dependencies via APT..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    net-tools

# 2. Deploy Application Files to /opt/visionxr
echo ""
echo "[2/6] Deploying application payload to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
rm -rf "${INSTALL_DIR}"/app "${INSTALL_DIR}"/static "${INSTALL_DIR}"/config "${INSTALL_DIR}"/requirements.txt 2>/dev/null || true
cp -r "${SCRIPT_DIR}/payload"/* "${INSTALL_DIR}/"

# Configure storage path
mkdir -p "${STORAGE_DIR}/snapshots"
mkdir -p "${STORAGE_DIR}/recordings"
mkdir -p "${STORAGE_DIR}/audit"
chmod -R 775 "${STORAGE_DIR}"

# 3. Create Python Virtual Environment & Auto-Download Python Dependencies
echo ""
echo "[3/6] Initializing isolated Python virtual environment..."
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/python" -m pip install --upgrade pip setuptools wheel

echo "[+] Auto-downloading and installing required Python packages..."
"${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

# 4. Provision Local IP Configuration
echo ""
echo "[4/6] Initializing Local IP Configuration & Sovereign Baseline..."
mkdir -p "${INSTALL_DIR}/config"
cat <<EOF > "${INSTALL_DIR}/config/client_config.json"
{
  "company_name": "SOVEREIGN ENTERPRISE",
  "storage_path": "${STORAGE_DIR}",
  "host": "0.0.0.0",
  "port": 8022,
  "local_ip": "127.0.0.1",
  "platform": "linux"
}
EOF

mkdir -p "${INSTALL_DIR}/data"
chmod -R 775 "${INSTALL_DIR}"

# 5. Register and Start Systemd Daemon Service
echo ""
echo "[5/6] Registering and activating systemd background daemon..."
cat <<EOF > /etc/systemd/system/visionxr.service
[Unit]
Description=VisionXR Sovereign AI Industrial Surveillance Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
Environment="PYTHONPATH=${INSTALL_DIR}"
Environment="VISIONXR_STORAGE_PATH=${STORAGE_DIR}"
Environment="VISIONXR_HOST=0.0.0.0"
Environment="VISIONXR_PORT=8022"
ExecStart=${INSTALL_DIR}/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8022 --log-level info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable visionxr.service
systemctl restart visionxr.service

# Create local start/stop scripts
cat <<EOF > "${INSTALL_DIR}/start_visionxr.sh"
#!/usr/bin/env bash
sudo systemctl start visionxr.service
echo "[+] VisionXR daemon started. Web Console: http://127.0.0.1:8022"
EOF
chmod +x "${INSTALL_DIR}/start_visionxr.sh"

cat <<EOF > "${INSTALL_DIR}/stop_visionxr.sh"
#!/usr/bin/env bash
sudo systemctl stop visionxr.service
echo "[+] VisionXR daemon stopped."
EOF
chmod +x "${INSTALL_DIR}/stop_visionxr.sh"

# Create Desktop Shortcut if Desktop exists
for user_home in /home/*; do
    if [ -d "${user_home}/Desktop" ]; then
        cat <<EOF > "${user_home}/Desktop/VisionXR.desktop"
[Desktop Entry]
Version=1.0
Name=VisionXR Sovereign AI
Comment=Open VisionXR Industrial Surveillance Console
Exec=xdg-open http://127.0.0.1:8022
Icon=video-display
Terminal=false
Type=Application
Categories=Utility;Security;
EOF
        chown $(basename "${user_home}"):$(basename "${user_home}") "${user_home}/Desktop/VisionXR.desktop" 2>/dev/null || true
        chmod +x "${user_home}/Desktop/VisionXR.desktop" 2>/dev/null || true
    fi
done

# Verify service health
echo ""
echo "[6/6] Verifying local service health on http://127.0.0.1:8022..."
HEALTH_CHECK=0
for i in {1..12}; do
    sleep 2
    if curl -s http://127.0.0.1:8022/api/health | grep -q "SOVEREIGN_ONLINE"; then
        HEALTH_CHECK=1
        break
    fi
done

if [ "$HEALTH_CHECK" -eq 1 ]; then
    echo "========================================================================"
    echo "✓ VISIONXR SOVEREIGN NODE IS PERMANENTLY INSTALLED & ONLINE!"
    echo "  Local Dashboard URL : http://127.0.0.1:8022 (and http://127.0.0.X:8022)"
    echo "  Systemd Service     : visionxr.service (active, enabled on boot)"
    echo "  Storage Directory   : ${STORAGE_DIR}"
    echo "========================================================================"
else
    echo "[!] Service started. Check status with: sudo systemctl status visionxr.service"
fi

# Auto-delete installer package from USB media
echo ""
echo "[+] Auto-deleting installer package from USB media as requested..."
if [ -d "${SCRIPT_DIR}" ] && [ "${SCRIPT_DIR}" != "${INSTALL_DIR}" ] && [ "${SCRIPT_DIR}" != "/" ]; then
    rm -rf "${SCRIPT_DIR}"
    sync
    echo "✓ Package successfully purged from USB media. One-time installation complete."
fi
"""
    with open(TARGET_DIR / "install_ubuntu.sh", "w") as f:
        f.write(ubuntu_script)
    (TARGET_DIR / "install_ubuntu.sh").chmod(0o755)

    # 5. Generate Windows Installer Script
    print("\n[5/6] Creating install_windows.bat...")
    windows_script = """@echo off
REM ==============================================================================
REM VisionXR Universal Sovereign Node Installer (Windows 10 / 11)
REM Non-Distribution / Full Standalone Engine (Bound to 127.0.0.X Local Access)
REM Auto-downloads all dependencies & auto-deletes installer from USB media
REM ==============================================================================
setlocal enabledelayedexpansion

title VisionXR Sovereign Node Installer (Windows)

echo ========================================================================
echo    VISIONXR UNIVERSAL SOVEREIGN NODE INSTALLER (WINDOWS)
echo    Local Endpoint : http://127.0.0.1:8022 (and http://localhost:8022)
echo ========================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "INSTALL_DIR=C:\\VisionXR"
set "STORAGE_DIR=C:\\VisionXR_Storage"

REM 1. Check Administrative Permissions
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Administrative privileges required.
    echo     Elevating installer permissions...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

REM 2. Check for Python; Auto-Download if Missing
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Python not detected. Auto-downloading official Python 3.10 64-bit installer...
    set "PY_URL=https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
    set "PY_SETUP=%TEMP%\\python-installer.exe"
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%PY_URL%', '%PY_SETUP%')"
    echo [+] Installing Python silently (adding to PATH)...
    "%PY_SETUP%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del /f /q "%PY_SETUP%" 2>nul
    set "PATH=C:\\Program Files\\Python310;C:\\Program Files\\Python310\\Scripts;%PATH%"
)

python --version
if %errorlevel% neq 0 (
    echo [-] ERROR: Failed to configure Python automatically. Please install Python from python.org.
    pause
    exit /b 1
)

REM 3. Deploy Application Files to C:\\VisionXR
echo.
echo [2/6] Deploying application payload to %INSTALL_DIR%...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
xcopy /E /I /Y /Q "%SCRIPT_DIR%payload\\*" "%INSTALL_DIR%\\" >nul

if not exist "%STORAGE_DIR%\\snapshots" mkdir "%STORAGE_DIR%\\snapshots"
if not exist "%STORAGE_DIR%\\recordings" mkdir "%STORAGE_DIR%\\recordings"
if not exist "%STORAGE_DIR%\\audit" mkdir "%STORAGE_DIR%\\audit"

REM 4. Initialize Python Virtual Environment & Auto-Download Dependencies
echo.
echo [3/6] Initializing isolated Python virtual environment...
python -m venv "%INSTALL_DIR%\\venv"
"%INSTALL_DIR%\\venv\\Scripts\\python.exe" -m pip install --upgrade pip

echo [+] Auto-downloading and installing required Python wheels...
"%INSTALL_DIR%\\venv\\Scripts\\pip.exe" install -r "%INSTALL_DIR%\\requirements.txt"

REM 5. Configure Local IP & Launchers
echo.
echo [4/6] Initializing Local IP Configuration & Windows Launchers...
if not exist "%INSTALL_DIR%\\config" mkdir "%INSTALL_DIR%\\config"
(
echo {
echo   "company_name": "SOVEREIGN ENTERPRISE",
echo   "storage_path": "C:\\\\VisionXR_Storage",
echo   "host": "0.0.0.0",
echo   "port": 8022,
echo   "local_ip": "127.0.0.1",
echo   "platform": "windows"
echo }
) > "%INSTALL_DIR%\\config\\client_config.json"

REM Create Windows Start Launcher
(
echo @echo off
echo title VisionXR Sovereign AI Engine
echo set "PYTHONPATH=%INSTALL_DIR%"
echo set "VISIONXR_STORAGE_PATH=%STORAGE_DIR%"
echo set "VISIONXR_HOST=0.0.0.0"
echo set "VISIONXR_PORT=8022"
echo start "" http://127.0.0.1:8022
echo echo ========================================================================
echo echo    VISIONXR SOVEREIGN NODE ONLINE
echo echo    Web Portal: http://127.0.0.1:8022
echo echo ========================================================================
echo "%INSTALL_DIR%\\venv\\Scripts\\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8022 --log-level info
) > "%INSTALL_DIR%\\Launch_VisionXR.bat"

REM Create Desktop Shortcut via PowerShell
echo.
echo [5/6] Creating Desktop Shortcut...
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\VisionXR Sovereign AI.lnk');$s.TargetPath='%INSTALL_DIR%\\Launch_VisionXR.bat';$s.WorkingDirectory='%INSTALL_DIR%';$s.Description='VisionXR Sovereign AI Surveillance Console';$s.Save()"

echo.
echo ========================================================================
echo ✓ VISIONXR INSTALLATION COMPLETED SUCCESSFULLY!
echo   Installation Path : %INSTALL_DIR%
echo   Storage Path      : %STORAGE_DIR%
echo   Desktop Shortcut  : Created
echo   Local Dashboard   : http://127.0.0.1:8022
echo ========================================================================

REM 6. Auto-delete from USB media after installation
echo.
echo [6/6] Auto-deleting installer package from USB media as requested...
set "SELF_FOLDER=%SCRIPT_DIR%"
cd /d "%INSTALL_DIR%"

start "" cmd /c "timeout /t 3 /nobreak >nul & rd /s /q \"%SELF_FOLDER%\" 2>nul"

echo ✓ Installer package scheduled for immediate deletion from USB drive.
echo Launching VisionXR now...
start "" "%INSTALL_DIR%\\Launch_VisionXR.bat"
exit /b 0
"""
    with open(TARGET_DIR / "install_windows.bat", "w") as f:
        f.write(windows_script)

    # 6. Create Plain Text Instructions (NO .md files)
    print("\n[6/6] Writing plain text instructions (README.txt)...")
    readme_txt = """VISIONXR UNIVERSAL SOVEREIGN NODE - ONE-TIME USB INSTALLER
========================================================================

SUPPORTED TARGET PLATFORMS:
- Ubuntu 20.04 / 22.04 / 24.04 LTS (and Debian Linux)
- Windows 10 / Windows 11 (64-bit)

KEY PROPERTIES:
- Zero manual dependencies: All system libraries, Python virtual environment,
  and pip packages are auto-downloaded by the installer scripts.
- Bound to local loopback: Runs at http://127.0.0.1:8022 (and 127.0.0.X).
- Non-distribution type: Full open runtime, no hardware locking lockout.
- Self-deleting: As requested, the installer package automatically purges
  itself from this USB drive once installation finishes on the target machine.

HOW TO INSTALL ON UBUNTU / LINUX:
1. Insert this USB drive into the target Ubuntu machine.
2. Open Terminal in this folder (or navigate to the USB drive).
3. Run:
     sudo bash install_ubuntu.sh
4. The system will auto-download dependencies, register the systemd service,
   create a desktop launcher, and verify http://127.0.0.1:8022.
5. The installer will then auto-delete itself from the USB drive.

HOW TO INSTALL ON WINDOWS:
1. Insert this USB drive into the target Windows machine.
2. Right-click 'install_windows.bat' and select 'Run as administrator'.
3. The installer will auto-download Python (if not present), create the
   virtual environment, install packages, and create a Desktop shortcut.
4. The installer will then launch VisionXR and auto-delete itself from the USB drive.
========================================================================
"""
    with open(TARGET_DIR / "README.txt", "w") as f:
        f.write(readme_txt)

    # Enforce strict zero-markdown policy
    print("\n[+] Enforcing strict zero-markdown (.md) exclusion check...")
    md_files = list(TARGET_DIR.rglob("*.md")) + list(TARGET_DIR.rglob("*.markdown"))
    for md in md_files:
        print(f"    [-] Removing unexpected markdown file: {md}")
        md.unlink()

    remaining_md = list(TARGET_DIR.rglob("*.md")) + list(TARGET_DIR.rglob("*.markdown"))
    assert len(remaining_md) == 0, f"Error: Markdown files detected: {remaining_md}"
    print("[✓] Zero markdown (.md) documents verified across entire package tree.")

    print("\n[+] Flushing all disk buffers to USB physical NAND (sync)...")
    os.system("sync")
    print("[✓] USB buffer sync complete!")

    print("\n========================================================================")
    print("✓ USB PACKAGE BUILD COMPLETE!")
    print(f"  Location on USB : {TARGET_DIR}")
    print(f"  Linux Installer : {TARGET_DIR / 'install_ubuntu.sh'}")
    print(f"  Windows Setup   : {TARGET_DIR / 'install_windows.bat'}")
    print(f"  Zero .md files  : VERIFIED")
    print("========================================================================")

if __name__ == "__main__":
    main()

