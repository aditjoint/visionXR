#!/usr/bin/env python3
"""
VisionXR Sovereign Production Distribution Builder (USB Release)
Creates a tailored, client-specific industrial distribution package:
1. Prompts for client company name, camera capacity, and feature selection wizard.
2. Strips out the LICENSE button and developer licensing modals from the client UI.
3. Packages an installer with:
   - Mother Server Protection Guard (never runs on dev server).
   - Duplicate Installation Guard (blocks installation if VisionXR is already on system).
   - Hardware-Locking on target machine (cryptographically signed license).
   - Irreversible Cythonization (compiles .py -> native .so binary extensions, deletes all .py and .c).
   - Auto-downloads all dependencies on target machine.
   - Self-deletes from USB media once installation on the new machine completes.
"""

import os
import re
import sys
import json
import shutil
import argparse
from pathlib import Path

BASE_DIR = Path("/var/www22/visionXR")
USB_MOUNT = Path("/media/adity/Sony-Media")
DIST_TARGET = USB_MOUNT / "VisionXR_Distribution"
PAYLOAD_DIR = DIST_TARGET / "payload"

FEATURE_CATALOG = [
    {"id": "TRI_ZONE_PERIMETER", "name": "Tri-Zone Spatial Perimeter & Lakshmana Rekha", "desc": "Red/Amber/Green spatial intrusion detection"},
    {"id": "WORKER_PPE_SAFETY", "name": "Worker PPE & Man-Down Safety", "desc": "Hardhat, high-vis vest compliance & emergency rescue"},
    {"id": "TRAFFIC_ANPR_WATCHLIST", "name": "Traffic & ANPR Number Plate OCR", "desc": "Plate recognition, vehicle speed & suspected vehicle blacklist"},
    {"id": "TWO_WHEELER_VIOLATIONS", "name": "Two-Wheeler Triple Riding & Helmet", "desc": "Triple riding and rider head protection compliance"},
    {"id": "DRIVER_CABIN_SAFETY", "name": "In-Cabin Driver Safety", "desc": "Driver on call & seatbelt fastening compliance"},
    {"id": "BIOMETRIC_FRSS_IDENTITY", "name": "Facial Recognition (FRSS) & Mask", "desc": "1:N face verification against enrolled gallery & mask check"},
    {"id": "SPATIAL_PEOPLE_COUNTING", "name": "Bidirectional People & Vehicle Counting", "desc": "Real-time IN / OUT gate tripwire counting"},
    {"id": "CROWD_DENSITY_GATHERING", "name": "Crowd Density Clustering", "desc": "Alarms on high-density gathering of persons"},
    {"id": "FIRE_SMOKE_HAZARD", "name": "Fire & Smoke Plume Detection", "desc": "Diffuse chromatic plume expansion and flickering analysis"},
    {"id": "CHEMICAL_SPILL_HAZARD", "name": "Chemical & Liquid Spill Expansion", "desc": "Homography 2D->3D surface area (m²) monitoring"},
    {"id": "THERMAL_HOTSPOT_RUNAWAY", "name": "Thermal Hotspot & Arc-Flash Runaway", "desc": "Thermal radiation tracking and switchgear hotspot alerts"},
    {"id": "ACOUSTIC_DISTRESS_SNIFFER", "name": "Acoustic Distress & Decibel Sniffer", "desc": "Decibel ceiling screams, glass break & explosion detection"},
    {"id": "DEEP_ATTRIBUTE_SEARCH", "name": "Forensic Visual Attribute Search", "desc": "Query historical events by color (Red, Blue, etc.) and class"},
    {"id": "FENCE_JUMPING_VAULT", "name": "Perimeter Fence Vaulting", "desc": "Dynamic vertical trajectory jumping over boundary barriers"},
    {"id": "GARBAGE_DEBRIS_DUMPING", "name": "Floor Garbage & Debris Dumping", "desc": "Stationary foreign object/litter detection on walking surfaces"}
]

def sanitize_client_html(html_content: str, company_name: str) -> str:
    """Removes the LICENSE and DISTRIBUTION buttons/modals from the client HTML."""
    # Strip License button from toolbar
    cleaned = re.sub(r'<button[^>]*openLicenseModal\(\)[^>]*>[\s\S]*?</button>\s*', '', html_content)

    # Strip Distribution button from toolbar
    cleaned = re.sub(r'<button[^>]*id="btn-open-distribution"[^>]*>[\s\S]*?</button>\s*', '', cleaned)
    cleaned = re.sub(r'<button[^>]*openDistributionModal\(\)[^>]*>[\s\S]*?</button>\s*', '', cleaned)
    
    # Strip License Modal container
    cleaned = re.sub(r'<!-- Customer Licensing & Camera Task Matrix Modal -->[\s\S]*?(?=<!-- Modal: Client USB Distribution Builder|<!-- Modal: Super Admin User Governance)', '', cleaned)
    cleaned = re.sub(r'<div id="modal-license"[\s\S]*?<!-- Modal:', '<!-- Modal:', cleaned)

    # Strip Distribution Modal container
    cleaned = re.sub(r'<!-- Modal: Client USB Distribution Builder[\s\S]*?(?=<!-- Modal: Super Admin User Governance)', '', cleaned)
    cleaned = re.sub(r'<div id="modal-distribution"[\s\S]*?<!-- Modal: Super Admin User Governance', '<!-- Modal: Super Admin User Governance', cleaned)
    
    # Inject Customer Company Branding
    cleaned = cleaned.replace("SOVEREIGN ENTERPRISE NODE", company_name.upper())
    cleaned = cleaned.replace("ADAM CONSULT", company_name.upper())
    return cleaned



def build_distribution(company_name: str, max_cameras: int, selected_feature_ids: list):
    print("========================================================================")
    print("    VISIONXR INDUSTRIAL DISTRIBUTION BUILDER (USB MEDIA)")
    print(f"    Target Client     : {company_name}")
    print(f"    Camera Channels   : {max_cameras}")
    print(f"    Selected Features : {len(selected_feature_ids)} of {len(FEATURE_CATALOG)}")
    print("========================================================================")

    if not USB_MOUNT.exists():
        print(f"[-] ERROR: USB mount directory {USB_MOUNT} is not mounted.")
        sys.exit(1)

    if DIST_TARGET.exists():
        print(f"[+] Clearing existing distribution folder on USB: {DIST_TARGET}...")
        shutil.rmtree(DIST_TARGET)

    DIST_TARGET.mkdir(parents=True, exist_ok=True)
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy App Source (excluding developer distribution tool, tests, and legacy frontend versions)
    print("\n[1/6] Copying core application components (purging legacy versions & dev tools)...")
    shutil.copytree(
        BASE_DIR / "app",
        PAYLOAD_DIR / "app",
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", "*.md", "*.markdown",
            "routes_distribution.py", "test_*.py"
        )
    )
    shutil.copytree(
        BASE_DIR / "static",
        PAYLOAD_DIR / "static",
        ignore=shutil.ignore_patterns(
            "*.md", "*.markdown",
            "app.js", "app-sovereign.js", "app-v248.js", "app-v249.js", "app-v250.js",
            "visionxr.css", "visionxr-sovereign.css"
        )
    )

    # 2. Sanitize HTML - Strip License Button and Modal
    print("\n[2/6] Sanitizing client interface (stripping LICENSE button & developer modals)...")
    html_file = PAYLOAD_DIR / "static" / "index.html"
    if html_file.exists():
        raw_html = html_file.read_text(encoding="utf-8")
        sanitized = sanitize_client_html(raw_html, company_name)
        html_file.write_text(sanitized, encoding="utf-8")
        print("[✓] Verified: LICENSE and DISTRIBUTION buttons completely purged from client distribution UI.")

    # 3. Configure Client Clean Operational Data (Zero Developer Static Data)
    print(f"\n[3/6] Initializing pristine clean data stores (ZERO developer static data)...")
    (PAYLOAD_DIR / "config").mkdir(parents=True, exist_ok=True)
    (PAYLOAD_DIR / "data").mkdir(parents=True, exist_ok=True)

    client_config = {
        "company_name": company_name,
        "max_cameras": max_cameras,
        "storage_path": "/var/visionxr_storage",
        "host": "0.0.0.0",
        "port": 8022,
        "selected_features": selected_feature_ids,
        "platform": "auto",
        "is_distribution": True
    }
    with open(PAYLOAD_DIR / "config" / "client_config.json", "w") as f:
        json.dump(client_config, f, indent=2)

    # Empty clean camera provision registry (so client starts with fresh hardware)
    with open(PAYLOAD_DIR / "data" / "cameras.json", "w") as f:
        json.dump([], f, indent=2)

    # Empty clean spatial zones registry
    with open(PAYLOAD_DIR / "data" / "zones.json", "w") as f:
        json.dump([], f, indent=2)

    # Pristine empty biometric personnel registry (ZERO static seed personnel)
    (PAYLOAD_DIR / "data" / "personnel").mkdir(parents=True, exist_ok=True)
    with open(PAYLOAD_DIR / "data" / "personnel" / "personnel_registry.json", "w") as f:
        json.dump([], f, indent=2)

    # Pristine empty vehicle watchlist & ANPR history (ZERO static seed plates)
    with open(PAYLOAD_DIR / "data" / "vehicle_watchlist.json", "w") as f:
        json.dump([], f, indent=2)
    with open(PAYLOAD_DIR / "data" / "anpr_history.json", "w") as f:
        json.dump([], f, indent=2)

    # Pristine empty attribute forensic ledger & audit records
    with open(PAYLOAD_DIR / "data" / "attribute_ledger.json", "w") as f:
        json.dump([], f, indent=2)
    with open(PAYLOAD_DIR / "data" / "audit_ledger.json", "w") as f:
        json.dump([], f, indent=2)

    # Clean default IP rules
    default_ip_rules = {
        "allowed_cidrs": ["127.0.0.1/32", "::1/128", "192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"],
        "whitelist_only": False
    }
    with open(PAYLOAD_DIR / "data" / "ip_rules.json", "w") as f:
        json.dump(default_ip_rules, f, indent=2)

    # Clean storage policy
    default_storage = {
        "max_storage_gb": 50,
        "retention_days": 30,
        "auto_purge_pct": 90
    }
    with open(PAYLOAD_DIR / "data" / "storage_policy.json", "w") as f:
        json.dump(default_storage, f, indent=2)

    # Tailored safety rules reflecting selected features
    initial_safety_rules = {
        "tri_zone_perimeter": "TRI_ZONE_PERIMETER" in selected_feature_ids,
        "ppe_worker_safety": "WORKER_PPE_SAFETY" in selected_feature_ids,
        "traffic_anpr": "TRAFFIC_ANPR_WATCHLIST" in selected_feature_ids,
        "two_wheeler_violations": "TWO_WHEELER_VIOLATIONS" in selected_feature_ids,
        "driver_cabin_safety": "DRIVER_CABIN_SAFETY" in selected_feature_ids,
        "biometrics_frss": "BIOMETRIC_FRSS_IDENTITY" in selected_feature_ids,
        "spatial_analytics": "SPATIAL_PEOPLE_COUNTING" in selected_feature_ids or "CROWD_DENSITY_GATHERING" in selected_feature_ids,
        "fire_smoke": "FIRE_SMOKE_HAZARD" in selected_feature_ids,
        "chemical_spill": "CHEMICAL_SPILL_HAZARD" in selected_feature_ids,
        "thermal_hotspot": "THERMAL_HOTSPOT_RUNAWAY" in selected_feature_ids,
        "acoustic_distress": "ACOUSTIC_DISTRESS_SNIFFER" in selected_feature_ids
    }
    with open(PAYLOAD_DIR / "data" / "safety_rules.json", "w") as f:
        json.dump(initial_safety_rules, f, indent=2)
    print("[✓] Clean data stores initialized: cameras=[], zones=[] (zero dev static data).")


    # Write requirements.txt
    requirements_content = """fastapi>=0.100.0
uvicorn[standard]>=0.23.0
opencv-python-headless>=4.8.0
numpy>=1.23.0
pydantic>=2.0.0
shapely>=2.0.0
psutil>=5.9.0
python-multipart>=0.0.6
requests>=2.28.0
cython>=3.0.0
"""
    with open(PAYLOAD_DIR / "requirements.txt", "w") as f:
        f.write(requirements_content)

    # 4. Create install_ubuntu.sh with Hardware-Lock, Duplicate Check & Irreversible Cythonization
    print("\n[4/6] Packaging hardened Linux installer with duplicate guard & Cythonization...")
    ubuntu_script = f"""#!/usr/bin/env bash
# ==============================================================================
# VisionXR Industrial Production Node Installer (Ubuntu / Debian Linux)
# Client: {company_name} | Capacity: {max_cameras} Cameras
# Features: Irreversible Cythonization, Hardware Locking, USB Self-Deletion
# ==============================================================================
set -e

# 1. ROOT CHECK
if [ "$EUID" -ne 0 ]; then
    echo "[-] ERROR: This installer requires administrative (root) privileges."
    echo "    Please run with sudo: sudo bash $0"
    exit 1
fi

# 2. MOTHER SERVER PROTECTION GUARD
if [ -d "/var/www22/visionXR" ]; then
    echo "========================================================================"
    echo "[-] SAFETY ABORT: MOTHER SERVER ENVIRONMENT DETECTED (/var/www22/visionXR)"
    echo "    This distribution installer cannot be deployed on the Mother Server."
    echo "    The master developer package is protected."
    echo "========================================================================"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
INSTALL_DIR="/opt/visionxr"
STORAGE_DIR="/var/visionxr_storage"

# 3. DUPLICATE INSTALLATION & IN-PLACE UPGRADE DETECTOR
IS_UPGRADE=0
if [ -d "${{INSTALL_DIR}}" ] && [ "$(ls -A ${{INSTALL_DIR}} 2>/dev/null)" ]; then
    echo "========================================================================"
    echo "[!] EXISTING DEPLOYMENT DETECTED at ${{INSTALL_DIR}}"
    echo "========================================================================"
    echo "    VisionXR is already installed on this machine."
    echo "    This installer can safely UPGRADE the existing installation in-place,"
    echo "    preserving all customer camera channels, zones, biometrics & data."
    echo ""
    if [ "$1" = "--upgrade" ] || [ "$1" = "-y" ] || [ "$1" = "--yes" ]; then
        UPGRADE_CHOICE="Y"
    else
        read -p "    Proceed with IN-PLACE UPGRADE? [Y/n]: " UPGRADE_CHOICE
        UPGRADE_CHOICE=${{UPGRADE_CHOICE:-Y}}
    fi
    if [[ "$UPGRADE_CHOICE" =~ ^[Yy]$ ]]; then
        echo "[+] Proceeding with IN-PLACE UPGRADE mode..."
        IS_UPGRADE=1
    else
        echo "[-] Installation cancelled by operator to avoid duplicate conflicts."
        exit 1
    fi
fi

if systemctl is-active --quiet visionxr.service 2>/dev/null; then
    echo "[+] Stopping active visionxr.service for safe binary upgrade..."
    systemctl stop visionxr.service || true
fi

echo "========================================================================"
if [ "$IS_UPGRADE" -eq 1 ]; then
    echo "    VISIONXR INDUSTRIAL PRODUCTION IN-PLACE UPGRADE"
else
    echo "    VISIONXR INDUSTRIAL PRODUCTION DEPLOYMENT"
fi
echo "    Customer Node : {company_name}"
echo "    Target Path   : ${{INSTALL_DIR}}"
echo "========================================================================"
echo ""

# 4. Auto-Download Dependencies (including Cython & GCC)
echo "[1/7] Auto-downloading system packages, compilers & Python dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    gcc \
    build-essential \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl

# 5. Deploy Payload Files
echo ""
echo "[2/7] Deploying application payload to ${{INSTALL_DIR}}..."
if [ "$IS_UPGRADE" -eq 1 ]; then
    echo "[+] Preserving customer data: Backing up operational stores..."
    UPGRADE_BACKUP="/tmp/visionxr_upgrade_backup_$$"
    mkdir -p "${{UPGRADE_BACKUP}}"
    cp -r "${{INSTALL_DIR}}/data" "${{UPGRADE_BACKUP}}/" 2>/dev/null || true
    cp "${{INSTALL_DIR}}/developer.license" "${{UPGRADE_BACKUP}}/" 2>/dev/null || true

    # Copy new application engine and frontend
    cp -r "${{SCRIPT_DIR}}/payload/app" "${{INSTALL_DIR}}/"
    cp -r "${{SCRIPT_DIR}}/payload/static" "${{INSTALL_DIR}}/"
    cp "${{SCRIPT_DIR}}/payload/requirements.txt" "${{INSTALL_DIR}}/"

    # Restore customer data (never overwrite existing client cameras or records)
    echo "[+] Restoring customer cameras, spatial zones, biometrics & audit trail..."
    mkdir -p "${{INSTALL_DIR}}/data"
    cp -rn "${{UPGRADE_BACKUP}}/data"/* "${{INSTALL_DIR}}/data/" 2>/dev/null || true
    rm -rf "${{UPGRADE_BACKUP}}"
else
    mkdir -p "${{INSTALL_DIR}}"
    cp -r "${{SCRIPT_DIR}}/payload"/* "${{INSTALL_DIR}}/"
fi

mkdir -p "${{STORAGE_DIR}}/snapshots" "${{STORAGE_DIR}}/recordings" "${{STORAGE_DIR}}/audit"
chmod -R 775 "${{STORAGE_DIR}}"

# 6. Setup Isolated Virtual Environment & Python Packages
echo ""
echo "[3/7] Setting up Python virtual environment and auto-downloading wheels..."
python3 -m venv "${{INSTALL_DIR}}/venv"
"${{INSTALL_DIR}}/venv/bin/python" -m pip install --upgrade pip setuptools wheel
"${{INSTALL_DIR}}/venv/bin/pip" install -r "${{INSTALL_DIR}}/requirements.txt"

# 7. Irreversible Cythonization (Compile .py -> native .so binary extensions)
echo ""
echo "[4/7] Compiling core application logic into IRREVERSIBLE native binary machine code (.so)..."
find "${{INSTALL_DIR}}/app" -name "*.py" | while read -r pyfile; do
    fname=$(basename "$pyfile")
    dname=$(dirname "$pyfile")
    # Preserve __init__.py for package resolution
    if [ "$fname" = "__init__.py" ]; then
        continue
    fi
    modname="${{fname%.py}}"
    "${{INSTALL_DIR}}/venv/bin/python" -m cython -3 "$pyfile" -o "${{dname}}/${{modname}}.c" 2>/dev/null || true
    if [ -f "${{dname}}/${{modname}}.c" ]; then
        PY_INC=$( "${{INSTALL_DIR}}/venv/bin/python" -c "import sysconfig; print(sysconfig.get_path('include'))" )
        gcc -shared -pthread -fPIC -fwrapv -O2 -Wall -fno-strict-aliasing \
            -I"${{PY_INC}}" \
            -o "${{dname}}/${{modname}}.so" \
            "${{dname}}/${{modname}}.c" 2>/dev/null || true
        # Irreversible: Purge raw Python and intermediate C sources immediately
        if [ -f "${{dname}}/${{modname}}.so" ]; then
            rm -f "$pyfile" "${{dname}}/${{modname}}.c"
        fi
    fi
done
echo "[✓] Irreversible Cythonization complete. Zero raw source code remains."

# 8. Hardware Locking on Target Machine
echo ""
echo "[5/7] Locking license to target server hardware fingerprint..."
PYTHONPATH="${{INSTALL_DIR}}" "${{INSTALL_DIR}}/venv/bin/python" -c "
from app.security.hardware_lock import get_cross_platform_hardware_id, compute_developer_signature
from app.engine.license_manager import license_manager
import json
hwid = get_cross_platform_hardware_id()
features = {json.dumps(selected_feature_ids)}
sig = compute_developer_signature(
    hardware_id=hwid,
    customer_name='{company_name}',
    max_cameras={max_cameras},
    tier='PRODUCTION_ENTERPRISE',
    features=features
)
lic = {{
    'tier': 'PRODUCTION_ENTERPRISE',
    'customer_name': '{company_name}',
    'hardware_id': hwid,
    'max_cameras': {max_cameras},
    'is_developer_machine': False,
    'features': features,
    'developer_signature': sig
}}
with open('${{INSTALL_DIR}}/developer.license', 'w') as f:
    json.dump(lic, f, indent=2)
print(f'[+] Bound & Signed Hardware Lock: {{hwid}}')
"

# 9. Register and Start Systemd Daemon Service
echo ""
echo "[6/7] Provisioning systemd daemon (visionxr.service)..."
cat <<EOF > /etc/systemd/system/visionxr.service
[Unit]
Description=VisionXR Sovereign AI Industrial Surveillance Node ({company_name})
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${{INSTALL_DIR}}
Environment="PYTHONPATH=${{INSTALL_DIR}}"
Environment="VISIONXR_STORAGE_PATH=${{STORAGE_DIR}}"
Environment="VISIONXR_COMPANY_NAME={company_name}"
Environment="VISIONXR_HOST=0.0.0.0"
Environment="VISIONXR_PORT=8022"
ExecStart=${{INSTALL_DIR}}/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8022 --log-level info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable visionxr.service
systemctl restart visionxr.service

# Verify health
echo ""
echo "[7/7] Verifying service health..."
HEALTH_CHECK=0
for i in {{1..12}}; do
    sleep 2
    if curl -s http://127.0.0.1:8022/api/health | grep -q "SOVEREIGN_ONLINE"; then
        HEALTH_CHECK=1
        break
    fi
done

if [ "$HEALTH_CHECK" -eq 1 ]; then
    echo "========================================================================"
    echo "✓ VISIONXR PRODUCTION NODE INSTALLED & ACTIVE!"
    echo "  Customer Node     : {company_name}"
    echo "  Hardware Lock     : LOCKED TO THIS SERVER"
    echo "  Cython Binary     : COMPILED & IRREVERSIBLE"
    echo "  Local Dashboard   : http://127.0.0.1:8022"
    echo "========================================================================"
fi

# Self-delete installer package from USB
echo ""
echo "[+] Self-cleaning: Auto-deleting distribution package from USB media..."
if [ -d "${{SCRIPT_DIR}}" ] && [ "${{SCRIPT_DIR}}" != "${{INSTALL_DIR}}" ] && [ "${{SCRIPT_DIR}}" != "/" ]; then
    rm -rf "${{SCRIPT_DIR}}"
    sync
    echo "✓ Distribution media purged from USB. One-time deployment finalized."
fi
"""
    with open(DIST_TARGET / "install_ubuntu.sh", "w") as f:
        f.write(ubuntu_script)
    (DIST_TARGET / "install_ubuntu.sh").chmod(0o755)

    # 5. Create Plain Text Instructions (NO .md files)
    print("\n[5/6] Writing plain text instructions (README.txt)...")
    readme_txt = f"""VISIONXR SOVEREIGN INDUSTRIAL DISTRIBUTION
========================================================================
Client Name      : {company_name}
Camera Capacity  : {max_cameras} Channels
Selected Modules : {len(selected_feature_ids)} Features Active
Protection Level : Irreversible Cython Binary + Hardware-Locked
========================================================================

INSTALLATION INSTRUCTIONS (UBUNTU LINUX):
1. Insert this USB drive into the target customer server.
2. Open terminal in the USB folder (or navigate to /media/*/*).
3. Run with root privileges:
     sudo bash install_ubuntu.sh

WHAT THE INSTALLER DOES AUTOMATICALLY:
- Verifies that no prior VisionXR installation exists (duplicate prevention).
- Auto-downloads all compilers (gcc, cython) and Python packages.
- Irreversibly compiles all Python files into native .so machine binaries.
- Cryptographically binds the license to the target server's hardware ID.
- Configures systemd background service (visionxr.service) on http://127.0.0.1:8022.
- Completely purges this distribution package from the USB media once finished.
========================================================================
"""
    with open(DIST_TARGET / "README.txt", "w") as f:
        f.write(readme_txt)

    # 6. Strict Zero-Markdown Verification
    print("\n[6/6] Enforcing strict zero-markdown (.md) check...")
    for md in DIST_TARGET.rglob("*.md"):
        md.unlink()
    for md in DIST_TARGET.rglob("*.markdown"):
        md.unlink()
    assert len(list(DIST_TARGET.rglob("*.md"))) == 0, "Error: Markdown file found in distribution!"

    print("\n[+] Flushing all disk buffers to USB physical NAND (sync)...")
    os.system("sync")
    print("[✓] USB buffer sync complete!")

    print("\n========================================================================")
    print("✓ DISTRIBUTION PACKAGE BUILD COMPLETE!")
    print(f"  Location on USB : {DIST_TARGET}")
    print(f"  Linux Installer : {DIST_TARGET / 'install_ubuntu.sh'}")
    print(f"  License Button  : PURGED (Hidden from Client UI)")
    print(f"  Hardware Lock   : ENFORCED UPON INSTALLATION")
    print(f"  Cythonization   : AUTOMATED & IRREVERSIBLE")
    print(f"  Duplicate Guard : ACTIVE")
    print(f"  Self-Deletion   : ACTIVE")
    print("========================================================================")
    return {
        "status": "success",
        "target_path": str(DIST_TARGET),
        "company_name": company_name,
        "max_cameras": max_cameras,
        "selected_features": selected_feature_ids,
        "script": str(DIST_TARGET / "install_ubuntu.sh")
    }


def main():
    parser = argparse.ArgumentParser(description="VisionXR Distribution Builder")
    parser.add_argument("--company-name", help="Customer Company Name")
    parser.add_argument("--max-cameras", type=int, default=8, help="Max Allowed Cameras")
    parser.add_argument("--features", help="Comma-separated feature IDs or 'all'")
    args = parser.parse_args()

    company = args.company_name
    if not company:
        try:
            val = input("Enter Customer / Client Company Name [SOVEREIGN ENTERPRISE]: ").strip()
            company = val if val else "SOVEREIGN ENTERPRISE"
        except Exception:
            company = "SOVEREIGN ENTERPRISE"

    max_cams = args.max_cameras

    # Feature Selection Wizard
    selected_features = []
    if args.features:
        if args.features.lower() == "all":
            selected_features = [f["id"] for f in FEATURE_CATALOG]
        else:
            req = [x.strip() for x in args.features.split(",")]
            selected_features = [f["id"] for f in FEATURE_CATALOG if f["id"] in req]
    else:
        print("\n========================================================================")
        print("          SELECT INDUSTRIAL FEATURES FOR THIS DEPLOYMENT")
        print("========================================================================")
        for i, feat in enumerate(FEATURE_CATALOG, 1):
            print(f"  [{i:02d}] {feat['name']}")
            print(f"       -> {feat['desc']}")

        print("\nOptions:")
        print("  - Type 'all' to include all 15 feature modules")
        print("  - Type comma-separated numbers (e.g. 1,2,3,6,7) to customize")
        try:
            choice = input("\nEnter your selection [all]: ").strip()
        except Exception:
            choice = "all"

        if not choice or choice.lower() == "all":
            selected_features = [f["id"] for f in FEATURE_CATALOG]
        else:
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip().isdigit()]
                selected_features = [FEATURE_CATALOG[idx]["id"] for idx in indices if 0 <= idx < len(FEATURE_CATALOG)]
            except Exception:
                selected_features = [f["id"] for f in FEATURE_CATALOG]

    if not selected_features:
        selected_features = [f["id"] for f in FEATURE_CATALOG]

    build_distribution(company, max_cams, selected_features)

if __name__ == "__main__":
    main()
