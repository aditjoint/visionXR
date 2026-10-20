import cv2
import time
import asyncio
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.engine.stream_manager import stream_manager
from app.engine.offloader import offloader
from app.engine.inference_worker import pipeline
from app.security.audit_logger import audit_logger

router = APIRouter(prefix="/api/stream", tags=["Streaming & Offloading Engine"])

class CameraSourceUpdate(BaseModel):
    source: str
    type: str = "rtsp"

class CameraDetailUpdate(BaseModel):
    name: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = "rtsp"
    location: Optional[str] = None

@router.get("/devices/discover")
def discover_devices():
    """Returns detected physical USB/V4L2 devices connected to the host."""
    return stream_manager.discover_physical_devices()

@router.get("/cameras")
def list_cameras():
    cams = stream_manager.list_cameras()
    result = []
    for c in cams:
        cid = c["id"]
        c_copy = c.copy()
        c_copy["viewers"] = offloader.get_subscriber_count(cid)
        c_copy["telemetry"] = pipeline.get_camera_telemetry(cid)
        result.append(c_copy)
    return result

@router.put("/cameras/{cam_id}")
def edit_camera(cam_id: str, req: CameraDetailUpdate):
    cam = stream_manager.get_camera(cam_id)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")
    new_src = req.source if req.source is not None else cam.get("source", "")
    new_type = req.type if req.type is not None else cam.get("type", "rtsp")
    stream_manager.update_camera_source(cam_id, new_src, new_type, name=req.name, location=req.location)
    audit_logger.log(
        actor="operator",
        role="OPERATOR",
        action="CAMERA_CONFIG_UPDATED",
        resource=cam_id,
        ip_address="127.0.0.22",
        result="SUCCESS",
        details=f"Updated camera {cam_id}: source={new_src}, name={req.name}, type={new_type}"
    )
    return {"status": "UPDATED", "camera": stream_manager.get_camera(cam_id)}

@router.delete("/cameras/{cam_id}")
def delete_camera(cam_id: str):
    success = stream_manager.deprovision_camera(cam_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")
    audit_logger.log(
        actor="operator",
        role="OPERATOR",
        action="CAMERA_DEPROVISIONED",
        resource=cam_id,
        ip_address="127.0.0.22",
        result="SUCCESS",
        details=f"Front-end operator deprovisioned feed {cam_id}"
    )
    return {"status": "DEPROVISIONED", "camera_id": cam_id}

@router.post("/cameras/{cam_id}/source")
def update_camera_source(cam_id: str, req: CameraSourceUpdate):
    stream_manager.update_camera_source(cam_id, req.source, req.type)
    audit_logger.log(
        actor="operator",
        role="OPERATOR",
        action="CAMERA_SOURCE_UPDATED",
        resource=cam_id,
        ip_address="127.0.0.22",
        result="SUCCESS",
        details=f"Updated source to: {req.source} ({req.type})"
    )
    return {"status": "UPDATED", "camera": stream_manager.get_camera(cam_id)}

@router.get("/{cam_id}/telemetry")
def get_telemetry(cam_id: str):
    return pipeline.get_camera_telemetry(cam_id)

@router.get("/{cam_id}/snapshot")
def get_snapshot(cam_id: str):
    frame = stream_manager.get_latest_frame(cam_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Camera stream offline")

    # Apply privacy obfuscation if enabled
    if pipeline.vision_ai.privacy_blur_enabled:
        faces = pipeline.vision_ai.detect_faces(frame)
        frame = pipeline.vision_ai.apply_privacy_obfuscation(frame, faces)

    ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ret:
        raise HTTPException(status_code=500, detail="Encoding failed")

    return Response(content=buffer.tobytes(), media_type="image/jpeg")

async def generate_mjpeg_frames(cam_id: str):
    last_frame_id = None
    last_jpeg_bytes = None
    while True:
        frame = stream_manager.get_latest_frame(cam_id)
        if frame is None:
            synth = stream_manager.synthesizers.get(cam_id)
            if synth:
                frame, _ = synth.render_frame()

        if frame is not None:
            if pipeline.vision_ai.privacy_blur_enabled:
                faces = pipeline.vision_ai.detect_faces(frame)
                frame = pipeline.vision_ai.apply_privacy_obfuscation(frame, faces)

            frame_id = id(frame)
            if frame_id == last_frame_id and last_jpeg_bytes is not None:
                frame_bytes = last_jpeg_bytes
            else:
                ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    frame_bytes = buffer.tobytes()
                    last_frame_id = frame_id
                    last_jpeg_bytes = frame_bytes
                else:
                    frame_bytes = None

            if frame_bytes:
                offloader.metrics["total_frames_served"] += 1
                offloader.metrics["bytes_served"] += len(frame_bytes)
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

        await asyncio.sleep(0.066) # ~15 FPS smooth surveillance cadence

@router.get("/{cam_id}/mjpeg")
def mjpeg_feed(cam_id: str):
    return StreamingResponse(
        generate_mjpeg_frames(cam_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.post("/privacy-toggle")
def toggle_privacy():
    current = pipeline.vision_ai.privacy_blur_enabled
    pipeline.vision_ai.privacy_blur_enabled = not current
    state = pipeline.vision_ai.privacy_blur_enabled
    audit_logger.log(
        actor="operator",
        role="OPERATOR",
        action="PRIVACY_OBFUSCATION_TOGGLE",
        resource="ALL_MONITORS",
        ip_address="127.0.0.22",
        result="SUCCESS",
        details=f"Privacy redaction set to {'ENABLED' if state else 'DISABLED'}"
    )
    return {"privacy_blur_enabled": state}

@router.get("/offloader/stats")
def get_offloader_stats():
    return offloader.get_offloader_stats()
