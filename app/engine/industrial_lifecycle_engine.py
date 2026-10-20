import time
import random
from typing import Dict, List, Any, Optional

class IndustrialLifecycleEngine:
    """
    Tracks materials across the complete industrial value chain:
    1. Raw Material Ingestion (Volumetric 3D scan, moisture, contamination).
    2. In-Process Manufacturing (Conveyor speed, vat agitation, dwell-time bottleneck).
    3. Finished Goods Verification (Pallet count, barcode/OCR, seal tear rejection).
    """
    def __init__(self):
        self.raw_materials: Dict[str, Dict[str, Any]] = {}
        self.in_process_batches: Dict[str, Dict[str, Any]] = {}
        self.finished_goods: Dict[str, Dict[str, Any]] = {}

    def _init_raw_materials(self) -> Dict[str, Dict[str, Any]]:
        return {
            "RAW_SILO_A": {
                "id": "RAW_SILO_A",
                "material": "Polymer Resin Pellets (High-Density PE)",
                "location": "Silo Yard 1 - Bay 4",
                "volume_m3": 142.5,
                "tonnage_metric": 128.2,
                "fill_level_pct": 74.5,
                "moisture_content_pct": 0.08, # Alert if > 0.2%
                "contamination_anomaly": False,
                "last_delivery_truck": "MH-04-AZ-8812",
                "status": "NOMINAL"
            },
            "RAW_TANK_B": {
                "id": "RAW_TANK_B",
                "material": "Industrial Solvents / Benzene Precursor",
                "location": "Tank Farm 3",
                "volume_m3": 85.0,
                "tonnage_metric": 76.5,
                "fill_level_pct": 85.0,
                "ullage_headspace_m3": 15.0,
                "contamination_anomaly": False,
                "status": "NOMINAL"
            }
        }

    def _init_in_process(self) -> Dict[str, Dict[str, Any]]:
        return {
            "BATCH_PROC_902": {
                "batch_id": "BATCH_PROC_902",
                "product": "Industrial Dielectric Insulation Layer",
                "line": "Conveyor Line 2 - Sector 22",
                "conveyor_speed_mps": 1.45, # meters per second
                "station": "Curing Oven Stage 3",
                "dwell_time_sec": 312,
                "target_dwell_sec": 300,
                "dwell_variance_status": "NORMAL", # OVER_DWELL or STARVATION
                "reactor_temp_c": 168.4,
                "agitation_rpm": 240,
                "defect_count": 0
            },
            "BATCH_PROC_903": {
                "batch_id": "BATCH_PROC_903",
                "product": "Composite Stamping Alloy Plate",
                "line": "Press Line Alpha",
                "conveyor_speed_mps": 0.85,
                "station": "Hydraulic Stamping Station",
                "dwell_time_sec": 420,
                "target_dwell_sec": 360,
                "dwell_variance_status": "OVER_DWELL_BOTTLENECK",
                "reactor_temp_c": 82.0,
                "defect_count": 1
            }
        }

    def _init_finished_goods(self) -> Dict[str, Dict[str, Any]]:
        return {
            "PALLET_FG_401": {
                "pallet_id": "PALLET_FG_401",
                "sku": "SKU-ISO-TRANSFORMER-OIL-DRUM",
                "batch_code": "LOT-2026-OCT-22",
                "verified_boxes_count": 48,
                "expected_count": 48,
                "count_match": True,
                "packaging_seal_intact": True,
                "shrinkwrap_tear_detected": False,
                "barcode_ocr_status": "VERIFIED_PASS",
                "destination_dock": "Dock 3 - Outbound Logistics",
                "rejection_kickout_active": False
            },
            "PALLET_FG_402": {
                "pallet_id": "PALLET_FG_402",
                "sku": "SKU-SECTOR22-MODULAR-CELL",
                "batch_code": "LOT-2026-OCT-23",
                "verified_boxes_count": 23,
                "expected_count": 24, # Missing 1 carton!
                "count_match": False,
                "packaging_seal_intact": False, # Puncture detected
                "shrinkwrap_tear_detected": True,
                "barcode_ocr_status": "MISMATCH_REJECT",
                "destination_dock": "Quarantine Staging Area",
                "rejection_kickout_active": True
            }
        }

    def update_metrics(self) -> Dict[str, Any]:
        """Dynamically simulate minor real-time variances in line speeds and tank levels."""
        for raw in self.raw_materials.values():
            raw["volume_m3"] = round(raw["volume_m3"] - random.uniform(0.01, 0.05), 2)
        return self.get_summary()

    def get_summary(self) -> Dict[str, Any]:
        return {
            "raw_materials": list(self.raw_materials.values()),
            "in_process_batches": list(self.in_process_batches.values()),
            "finished_goods": list(self.finished_goods.values()),
            "total_raw_tonnage": sum(r["tonnage_metric"] for r in self.raw_materials.values()),
            "active_batches_count": len(self.in_process_batches),
            "rejections_count": sum(1 for fg in self.finished_goods.values() if fg["rejection_kickout_active"])
        }

lifecycle_engine = IndustrialLifecycleEngine()
