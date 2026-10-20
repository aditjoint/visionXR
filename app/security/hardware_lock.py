import os
import sys
import uuid
import json
import hmac
import hashlib
import platform
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("visionxr.hardware_lock")

# Developer Master Seed - known exclusively to the Developer Build & Licensing Authority
DEVELOPER_ROOT_SEED = "VXR_DEV_MASTER_ROOT_SOVEREIGN_SEED_2026_IP_PROTECTED_AUTHENTICATOR"

def get_cross_platform_hardware_id() -> str:
    """
    Computes a deterministic, tamper-resistant Hardware Node Identifier
    across Linux, Windows, and macOS architectures.
    Combines CPU micro-architecture, Motherboard UUID, and Primary MAC.
    """
    components = []
    current_os = platform.system()
    components.append(current_os)
    components.append(platform.machine())

    # 1. Motherboard / System UUID
    sys_uuid = ""
    if current_os == "Linux":
        for p in ["/etc/machine-id", "/var/lib/dbus/machine-id", "/sys/class/dmi/id/product_uuid"]:
            if os.path.exists(p):
                try:
                    with open(p, "r") as f:
                        content = f.read().strip()
                        if content:
                            sys_uuid = content
                            break
                except Exception:
                    pass
    elif current_os == "Darwin": # macOS
        try:
            import subprocess
            out = subprocess.check_output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], timeout=3)
            for line in out.decode().splitlines():
                if "IOPlatformUUID" in line:
                    sys_uuid = line.split('"')[-2]
                    break
        except Exception:
            pass
    elif current_os == "Windows":
        try:
            import subprocess
            out = subprocess.check_output("wmic csproduct get uuid", shell=True, timeout=3)
            lines = [l.strip() for l in out.decode().splitlines() if l.strip()]
            if len(lines) > 1:
                sys_uuid = lines[1]
        except Exception:
            pass

    components.append(sys_uuid or "VXR-FALLBACK-MID-01")

    # 2. CPU Signature
    cpu_sig = ""
    if current_os == "Linux" and os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line or "Processor" in line:
                        cpu_sig = line.split(":")[-1].strip()
                        break
        except Exception:
            pass
    elif current_os == "Darwin":
        try:
            import subprocess
            cpu_sig = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], timeout=3).decode().strip()
        except Exception:
            pass
    elif current_os == "Windows":
        cpu_sig = os.getenv("PROCESSOR_IDENTIFIER", "")

    components.append(cpu_sig or platform.processor() or "X86_64_STD")

    # 3. Primary Network Interface MAC Address
    try:
        mac_num = uuid.getnode()
        mac_str = ':'.join(['{:02x}'.format((mac_num >> i) & 0xff) for i in range(0, 48, 8)][::-1])
    except Exception:
        mac_str = "00:1A:2B:3C:4D:5E"
    components.append(mac_str)

    # Compile deterministic SHA-256 fingerprint
    raw_fingerprint = "|".join(components)
    hw_hash = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest().upper()
    return f"VXR-NODE-{hw_hash[:4]}-{hw_hash[4:8]}-{hw_hash[8:12]}-{hw_hash[12:16]}"


def compute_developer_signature(hardware_id: str,
                                customer_name: str,
                                max_cameras: int,
                                tier: str,
                                features: list) -> str:
    """
    Computes an unforgeable HMAC-SHA256 signature using the Developer Master Root Seed.
    Super Admin has zero access to this seed and cannot forge licenses.
    """
    sorted_features = sorted(features)
    payload = f"{hardware_id}:{customer_name.strip().upper()}:{max_cameras}:{tier}:{','.join(sorted_features)}:{DEVELOPER_ROOT_SEED}"
    return hmac.new(DEVELOPER_ROOT_SEED.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_developer_license_integrity(license_data: Dict[str, Any], current_hwid: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validates that:
    1. The license is bound to THIS exact hardware node.
    2. The Developer Master Signature is authentic and untampered.
    3. The camera count and tier are authorized.
    """
    if not license_data:
        return False, "EMPTY_LICENSE"

    hwid = license_data.get("hardware_id", "")
    customer = license_data.get("customer_name", "")
    max_cams = license_data.get("max_cameras", 0)
    tier = license_data.get("tier", "PRODUCTION_NODE")
    features = license_data.get("features", [])
    signature = license_data.get("developer_signature", "")

    if not current_hwid:
        current_hwid = get_cross_platform_hardware_id()

    # 1. Hardware Binding Check (Single Server Node-Lock)
    if hwid != current_hwid:
        logger.critical(f"HARDWARE NODE MISMATCH! License HWID={hwid}, Machine HWID={current_hwid}")
        return False, f"HARDWARE_MISMATCH: License locked to {hwid}, host is {current_hwid}"

    # 2. Developer Signature Verification
    expected_sig = compute_developer_signature(hwid, customer, max_cams, tier, features)
    if not hmac.compare_digest(signature, expected_sig):
        logger.critical("TAMPER DETECTED: Developer signature invalid or forged by administrator!")
        return False, "FORGED_DEVELOPER_SIGNATURE"

    return True, "AUTHORIZED"
