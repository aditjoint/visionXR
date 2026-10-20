from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.engine.safety_rules_engine import safety_rules
from app.security.rbac_abac import PolicyEngine, Role
from app.security.profile_manager import profile_manager
from app.security.audit_logger import audit_logger

router = APIRouter(prefix="/api/governance/safety-rules", tags=["Super Admin Safety & Alarm Parameter Governance"])

class SafetyRulesUpdateRequest(BaseModel):
    user_id: str = "usr_admin"
    subject: Optional[Dict[str, Any]] = None
    object: Optional[Dict[str, Any]] = None
    escalation: Optional[Dict[str, Any]] = None

@router.get("")
def get_safety_rules():
    return {
        "status": "ACTIVE_PARAMETERS",
        "rules": safety_rules.get_rules(),
        "storage_backing": "NVMe Boot Sector (/boot/visionxr_storage/safety_rules.json)"
    }

@router.post("")
def update_safety_rules(req: SafetyRulesUpdateRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)

    # RBAC Enforcement: Super Admin or SecOps Chief only
    if user_ctx.role not in [Role.SUPER_ADMIN, Role.SECOPS_CHIEF]:
        audit_logger.log(
            actor=user_ctx.username,
            role=user_ctx.role,
            action="SAFETY_RULES_UPDATE_DENIED",
            resource="ALARM_GOVERNANCE_CORE",
            ip_address=ip,
            result="DENIED",
            details="Safety and alarm parameter modification restricted to SUPER_ADMIN"
        )
        raise HTTPException(status_code=403, detail="Governance Access Denied: Only Super Admin can modify alarm trigger parameters")

    update_payload = {}
    if req.subject:
        update_payload["subject"] = req.subject
    if req.object:
        update_payload["object"] = req.object
    if req.escalation:
        update_payload["escalation"] = req.escalation

    updated = safety_rules.update_rules(update_payload)

    # Chained SHA-256 Audit Seal
    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="SAFETY_PARAMETERS_UPDATED",
        resource="ALARM_GOVERNANCE_CORE",
        ip_address=ip,
        result="SUCCESS",
        details="Super Admin updated Subject & Object safety thresholds"
    )

    return {
        "status": "PARAMETERS_DEPLOYED",
        "governor": user_ctx.username,
        "active_rules": updated
    }

@router.post("/reset")
def reset_safety_rules(req: SafetyRulesUpdateRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    user_ctx = profile_manager.create_user_context(req.user_id, ip)
    if user_ctx.role != Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Resetting safety rules restricted to SUPER_ADMIN")

    res = safety_rules.reset_to_defaults()
    audit_logger.log(
        actor=user_ctx.username,
        role=user_ctx.role,
        action="SAFETY_PARAMETERS_RESET_DEFAULT",
        resource="ALARM_GOVERNANCE_CORE",
        ip_address=ip,
        result="SUCCESS",
        details="Super Admin reset safety rules to factory baseline"
    )
    return {"status": "RESET_TO_DEFAULTS", "rules": res}
