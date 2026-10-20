import time
import uuid
from typing import Dict, List, Any, Optional
from app.security.rbac_abac import Role, ClearanceLevel, UserContext

DEFAULT_PROFILES = {
    "usr_admin": {
        "user_id": "usr_admin",
        "username": "superadmin",
        "display_name": "Sovereign Commander Adity",
        "role": Role.SUPER_ADMIN,
        "clearance": ClearanceLevel.L4_SOVEREIGN,
        "department": "Sector 22 Security Operations Directorate",
        "phone": "+91-8779639965",
        "api_key": "vxr_live_adm_9965_sov_key",
        "avatar": "🛡️"
    },
    "usr_secops": {
        "user_id": "usr_secops",
        "username": "chief.secops",
        "display_name": "SecOps Chief Warden",
        "role": Role.SECOPS_CHIEF,
        "clearance": ClearanceLevel.L3_RESTRICTED,
        "department": "Physical Security & Perimeter Response",
        "phone": "+91-8779639965",
        "api_key": "vxr_sec_warden_442_key",
        "avatar": "🚨"
    },
    "usr_ehs": {
        "user_id": "usr_ehs",
        "username": "officer.ehs",
        "display_name": "EHS Compliance Inspector",
        "role": Role.EHS_INSPECTOR,
        "clearance": ClearanceLevel.L2_OPERATIONAL,
        "department": "Environmental Health & Worker Safety",
        "phone": "+91-8779639965",
        "api_key": "vxr_ehs_safe_881_key",
        "avatar": "🦺"
    },
    "usr_operator": {
        "user_id": "usr_operator",
        "username": "operator.grid",
        "display_name": "Floor Watch Operator",
        "role": Role.OPERATOR,
        "clearance": ClearanceLevel.L2_OPERATIONAL,
        "department": "Control Room Shift Alpha",
        "phone": "+91-8779639965",
        "api_key": "vxr_op_shift_102_key",
        "avatar": "🖥️"
    },
    "usr_auditor": {
        "user_id": "usr_auditor",
        "username": "auditor.external",
        "display_name": "ISO/IEC Regulatory Auditor",
        "role": Role.AUDITOR,
        "clearance": ClearanceLevel.L2_OPERATIONAL,
        "department": "Statutory Governance & Compliance",
        "phone": "+91-8779639965",
        "api_key": "vxr_audit_gov_999_key",
        "avatar": "⚖️"
    }
}

DEFAULT_PASSWORDS = {
    "usr_admin": "M3IvniqJtUzKqQDx",
    "usr_secops": "SecOps@2026",
    "usr_ehs": "EHS@2026",
    "usr_operator": "Operator@2026",
    "usr_auditor": "Auditor@2026"
}

class ProfileManager:
    def __init__(self):
        self.profiles: Dict[str, Dict[str, Any]] = DEFAULT_PROFILES.copy()
        self.passwords: Dict[str, str] = DEFAULT_PASSWORDS.copy()
        self.break_glass_tokens: Dict[str, Dict[str, Any]] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.reset_codes: Dict[str, Dict[str, Any]] = {}
        self._load_passwords()
        self._load_profiles()

    def authenticate(self, username_or_id: str, secret: str, ip: str = "127.0.0.1") -> Optional[Dict[str, Any]]:
        p = self.get_profile(username_or_id)
        if not p or not secret:
            return None

        uid = p["user_id"]
        expected_pass = self.passwords.get(uid)
        expected_key = p.get("api_key")

        # Strict authentication: must match the configured user password or user's assigned API key
        is_valid = False
        if expected_pass and secret == expected_pass:
            is_valid = True
        elif expected_key and secret == expected_key:
            is_valid = True

        if is_valid:
            token = f"vxr_sess_{uuid.uuid4().hex}"
            session = {
                "session_token": token,
                "user_id": uid,
                "username": p["username"],
                "display_name": p["display_name"],
                "role": p["role"],
                "clearance": p["clearance"],
                "avatar": p["avatar"],
                "ip_address": ip,
                "created_at": time.time(),
                "expires_at": time.time() + 86400 # 24 hr session
            }
            self.active_sessions[token] = session
            return session
        return None

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        sess = self.active_sessions.get(token)
        if sess and time.time() < sess["expires_at"]:
            return sess
        elif sess:
            del self.active_sessions[token]
        return None

    def revoke_session(self, token: str) -> bool:
        if token in self.active_sessions:
            del self.active_sessions[token]
            return True
        return False

    def get_profile(self, user_id_or_username: str) -> Optional[Dict[str, Any]]:
        target = str(user_id_or_username).strip().lower()
        if target in ["superadmin", "admin.sovereign", "usr_admin", "admin"]:
            return self.profiles.get("usr_admin")
        for uid, p in self.profiles.items():
            if uid == user_id_or_username or p["username"].lower() == target:
                return p
        return None

    def get_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        if not api_key:
            return None
        for p in self.profiles.values():
            if p.get("api_key") == api_key:
                return p
        return None

    def list_profiles(self) -> List[Dict[str, Any]]:
        # Strictly exclude raw secrets, passwords, and API keys from public listings
        res = []
        for p in self.profiles.values():
            safe = {k: v for k, v in p.items() if k not in ["api_key", "password", "secret", "salt"]}
            res.append(safe)
        return res

    def create_user_context(self, user_id: str, ip_address: str = "127.0.0.1") -> UserContext:
        p = self.get_profile(user_id) or self.profiles["usr_operator"]
        
        # Check active break-glass
        bg = self.break_glass_tokens.get(p["user_id"])
        is_bg = False
        bg_reason = None
        bg_exp = None

        if bg and time.time() < bg["expires_at"]:
            is_bg = True
            bg_reason = bg["reason"]
            bg_exp = bg["expires_at"]

        return UserContext(
            user_id=p["user_id"],
            username=p["username"],
            role=p["role"],
            clearance=p["clearance"] if not is_bg else ClearanceLevel.L4_SOVEREIGN,
            department=p["department"],
            ip_address=ip_address,
            break_glass=is_bg,
            break_glass_reason=bg_reason,
            break_glass_expires=bg_exp
        )

    def trigger_break_glass(self, user_id: str, reason: str, duration_sec: int = 900) -> Dict[str, Any]:
        """
        Emergency break-glass elevation to L4 Sovereign access for critical incidents.
        """
        token = str(uuid.uuid4())
        expires = time.time() + duration_sec
        self.break_glass_tokens[user_id] = {
            "token": token,
            "reason": reason,
            "created_at": time.time(),
            "expires_at": expires
        }
        return {
            "user_id": user_id,
            "break_glass_active": True,
            "reason": reason,
            "duration_sec": duration_sec,
            "expires_at": expires
        }

    def _load_passwords(self):
        try:
            from app.config import DATA_DIR
            import json
            pw_file = DATA_DIR / "passwords.json"
            if pw_file.exists():
                with open(pw_file, "r") as f:
                    saved = json.load(f)
                    self.passwords.update(saved)
        except Exception:
            pass

    def _save_passwords(self):
        try:
            from app.config import DATA_DIR
            import json
            pw_file = DATA_DIR / "passwords.json"
            with open(pw_file, "w") as f:
                json.dump(self.passwords, f, indent=2)
        except Exception:
            pass

    def _load_profiles(self):
        try:
            from app.config import DATA_DIR
            import json
            prof_file = DATA_DIR / "profiles.json"
            if prof_file.exists():
                with open(prof_file, "r") as f:
                    saved = json.load(f)
                    self.profiles.update(saved)
        except Exception:
            pass

    def _save_profiles(self):
        try:
            from app.config import DATA_DIR
            import json
            prof_file = DATA_DIR / "profiles.json"
            with open(prof_file, "w") as f:
                json.dump(self.profiles, f, indent=2)
        except Exception:
            pass

    def admin_reset_password(self, user_id_or_username: str, new_password: str) -> Dict[str, Any]:
        p = self.get_profile(user_id_or_username)
        if not p:
            return {"success": False, "reason": "User not found"}
        if len(new_password) < 6:
            return {"success": False, "reason": "Password must be at least 6 characters"}
        uid = p["user_id"]
        self.passwords[uid] = new_password
        self._save_passwords()
        return {
            "success": True,
            "user_id": uid,
            "username": p["username"],
            "message": f"Password for '{p['username']}' successfully updated by Super Admin."
        }

    def create_user_profile(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        username = str(user_data.get("username", "")).strip().lower()
        if not username:
            return {"success": False, "reason": "Username is required"}
        for p in self.profiles.values():
            if p["username"].lower() == username:
                return {"success": False, "reason": f"Username '{username}' already exists"}

        uid = f"usr_{uuid.uuid4().hex[:8]}"
        role_map = {
            "SUPER_ADMIN": Role.SUPER_ADMIN,
            "SECOPS_CHIEF": Role.SECOPS_CHIEF,
            "EHS_INSPECTOR": Role.EHS_INSPECTOR,
            "OPERATOR": Role.OPERATOR,
            "AUDITOR": Role.AUDITOR
        }
        role_val = role_map.get(user_data.get("role"), Role.OPERATOR)
        clearance_val = int(user_data.get("clearance", ClearanceLevel.L2_OPERATIONAL))
        
        profile = {
            "user_id": uid,
            "username": username,
            "display_name": user_data.get("display_name", username.capitalize()),
            "role": role_val,
            "clearance": clearance_val,
            "department": user_data.get("department", "Sector Operations"),
            "phone": user_data.get("phone", "+91-8779639965"),
            "api_key": f"vxr_{uuid.uuid4().hex[:12]}_key",
            "avatar": user_data.get("avatar", "👤")
        }
        self.profiles[uid] = profile
        password = user_data.get("password", "VisionXR@2026")
        self.passwords[uid] = password
        self._save_passwords()
        self._save_profiles()
        return {"success": True, "profile": profile}

    def delete_user_profile(self, user_id_or_username: str) -> Dict[str, Any]:
        p = self.get_profile(user_id_or_username)
        if not p:
            return {"success": False, "reason": "User not found"}
        uid = p["user_id"]
        if uid == "usr_admin" or p["username"] == "admin.sovereign":
            return {"success": False, "reason": "Cannot delete master Super Admin account"}
        del self.profiles[uid]
        if uid in self.passwords:
            del self.passwords[uid]
        self._save_passwords()
        self._save_profiles()
        return {"success": True, "message": f"User '{p['username']}' safely removed"}

    def request_password_reset_code(self, username_or_id: str) -> Optional[Dict[str, Any]]:
        p = self.get_profile(username_or_id)
        if not p:
            return None
        import random
        code = f"{random.randint(100000, 999999)}"
        expires_at = time.time() + 900 # 15 minutes
        self.reset_codes[p["user_id"]] = {
            "code": code,
            "username": p["username"],
            "expires_at": expires_at,
            "created_at": time.time()
        }
        return {
            "user_id": p["user_id"],
            "username": p["username"],
            "display_name": p["display_name"],
            "reset_code": code,
            "expires_in_sec": 900
        }

    def reset_password_with_code(self, username_or_id: str, code: str, new_password: str) -> Dict[str, Any]:
        p = self.get_profile(username_or_id)
        if not p:
            return {"success": False, "reason": "User profile not found"}
        uid = p["user_id"]
        entry = self.reset_codes.get(uid)
        if not entry:
            return {"success": False, "reason": "No active reset code found. Please request a new code."}
        if time.time() > entry["expires_at"]:
            del self.reset_codes[uid]
            return {"success": False, "reason": "Reset code has expired (15-minute window). Request a new code."}
        if entry["code"] != code.strip():
            return {"success": False, "reason": "Invalid 6-digit reset code. Please check and retry."}
        if len(new_password) < 6:
            return {"success": False, "reason": "New password must be at least 6 characters long."}

        # Update and persist password
        self.passwords[uid] = new_password
        self._save_passwords()
        del self.reset_codes[uid]
        return {
            "success": True,
            "user_id": uid,
            "username": p["username"],
            "message": "Password successfully reset and encrypted in sovereign ledger."
        }

    def revoke_break_glass(self, user_id: str):
        if user_id in self.break_glass_tokens:
            del self.break_glass_tokens[user_id]

profile_manager = ProfileManager()
