import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from app.config import DATA_DIR

logger = logging.getLogger("visionxr.audit")
AUDIT_LOG_FILE = DATA_DIR / "audit_ledger.json"

class AuditLogger:
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self.last_hash: str = "0" * 64
        self.load_ledger()

    def load_ledger(self):
        if AUDIT_LOG_FILE.exists():
            try:
                with open(AUDIT_LOG_FILE, "r") as f:
                    self.entries = json.load(f)
                    if self.entries:
                        self.last_hash = self.entries[-1].get("entry_hash", "0" * 64)
            except Exception as e:
                logger.error(f"Error reading audit ledger: {e}")
                self.entries = []
                self.last_hash = "0" * 64
        else:
            self._record_genesis_block()

    def _record_genesis_block(self):
        genesis = {
            "entry_id": "genesis_000000",
            "timestamp": time.time(),
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "actor": "SYSTEM_CORE",
            "role": "SYSTEM",
            "action": "LEDGER_INITIALIZATION",
            "resource": "Sector22_VisionXR",
            "ip_address": "127.0.0.22",
            "result": "SUCCESS",
            "details": "Sovereign Audit Ledger Genesis Block initialized.",
            "prev_hash": "0" * 64
        }
        genesis_str = json.dumps(genesis, sort_keys=True)
        genesis["entry_hash"] = hashlib.sha256(genesis_str.encode()).hexdigest()
        self.entries.append(genesis)
        self.last_hash = genesis["entry_hash"]
        self._save_ledger()

    def _save_ledger(self):
        try:
            with open(AUDIT_LOG_FILE, "w") as f:
                json.dump(self.entries, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist audit ledger: {e}")

    def log(self, actor: str, role: str, action: str, resource: str, ip_address: str, result: str = "SUCCESS", details: str = "") -> Dict[str, Any]:
        """
        Record a cryptographically chained audit entry.
        """
        now = time.time()
        entry_data = {
            "entry_id": f"aud_{int(now * 1000)}_{len(self.entries)}",
            "timestamp": now,
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "actor": actor,
            "role": role,
            "action": action,
            "resource": resource,
            "ip_address": ip_address,
            "result": result,
            "details": details,
            "prev_hash": self.last_hash
        }
        # Compute SHA-256 seal
        hash_payload = json.dumps(entry_data, sort_keys=True)
        entry_hash = hashlib.sha256(hash_payload.encode()).hexdigest()
        entry_data["entry_hash"] = entry_hash

        self.entries.append(entry_data)
        self.last_hash = entry_hash
        self._save_ledger()

        return entry_data

    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verify the mathematical integrity of the SHA-256 audit hash chain.
        """
        if not self.entries:
            return {"valid": True, "count": 0, "message": "Ledger is empty"}

        expected_prev = "0" * 64
        for idx, entry in enumerate(self.entries):
            if idx > 0 and entry.get("prev_hash") != expected_prev:
                return {
                    "valid": False,
                    "tampered_index": idx,
                    "entry_id": entry.get("entry_id"),
                    "message": f"Hash chain broken at index {idx}: expected prev_hash {expected_prev}, got {entry.get('prev_hash')}"
                }
            
            # Recompute hash
            clone = entry.copy()
            claimed_hash = clone.pop("entry_hash", None)
            recalc = hashlib.sha256(json.dumps(clone, sort_keys=True).encode()).hexdigest()

            if recalc != claimed_hash:
                return {
                    "valid": False,
                    "tampered_index": idx,
                    "entry_id": entry.get("entry_id"),
                    "message": f"Data integrity violation at index {idx}: recomputed hash does not match seal!"
                }

            expected_prev = claimed_hash

        return {
            "valid": True,
            "total_entries": len(self.entries),
            "latest_hash": self.last_hash,
            "message": "Audit chain mathematically intact & verified against SHA-256 seals."
        }

    def get_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self.entries[-limit:]))

audit_logger = AuditLogger()
