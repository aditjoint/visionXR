from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.security.ip_guard import ip_guard
from app.security.audit_logger import audit_logger
from app.security.rbac_abac import PolicyEngine
from app.security.profile_manager import profile_manager

router = APIRouter(prefix="/api/security", tags=["Security Governance & Audit"])

class IPActionRequest(BaseModel):
    ip_or_cidr: str

class PolicyTestRequest(BaseModel):
    user_id: str
    action: str
    resource_id: str = "general"

@router.get("/ip/rules")
def get_ip_rules():
    return ip_guard.get_stats()

@router.post("/ip/whitelist/add")
def add_whitelist(req: IPActionRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    ip_guard.add_whitelist(req.ip_or_cidr)
    audit_logger.log(
        actor="admin",
        role="SUPER_ADMIN",
        action="IP_WHITELIST_ADD",
        resource=req.ip_or_cidr,
        ip_address=ip,
        result="SUCCESS",
        details=f"Added {req.ip_or_cidr} to trusted IP whitelist"
    )
    return {"status": "SUCCESS", "rules": ip_guard.get_stats()}

@router.post("/ip/whitelist/remove")
def remove_whitelist(req: IPActionRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    ip_guard.remove_whitelist(req.ip_or_cidr)
    audit_logger.log(
        actor="admin",
        role="SUPER_ADMIN",
        action="IP_WHITELIST_REMOVE",
        resource=req.ip_or_cidr,
        ip_address=ip,
        result="SUCCESS",
        details=f"Removed {req.ip_or_cidr} from whitelist"
    )
    return {"status": "SUCCESS", "rules": ip_guard.get_stats()}

@router.post("/ip/blacklist/add")
def add_blacklist(req: IPActionRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    ip_guard.add_blacklist(req.ip_or_cidr)
    audit_logger.log(
        actor="admin",
        role="SUPER_ADMIN",
        action="IP_BLACKLIST_ADD",
        resource=req.ip_or_cidr,
        ip_address=ip,
        result="SUCCESS",
        details=f"Blacklisted threat IP: {req.ip_or_cidr}"
    )
    return {"status": "SUCCESS", "rules": ip_guard.get_stats()}

@router.post("/ip/blacklist/remove")
def remove_blacklist(req: IPActionRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    ip_guard.remove_blacklist(req.ip_or_cidr)
    return {"status": "SUCCESS", "rules": ip_guard.get_stats()}

@router.post("/policy/evaluate")
def evaluate_policy(req: PolicyTestRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    ctx = profile_manager.create_user_context(req.user_id, ip)
    decision = PolicyEngine.evaluate(ctx, req.action, req.resource_id)
    return {
        "user": ctx.dict(),
        "request": {"action": req.action, "resource": req.resource_id},
        "decision": decision
    }

@router.get("/audit/ledger")
def get_audit_ledger(limit: int = 100):
    return {
        "entries": audit_logger.get_entries(limit),
        "latest_hash": audit_logger.last_hash
    }

@router.get("/audit/verify")
def verify_audit_ledger():
    return audit_logger.verify_integrity()
