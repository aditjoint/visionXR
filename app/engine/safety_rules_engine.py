import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import DATA_DIR

logger = logging.getLogger("visionxr.safety_rules")
SAFETY_RULES_FILE = DATA_DIR / "safety_rules.json"

DEFAULT_SAFETY_RULES = {
    # 1. Subject (Human / Worker) Thresholds
    "subject": {
        "amber_max_dwell_sec": 5.0,            # Max seconds in Amber zone before loitering warning
        "red_grace_period_sec": 0.0,           # Zero tolerance (0.0s) for Red hazard zone entry
        "man_down_motionless_sec": 15.0,       # Horizontal motionless threshold for rescue dispatch
        "running_speed_kmh": 14.0,             # Speed threshold for rushing/sprinting alert
        "sleeping_inactivity_sec": 45.0,       # Inactivity threshold at desk/bench before sleeping alert
        "cheating_glance_deg": 45.0,           # Lateral head glance divergence for secure desk breach
        "require_ppe_vest": True,              # High-visibility fluorescent vest enforcement
        "require_ppe_helmet": True,            # Industrial safety hard-hat enforcement
        "curfew_enabled": True,                # Time-scheduled perimeter curfew rule
        "curfew_start_hour": 20,               # 8:00 PM
        "curfew_end_hour": 6                   # 6:00 AM
    },
    # 2. Object, Machine & Material Thresholds
    "object": {
        "forklift_speed_limit_kmh": 12.0,      # Forklift indoor corridor speed limit
        "cargo_tilt_max_deg": 15.0,            # Maximum allowable pallet tilt before tip-over alarm
        "chemical_spill_max_m2": 1.50,         # Maximum allowable puddle area before hazmat dispatch
        "spill_expansion_rate_m2_min": 0.15,   # Spill expansion velocity (dA/dt)
        "thermal_hotspot_threshold_c": 80.0,   # Temperature threshold for switchgear/fire pre-cursor
        "thermal_heating_rate_c_min": 2.5,     # Rate of temperature rise (dT/dt)
        "turbulence_chaos_threshold": 70.0,    # Optical flow commotion/panic index (0 - 100)
        "acoustic_decibel_threshold_db": 85.0  # Decibel ceiling for noise/screams
    },
    # 3. Emergency Alarm & Escalation Gateways
    "escalation": {
        "auto_trigger_siren_on_red": True,
        "auto_dispatch_whatsapp": True,
        "auto_trip_scada_esd": True,
        "whatsapp_target": "+91-8779639965"
    },
    # 4. Traffic, Vehicles & ANPR Thresholds
    "traffic": {
        "anpr_enabled": True,
        "speed_limit_kmh": 40.0,
        "no_parking_dwell_sec": 30.0,
        "enforce_helmet": True,
        "enforce_triple_riding": True,
        "enforce_driver_phone": True,
        "enforce_seatbelt": True,
        "enforce_wrong_direction": True
    },
    # 5. Sovereign Biometrics & Face Compliance (FRSS)
    "biometrics": {
        "frss_enabled": True,
        "match_threshold": 0.65,
        "enforce_mask": False,
        "alert_on_unknown": True
    },
    # 6. Spatial Analytics & Site Monitoring
    "analytics": {
        "crowd_min_cluster": 4,
        "crowd_distance_px": 85.0,
        "fence_jump_enabled": True,
        "garbage_detection_enabled": True,
        "garbage_min_dwell_sec": 15.0,
        "attribute_indexing_enabled": True
    }
}

class SafetyRulesEngine:
    def __init__(self):
        self.rules: Dict[str, Any] = DEFAULT_SAFETY_RULES.copy()
        self.load_rules()

    def load_rules(self):
        if SAFETY_RULES_FILE.exists():
            try:
                with open(SAFETY_RULES_FILE, "r") as f:
                    data = json.load(f)
                    for k in ["subject", "object", "escalation", "traffic", "biometrics", "analytics"]:
                        if k in data:
                            self.rules[k].update(data[k])
                    logger.info("Loaded custom Super Admin safety parameters from NVMe boot storage.")
            except Exception as e:
                logger.error(f"Error loading safety rules: {e}. Fallback to sovereign defaults.")

        else:
            self.save_rules()

    def save_rules(self):
        try:
            with open(SAFETY_RULES_FILE, "w") as f:
                json.dump(self.rules, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist safety rules: {e}")

    def get_rules(self) -> Dict[str, Any]:
        return self.rules

    def update_rules(self, new_rules: Dict[str, Any]) -> Dict[str, Any]:
        if "subject" in new_rules:
            self.rules["subject"].update(new_rules["subject"])
        if "object" in new_rules:
            self.rules["object"].update(new_rules["object"])
        if "escalation" in new_rules:
            self.rules["escalation"].update(new_rules["escalation"])
        self.save_rules()
        logger.info("Super Admin updated live safety & alarm trigger parameters.")
        return self.rules

    def reset_to_defaults(self) -> Dict[str, Any]:
        self.rules = DEFAULT_SAFETY_RULES.copy()
        self.save_rules()
        return self.rules

safety_rules = SafetyRulesEngine()
