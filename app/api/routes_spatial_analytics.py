from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from app.engine.spatial_analytics_engine import spatial_analytics

router = APIRouter(prefix="/api/analytics", tags=["Spatial Analytics, Counting & Visual Attribute Search"])

class AssetMonitorRequest(BaseModel):
    asset_id: str
    camera_id: str
    bbox: List[int]

@router.get("/counts")
def get_all_counts():
    return {"counts": spatial_analytics.occupancy_counts}

@router.get("/counts/{cam_id}")
def get_camera_counts(cam_id: str):
    return {"camera_id": cam_id, "counts": spatial_analytics.get_counts(cam_id)}

@router.get("/search")
def search_attribute_ledger(
    color: Optional[str] = Query(None, description="Dominant color: RED, BLUE, GREEN, YELLOW, WHITE, BLACK, GREY"),
    class_label: Optional[str] = Query(None, description="Object class: person, car, truck, motorcycle"),
    min_time: Optional[int] = Query(None, description="Unix timestamp start"),
    max_time: Optional[int] = Query(None, description="Unix timestamp end")
):
    results = spatial_analytics.search_attributes(
        color=color,
        class_label=class_label,
        min_time=min_time,
        max_time=max_time
    )
    return {"total_matches": len(results), "results": results}

@router.get("/ledger")
def get_attribute_ledger():
    return {"ledger": spatial_analytics.attribute_ledger[-100:]}
