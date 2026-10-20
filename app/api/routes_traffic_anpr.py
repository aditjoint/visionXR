from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import cv2
import numpy as np
from app.engine.traffic_anpr_engine import traffic_engine

router = APIRouter(prefix="/api/anpr", tags=["Traffic & ANPR Intelligence"])

class WatchlistEntry(BaseModel):
    plate: str
    owner: str = "Unknown"
    reason: str = "Flagged Vehicle"
    risk: str = "HIGH"

@router.get("/watchlist")
def get_watchlist():
    return {"watchlist": traffic_engine.watchlist}

@router.post("/watchlist")
def add_to_watchlist(entry: WatchlistEntry):
    traffic_engine.watchlist.append(entry.dict())
    traffic_engine.save_watchlist()
    return {"status": "SUCCESS", "message": f"Added plate {entry.plate} to watchlist", "watchlist": traffic_engine.watchlist}

@router.delete("/watchlist/{plate}")
def delete_from_watchlist(plate: str):
    clean = plate.replace(" ", "").upper()
    traffic_engine.watchlist = [w for w in traffic_engine.watchlist if w.get("plate", "").replace(" ", "").upper() != clean]
    traffic_engine.save_watchlist()
    return {"status": "SUCCESS", "message": f"Plate {plate} removed from watchlist"}

@router.get("/gates")
def get_gate_counts():
    return {"gate_counts": traffic_engine.gate_counts}

@router.get("/parking")
def get_parked_vehicles():
    return {"parked_vehicles": traffic_engine.parked_vehicles}

@router.post("/recognize")
async def recognize_plate_file(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image payload")
    
    anpr_res = traffic_engine.detect_and_recognize_plate(img)
    if not anpr_res:
        return {"status": "NO_PLATE_DETECTED", "result": None}

    watchlist_hit = traffic_engine.check_watchlist(anpr_res["plate_number"])
    return {
        "status": "SUCCESS",
        "anpr": anpr_res,
        "is_suspected": watchlist_hit is not None,
        "watchlist_details": watchlist_hit
    }
