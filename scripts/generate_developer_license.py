#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security.hardware_lock import (
    compute_developer_signature,
    get_cross_platform_hardware_id,
    verify_developer_license_integrity
)
from app.engine.license_manager import AVAILABLE_TASKS

def main():
    parser = argparse.ArgumentParser(description="VisionXR Developer Master License Generation Tool")
    parser.add_argument("--hwid", help="Target Server Hardware ID (e.g. VXR-NODE-8369-029A-0CC1-D6A7). Defaults to current server hardware.")
    parser.add_argument("--company", help="Customer Company Name (e.g. ACME Industrial)", default="SOVEREIGN ENTERPRISE")
    parser.add_argument("--cameras", type=int, help="Maximum Allowed Camera Feeds", default=8)
    parser.add_argument("--tier", help="License Tier", default="PRODUCTION_ENTERPRISE")
    parser.add_argument("--output", help="Output path for developer.license file", default="developer.license")
    args = parser.parse_args()

    hwid = args.hwid or get_cross_platform_hardware_id()
    customer_name = args.company.strip().upper()
    max_cameras = args.cameras
    tier = args.tier
    features = [t["id"] for t in AVAILABLE_TASKS]

    sig = compute_developer_signature(
        hardware_id=hwid,
        customer_name=customer_name,
        max_cameras=max_cameras,
        tier=tier,
        features=features
    )

    license_data = {
        "tier": tier,
        "tier_name": f"VisionXR Production License ({customer_name})",
        "customer_name": customer_name,
        "hardware_id": hwid,
        "max_cameras": max_cameras,
        "is_developer_machine": False,
        "features": features,
        "developer_signature": sig,
        "camera_tasks": {
            f"cam_{i+1:02d}": ["TRI_ZONE_PERIMETER", "WORKER_PPE_SAFETY"]
            for i in range(max_cameras)
        }
    }

    # Verify self-integrity
    valid, reason = verify_developer_license_integrity(license_data, hwid)
    if not valid:
        print(f"[!] Critical Error: Generated license failed verification: {reason}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(license_data, f, indent=2)

    print("===================================================================")
    print("✓ DEVELOPER NODE-LOCKED LICENSE GENERATED SUCCESSFULLY")
    print("===================================================================")
    print(f"Customer Name : {customer_name}")
    print(f"Hardware Node : {hwid}")
    print(f"Max Cameras   : {max_cameras}")
    print(f"Tier          : {tier}")
    print(f"Signature     : {sig}")
    print(f"License File  : {out_path.resolve()}")
    print("===================================================================")

if __name__ == "__main__":
    main()
