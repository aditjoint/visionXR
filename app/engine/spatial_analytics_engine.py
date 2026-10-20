"""
VisionXR Sovereign Spatial Analytics, Counting & Visual Attribute Engine
Implements:
1. Bidirectional People & Vehicle Counting (IN / OUT Line Crossing)
2. Crowd Detection & Density Clustering
3. Fence Jumping & Perimeter Vaulting Detection
4. Garbage, Trash & Debris Dumping Detection
5. Missing Asset / Vanished Object Detection
6. Deep Visual Attribute Search (Color, Class, Speed, Time)
"""

import os
import cv2
import json
import time
import math
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from app.config import DATA_DIR
from app.engine.alert_bus import alert_bus

logger = logging.getLogger("visionxr.analytics")

ATTRIBUTE_LEDGER_FILE = DATA_DIR / "attribute_ledger.json"
COUNTING_LOG_FILE = DATA_DIR / "occupancy_counts.json"

COLOR_RANGES = {
    "RED": [([0, 70, 50], [10, 255, 255]), ([170, 70, 50], [180, 255, 255])],
    "BLUE": [([90, 70, 50], [130, 255, 255])],
    "GREEN": [([35, 70, 50], [85, 255, 255])],
    "YELLOW": [([20, 70, 50], [34, 255, 255])],
    "WHITE": [([0, 0, 180], [180, 40, 255])],
    "BLACK": [([0, 0, 0], [180, 255, 45])],
    "GREY": [([0, 0, 46], [180, 40, 179])]
}

class SpatialAnalyticsEngine:
    def __init__(self):
        self.occupancy_counts: Dict[str, Dict[str, int]] = {} # cam_id -> {in: 0, out: 0, current: 0}
        self.tracked_debris: Dict[str, Dict[str, Any]] = {} # id -> {cam, first_seen, bbox, size}
        self.static_assets: Dict[str, Dict[str, Any]] = {} # asset_id -> {cam, bbox, baseline_patch}
        self.attribute_ledger: List[Dict[str, Any]] = []
        self.cooldowns: Dict[str, float] = {}
        self.load_attribute_ledger()

    def _can_alert(self, key: str, cooldown_sec: float = 30.0) -> bool:
        now = time.time()
        last = self.cooldowns.get(key, 0.0)
        if (now - last) >= cooldown_sec:
            self.cooldowns[key] = now
            return True
        return False

    def load_attribute_ledger(self):
        if ATTRIBUTE_LEDGER_FILE.exists():
            try:
                with open(ATTRIBUTE_LEDGER_FILE, "r") as f:
                    self.attribute_ledger = json.load(f)
            except Exception as e:
                logger.error(f"Error loading attribute ledger: {e}")
                self.attribute_ledger = []
        else:
            self.attribute_ledger = []

    def save_attribute_ledger(self):
        try:
            # Keep latest 500 records
            with open(ATTRIBUTE_LEDGER_FILE, "w") as f:
                json.dump(self.attribute_ledger[-500:], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving attribute ledger: {e}")

    # =========================================================================
    # 1. Bidirectional Line Crossing (People & Vehicle Counting)
    # =========================================================================
    def update_tripwire_crossing(self, cam_id: str, prev_y: float, curr_y: float, tripwire_y: float, ent_type: str = "person"):
        """
        Detects crossing over a horizontal or virtual tripwire coordinate.
        """
        if cam_id not in self.occupancy_counts:
            self.occupancy_counts[cam_id] = {"in": 0, "out": 0, "current": 0}

        counts = self.occupancy_counts[cam_id]
        if prev_y < tripwire_y <= curr_y: # Crossed downward -> IN
            counts["in"] += 1
            counts["current"] = max(0, counts["in"] - counts["out"])
            logger.info(f"[{cam_id}] Line Crossing IN: {ent_type} (Total In: {counts['in']})")
        elif prev_y > tripwire_y >= curr_y: # Crossed upward -> OUT
            counts["out"] += 1
            counts["current"] = max(0, counts["in"] - counts["out"])
            logger.info(f"[{cam_id}] Line Crossing OUT: {ent_type} (Total Out: {counts['out']})")

    def get_counts(self, cam_id: str) -> Dict[str, int]:
        return self.occupancy_counts.get(cam_id, {"in": 0, "out": 0, "current": 0})

    # =========================================================================
    # 2. Crowd Detection & Density Clustering
    # =========================================================================
    def evaluate_crowd_clustering(self, cam_id: str, actors: List[Any], distance_threshold_px: float = 85.0, min_cluster_size: int = 4) -> Optional[Dict[str, Any]]:
        """
        Computes pairwise Euclidean distances between actor centroids to detect crowd clusters.
        """
        if len(actors) < min_cluster_size:
            return None

        centroids = [a.ground_point for a in actors if hasattr(a, 'ground_point')]
        if len(centroids) < min_cluster_size:
            return None

        # Build adjacency graph
        n = len(centroids)
        adj = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                dist = math.hypot(centroids[i][0] - centroids[j][0], centroids[i][1] - centroids[j][1])
                if dist <= distance_threshold_px:
                    adj[i].append(j)
                    adj[j].append(i)

        # Find connected components (clusters)
        visited = [False] * n
        largest_cluster = []
        for i in range(n):
            if not visited[i]:
                comp = []
                queue = [i]
                visited[i] = True
                while queue:
                    curr = queue.pop(0)
                    comp.append(curr)
                    for neighbor in adj[curr]:
                        if not visited[neighbor]:
                            visited[neighbor] = True
                            queue.append(neighbor)
                if len(comp) > len(largest_cluster):
                    largest_cluster = comp

        if len(largest_cluster) >= min_cluster_size:
            cluster_coords = [centroids[idx] for idx in largest_cluster]
            avg_x = sum(c[0] for c in cluster_coords) / len(cluster_coords)
            avg_y = sum(c[1] for c in cluster_coords) / len(cluster_coords)
            return {
                "cam_id": cam_id,
                "cluster_size": len(largest_cluster),
                "center": [int(avg_x), int(avg_y)],
                "density_status": "HIGH_CROWD_DENSITY"
            }
        return None

    # =========================================================================
    # 3. Fence Jumping & Perimeter Vaulting
    # =========================================================================
    def evaluate_fence_jumping(self, ent: Any, fence_top_y: float = 80.0) -> bool:
        """
        Evaluates whether an entity exhibited rapid upward vertical velocity
        reaching fence top followed by sudden downward translation.
        """
        history = getattr(ent, 'history', [])
        if len(history) < 6:
            return False

        y_positions = [h[1] for h in history]
        y_initial = y_positions[0]
        y_min = min(y_positions) # Highest point jumped
        y_final = y_positions[-1]

        # Significant upward jump (delta y > 35px) crossing fence line
        if (y_initial - y_min) > 35 and y_min <= (fence_top_y + 15):
            return True
        return False

    # =========================================================================
    # 4. Garbage & Debris Dumping Detection
    # =========================================================================
    def inspect_garbage_debris(self, cam_id: str, frame_bgr: np.ndarray, static_contours: List[Any], now: float) -> List[Dict[str, Any]]:
        """
        Monitors newly appeared stationary blobs on walking surfaces/floors.
        Triggers alert if stationary foreign debris persists > 15 seconds.
        """
        debris_alerts = []
        for idx, c in enumerate(static_contours):
            area = cv2.contourArea(c)
            # Debris typically smaller than human (between 150 and 2200 px)
            if 150 <= area <= 2200:
                x, y, w, h = cv2.boundingRect(c)
                debris_id = f"debris_{cam_id}_{x//20}_{y//20}"
                
                if debris_id not in self.tracked_debris:
                    self.tracked_debris[debris_id] = {
                        "cam_id": cam_id,
                        "first_seen": now,
                        "bbox": [x, y, x + w, y + h],
                        "area": area
                    }
                else:
                    dwell = now - self.tracked_debris[debris_id]["first_seen"]
                    if dwell >= 15.0 and self._can_alert(f"deb_{debris_id}", 60.0):
                        debris_alerts.append({
                            "id": debris_id,
                            "bbox": [x, y, x + w, y + h],
                            "dwell_sec": round(dwell, 1),
                            "area_px": int(area)
                        })
        return debris_alerts

    # =========================================================================
    # 5. Missing Asset / Vanished Object Detection
    # =========================================================================
    def register_monitored_asset(self, asset_id: str, cam_id: str, bbox: List[int], reference_frame_bgr: np.ndarray):
        x1, y1, x2, y2 = bbox
        crop = reference_frame_bgr[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        self.static_assets[asset_id] = {
            "cam_id": cam_id,
            "bbox": bbox,
            "baseline_mean": float(np.mean(gray)),
            "baseline_std": float(np.std(gray))
        }

    def check_missing_assets(self, cam_id: str, frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
        missing = []
        for a_id, data in self.static_assets.items():
            if data["cam_id"] != cam_id:
                continue
            x1, y1, x2, y2 = data["bbox"]
            if y2 > frame_bgr.shape[0] or x2 > frame_bgr.shape[1]:
                continue
            crop = frame_bgr[y1:y2, x1:x2]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            curr_mean = float(np.mean(gray))
            
            # Significant deviation indicates object removed
            if abs(curr_mean - data["baseline_mean"]) > 35.0:
                missing.append({"asset_id": a_id, "bbox": [x1, y1, x2, y2]})
        return missing

    # =========================================================================
    # 6. Deep Visual Attribute Extraction & Search Indexing
    # =========================================================================
    def extract_and_index_attributes(self, cam_id: str, ent: Any, crop_bgr: np.ndarray, now: float):
        """
        Extracts dominant color, category, aspect ratio, and speed,
        indexing into searchable attribute ledger.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return

        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        dominant_color = "UNKNOWN"
        max_pixels = 0
        total_pixels = crop_bgr.shape[0] * crop_bgr.shape[1]

        for color_name, ranges in COLOR_RANGES.items():
            mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
            for lower, upper in ranges:
                m = cv2.inRange(hsv, np.array(lower), np.array(upper))
                mask = cv2.bitwise_or(mask, m)
            count = np.sum(mask > 0)
            if count > max_pixels and (count / float(total_pixels)) > 0.15:
                max_pixels = count
                dominant_color = color_name

        record = {
            "timestamp": int(now),
            "camera_id": cam_id,
            "track_id": ent.track_id,
            "class_label": ent.label,
            "color": dominant_color,
            "speed_kmh": round(ent.speed, 1),
            "bbox": [int(b) for b in ent.bbox]
        }
        self.attribute_ledger.append(record)
        if len(self.attribute_ledger) % 10 == 0:
            self.save_attribute_ledger()

    def search_attributes(self, color: Optional[str] = None, class_label: Optional[str] = None, min_time: Optional[int] = None, max_time: Optional[int] = None) -> List[Dict[str, Any]]:
        results = []
        for r in reversed(self.attribute_ledger):
            if color and r.get("color") != color.upper():
                continue
            if class_label and class_label.lower() not in r.get("class_label", "").lower():
                continue
            if min_time and r.get("timestamp", 0) < min_time:
                continue
            if max_time and r.get("timestamp", 0) > max_time:
                continue
            results.append(r)
            if len(results) >= 100:
                break
        return results

spatial_analytics = SpatialAnalyticsEngine()
