import time
import math
import random
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("visionxr.acoustic")

ACOUSTIC_PROFILES = {
    "GLASS_BREAK": {
        "label": "Glass Shatter / Perimeter Breach",
        "severity": "CRITICAL",
        "freq_band": "High (4.5kHz - 8kHz)",
        "db_threshold": 82
    },
    "DISTRESS_SCREAM": {
        "label": "Worker Distress Call / Shouting",
        "severity": "CRITICAL",
        "freq_band": "Mid-High (1.2kHz - 3.5kHz)",
        "db_threshold": 88
    },
    "METAL_IMPACT": {
        "label": "Heavy Machine Clatter / Structural Impact",
        "severity": "WARNING",
        "freq_band": "Low-Mid (200Hz - 1kHz)",
        "db_threshold": 95
    },
    "ACOUSTIC_SIREN": {
        "label": "Facility Evacuation Siren Echo",
        "severity": "WARNING",
        "freq_band": "Dual Tone (800Hz / 1200Hz)",
        "db_threshold": 90
    },
    "NORMAL_HUM": {
        "label": "Ambient Industrial Baseline",
        "severity": "INFO",
        "freq_band": "Sub-100Hz",
        "db_threshold": 65
    }
}

class AcousticEngine:
    def __init__(self):
        self.current_decibel = 0.0
        self.recent_events: List[Dict[str, Any]] = []

    def process_ambient_telemetry(self, cam_id: str) -> Optional[Dict[str, Any]]:
        # Zero synthetic baseline: Real ambient sound only processed when acoustic hardware sensor is provisioned
        self.current_decibel = 0.0
        return None

    def trigger_acoustic_event(self, cam_id: str, event_type: str, confidence: float = 0.93) -> Dict[str, Any]:
        meta = ACOUSTIC_PROFILES.get(event_type, ACOUSTIC_PROFILES["METAL_IMPACT"])
        event = {
            "id": f"ac_{int(time.time()*1000)}",
            "camera_id": cam_id,
            "type": "ACOUSTIC_ANOMALY",
            "subtype": event_type,
            "label": meta["label"],
            "severity": meta["severity"],
            "decibel_db": meta["db_threshold"] + round(random.uniform(1.2, 5.8), 1),
            "freq_band": meta["freq_band"],
            "confidence": confidence,
            "timestamp": time.time(),
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.recent_events.insert(0, event)
        if len(self.recent_events) > 50:
            self.recent_events.pop()
        logger.warning(f"Acoustic alert triggered on {cam_id}: {event['label']} ({event['decibel_db']} dB)")
        return event

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "ambient_db": self.current_decibel,
            "status": "NORMAL" if self.current_decibel < 85 else "HIGH_NOISE",
            "recent_events": self.recent_events[:5]
        }

acoustic_engine = AcousticEngine()
