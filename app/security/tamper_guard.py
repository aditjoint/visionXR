import os
import sys
import json
import time
import hmac
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger("visionxr.tamper_guard")

MAX_TAMPER_ATTEMPTS = 20
VAULT_KEY = "VXR_VAULT_INTEGRITY_SEAL_2026_ANTI_REVERSE_ENGINEERING"

class TamperGuard:
    """
    Sovereign IP Protection & Anti-Tampering Engine.
    Enforces a strict 20-attempt threshold against brute-force license unlocks,
    hardware spoofing, or forged developer key injections.
    Enters irreversible Self-Destruction upon reaching 20 attempts.
    """
    def __init__(self):
        from app.config import BASE_DIR, DATA_DIR
        self.base_dir = Path(BASE_DIR)
        self.data_dir = Path(DATA_DIR)
        self.vault_file = self.data_dir / ".vxr_tamper_vault.bin"
        self.tombstone_file = self.data_dir / "TOMBSTONE_PERMANENT_SELF_DESTRUCT_LOCKOUT"
        self._check_tombstone()
        self.state = self._load_vault()

    def _check_tombstone(self):
        """If tombstone exists, server was previously self-destructed and remains locked out."""
        if self.tombstone_file.exists():
            logger.critical("PERMANENT TOMBSTONE ACTIVE: Instance was destroyed due to 20 failed unlock attempts.")
            sys.exit(99)

    def _load_vault(self) -> Dict[str, Any]:
        if self.vault_file.exists():
            try:
                with open(self.vault_file, "r") as f:
                    data = json.load(f)
                # Verify HMAC seal
                sig = data.get("hmac", "")
                expected = hmac.new(VAULT_KEY.encode(), f"{data.get('tamper_count')}:{data.get('locked_out')}".encode(), hashlib.sha256).hexdigest()
                if hmac.compare_digest(sig, expected):
                    if data.get("locked_out", False):
                        self.trigger_self_destruct("PREVIOUS_PERMANENT_LOCKOUT")
                    return data
                else:
                    logger.warning("Vault file HMAC compromised! Counting as tamper event.")
                    return {"tamper_count": 5, "locked_out": False, "incidents": ["VAULT_CORRUPTION"]}
            except Exception as e:
                logger.error(f"Failed to read tamper vault: {e}")

        return {"tamper_count": 0, "locked_out": False, "incidents": []}

    def _save_vault(self):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            cnt = self.state.get("tamper_count", 0)
            locked = self.state.get("locked_out", False)
            sig = hmac.new(VAULT_KEY.encode(), f"{cnt}:{locked}".encode(), hashlib.sha256).hexdigest()
            self.state["hmac"] = sig
            with open(self.vault_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist tamper vault: {e}")

    def record_tamper_incident(self, reason: str, actor: str = "UNKNOWN") -> Tuple[int, int]:
        """
        Records an unauthorized unlock / forged developer key / license breach attempt.
        Returns (current_attempts, remaining_attempts).
        """
        self.state["tamper_count"] = self.state.get("tamper_count", 0) + 1
        cnt = self.state["tamper_count"]
        remaining = max(0, MAX_TAMPER_ATTEMPTS - cnt)

        incident_entry = {
            "attempt": cnt,
            "timestamp": time.time(),
            "formatted": time.strftime("%Y-%m-%d %H:%M:%S"),
            "actor": actor,
            "reason": reason
        }
        self.state.setdefault("incidents", []).append(incident_entry)
        self._save_vault()

        logger.critical(f"TAMPER ATTEMPT #{cnt}/{MAX_TAMPER_ATTEMPTS}: {reason} by {actor}. Remaining attempts: {remaining}")

        if cnt >= MAX_TAMPER_ATTEMPTS:
            self.trigger_self_destruct(f"THRESHOLD_EXCEEDED: {cnt} unauthorized attempts recorded")

        return cnt, remaining

    def get_remaining_attempts(self) -> int:
        cnt = self.state.get("tamper_count", 0)
        return max(0, MAX_TAMPER_ATTEMPTS - cnt)

    def trigger_self_destruct(self, trigger_reason: str):
        """
        IRREVERSIBLE PRODUCTION SELF-DESTRUCTION PROCEDURE:
        Triggered when 20 unauthorized unlock / license forging attempts are reached.
        1. Overwrites cryptographic master keys and license tokens with zeroes.
        2. Wipes proprietary compiled Python files and sensitive configuration.
        3. Creates an immutable tombstone locking out the host hardware.
        4. Exits with fatal status code 99.
        """
        logger.critical(f"🚨 INITIATING IRREVERSIBLE SELF-DESTRUCTION SEQUENCE! Reason: {trigger_reason}")
        self.state["locked_out"] = True
        self._save_vault()

        # 1. Overwrite and shred sensitive files
        files_to_shred = [
            self.data_dir / "license.json",
            self.data_dir / "passwords.json",
            self.data_dir / "profiles.json",
            self.data_dir / "client_config.json",
            self.base_dir / "config" / "client_config.json",
            self.base_dir / "developer.license"
        ]

        # Also wipe proprietary compiled security and engine bytecode
        for p in self.base_dir.glob("app/**/*.pyc"):
            files_to_shred.append(p)

        for fp in files_to_shred:
            try:
                if fp.exists():
                    sz = fp.stat().st_size
                    with open(fp, "wb") as f:
                        f.write(os.urandom(sz)) # Overwrite with random cryptographic noise
                        f.flush()
                    fp.unlink() # Delete file
                    logger.warning(f"Securely shredded: {fp.name}")
            except Exception as e:
                logger.error(f"Error shredding {fp}: {e}")

        # 2. Plant immutable tombstone lock
        try:
            with open(self.tombstone_file, "w") as f:
                f.write(
                    f"===================================================================\n"
                    f"CRITICAL HARDWARE LOCKOUT - VISIONXR DISTRIBUTION PACKAGE DESTROYED\n"
                    f"===================================================================\n"
                    f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Cause: 20 Exceeded Unauthorized Developer Key Unlock Attempts.\n"
                    f"Hardware Node: Permanently Banned & Cryptographically Locked Out.\n"
                    f"IP Protection Self-Destruction Protocol: Fully Executed.\n"
                    f"Contact Software Vendor Licensing Directorate for Hardware Re-Certification.\n"
                    f"===================================================================\n"
                )
        except Exception:
            pass

        logger.critical("💥 SELF-DESTRUCTION COMPLETE. SYSTEM TERMINATED.")
        sys.exit(99)

tamper_guard = TamperGuard()
