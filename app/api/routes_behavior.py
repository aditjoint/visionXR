from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.engine.human_behavior_engine import human_behavior_engine, BEHAVIOR_CATALOG

router = APIRouter(prefix="/api/behavior", tags=["Workplace & Human Behavioral AI Sniffing"])

class TriggerBehaviorRequest(BaseModel):
    camera_id: str = "cam_01"
    behavior_type: str = "SLEEPING_DROWSINESS" # SLEEPING_DROWSINESS, THEFT_CONCEALMENT, UNREST_VIOLENCE, SABOTAGE_TAMPERING, CHEATING_PHONE_USE, UNATTENDED_BAGGAGE

@router.get("/workplaces")
def get_workplaces():
    return human_behavior_engine.get_workplace_telemetry()

@router.get("/catalog")
def get_catalog():
    return BEHAVIOR_CATALOG

@router.post("/trigger")
def trigger_behavior(req: TriggerBehaviorRequest):
    return human_behavior_engine.trigger_behavior_scenario(req.camera_id, req.behavior_type)
