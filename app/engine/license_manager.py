import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from app.config import BASE_DIR, DATA_DIR, CUSTOMER_COMPANY_NAME
from app.security.hardware_lock import (
    get_cross_platform_hardware_id,
    compute_developer_signature,
    verify_developer_license_integrity
)
from app.security.tamper_guard import tamper_guard

logger = logging.getLogger("visionxr.license")

DEV_LICENSE_FILE = BASE_DIR / "developer.license"
DATA_LICENSE_FILE = DATA_DIR / "license.json"

AVAILABLE_TASKS = [
    {"id": "TRI_ZONE_PERIMETER", "name": "Tri-Zone Spatial Perimeter", "desc": "Red/Amber/Green spatial boundary intrusion & loitering detection"},
    {"id": "WORKER_PPE_SAFETY", "name": "Worker PPE & Posture", "desc": "Hardhat, high-vis vest compliance & Man-Down emergency tracking"},
    {"id": "VEHICLE_SPEED_COLLISION", "name": "Forklift & Vehicle Dynamics", "desc": "Velocity vectors, speed limit enforcement & cargo tilt detection"},
    {"id": "CHEMICAL_SPILL_HAZARD", "name": "Chemical & Liquid Spill Expansion", "desc": "Homography 2D->3D surface area (m²) monitoring"},
    {"id": "THERMAL_HOTSPOT_RUNAWAY", "name": "Thermal Runaway & Arc-Flash", "desc": "Thermal radiation tracking and switchgear hotspot alerts"},
    {"id": "HUMAN_BEHAVIOR_THEFT_SLEEP", "name": "Human Misconduct Sniffer", "desc": "Sleeping at bench, theft attempt, fighting, unrest and cheating"},
    {"id": "ACOUSTIC_DISTRESS_SNIFFER", "name": "Acoustic Audio Sniffer", "desc": "Acoustic dB decibel scream, glass break & explosion detection"}
]

class LicenseManager:
    """
    Sovereign Hardware-Locked License Manager.
    Tied to single server hardware fingerprint with Developer Master Signature.
    Super Admin cannot bypass or elevate quota without genuine Developer Signature.
    Enforces 20-attempt anti-tamper threshold with irreversible self-destruction.
    """
    def __init__(self):
        self.hardware_id = get_cross_platform_hardware_id()
        self.license_data = self._load_or_provision_license()

    def _load_or_provision_license(self) -> Dict[str, Any]:
        # 1. Check developer.license in installation root first
        for lic_path in [DEV_LICENSE_FILE, DATA_LICENSE_FILE]:
            if lic_path.exists():
                try:
                    with open(lic_path, "r") as f:
                        data = json.load(f)
                    
                    valid, reason = verify_developer_license_integrity(data, self.hardware_id)
                    if valid:
                        logger.info(f"Verified authentic Developer License: HWID={self.hardware_id}, MaxCams={data.get('max_cameras')}")
                        return data
                    else:
                        logger.critical(f"UNAUTHORIZED LICENSE DETECTED ({reason})! Hardware mismatch or forged developer key.")
                        tamper_guard.record_tamper_incident(f"INVALID_OR_MISMATCHED_LICENSE_FILE: {reason}")
                except Exception as e:
                    logger.error(f"Error reading {lic_path}: {e}")

        # 2. Provision local Hardware-Bound Developer Pilot Baseline
        default_features = [t["id"] for t in AVAILABLE_TASKS]
        dev_sig = compute_developer_signature(
            hardware_id=self.hardware_id,
            customer_name=CUSTOMER_COMPANY_NAME,
            max_cameras=4,
            tier="DEVELOPER_NODE",
            features=default_features
        )
        baseline = {
            "tier": "DEVELOPER_NODE",
            "tier_name": f"VisionXR Single-Server Node ({CUSTOMER_COMPANY_NAME})",
            "customer_name": CUSTOMER_COMPANY_NAME,
            "hardware_id": self.hardware_id,
            "max_cameras": 4,
            "is_developer_machine": True,
            "features": default_features,
            "developer_signature": dev_sig,
            "camera_tasks": {
                "cam_01": ["TRI_ZONE_PERIMETER", "WORKER_PPE_SAFETY", "VEHICLE_SPEED_COLLISION"],
                "cam_02": ["TRI_ZONE_PERIMETER", "THERMAL_HOTSPOT_RUNAWAY", "ACOUSTIC_DISTRESS_SNIFFER"],
                "cam_03": ["TRI_ZONE_PERIMETER", "HUMAN_BEHAVIOR_THEFT_SLEEP", "WORKER_PPE_SAFETY"],
                "cam_04": ["TRI_ZONE_PERIMETER", "VEHICLE_SPEED_COLLISION", "CHEMICAL_SPILL_HAZARD"]
            }
        }
        self._save_license(baseline)
        return baseline

    def _save_license(self, data: Dict[str, Any]):
        DATA_LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_LICENSE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def get_license_info(self) -> Dict[str, Any]:
        return {
            "tier": self.license_data.get("tier"),
            "tier_name": self.license_data.get("tier_name"),
            "customer_name": self.license_data.get("customer_name", CUSTOMER_COMPANY_NAME),
            "hardware_id": self.hardware_id,
            "max_cameras": self.license_data.get("max_cameras", 4),
            "is_developer_machine": self.license_data.get("is_developer_machine", False),
            "features": self.license_data.get("features", []),
            "available_tasks": AVAILABLE_TASKS,
            "camera_tasks": self.license_data.get("camera_tasks", {}),
            "tamper_security": {
                "attempts_used": tamper_guard.state.get("tamper_count", 0),
                "remaining_attempts_before_destruction": tamper_guard.get_remaining_attempts(),
                "threshold": 20
            }
        }

    def can_provision_camera(self, current_camera_count: int) -> Dict[str, Any]:
        """Enforces strictly hardware-bound developer camera ceiling."""
        max_cams = self.license_data.get("max_cameras", 4)
        if current_camera_count >= max_cams:
            return {
                "allowed": False,
                "reason": (
                    f"DEVELOPER_HARDWARE_LOCK_ENFORCED: This single server node is hardware-locked to "
                    f"a maximum of {max_cams} camera feeds. Super Admin cannot override Developer Master Key. "
                    f"Contact Software Vendor Licensing Directorate for an upgraded hardware-bound license."
                ),
                "max_cameras": max_cams,
                "current_count": current_camera_count
            }
        return {"allowed": True, "max_cameras": max_cams, "current_count": current_camera_count}

    def is_task_enabled(self, cam_id: str, task_id: str) -> bool:
        tasks = self.license_data.get("camera_tasks", {}).get(cam_id, [])
        return task_id in tasks

    def assign_camera_tasks(self, cam_id: str, task_ids: List[str]) -> Dict[str, Any]:
        valid_ids = {t["id"] for t in AVAILABLE_TASKS}
        filtered = [t for t in task_ids if t in valid_ids]
        if "camera_tasks" not in self.license_data:
            self.license_data["camera_tasks"] = {}
        self.license_data["camera_tasks"][cam_id] = filtered
        self._save_license(self.license_data)
        logger.info(f"Assigned tasks to {cam_id}: {filtered}")
        return {"camera_id": cam_id, "assigned_tasks": filtered}

    def apply_developer_license_key(self,
                                   developer_license_token: str,
                                   actor: str = "SuperAdmin") -> Dict[str, Any]:
        """
        Validates and installs a Developer Master License issued for this hardware node.
        If the token is forged, invalid, or belongs to another machine:
        Counts toward the 20-attempt tamper counter. If 20 attempts reached -> Self Destructs!
        """
        try:
            # Parse token if JSON or Base64
            token_clean = developer_license_token.strip()
            data = None
            if token_clean.startswith("{"):
                data = json.loads(token_clean)
            else:
                import base64
                decoded = base64.b64decode(token_clean).decode("utf-8")
                data = json.loads(decoded)

            valid, reason = verify_developer_license_integrity(data, self.hardware_id)
            if not valid:
                cnt, rem = tamper_guard.record_tamper_incident(f"FORGED_OR_INVALID_LICENSE_TOKEN: {reason}", actor=actor)
                return {
                    "success": False,
                    "error": (
                        f"CRITICAL_VALIDATION_FAILURE: {reason}. "
                        f"Attempt {cnt}/20 recorded in sovereign tamper ledger. "
                        f"Warning: {rem} attempts remaining before permanent self-destruction."
                    ),
                    "remaining_attempts": rem
                }

            # Apply verified developer license
            self.license_data = data
            self._save_license(self.license_data)
            logger.info(f"Developer License successfully unlocked for {data.get('customer_name')}: MaxCams={data.get('max_cameras')}")
            return {
                "success": True,
                "message": f"Successfully activated Developer Node License for {data.get('customer_name')}.",
                "license": self.get_license_info()
            }

        except Exception as e:
            cnt, rem = tamper_guard.record_tamper_incident(f"MALFORMED_LICENSE_ATTEMPT: {str(e)}", actor=actor)
            return {
                "success": False,
                "error": f"Invalid license token format. Attempt {cnt}/20 recorded. {rem} attempts remaining before self-destruction.",
                "remaining_attempts": rem
            }

license_manager = LicenseManager()
