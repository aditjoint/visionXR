from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import cv2
import numpy as np
from app.engine.face_recognition_engine import face_engine

router = APIRouter(prefix="/api/biometrics", tags=["Sovereign Facial Recognition & Biometrics (FRSS)"])

class VerifyRequest(BaseModel):
    threshold: float = 0.65

@router.get("/personnel")
def list_personnel():
    return {"personnel": face_engine.list_personnel()}

@router.post("/enroll")
async def enroll_personnel(
    name: str = Form(...),
    badge_id: str = Form(...),
    department: str = Form("Security Operations"),
    role: str = Form("Authorized Personnel"),
    is_authorized: bool = Form(True),
    photo: UploadFile = File(...)
):
    contents = await photo.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid photo data")

    try:
        record = face_engine.enroll_person(
            name=name,
            badge_id=badge_id,
            department=department,
            role=role,
            is_authorized=is_authorized,
            face_bgr=img
        )
        return {"status": "SUCCESS", "message": f"Successfully enrolled {name}", "record": record}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/personnel/{person_id}")
def delete_personnel(person_id: str):
    removed = face_engine.remove_person(person_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Personnel ID {person_id} not found")
    return {"status": "SUCCESS", "message": f"Revoked credentials for {person_id}"}

@router.post("/verify")
async def verify_face(threshold: float = Form(0.65), photo: UploadFile = File(...)):
    contents = await photo.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid face image")

    match_result = face_engine.match_face(img, threshold=threshold)
    mask_result = face_engine.detect_face_mask(img)

    return {
        "status": "SUCCESS",
        "match": match_result,
        "mask_compliance": mask_result
    }
