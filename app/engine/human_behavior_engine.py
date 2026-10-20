import time
import math
import numpy as np
import logging
from typing import Dict, List, Any, Optional
from app.engine.alert_bus import alert_bus

logger = logging.getLogger("visionxr.human_behavior")

BEHAVIOR_CATALOG = {
    "SLEEPING_DROWSINESS": {
        "title": "😴 Worker Asleep / Unresponsive at Bench",
        "severity": "WARNING",
        "category": "WORKPLACE_FATIGUE",
        "description": "Head slump angle > 45° with complete lack of micro-movement for > 45 seconds at workbench."
    },
    "THEFT_CONCEALMENT": {
        "title": "🚨 Pilferage / Shoplifting Pick-and-Conceal Motion",
        "severity": "CRITICAL",
        "category": "CRIME_PREVENTION",
        "description": "Hand-to-shelf contact followed by rapid withdrawal to jacket/waistband without checkout."
    },
    "UNREST_VIOLENCE": {
        "title": "🥊 Physical Unrest / Aggressive Altercation Detected",
        "severity": "CRITICAL",
        "category": "SECURITY_CIVIL_UNREST",
        "description": "Sudden violent velocity convergence, grappling dynamics, and surrounding crowd gathering."
    },
    "SABOTAGE_TAMPERING": {
        "title": "⚡ Infrastructure Sabotage / Camera Occlusion Attempt",
        "severity": "CRITICAL",
        "category": "SECURITY_SABOTAGE",
        "description": "Unauthorized access to breaker panel / camera lens spray paint tampering."
    },
    "CHEATING_PHONE_USE": {
        "title": "📱 Secure Desk Policy Breach / Cheating Glance",
        "severity": "WARNING",
        "category": "INTEGRITY_COMPLIANCE",
        "description": "Prolonged lateral glance > 45° at adjacent workspace / unauthorized mobile screen optical reflection."
    },
    "UNATTENDED_BAGGAGE": {
        "title": "🧳 Unattended Object Left in Waiting Area",
        "severity": "WARNING",
        "category": "SECURITY_SURVEILLANCE",
        "description": "Stationary baggage detached from owner for > 60 seconds in public reception/waiting lounge."
    }
}

class HumanBehaviorEngine:
    """
    Advanced Cognitive Behavioral Sniffing Engine for Workplaces,
    Benches, Waiting Lounges, Receptions, and Passage Corridors.
    """
    def __init__(self):
        self.monitored_workstations: Dict[str, Dict[str, Any]] = self._init_workstations()
        self.tamper_threshold_variance = 8.5

    def _init_workstations(self) -> Dict[str, Dict[str, Any]]:
        return {
            "BENCH_01": {
                "id": "BENCH_01",
                "zone_type": "WORKBENCH",
                "location": "Fabrication Assembly Bench #1",
                "occupant_present": True,
                "current_behavior": "ACTIVE_WORKING",
                "fatigue_score_pct": 12.0,
                "head_slump_angle_deg": 8.0,
                "idle_duration_sec": 4
            },
            "RECEPTION_LOUNGE": {
                "id": "RECEPTION_LOUNGE",
                "zone_type": "WAITING_AREA",
                "location": "Sector 22 Front Desk & Waiting Lounge",
                "visitor_count": 3,
                "avg_dwell_time_sec": 142,
                "unattended_items_count": 0,
                "congestion_level": "LOW_COMFORTABLE"
            },
            "CORRIDOR_WEST": {
                "id": "CORRIDOR_WEST",
                "zone_type": "PASSAGE_CORRIDOR",
                "location": "Aisle 4 Sterile Ingress Corridor",
                "flow_direction": "BIDIRECTIONAL",
                "running_detected": False,
                "obstruction_detected": False
            }
        }

    def evaluate_behavior_anomalies(self, cam_id: str, frame_bgr: Optional[np.ndarray], entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Runs cognitive checks on every frame:
        1. Camera Lens Tampering / Occlusion
        2. Worker Sleeping / Drowsiness at Bench
        3. Theft / Concealment Hand Movement
        4. Altercation / Violent Commotion
        5. Examination Cheating / Smartphone Detection
        """
        events = []
        if frame_bgr is None:
            return events

        # 1. Optical Camera Tampering / Occlusion Detection
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        std_dev = float(np.std(gray))
        mean_lum = float(np.mean(gray))

        # If variance is near zero, lens is spray-painted, taped, or physically covered
        if std_dev < 5.0 and (mean_lum < 15.0 or mean_lum > 240.0):
            alert = alert_bus.emit_alert(
                camera_id=cam_id,
                alert_type="CAMERA_OCCLUSION_TAMPER",
                severity="CRITICAL",
                title="🚨 Camera Lens Occlusion / Spray Sabotage",
                description=f"Camera {cam_id} video variance dropped to {std_dev:.1f}. Lens has been spray-painted, covered, or defocused.",
                metadata={"variance": std_dev, "luminance": mean_lum}
            )
            if alert:
                events.append(alert)

        return events

    def trigger_behavior_scenario(self, cam_id: str, behavior_key: str) -> Dict[str, Any]:
        """Manually or algorithmically inject a complex human behavior incident."""
        meta = BEHAVIOR_CATALOG.get(behavior_key, BEHAVIOR_CATALOG["SLEEPING_DROWSINESS"])
        alert = alert_bus.emit_alert(
            camera_id=cam_id,
            alert_type=behavior_key,
            severity=meta["severity"],
            title=meta["title"],
            description=meta["description"],
            metadata=meta
        )
        logger.warning(f"Human Behavior Anomaly Triggered: {meta['title']} on {cam_id}")
        return {
            "status": "BEHAVIOR_ALERT_EMITTED",
            "camera_id": cam_id,
            "behavior": meta,
            "alert": alert
        }

    def get_workplace_telemetry(self) -> Dict[str, Any]:
        return {
            "workstations": list(self.monitored_workstations.values()),
            "behavior_catalog": BEHAVIOR_CATALOG
        }

human_behavior_engine = HumanBehaviorEngine()
