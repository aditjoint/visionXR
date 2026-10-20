import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Customer branding & configurable customer storage path
CLIENT_CONFIG_FILE = BASE_DIR / "config" / "client_config.json"
CUSTOM_STORAGE = None
CUSTOMER_COMPANY_NAME = "SOVEREIGN ENTERPRISE"

if CLIENT_CONFIG_FILE.exists():
    try:
        with open(CLIENT_CONFIG_FILE, "r") as cf:
            cdata = json.load(cf)
            CUSTOM_STORAGE = cdata.get("storage_path")
            CUSTOMER_COMPANY_NAME = cdata.get("company_name", CUSTOMER_COMPANY_NAME)
    except Exception:
        pass

CUSTOMER_COMPANY_NAME = os.getenv("VISIONXR_COMPANY_NAME", CUSTOMER_COMPANY_NAME)

# Dynamic Storage Path - configured during installation on customer server
STORAGE_DIR_ENV = os.getenv("VISIONXR_STORAGE_PATH", CUSTOM_STORAGE)
if STORAGE_DIR_ENV:
    DATA_DIR = Path(STORAGE_DIR_ENV)
else:
    DATA_DIR = BASE_DIR / "data"

SNAPSHOTS_DIR = DATA_DIR / "snapshots"
RECORDINGS_DIR = DATA_DIR / "recordings"
AUDIT_DIR = DATA_DIR / "audit"
STATIC_DIR = BASE_DIR / "static"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)

# Sovereign Network & Service Configuration
HOST = os.getenv("VISIONXR_HOST", "0.0.0.0")
PORT = int(os.getenv("VISIONXR_PORT", "8022"))
SECTOR_IP = "127.0.0.22"
DOMAIN = "visionxr.adamconsult.com"

# Escalation & Integration
WHATSAPP_TARGET = os.getenv("VISIONXR_WHATSAPP", "+91-8779639965")
OMNIGRID_DCIM_WEBHOOK = os.getenv("VISIONXR_DCIM_URL", "http://127.0.0.14:8000/api/dcim/events")

# Default Curfew Rules
DEFAULT_CURFEW = {
    "enabled": True,
    "start_hour": 20, # 8 PM
    "end_hour": 6,    # 6 AM
    "action": "CRITICAL_ALARM"
}

# Pre-configured Industrial CCTV Channels (Pure Physical Feeds)
DEFAULT_CAMERAS = [
    {
        "id": "cam_01",
        "name": "Live USB Camera #1 (Sony PS Eye)",
        "type": "usb_v4l2",
        "source": "2",
        "location": "Sector 22 - Primary Optical Workstation",
        "fps": 30,
        "width": 854,
        "height": 480,
        "description": "Live optical camera feed with real-time AI Tri-Zone & behavior analysis."
    },
    {
        "id": "cam_02",
        "name": "Live Optical Camera #2 (Built-in Webcam)",
        "type": "usb_v4l2",
        "source": "0",
        "location": "Sector 22 - Secondary Physical Angle",
        "fps": 30,
        "width": 854,
        "height": 480,
        "description": "Live optical secondary feed with real-time motion and zone analysis."
    },
    {
        "id": "cam_03",
        "name": "Physical CCTV Feed #3 (RTSP Channel)",
        "type": "rtsp",
        "source": "rtsp://127.0.0.1:8554/cam03",
        "location": "Access Control Gateway (Awaiting RTSP Provisioning)",
        "fps": 25,
        "width": 854,
        "height": 480,
        "description": "Physical RTSP/ONVIF camera channel. Standby mode until stream provisioned."
    },
    {
        "id": "cam_04",
        "name": "Physical CCTV Feed #4 (RTSP Channel)",
        "type": "rtsp",
        "source": "rtsp://127.0.0.1:8554/cam04",
        "location": "Perimeter Loading Bay (Awaiting RTSP Provisioning)",
        "fps": 25,
        "width": 854,
        "height": 480,
        "description": "Physical RTSP/ONVIF camera channel. Standby mode until stream provisioned."
    }
]
