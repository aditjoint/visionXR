import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from shapely.geometry import Point, Polygon
from app.config import DATA_DIR

logger = logging.getLogger("visionxr.spatial")
ZONES_FILE = DATA_DIR / "zones.json"

class ZoneType:
    GREEN = "green"   # Operational corridor / safe path
    AMBER = "amber"   # Cautionary buffer / loitering alert
    RED = "red"       # High-hazard zero-tolerance alarm

DEFAULT_ZONES_PRESETS = {
    # All cameras start with a clean workspace (no autoset factory boundaries)
    "cam_01": [],
    "cam_02": [],
    "cam_03": [],
    "cam_04": []
}

class SpatialZoneEngine:
    def __init__(self):
        self.camera_zones: Dict[str, List[Dict[str, Any]]] = {}
        self.compiled_polygons: Dict[str, Dict[str, Polygon]] = {}
        self.load_zones()

    def load_zones(self):
        if ZONES_FILE.exists():
            try:
                with open(ZONES_FILE, "r") as f:
                    self.camera_zones = json.load(f)
                    logger.info("Loaded custom zones from file.")
            except Exception as e:
                logger.error(f"Error loading zones file: {e}. Fallback to presets.")
                self.camera_zones = DEFAULT_ZONES_PRESETS.copy()
        else:
            self.camera_zones = DEFAULT_ZONES_PRESETS.copy()
            self.save_zones()

        self._recompile_polygons()

    def save_zones(self):
        try:
            with open(ZONES_FILE, "w") as f:
                json.dump(self.camera_zones, f, indent=2)
            self._recompile_polygons()
        except Exception as e:
            logger.error(f"Failed to persist zones: {e}")

    def _recompile_polygons(self):
        self.compiled_polygons = {}
        for cam_id, zones in self.camera_zones.items():
            self.compiled_polygons[cam_id] = {}
            for zone in zones:
                pts = zone.get("polygon", [])
                if len(pts) >= 3:
                    try:
                        self.compiled_polygons[cam_id][zone["id"]] = Polygon(pts)
                    except Exception as err:
                        logger.warning(f"Invalid polygon for {zone.get('id')}: {err}")

    def get_zones_for_camera(self, cam_id: str) -> List[Dict[str, Any]]:
        return self.camera_zones.get(cam_id, [])

    def set_zones_for_camera(self, cam_id: str, zones: List[Dict[str, Any]]):
        self.camera_zones[cam_id] = zones
        self.save_zones()

    def check_point(self, cam_id: str, x: float, y: float) -> List[Dict[str, Any]]:
        """
        Evaluate if a point (x, y) resides inside any Green, Amber, or Red zones.
        Returns list of matching zone metadata.
        """
        matches = []
        if cam_id not in self.compiled_polygons:
            return matches

        p = Point(x, y)
        cam_zones = self.camera_zones.get(cam_id, [])
        for zone in cam_zones:
            poly = self.compiled_polygons[cam_id].get(zone["id"])
            if poly and (poly.contains(p) or poly.touches(p)):
                matches.append(zone)
        return matches

    def check_bbox(self, cam_id: str, bbox: List[float]) -> List[Dict[str, Any]]:
        """
        Evaluate bounding box [x1, y1, x2, y2]. Uses bottom-center of bounding box as ground contact point.
        """
        x1, y1, x2, y2 = bbox
        foot_x = (x1 + x2) / 2.0
        foot_y = y2  # ground contact point for pedestrian / machine
        return self.check_point(cam_id, foot_x, foot_y)
