from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.security.profile_manager import profile_manager
from app.security.audit_logger import audit_logger

router = APIRouter(prefix="/api/auth", tags=["Authentication & Profiles"])

class BreakGlassRequest(BaseModel):
    user_id: str
    reason: str
    duration_sec: int = 900

class LoginRequest(BaseModel):
    username: str
    secret: str # Password or API key

@router.post("/login")
def login(req: LoginRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    sess = profile_manager.authenticate(req.username, req.secret, ip)
    if not sess:
        audit_logger.log(
            actor=req.username,
            role="UNKNOWN",
            action="LOGIN_FAILED",
            resource="VISIONXR_PORTAL",
            ip_address=ip,
            result="DENIED",
            details="Invalid username or password"
        )
        raise HTTPException(status_code=401, detail="Invalid username or authentication secret")

    audit_logger.log(
        actor=sess["username"],
        role=sess["role"],
        action="LOGIN_SUCCESS",
        resource="VISIONXR_PORTAL",
        ip_address=ip,
        result="SUCCESS",
        details=f"Authenticated with {sess['role']} clearance {sess['clearance']}"
    )
    return {
        "status": "AUTHENTICATED",
        "session": sess
    }

class LogoutRequest(BaseModel):
    session_token: str

@router.post("/logout")
def logout(req: LogoutRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    revoked = profile_manager.revoke_session(req.session_token)
    audit_logger.log(
        actor="user",
        role="OPERATOR",
        action="LOGOUT",
        resource="VISIONXR_PORTAL",
        ip_address=ip,
        result="SUCCESS",
        details="Session terminated"
    )
    return {"status": "LOGGED_OUT", "revoked": revoked}

@router.get("/session")
def check_session(token: str):
    sess = profile_manager.validate_session(token)
    if not sess:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {"status": "ACTIVE", "session": sess}

@router.get("/profiles")
def list_profiles():
    return profile_manager.list_profiles()

@router.get("/current")
def get_current_user(user_id: str = "usr_admin", request: Request = None):
    ip = request.client.host if request and request.client else "127.0.0.1"
    ctx = profile_manager.create_user_context(user_id, ip)
    profile = profile_manager.get_profile(user_id)
    safe_profile = {k: v for k, v in profile.items() if k not in ["api_key", "password", "secret"]} if profile else None
    return {
        "context": ctx.dict(),
        "profile": safe_profile
    }

@router.post("/break-glass/elevate")
def break_glass_elevate(req: BreakGlassRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    res = profile_manager.trigger_break_glass(req.user_id, req.reason, req.duration_sec)
    
    audit_logger.log(
        actor=req.user_id,
        role="BREAK_GLASS_ELEVATION",
        action="BREAK_GLASS_TRIGGERED",
        resource="SOVEREIGN_SYSTEM",
        ip_address=ip,
        result="SUCCESS",
        details=f"Emergency clearance elevation granted: {req.reason} ({req.duration_sec}s)"
    )
    return res

@router.post("/break-glass/revoke")
def break_glass_revoke(user_id: str, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    profile_manager.revoke_break_glass(user_id)
    audit_logger.log(
        actor=user_id,
        role="BREAK_GLASS_REVOCATION",
        action="BREAK_GLASS_REVOKED",
        resource="SOVEREIGN_SYSTEM",
        ip_address=ip,
        result="SUCCESS",
        details="Emergency elevation revoked."
    )
    return {"status": "REVOKED", "user_id": user_id}
 
class PasswordResetCodeRequest(BaseModel):
    username: str

class PasswordResetConfirmRequest(BaseModel):
    username: str
    reset_code: str
    new_password: str

@router.post("/reset-password/request")
def request_password_reset(req: PasswordResetCodeRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    res = profile_manager.request_password_reset_code(req.username)
    if not res:
        audit_logger.log(
            actor=req.username,
            role="UNKNOWN",
            action="PASSWORD_RESET_CODE_DENIED",
            resource="AUTH_PROFILE",
            ip_address=ip,
            result="DENIED",
            details="Password reset code requested for non-existent username."
        )
        raise HTTPException(status_code=404, detail="User account not found.")

    audit_logger.log(
        actor=res["username"],
        role="USER",
        action="PASSWORD_RESET_CODE_GENERATED",
        resource="AUTH_PROFILE",
        ip_address=ip,
        result="SUCCESS",
        details=f"6-digit reset code issued for {res['username']} (expires in 15m)."
    )
    return {
        "status": "RESET_CODE_GENERATED",
        "message": f"Verification code generated. Dispatching to verified contact: {res['username']}",
        "user_id": res["user_id"],
        "username": res["username"],
        "display_name": res["display_name"],
        "reset_code": res["reset_code"], # Displayed on screen / logged for local user verification
        "expires_in_sec": res["expires_in_sec"]
    }

@router.post("/reset-password/confirm")
def confirm_password_reset(req: PasswordResetConfirmRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    outcome = profile_manager.reset_password_with_code(req.username, req.reset_code, req.new_password)
    if not outcome.get("success"):
        audit_logger.log(
            actor=req.username,
            role="USER",
            action="PASSWORD_RESET_FAILED",
            resource="AUTH_PROFILE",
            ip_address=ip,
            result="DENIED",
            details=outcome.get("reason", "Invalid reset code")
        )
        raise HTTPException(status_code=400, detail=outcome.get("reason", "Failed to reset password"))

    audit_logger.log(
        actor=outcome["username"],
        role="USER",
        action="PASSWORD_RESET_SUCCESS",
        resource="AUTH_PROFILE",
        ip_address=ip,
        result="SUCCESS",
        details="Password successfully updated via verified reset code."
    )
    return {
        "status": "PASSWORD_UPDATED",
        "message": outcome["message"],
        "username": outcome["username"]
    }

class AdminPasswordResetRequest(BaseModel):
    user_id: str
    new_password: str

class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    role: str = "OPERATOR"
    clearance: int = 2
    department: str = "Operations"
    phone: str = "+91-8779639965"
    password: str = "VisionXR@2026"
    avatar: str = "👤"

@router.get("/users")
def get_all_users():
    profiles = profile_manager.list_profiles()
    return {"status": "ACTIVE_USERS", "total": len(profiles), "users": profiles}

@router.post("/users/create")
def create_user(req: CreateUserRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    res = profile_manager.create_user_profile(req.dict())
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("reason", "Could not create user"))
    audit_logger.log(
        actor="superadmin",
        role="SUPER_ADMIN",
        action="USER_PROVISIONED",
        resource=res["profile"]["username"],
        ip_address=ip,
        result="SUCCESS",
        details=f"New user {res['profile']['username']} provisioned with role {res['profile']['role']}"
    )
    return {"status": "USER_CREATED", "profile": res["profile"]}

@router.post("/users/admin-reset-password")
def admin_reset_password(req: AdminPasswordResetRequest, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    res = profile_manager.admin_reset_password(req.user_id, req.new_password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("reason", "Failed to reset password"))
    audit_logger.log(
        actor="superadmin",
        role="SUPER_ADMIN",
        action="ADMIN_PASSWORD_RESET",
        resource=res.get("username", req.user_id),
        ip_address=ip,
        result="SUCCESS",
        details=f"Direct password override applied by Super Admin for {res.get('username')}"
    )
    return {"status": "PASSWORD_RESET_SUCCESS", "message": res["message"]}

@router.delete("/users/{user_id}")
def delete_user(user_id: str, request: Request):
    ip = request.client.host if request and request.client else "127.0.0.1"
    res = profile_manager.delete_user_profile(user_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("reason", "Could not delete user"))
    audit_logger.log(
        actor="superadmin",
        role="SUPER_ADMIN",
        action="USER_DEPROVISIONED",
        resource=user_id,
        ip_address=ip,
        result="SUCCESS",
        details=res.get("message", "User deleted")
    )
    return {"status": "USER_DELETED", "message": res["message"]}
