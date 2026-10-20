import time
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class Role:
    SUPER_ADMIN = "SUPER_ADMIN"
    SECOPS_CHIEF = "SECOPS_CHIEF"
    EHS_INSPECTOR = "EHS_INSPECTOR"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"

class ClearanceLevel:
    L1_BASIC = 1       # Green zone / public lobby
    L2_OPERATIONAL = 2 # General shopfloor / loading dock
    L3_RESTRICTED = 3  # Amber buffer / electrical switchyard
    L4_SOVEREIGN = 4   # Red zone / high-hazard / sovereign core

# Base RBAC Permissions Matrix
ROLE_PERMISSIONS = {
    Role.SUPER_ADMIN: [
        "stream:view", "stream:export", "ptz:control",
        "zones:view", "zones:edit",
        "alerts:view", "alerts:ack", "alerts:siren", "facility:lockdown",
        "security:ip_manage", "security:users_manage", "security:audit_read",
        "sniffer:scan", "governance:break_glass", "privacy:override",
        "camera:provision", "camera:deprovision"
    ],
    Role.SECOPS_CHIEF: [
        "stream:view", "stream:export", "ptz:control",
        "zones:view", "zones:edit",
        "alerts:view", "alerts:ack", "alerts:siren", "facility:lockdown",
        "security:audit_read", "sniffer:scan", "governance:break_glass"
    ],
    Role.EHS_INSPECTOR: [
        "stream:view", "zones:view", "alerts:view", "alerts:ack",
        "security:audit_read"
    ],
    Role.OPERATOR: [
        "stream:view", "zones:view", "alerts:view", "alerts:ack"
    ],
    Role.AUDITOR: [
        "stream:view", "zones:view", "alerts:view", "security:audit_read"
    ]
}

# Resource Clearance Requirements
RESOURCE_CLEARANCE = {
    "cam_01": ClearanceLevel.L2_OPERATIONAL,
    "cam_02": ClearanceLevel.L3_RESTRICTED,   # High hazard switchyard
    "cam_03": ClearanceLevel.L2_OPERATIONAL,
    "cam_04": ClearanceLevel.L2_OPERATIONAL,
    "red_zone": ClearanceLevel.L3_RESTRICTED,
    "evidence_vault": ClearanceLevel.L3_RESTRICTED,
    "security_admin": ClearanceLevel.L4_SOVEREIGN
}

class UserContext(BaseModel):
    user_id: str
    username: str
    role: str
    clearance: int
    department: str
    ip_address: str
    break_glass: bool = False
    break_glass_reason: Optional[str] = None
    break_glass_expires: Optional[float] = None

class PolicyEngine:
    """
    Unified RBAC + ABAC Policy Decision Point (PDP).
    Evaluates Subject, Resource, Action, and Environmental context.
    """
    @staticmethod
    def evaluate(user: UserContext, action: str, resource_id: str = "general", env_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        env_context = env_context or {}
        now = time.time()

        # 1. Break-Glass Emergency Elevation Check
        if user.break_glass:
            if user.break_glass_expires and now > user.break_glass_expires:
                return {
                    "allowed": False,
                    "reason": "Break-Glass emergency authorization expired",
                    "code": "BREAK_GLASS_EXPIRED"
                }
            return {
                "allowed": True,
                "reason": f"Authorized via Active Break-Glass elevation: {user.break_glass_reason}",
                "mode": "BREAK_GLASS_OVERRIDE"
            }

        # 2. RBAC Base Permission Check
        user_role_perms = ROLE_PERMISSIONS.get(user.role, [])
        if action not in user_role_perms and user.role != Role.SUPER_ADMIN:
            return {
                "allowed": False,
                "reason": f"Role '{user.role}' lacks base permission '{action}'",
                "code": "RBAC_DENIED"
            }

        # 3. ABAC Clearance Attribute Check
        required_clearance = RESOURCE_CLEARANCE.get(resource_id, ClearanceLevel.L1_BASIC)
        if user.clearance < required_clearance:
            return {
                "allowed": False,
                "reason": f"Insufficient clearance: user has L{user.clearance}, resource requires L{required_clearance}",
                "code": "ABAC_INSUFFICIENT_CLEARANCE"
            }

        # 4. ABAC Environmental Curfew Check
        is_curfew = env_context.get("is_curfew", False)
        if is_curfew and action in ["ptz:control", "facility:lockdown"] and user.clearance < ClearanceLevel.L3_RESTRICTED:
            return {
                "allowed": False,
                "reason": "Restricted action during active Curfew hours requires L3+ clearance",
                "code": "ABAC_CURFEW_RESTRICTION"
            }

        # 5. ABAC Network IP Integrity Check
        is_ip_trusted = env_context.get("ip_trusted", True)
        if not is_ip_trusted and action in ["zones:edit", "facility:lockdown", "security:ip_manage"]:
            return {
                "allowed": False,
                "reason": "High-risk administrative actions are restricted to trusted sovereign IP addresses",
                "code": "ABAC_UNTRUSTED_NETWORK"
            }

        return {
            "allowed": True,
            "reason": "Authorized by RBAC & ABAC Policy Matrix",
            "mode": "STANDARD_POLICY"
        }
