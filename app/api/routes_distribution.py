import os
import shutil
import asyncio
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from scripts.build_distribution_usb import FEATURE_CATALOG, build_distribution, USB_MOUNT, DIST_TARGET

distribution_router = APIRouter(prefix="/api/distribution", tags=["distribution"])

class BuildDistributionRequest(BaseModel):
    company_name: str
    max_cameras: int = 8
    features: List[str]

@distribution_router.get("/features")
async def get_distribution_features():
    """Returns available feature catalog and USB status."""
    usb_detected = USB_MOUNT.exists()
    free_mb = 0
    total_mb = 0
    if usb_detected:
        try:
            stat = shutil.disk_usage(USB_MOUNT)
            free_mb = round(stat.free / (1024 * 1024), 2)
            total_mb = round(stat.total / (1024 * 1024), 2)
        except Exception:
            pass

    existing_dist = DIST_TARGET.exists()

    return {
        "features": FEATURE_CATALOG,
        "usb": {
            "path": str(USB_MOUNT),
            "mounted": usb_detected,
            "free_mb": free_mb,
            "total_mb": total_mb,
            "existing_package": existing_dist
        }
    }

@distribution_router.post("/build")
async def build_distribution_package(req: BuildDistributionRequest):
    """Builds a customized, hardened client distribution package to USB media."""
    if not USB_MOUNT.exists():
        raise HTTPException(status_code=400, detail=f"Target USB drive is not mounted at {USB_MOUNT}.")

    if not req.features or len(req.features) == 0:
        raise HTTPException(status_code=400, detail="At least one feature module must be selected for deployment.")

    valid_feature_ids = {f["id"] for f in FEATURE_CATALOG}
    selected_valid = [fid for fid in req.features if fid in valid_feature_ids]

    if not selected_valid:
        raise HTTPException(status_code=400, detail="No valid feature IDs specified.")

    clean_company = req.company_name.strip() if req.company_name.strip() else "SOVEREIGN ENTERPRISE"
    cams = max(1, min(128, req.max_cameras))

    try:
        result = await asyncio.to_thread(
            build_distribution,
            company_name=clean_company,
            max_cameras=cams,
            selected_feature_ids=selected_valid
        )
        return {
            "success": True,
            "message": f"Distribution package successfully generated on USB for {clean_company}.",
            "details": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build distribution: {str(e)}")

