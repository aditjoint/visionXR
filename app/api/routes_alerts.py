from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.engine.alert_bus import alert_bus
from app.engine.acoustic_engine import acoustic_engine

router = APIRouter(prefix="/api/alerts", tags=["Alerts & Escalation Gateway"])

class AckRequest(BaseModel):
    operator_name: str = "Operator Shift Alpha"

class SirenRequest(BaseModel):
    state: Optional[bool] = None
    active: Optional[bool] = None
    actor: str = "Commander"

    def get_state(self) -> bool:
        if self.state is not None:
            return self.state
        if self.active is not None:
            return self.active
        return True

class LockdownRequest(BaseModel):
    state: Optional[bool] = None
    active: Optional[bool] = None
    actor: str = "Commander"

    def get_state(self) -> bool:
        if self.state is not None:
            return self.state
        if self.active is not None:
            return self.active
        return True

class AcousticTestRequest(BaseModel):
    camera_id: str = "cam_01"
    event_type: str = "DISTRESS_SCREAM" # GLASS_BREAK, DISTRESS_SCREAM, METAL_IMPACT

@router.get("")
def get_alerts(limit: int = 50):
    return {
        "alerts": alert_bus.get_recent_alerts(limit),
        "siren_active": alert_bus.siren_active,
        "lockdown_active": alert_bus.lockdown_active
    }

@router.post("/{alert_id}/ack")
def ack_alert(alert_id: str, req: AckRequest):
    success = alert_bus.acknowledge_alert(alert_id, req.operator_name)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "ACKNOWLEDGED", "alert_id": alert_id}

@router.post("/siren")
def set_siren(req: SirenRequest):
    new_state = alert_bus.toggle_siren(req.get_state(), req.actor)
    return {"siren_active": new_state}

@router.post("/silence")
def silence_all(actor: str = "Operator"):
    state = alert_bus.silence_all_alarms(actor)
    return {"status": "SILENCED", "siren_active": state}

@router.post("/clear")
def clear_all(actor: str = "Operator"):
    alert_bus.clear_all_alerts(actor)
    return {"status": "CLEARED", "siren_active": False, "alerts": []}


@router.post("/lockdown")
def set_lockdown(req: LockdownRequest):
    new_state = alert_bus.toggle_lockdown(req.get_state(), req.actor)
    return {"lockdown_active": new_state}

@router.post("/test-whatsapp")
def test_whatsapp_escalation():
    test_alert = {
        "id": "wa_test_01",
        "camera_id": "cam_02",
        "title": "🚨 [TEST] Sovereign Perimeter High-Voltage Alarm",
        "description": "Manual diagnostic test trigger to verify instant WhatsApp Gateway dispatch to +91-8779639965.",
        "formatted_time": "Real-time Verification",
        "snapshot_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
    alert_bus.dispatch_whatsapp_escalation(test_alert)
    return {
        "status": "DISPATCHED",
        "target": "+91-8779639965",
        "logs": alert_bus.whatsapp_logs[:3]
    }

@router.get("/whatsapp/logs")
def get_whatsapp_logs():
    return alert_bus.whatsapp_logs

@router.post("/test-acoustic")
def test_acoustic(req: AcousticTestRequest):
    evt = acoustic_engine.trigger_acoustic_event(req.camera_id, req.event_type)
    alert_bus.emit_alert(
        camera_id=req.camera_id,
        alert_type=evt["subtype"],
        severity=evt["severity"],
        title=f"🔊 Acoustic Anomaly: {evt['label']}",
        description=f"Acoustic impulse verified at {evt['decibel_db']} dB in {evt['freq_band']}.",
        metadata=evt
    )
    return {"status": "TRIGGERED", "event": evt}
