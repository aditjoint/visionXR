import os
import json
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import STATIC_DIR, SNAPSHOTS_DIR, HOST, PORT, DOMAIN
from app.security.ip_guard import ip_guard
from app.engine.stream_manager import stream_manager
from app.engine.offloader import offloader
from app.engine.inference_worker import pipeline
from app.engine.alert_bus import alert_bus
from app.engine.acoustic_engine import acoustic_engine

from app.api.routes_auth import router as auth_router
from app.api.routes_security import router as sec_router
from app.api.routes_stream import router as stream_router
from app.api.routes_zones import router as zones_router
from app.api.routes_alerts import router as alerts_router
from app.api.routes_sniffer import router as sniffer_router
from app.api.routes_materials import router as hazards_router
from app.api.routes_governance import router as governance_router
from app.api.routes_disasters import router as industrial_router
from app.api.routes_behavior import router as behavior_router
from app.api.routes_safety_rules import router as safety_rules_router
from app.api.routes_audio import router as audio_router
from app.api.routes_traffic_anpr import router as anpr_router
from app.api.routes_biometrics import router as biometrics_router
from app.api.routes_spatial_analytics import router as analytics_router
try:
    from app.api.routes_distribution import distribution_router
except ImportError:
    distribution_router = None
from app.engine.material_hazard_engine import material_hazard_tracker



logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("visionxr.main")

app = FastAPI(
    title="VisionXR Sovereign Surveillance & Behavioral AI Engine",
    description="Sector 22 Sovereign Multi-Format CCTV Ingestion, Tri-Zone Spatial Engine, Worker Pattern Analytics & Escalation Gateway",
    version="2.0.0"
)

# CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sovereign IP Protection Middleware
@app.middleware("http")
async def ip_protection_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "127.0.0.1"
    # Allow localhost / loopback unconditionally
    guard_decision = ip_guard.is_allowed(client_ip)
    if not guard_decision["allowed"]:
        return JSONResponse(
            status_code=403,
            content={"error": "Access Denied by VisionXR Sovereign IP Guard", "details": guard_decision}
        )
    response = await call_next(request)
    return response

# Anti-Cache Middleware for Static Assets & Real-time API
@app.middleware("http")
async def no_cache_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Mount APIs
app.include_router(auth_router)
app.include_router(sec_router)
app.include_router(stream_router)
app.include_router(zones_router)
app.include_router(alerts_router)
app.include_router(sniffer_router)
app.include_router(hazards_router)
app.include_router(governance_router)
app.include_router(industrial_router)
app.include_router(behavior_router)
app.include_router(safety_rules_router)
app.include_router(audio_router)
app.include_router(anpr_router)
app.include_router(biometrics_router)
app.include_router(analytics_router)
if distribution_router:
    app.include_router(distribution_router)



# Mount Static assets, evidence snapshots & PA broadcasts
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/data/snapshots", StaticFiles(directory=str(SNAPSHOTS_DIR)), name="snapshots")
os.makedirs("/var/www22/visionXR/data/pa_broadcasts", exist_ok=True)
app.mount("/data/pa_broadcasts", StaticFiles(directory="/var/www22/visionXR/data/pa_broadcasts"), name="pa_broadcasts")

@app.get("/", response_class=HTMLResponse)
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r") as f:
            return f.read()
    return "<h1>VisionXR Command Engine Initializing...</h1>"

@app.get("/api/health")
def health_check():
    return {
        "status": "SOVEREIGN_ONLINE",
        "sector": 22,
        "domain": DOMAIN,
        "cameras_active": len(stream_manager.list_cameras()),
        "siren_active": alert_bus.siren_active,
        "lockdown_active": alert_bus.lockdown_active,
        "curfew_active": pipeline.is_curfew_active(),
        "privacy_mode": pipeline.vision_ai.privacy_blur_enabled
    }

# Live Telemetry & Event Broadcast WebSocket
connected_clients = set()

@app.websocket("/ws/telemetry")
async def telemetry_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            # Build unified real-time dashboard telemetry
            cams_data = {}
            for cam in stream_manager.list_cameras():
                cid = cam["id"]
                cams_data[cid] = pipeline.get_camera_telemetry(cid)

            payload = {
                "type": "TELEMETRY_PULSE",
                "timestamp": asyncio.get_event_loop().time(),
                "cameras": cams_data,
                "recent_alerts": alert_bus.get_recent_alerts(12),
                "siren_active": alert_bus.siren_active,
                "lockdown_active": alert_bus.lockdown_active,
                "curfew_active": pipeline.is_curfew_active(),
                "acoustic": acoustic_engine.get_telemetry(),
                "hazards": material_hazard_tracker.list_active_hazards(),
                "offloader": offloader.get_offloader_stats()
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.25) # 4Hz balanced UI refresh (cool & smooth)
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    except Exception as e:
        connected_clients.discard(websocket)

@app.on_event("startup")
async def start_storage_guardian():
    async def storage_monitor_loop():
        from app.engine.storage_governance import storage_governor
        while True:
            try:
                storage_governor.enforce_quota()
            except Exception as e:
                logger.error(f"Storage guardian error: {e}")
            await asyncio.sleep(60.0) # Check every 60s
    asyncio.create_task(storage_monitor_loop())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
