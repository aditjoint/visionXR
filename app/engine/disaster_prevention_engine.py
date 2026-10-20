import time
import math
import random
import logging
from typing import Dict, List, Any, Optional
from app.engine.alert_bus import alert_bus

logger = logging.getLogger("visionxr.disaster")

DISASTER_TAXONOMY = {
    "ACID_FUMING_SPILL": {
        "title": "☣️ Severe Corrosive Acid Spill & Exothermic Fuming",
        "severity": "CRITICAL",
        "agent": "Concentrated Nitric Acid (HNO3) / H2SO4",
        "risk": "Rapid concrete etching, toxic NOx orange/white fuming vapor",
        "ph_level": 1.2,
        "fume_opacity_pct": 78.4
    },
    "TOXIC_GAS_PLUME": {
        "title": "💨 Toxic Vapor Cloud Dispersion (OGI Optical Gas Shimmer)",
        "severity": "CRITICAL",
        "agent": "Ammonia (NH3) / Chlorine Gas Vapor",
        "risk": "Downwind atmospheric dispersion, respiratory casualty hazard",
        "plume_radius_meters": 18.5,
        "wind_vector_bearing_deg": 245
    },
    "PIPE_BURST_FLOOD": {
        "title": "🌊 High-Pressure Main Line Pipe Burst & Flash Flood",
        "severity": "CRITICAL",
        "agent": "Industrial Chilled Water Loop / Deluge Header",
        "risk": "Switchgear inundation, electrical arc-flash ground fault",
        "flow_rate_lpm": 850.0, # Liters per minute
        "water_depth_cm": 14.2
    },
    "THERMAL_RUNAWAY": {
        "title": "🔥 Battery Energy Storage (BESS) Thermal Runaway",
        "severity": "CRITICAL",
        "agent": "Lithium Iron Phosphate (LFP) Battery Rack 4",
        "risk": "Self-sustaining exothermic decomposition, toxic gas ejection",
        "temperature_celsius": 385.0,
        "heating_rate_c_sec": 8.5
    },
    "CRYOGENIC_FREEZE_LEAK": {
        "title": "❄️ Cryogenic Liquid Nitrogen (LN2) Flash Boil-Off",
        "severity": "CRITICAL",
        "agent": "Liquid Nitrogen Transfer Line",
        "risk": "Rapid oxygen depletion asphyxiation, cryogenic embrittlement",
        "temperature_celsius": -162.0,
        "oxygen_concentration_pct": 16.4 # Normal is 20.9%
    },
    "BIOHAZARD_SPOILAGE": {
        "title": "🦠 Biological Contamination & Microbial Spoilage",
        "severity": "WARNING",
        "agent": "Cleanroom Organic Bacterial Bloom / Mold Culture",
        "risk": "Airlock sterility compromise, pharmaceutical batch loss",
        "spoilage_index_pct": 34.2
    }
}

class DisasterPreventionEngine:
    def __init__(self):
        self.active_disasters: Dict[str, Dict[str, Any]] = {}
        self.esd_interlock_tripped = False # Emergency Shut Down
        self._init_default_scenario()

    def _init_default_scenario(self):
        # Pure physical mode: Zero pre-seeded or fake disaster anomalies
        self.active_disasters = {}

    def trigger_disaster_event(self, cam_id: str, disaster_type: str) -> Dict[str, Any]:
        """
        Inject or detect an industrial disaster anomaly.
        Immediately activates ESD Interlock, sirens, and WhatsApp emergency dispatch.
        """
        tax = DISASTER_TAXONOMY.get(disaster_type, DISASTER_TAXONOMY["ACID_FUMING_SPILL"])
        dis_id = f"DIS_{int(time.time()*1000)}"

        event = {
            "id": dis_id,
            "cam_id": cam_id,
            "type": disaster_type,
            "location": f"Sector 22 • {cam_id.upper()}",
            "meta": tax,
            "active_since": time.time(),
            "status": "ACTIVE_CRITICAL",
            "esd_triggered": True
        }

        self.active_disasters[dis_id] = event
        self.esd_interlock_tripped = True

        # Emit Critical Alarm
        alert_bus.emit_alert(
            camera_id=cam_id,
            alert_type=disaster_type,
            severity="CRITICAL",
            title=tax["title"],
            description=f"Agent: {tax['agent']} | Risk: {tax['risk']}. Automatic SCADA Emergency Shutdown (ESD) interlock engaged.",
            metadata=tax
        )

        logger.critical(f"INDUSTRIAL DISASTER ENGAGED: {tax['title']} on {cam_id}")
        return event

    def reset_esd_interlock(self, actor: str = "Chief Safety Officer") -> bool:
        """Manual reset of SCADA Emergency ShutDown interlock after all-clear."""
        self.esd_interlock_tripped = False
        self.active_disasters.clear()
        logger.info(f"SCADA ESD Interlock reset by {actor}.")
        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "esd_interlock_tripped": self.esd_interlock_tripped,
            "active_disasters_count": len(self.active_disasters),
            "disasters": list(self.active_disasters.values()),
            "taxonomy": DISASTER_TAXONOMY
        }

disaster_engine = DisasterPreventionEngine()
