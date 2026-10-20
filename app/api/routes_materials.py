from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.engine.material_hazard_engine import material_hazard_tracker
from app.engine.homography_3d import homography_3d

router = APIRouter(prefix="/api/hazards", tags=["Material Defects & Homography 3D"])

class HomographyTransformRequest(BaseModel):
    camera_id: str = "cam_01"
    pixel_u: float
    pixel_v: float

class HomographyAreaRequest(BaseModel):
    camera_id: str = "cam_01"
    polygon_uv: List[List[float]]

@router.get("/list")
def list_hazards(camera_id: Optional[str] = None):
    return {
        "active_hazards": material_hazard_tracker.list_active_hazards(camera_id),
        "count": len(material_hazard_tracker.list_active_hazards(camera_id))
    }

@router.post("/homography/pixel-to-world")
def pixel_to_world(req: HomographyTransformRequest):
    wx, wy = homography_3d.pixel_to_world(req.camera_id, req.pixel_u, req.pixel_v)
    return {
        "camera_id": req.camera_id,
        "input_pixel_uv": [req.pixel_u, req.pixel_v],
        "metric_world_xy_meters": [wx, wy],
        "ground_plane_reference": "Sector 22 Metric Survey Grid"
    }

@router.post("/homography/polygon-area")
def polygon_area(req: HomographyAreaRequest):
    area_m2 = homography_3d.compute_metric_polygon_area(req.camera_id, req.polygon_uv)
    return {
        "camera_id": req.camera_id,
        "vertices_count": len(req.polygon_uv),
        "physical_surface_area_m2": area_m2
    }
