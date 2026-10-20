from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Union
from app.engine.inference_worker import pipeline
from app.security.audit_logger import audit_logger

router = APIRouter(prefix="/api/zones", tags=["Spatial Tri-Zones"])

class ZoneModel(BaseModel):
    id: str
    name: str
    type: str # green, amber, red
    polygon: List[List[float]] # [[x, y], ...]
    max_dwell_sec: int = 5
    description: str = ""

class ZonesUpdateRequest(BaseModel):
    zones: List[ZoneModel]

@router.get("/{cam_id}")
def get_camera_zones(cam_id: str):
    return pipeline.spatial_engine.get_zones_for_camera(cam_id)

@router.post("/{cam_id}")
def update_camera_zones(cam_id: str, req: Union[ZonesUpdateRequest, List[ZoneModel]], request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    if isinstance(req, list):
        raw_zones = [z.dict() if hasattr(z, 'dict') else z for z in req]
    elif hasattr(req, 'zones'):
        raw_zones = [z.dict() if hasattr(z, 'dict') else z for z in req.zones]
    else:
        raw_zones = []
    pipeline.spatial_engine.set_zones_for_camera(cam_id, raw_zones)

    audit_logger.log(
        actor="operator",
        role="OPERATOR",
        action="ZONES_UPDATED",
        resource=cam_id,
        ip_address=ip,
        result="SUCCESS",
        details=f"Updated {len(raw_zones)} Tri-Zone polygons for camera {cam_id}"
    )
    return {
        "status": "SAVED",
        "cam_id": cam_id,
        "zones": pipeline.spatial_engine.get_zones_for_camera(cam_id)
    }

@router.post("/{cam_id}/reset")
def reset_camera_zones(cam_id: str, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    from app.engine.spatial_zones import DEFAULT_ZONES_PRESETS
    if cam_id in DEFAULT_ZONES_PRESETS:
        pipeline.spatial_engine.set_zones_for_camera(cam_id, DEFAULT_ZONES_PRESETS[cam_id])
    audit_logger.log(
        actor="operator",
        role="OPERATOR",
        action="ZONES_RESET_DEFAULT",
        resource=cam_id,
        ip_address=ip,
        result="SUCCESS",
        details=f"Reset Tri-Zones to factory presets for {cam_id}"
    )
    return {"status": "RESET", "zones": pipeline.spatial_engine.get_zones_for_camera(cam_id)}
