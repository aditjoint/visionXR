#!/usr/bin/env python3
import os
import sys
import shutil
import tarfile
import zipfile
import compileall
import argparse
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.security.hardware_lock import (
    get_cross_platform_hardware_id,
    compute_developer_signature
)
from app.engine.license_manager import AVAILABLE_TASKS

def build_production_distribution(company_name: str,
                                 max_cameras: int,
                                 target_hwid: str,
                                 output_dir: str = "dist",
                                 version: str = "2.4.0"):
    """
    Builds a complete, unleft-dependency, IP-protected production distribution package.
    - Locks to single server hardware ID with Developer Master Key.
    - Strips all raw .py source files (compiles exclusively to .pyc bytecode).
    - Excludes 100% of .md documentation files.
    - Packages cross-platform Linux, Windows, and macOS installers.
    """
    print("========================================================================")
    print("    VISIONXR SOVEREIGN PRODUCTION PACKAGE BUILDER")
    print(f"    Target Customer : {company_name}")
    print(f"    Hardware Node   : {target_hwid}")
    print(f"    Camera Capacity : {max_cameras} channels (Developer Locked)")
    print("========================================================================")

    dist_path = Path(output_dir)
    dist_path.mkdir(parents=True, exist_ok=True)

    stage_name = f"visionxr-{company_name.lower().replace(' ', '-')}-{version}"
    stage_dir = dist_path / stage_name
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy Application Core Directories
    print("\n[1/7] Copying core runtime components...")
    for item in ["app", "static", "scripts"]:
        src = BASE_DIR / item
        dst = stage_dir / item
        if src.exists():
            shutil.copytree(src, dst)

    # Copy data templates (excluding live camera streams or temp files)
    (stage_dir / "config").mkdir(parents=True, exist_ok=True)
    (stage_dir / "data").mkdir(parents=True, exist_ok=True)
    for data_item in ["profiles.json", "passwords.json", "cameras.json"]:
        p = BASE_DIR / "data" / data_item
        if p.exists():
            shutil.copy2(p, stage_dir / "data" / data_item)

    # 2. Inject Customer Company Branding
    print(f"\n[2/7] Injecting customer branding: '{company_name}'...")
    client_config = {
        "company_name": company_name,
        "product_name": "VisionXR AI Sovereign Command Node",
        "version": version,
        "built_for_hardware_id": target_hwid,
        "max_allowed_cameras": max_cameras,
        "tamper_limit": 20
    }
    with open(stage_dir / "config" / "client_config.json", "w") as cf:
        import json
        json.dump(client_config, cf, indent=2)

    # Replace placeholder in static/index.html
    html_file = stage_dir / "static" / "index.html"
    if html_file.exists():
        html_content = html_file.read_text(encoding="utf-8")
        html_content = html_content.replace("SOVEREIGN ENTERPRISE NODE", company_name.upper())
        html_content = html_content.replace("ADAM CONSULT", company_name.upper())
        html_file.write_text(html_content, encoding="utf-8")

    # 3. Generate Hardware-Bound Developer License File
    print(f"\n[3/7] Generating Developer Master Lock Token for {target_hwid}...")
    features = [t["id"] for t in AVAILABLE_TASKS]
    dev_sig = compute_developer_signature(
        hardware_id=target_hwid,
        customer_name=company_name,
        max_cameras=max_cameras,
        tier="PRODUCTION_ENTERPRISE",
        features=features
    )
    license_obj = {
        "tier": "PRODUCTION_ENTERPRISE",
        "tier_name": f"VisionXR Single-Server Enterprise Node ({company_name})",
        "customer_name": company_name,
        "hardware_id": target_hwid,
        "max_cameras": max_cameras,
        "is_developer_machine": False,
        "features": features,
        "developer_signature": dev_sig,
        "camera_tasks": {
            f"cam_{i+1:02d}": ["TRI_ZONE_PERIMETER", "WORKER_PPE_SAFETY"]
            for i in range(max_cameras)
        }
    }
    with open(stage_dir / "developer.license", "w") as lf:
        import json
        json.dump(license_obj, lf, indent=2)

    # 4. Strict Exclusion of ALL Markdown (.md) Documentation Files
    print("\n[4/7] Enforcing strict IP sanitization: Excluding all .md files...")
    md_count = 0
    for p in stage_dir.rglob("*.md"):
        p.unlink()
        md_count += 1
    for p in stage_dir.rglob("*.markdown"):
        p.unlink()
        md_count += 1
    print(f"[+] Purged {md_count} markdown documentation files from distribution tree.")

    # Exclude developer-internal licensing and build utilities from customer distribution
    for dev_tool in ["build_distribution_package.py", "generate_developer_license.py", "keep_alive.sh", "auto_heal_watchdog.sh", "stop_visionxr.sh"]:
        dt_file = stage_dir / "scripts" / dev_tool
        if dt_file.exists():
            dt_file.unlink()

    # 5. IP Protection: Bytecode Compilation & Raw Source Stripping
    print("\n[5/7] IP Protection: Compiling Python to optimized .pyc and stripping .py sources...")
    # Compile all python files into bytecode with optimization level 2
    compileall.compile_dir(str(stage_dir / "app"), force=True, quiet=1, legacy=True, optimize=2)
    compileall.compile_dir(str(stage_dir / "scripts"), force=True, quiet=1, legacy=True, optimize=2)

    # Remove all raw .py files across the entire package tree (only leave compiled .pyc files)
    py_files_removed = 0
    for p in stage_dir.rglob("*.py"):
        p.unlink()
        py_files_removed += 1
    print(f"[+] Protected {py_files_removed} proprietary source code files into optimized bytecode.")

    # 6. Include Cross-Platform Installers
    print("\n[6/7] Packaging cross-platform installer scripts...")
    for scr in ["install_visionxr_linux.sh", "install_visionxr_windows.bat", "install_visionxr_macos.sh"]:
        s_src = BASE_DIR / "scripts" / scr
        if s_src.exists():
            shutil.copy2(s_src, stage_dir / scr)
            try:
                os.chmod(stage_dir / scr, 0o755)
            except Exception:
                pass

    # 7. Create Distribution Archives (tar.gz for Linux/macOS and .zip for Windows)
    print("\n[7/7] Compiling release distribution media archives...")
    tar_path = dist_path / f"{stage_name}.tar.gz"
    zip_path = dist_path / f"{stage_name}.zip"

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(stage_dir, arcname=stage_name)
    print(f"[+] Created Linux/macOS Release Archive: {tar_path} ({os.path.getsize(tar_path) // 1024} KB)")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(stage_dir):
            for file in files:
                abs_f = os.path.join(root, file)
                rel_f = os.path.relpath(abs_f, dist_path)
                zipf.write(abs_f, rel_f)
    print(f"[+] Created Windows Release Archive    : {zip_path} ({os.path.getsize(zip_path) // 1024} KB)")

    # Final Verification Scan
    assert not list(stage_dir.rglob("*.md")), "ERROR: Markdown files detected in distribution package!"
    assert not list(stage_dir.rglob("*.py")), "ERROR: Raw Python source files detected in distribution tree!"

    print("\n========================================================================")
    print("✓ PRODUCTION DISTRIBUTION PACKAGE BUILD COMPLETE!")
    print(f"  Distribution Folder : {stage_dir.resolve()}")
    print(f"  Linux/macOS Tarball : {tar_path.resolve()}")
    print(f"  Windows Zip Package : {zip_path.resolve()}")
    print("  Zero .md files      : VERIFIED")
    print("  Zero .py files      : VERIFIED (Full Bytecode Protection)")
    print(f"  Node Hardware Lock  : {target_hwid} (Locked & Signed)")
    print("  Self-Destruction    : Active (20 Tamper Attempts Threshold)")
    print("========================================================================")
    return stage_dir, tar_path, zip_path

def main():
    parser = argparse.ArgumentParser(description="VisionXR Sovereign Production Package Builder")
    parser.add_argument("--company-name", help="Customer Company Name (prompts interactively if not provided)")
    parser.add_argument("--max-cameras", type=int, default=8, help="Max Allowed Camera Feeds (default: 8)")
    parser.add_argument("--target-hwid", help="Target Server Hardware ID (defaults to current hardware)")
    parser.add_argument("--output-dir", default=str(BASE_DIR / "dist"), help="Output directory")
    args = parser.parse_args()

    company = args.company_name
    if not company:
        try:
            val = input("Enter Customer Company Name for Production Build [SOVEREIGN ENTERPRISE]: ").strip()
            company = val if val else "SOVEREIGN ENTERPRISE"
        except Exception:
            company = "SOVEREIGN ENTERPRISE"

    hwid = args.target_hwid or get_cross_platform_hardware_id()
    build_production_distribution(
        company_name=company,
        max_cameras=args.max_cameras,
        target_hwid=hwid,
        output_dir=args.output_dir
    )

if __name__ == "__main__":
    main()
