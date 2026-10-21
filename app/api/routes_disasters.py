from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.engine.disaster_prevention_engine import disaster_engine
from app.engine.industrial_lifecycle_engine import lifecycle_engine

router = APIRouter(prefix="/api/industrial", tags=["Industrial Lifecycle & Disaster Prevention"])

class DisasterTriggerRequest(BaseModel):
    camera_id: str = "cam_02"
    disaster_type: str = "ACID_FUMING_SPILL" # ACID_FUMING_SPILL, TOXIC_GAS_PLUME, PIPE_BURST_FLOOD, THERMAL_RUNAWAY, CRYOGENIC_FREEZE_LEAK, BIOHAZARD_SPOILAGE

class ESDResetRequest(BaseModel):
    actor: str = "Chief Safety Officer"

@router.get("/status")
def get_industrial_status():
    return {
        "lifecycle": lifecycle_engine.get_summary(),
        "disaster_preparedness": disaster_engine.get_status()
    }

@router.post("/disaster/trigger")
def trigger_disaster(req: DisasterTriggerRequest):
    event = disaster_engine.trigger_disaster_event(req.camera_id, req.disaster_type)
    return {
        "status": "DISASTER_ENGAGED",
        "event": event,
        "esd_interlock_state": disaster_engine.esd_interlock_tripped
    }

@router.post("/esd/reset")
def reset_esd(req: ESDResetRequest):
    disaster_engine.reset_esd_interlock(req.actor)
    return {
        "status": "ESD_INTERLOCK_NORMALIZED",
        "actor": req.actor,
        "esd_interlock_state": False
    }
