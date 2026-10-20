import os
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from app.config import DATA_DIR, SNAPSHOTS_DIR

logger = logging.getLogger("visionxr.storage")
STORAGE_CONFIG_FILE = DATA_DIR / "storage_policy.json"

DEFAULT_STORAGE_POLICY = {
    "max_storage_mb": 100.0,     # Strict 100MB limit for developer machine
    "prune_threshold_pct": 85.0, # Prune when reaching 85% of quota
    "auto_pruning_enabled": True,
    "mount_partition": "/boot (nvme0n1p3)",
    "storage_path": str(DATA_DIR)
}

class StorageGovernanceEngine:
    def __init__(self):
        self.policy = DEFAULT_STORAGE_POLICY.copy()
        self.load_policy()

    def load_policy(self):
        if STORAGE_CONFIG_FILE.exists():
            try:
                with open(STORAGE_CONFIG_FILE, "r") as f:
                    self.policy.update(json.load(f))
            except Exception as e:
                logger.error(f"Error loading storage policy: {e}")
        else:
            self.save_policy()

    def save_policy(self):
        try:
            with open(STORAGE_CONFIG_FILE, "w") as f:
                json.dump(self.policy, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving storage policy: {e}")

    def get_storage_metrics(self) -> Dict[str, Any]:
        """Calculate exact disk consumption across snapshots and audit logs."""
        total_bytes = 0
        snapshot_bytes = 0
        snapshot_files = []
        log_bytes = 0

        # Scan snapshots
        if SNAPSHOTS_DIR.exists():
            for p in SNAPSHOTS_DIR.iterdir():
                if p.is_file():
                    sz = p.stat().st_size
                    total_bytes += sz
                    snapshot_bytes += sz
                    snapshot_files.append((p, p.stat().st_mtime, sz))

        # Scan audit and data files
        if DATA_DIR.exists():
            for p in DATA_DIR.iterdir():
                if p.is_file():
                    sz = p.stat().st_size
                    total_bytes += sz
                    log_bytes += sz

        total_mb = round(total_bytes / (1024 * 1024), 2)
        snapshot_mb = round(snapshot_bytes / (1024 * 1024), 2)
        log_mb = round(log_bytes / (1024 * 1024), 2)
        max_mb = self.policy.get("max_storage_mb", 100.0)
        usage_pct = round((total_mb / max_mb) * 100.0, 1) if max_mb > 0 else 0.0

        return {
            "total_used_mb": total_mb,
            "max_quota_mb": max_mb,
            "usage_pct": usage_pct,
            "snapshot_used_mb": snapshot_mb,
            "snapshot_count": len(snapshot_files),
            "logs_used_mb": log_mb,
            "mount_partition": "/boot (nvme0n1p3 365GB NVMe)",
            "storage_path": str(DATA_DIR),
            "quota_exceeded": total_mb > max_mb
        }

    def enforce_quota(self) -> Dict[str, Any]:
        """
        Enforce strict 100MB quota. If storage exceeds threshold,
        FIFO-prunes oldest evidence snapshots and trims audit logs.
        """
        metrics = self.get_storage_metrics()
        max_mb = self.policy.get("max_storage_mb", 100.0)
        threshold_mb = max_mb * (self.policy.get("prune_threshold_pct", 85.0) / 100.0)

        pruned_snapshots_count = 0
        bytes_freed = 0

        if metrics["total_used_mb"] > threshold_mb:
            logger.warning(f"Storage usage ({metrics['total_used_mb']} MB) exceeded threshold ({threshold_mb:.1f} MB). Pruning...")
            
            # 1. Prune oldest snapshots first (FIFO)
            if SNAPSHOTS_DIR.exists():
                snapshots = [(p, p.stat().st_mtime, p.stat().st_size) for p in SNAPSHOTS_DIR.iterdir() if p.is_file()]
                snapshots.sort(key=lambda x: x[1]) # Oldest first

                for p, mtime, sz in snapshots:
                    try:
                        p.unlink()
                        pruned_snapshots_count += 1
                        bytes_freed += sz
                        current_mb = metrics["total_used_mb"] - (bytes_freed / (1024 * 1024))
                        if current_mb <= (max_mb * 0.60): # Prune down to 60MB
                            break
                    except Exception as e:
                        logger.error(f"Failed to delete {p}: {e}")

            # 2. Trim audit ledger if still large (> 15MB)
            audit_file = DATA_DIR / "audit_ledger.json"
            if audit_file.exists() and audit_file.stat().st_size > (15 * 1024 * 1024):
                try:
                    with open(audit_file, "r") as f:
                        entries = json.load(f)
                    if len(entries) > 500:
                        trimmed = entries[-500:] # Keep last 500 entries
                        with open(audit_file, "w") as f:
                            json.dump(trimmed, f, indent=2)
                        logger.info("Trimmed audit ledger to last 500 entries for storage optimization.")
                except Exception as e:
                    logger.error(f"Failed to trim audit ledger: {e}")

        new_metrics = self.get_storage_metrics()
        return {
            "status": "QUOTA_ENFORCED",
            "pruned_snapshots_count": pruned_snapshots_count,
            "freed_mb": round(bytes_freed / (1024 * 1024), 2),
            "current_metrics": new_metrics
        }

    def set_max_quota(self, max_mb: float) -> Dict[str, Any]:
        self.policy["max_storage_mb"] = max(10.0, float(max_mb))
        self.save_policy()
        self.enforce_quota()
        return self.get_storage_metrics()

storage_governor = StorageGovernanceEngine()
