from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from app.engine.stream_manager import stream_manager
from app.security.rbac_abac import PolicyEngine, Role
from app.security.profile_manager import profile_manager
from app.security.audit_logger import audit_logger

router = APIRouter(prefix="/api/governance", tags=["Super Admin Governance & Feed Provisioning"])

class CameraProvisionRequest(BaseModel):
    user_id: str = "usr_admin"
    id: str
    name: str
    source: str # rtsp://... or synth://...
    type: str = "rtsp"
    location: str
    fps: int = 25
    width: int = 854
    height: int = 480
    description: str = ""

class CameraDeprovisionRequest(BaseModel):
    user_id: str = "usr_admin"
    reason: str = "Decommissioned / Shift rotation"

@router.post("/cameras/provision")
def provision_camera(req: CameraProvisionRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)

    # ABAC / RBAC Policy Check
    decision = PolicyEngine.evaluate(user_ctx, "camera:provision", req.id)
    if not decision["allowed"]:
        audit_logger.log(
            actor=user_ctx.username,
            role=user_ctx.role,
            action="CAMERA_PROVISION_DENIED",
            resource=req.id,
            ip_address=ip,
            result="DENIED",
            details=decision["reason"]
        )
        raise HTTPException(status_code=403, detail=f"Governance Access Denied: {decision['reason']}")

    # Hardware & Developer Machine License Quota Check
    from app.engine.license_manager import license_manager
    current_count = len(stream_manager.list_cameras())
    lic_check = license_manager.can_provision_camera(current_count)
    if not lic_check["allowed"]:
        audit_logger.log(
            actor=user_ctx.username,
            role=user_ctx.role,
            action="CAMERA_PROVISION_LICENSE_EXCEEDED",
            resource=req.id,
            ip_address=ip,
            result="DENIED",
            details=lic_check["reason"]
        )
        raise HTTPException(status_code=403, detail=lic_check["reason"])

    cam_dict = {
        "id": req.id,
        "name": req.name,
        "source": req.source,
        "type": req.type,
        "location": req.location,
        "fps": req.fps,
        "width": req.width,
        "height": req.height,
        "description": req.description
    }

    provisioned = stream_manager.provision_camera(cam_dict)

    # Tamper-evident Audit Seal
    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="CAMERA_PROVISIONED",
        resource=req.id,
        ip_address=ip,
        result="SUCCESS",
        details=f"Super Admin provisioned feed: {req.name} ({req.source}) at {req.location}"
    )

    return {
        "status": "PROVISIONED",
        "governance_approval": decision["mode"],
        "camera": provisioned
    }

@router.delete("/cameras/{cam_id}/deprovision")
def deprovision_camera(cam_id: str, req: CameraDeprovisionRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)

    # ABAC / RBAC Policy Check
    decision = PolicyEngine.evaluate(user_ctx, "camera:deprovision", cam_id)
    if not decision["allowed"]:
        audit_logger.log(
            actor=user_ctx.username,
            role=user_ctx.role,
            action="CAMERA_DEPROVISION_DENIED",
            resource=cam_id,
            ip_address=ip,
            result="DENIED",
            details=decision["reason"]
        )
        raise HTTPException(status_code=403, detail=f"Governance Access Denied: {decision['reason']}")

    success = stream_manager.deprovision_camera(cam_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")

    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="CAMERA_DEPROVISIONED",
        resource=cam_id,
        ip_address=ip,
        result="SUCCESS",
        details=f"Super Admin deprovisioned feed {cam_id}. Reason: {req.reason}"
    )

    return {
        "status": "DEPROVISIONED",
        "camera_id": cam_id,
        "reason": req.reason,
        "governance_approval": decision["mode"]
    }

class StorageQuotaRequest(BaseModel):
    user_id: str = "usr_admin"
    max_storage_mb: float = 100.0

@router.get("/storage")
def get_storage_metrics():
    from app.engine.storage_governance import storage_governor
    return storage_governor.get_storage_metrics()

@router.post("/storage/quota")
def set_storage_quota(req: StorageQuotaRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)
    if user_ctx.role != Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Storage Quota modification restricted to SUPER_ADMIN")
    
    from app.engine.storage_governance import storage_governor
    res = storage_governor.set_max_quota(req.max_storage_mb)
    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="STORAGE_QUOTA_UPDATED",
        resource="BOOT_SECTOR_NVME",
        ip_address=ip,
        result="SUCCESS",
        details=f"Storage ceiling adjusted to {req.max_storage_mb} MB on /boot (nvme0n1p3)"
    )
    return res

@router.post("/storage/prune")
def prune_storage_now(request: Request):
    from app.engine.storage_governance import storage_governor
    return storage_governor.enforce_quota()

class EngineControlRequest(BaseModel):
    user_id: str = "usr_admin"
    action: str = "TOGGLE" # START, STOP, TOGGLE

@router.get("/engine/status")
def get_engine_status():
    from app.engine.inference_worker import pipeline
    return {
        "status": "RUNNING" if pipeline.is_active else "STOPPED",
        "is_active": pipeline.is_active
    }

@router.post("/engine/control")
def control_engine(req: EngineControlRequest, request: Request):
    from app.engine.inference_worker import pipeline
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)

    if user_ctx.role not in [Role.SUPER_ADMIN, Role.SECOPS_CHIEF]:
        raise HTTPException(status_code=403, detail="Engine start/stop restricted to SUPER_ADMIN")

    action = req.action.upper()
    if action == "START":
        pipeline.start_surveillance()
    elif action == "STOP":
        pipeline.stop_surveillance()
    elif action == "TOGGLE":
        pipeline.toggle_surveillance()

    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action=f"SURVEILLANCE_ENGINE_{'STARTED' if pipeline.is_active else 'STOPPED'}",
        resource="VISIONXR_CORE",
        ip_address=ip,
        result="SUCCESS",
        details=f"Master Surveillance Engine state set to: {'RUNNING' if pipeline.is_active else 'STOPPED'}"
    )
    return {
        "status": "RUNNING" if pipeline.is_active else "STOPPED",
        "is_active": pipeline.is_active
    }

class SubsystemResetRequest(BaseModel):
    user_id: str = "usr_admin"

@router.post("/subsystem/reset")
def reset_camera_subsystem(req: SubsystemResetRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)

    if user_ctx.role not in [Role.SUPER_ADMIN, Role.SECOPS_CHIEF]:
        raise HTTPException(status_code=403, detail="Camera subsystem reset restricted to SUPER_ADMIN clearance")

    res = stream_manager.reset_camera_subsystem()
    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="CAMERA_SUBSYSTEM_RESET",
        resource="V4L2_INGESTION_BUS",
        ip_address=ip,
        result="SUCCESS",
        details=f"Super Admin reset camera hardware subsystem. Logs & memory intact: {res.get('message')}"
    )
    return res

class LicenseActivationRequest(BaseModel):
    user_id: str = "usr_admin"
    license_key: str
    tier: str = "COMMERCIAL_ENTERPRISE"
    max_cameras: int = 16

class CameraTaskAssignRequest(BaseModel):
    user_id: str = "usr_admin"
    task_ids: List[str]

@router.get("/branding")
def get_branding():
    from app.config import CUSTOMER_COMPANY_NAME
    from app.security.hardware_lock import get_cross_platform_hardware_id
    from app.security.tamper_guard import tamper_guard
    return {
        "company_name": CUSTOMER_COMPANY_NAME,
        "hardware_id": get_cross_platform_hardware_id(),
        "tamper_remaining": tamper_guard.get_remaining_attempts()
    }

@router.get("/license")
def get_license():
    from app.engine.license_manager import license_manager
    info = license_manager.get_license_info()
    info["active_cameras"] = len(stream_manager.list_cameras())
    return info

@router.post("/license/activate")
def activate_license(req: LicenseActivationRequest, request: Request):
    from app.engine.license_manager import license_manager
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)
    if user_ctx.role != Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="License Activation restricted to SUPER_ADMIN")

    res = license_manager.apply_developer_license_key(req.license_key, actor=user_ctx.username)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))

    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="DEVELOPER_LICENSE_ACTIVATED",
        resource="VISIONXR_CORE",
        ip_address=ip,
        result="SUCCESS",
        details=f"Developer Node License activated: {res.get('message')}"
    )
    return res

class LicenseQuotaRequest(BaseModel):
    user_id: str = "usr_admin"
    license_key: str

@router.post("/license/quota")
def update_license_quota(req: LicenseQuotaRequest, request: Request):
    from app.engine.license_manager import license_manager
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)
    if user_ctx.role != Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="License Quota elevation restricted to SUPER_ADMIN")

    res = license_manager.apply_developer_license_key(req.license_key, actor=user_ctx.username)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/cameras/{cam_id}/tasks")
def get_camera_tasks(cam_id: str):
    from app.engine.license_manager import license_manager, AVAILABLE_TASKS
    tasks = license_manager.license_data.get("camera_tasks", {}).get(cam_id, [])
    return {
        "camera_id": cam_id,
        "assigned_tasks": tasks,
        "available_tasks": AVAILABLE_TASKS
    }

@router.post("/cameras/{cam_id}/tasks")
def assign_camera_tasks(cam_id: str, req: CameraTaskAssignRequest, request: Request):
    from app.engine.license_manager import license_manager
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)
    if user_ctx.role not in [Role.SUPER_ADMIN, Role.SECOPS_CHIEF]:
        raise HTTPException(status_code=403, detail="Task assignment restricted to SUPER_ADMIN / SECOPS")

    res = license_manager.assign_camera_tasks(cam_id, req.task_ids)
    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="CAMERA_TASKS_ASSIGNED",
        resource=cam_id,
        ip_address=ip,
        result="SUCCESS",
        details=f"Assigned tasks: {', '.join(req.task_ids)}"
    )
    return res

class PPEToggleRequest(BaseModel):
    user_id: str = "usr_admin"
    enabled: Optional[bool] = None
    enable: Optional[bool] = None
    require_vest: Optional[bool] = None
    require_helmet: Optional[bool] = None

@router.get("/ppe-status")
def get_ppe_status():
    from app.engine.safety_rules_engine import safety_rules
    sub = safety_rules.get_rules().get("subject", {})
    vest = sub.get("require_ppe_vest", True)
    helmet = sub.get("require_ppe_helmet", True)
    return {
        "ppe_enforced": vest or helmet,
        "require_ppe_vest": vest,
        "require_ppe_helmet": helmet
    }

@router.post("/toggle-ppe")
def toggle_ppe_governance(req: PPEToggleRequest, request: Request):
    from app.engine.safety_rules_engine import safety_rules
    from app.engine.alert_bus import alert_bus
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)
    if user_ctx.role not in [Role.SUPER_ADMIN, Role.SECOPS_CHIEF]:
        raise HTTPException(status_code=403, detail="PPE Compliance Policy modification restricted to SUPER_ADMIN")

    sub = safety_rules.get_rules().get("subject", {})
    target_state = req.enabled if req.enabled is not None else req.enable
    if target_state is not None:
        new_vest = target_state
        new_helmet = target_state
    else:
        new_vest = req.require_vest if req.require_vest is not None else sub.get("require_ppe_vest", True)
        new_helmet = req.require_helmet if req.require_helmet is not None else sub.get("require_ppe_helmet", True)

    safety_rules.update_rules({
        "subject": {
            "require_ppe_vest": new_vest,
            "require_ppe_helmet": new_helmet
        }
    })

    # If disabled, immediately clear any PPE violation alerts from event bus
    if not (new_vest or new_helmet):
        alert_bus.alerts = [a for a in alert_bus.alerts if a.get("type") != "PPE_VIOLATION"]

    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="PPE_POLICY_UPDATED",
        resource="SAFETY_GOVERNANCE",
        ip_address=ip,
        result="SUCCESS",
        details=f"Super Admin updated PPE enforcement: vest={new_vest}, helmet={new_helmet}"
    )

    return {
        "status": "UPDATED",
        "ppe_enforced": new_vest or new_helmet,
        "require_ppe_vest": new_vest,
        "require_ppe_helmet": new_helmet
    }
