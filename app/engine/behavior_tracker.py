import time
import math
import numpy as np
from typing import Dict, List, Tuple, Any, Optional

class TrackedEntity:
    def __init__(self, track_id: int, label: str, bbox: List[float], timestamp: float):
        self.track_id = track_id
        self.label = label  # person, forklift, machine, animal
        self.bbox = bbox    # [x1, y1, x2, y2]
        self.history = [(bbox, timestamp)]
        self.first_seen = timestamp
        self.last_seen = timestamp
        self.velocity = (0.0, 0.0) # px/s
        self.speed = 0.0           # px/s
        self.intent = "NORMAL"     # NORMAL, RUSHING, SNEAKING, COLLISION_RISK, MAN_DOWN
        self.dwell_zone_id: Optional[str] = None
        self.dwell_start: float = timestamp
        self.motionless_start: float = timestamp
        self.is_horizontal = False
        self.ppe_vest = False
        self.ppe_helmet = False

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def ground_point(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, y2)

    def update(self, new_bbox: List[float], timestamp: float):
        dt = max(timestamp - self.last_seen, 0.001)
        prev_cx, prev_cy = self.center
        self.bbox = new_bbox
        curr_cx, curr_cy = self.center

        vx = (curr_cx - prev_cx) / dt
        vy = (curr_cy - prev_cy) / dt
        self.velocity = (vx, vy)
        self.speed = math.hypot(vx, vy)

        # Posture aspect ratio: horizontal vs vertical
        w = max(new_bbox[2] - new_bbox[0], 1.0)
        h = max(new_bbox[3] - new_bbox[1], 1.0)
        self.is_horizontal = (w / h) > 1.25

        # Motionless check (speed < 12 px/sec)
        if self.speed > 18.0:
            self.motionless_start = timestamp
        
        motionless_duration = timestamp - self.motionless_start

        # Intent assessment
        if self.is_horizontal and motionless_duration > 15.0 and self.label == "person":
            self.intent = "MAN_DOWN"
        elif self.speed > 160.0:
            self.intent = "RUSHING"
        elif self.speed < 8.0 and (timestamp - self.dwell_start) > 25.0:
            self.intent = "LOITERING"
        else:
            self.intent = "NORMAL"

        self.last_seen = timestamp
        self.history.append((new_bbox, timestamp))
        if len(self.history) > 30:
            self.history.pop(0)

class BehaviorEngine:
    def __init__(self):
        self.next_track_id = 1
        self.tracks: Dict[str, Dict[int, TrackedEntity]] = {} # cam_id -> {id: TrackedEntity}
        self.optical_flow_history: Dict[str, float] = {}

    def update_tracks(self, cam_id: str, detections: List[Dict[str, Any]], timestamp: float) -> List[TrackedEntity]:
        """
        Associate detections to existing tracks using Euclidean distance.
        detections format: [{'label': 'person', 'bbox': [x1, y1, x2, y2], 'confidence': 0.9, ...}]
        """
        if cam_id not in self.tracks:
            self.tracks[cam_id] = {}

        current_tracks = self.tracks[cam_id]
        active_entities: List[TrackedEntity] = []

        if not detections:
            # Expire old tracks (> 2.0s without sighting)
            to_del = [tid for tid, ent in current_tracks.items() if (timestamp - ent.last_seen) > 2.0]
            for tid in to_del:
                del current_tracks[tid]
            return []

        # Simple greedy distance matching
        matched_tracks = set()
        for det in detections:
            bbox = det["bbox"]
            det_cx = (bbox[0] + bbox[2]) / 2.0
            det_cy = (bbox[1] + bbox[3]) / 2.0

            best_tid = None
            best_dist = 120.0  # max association threshold px

            for tid, ent in current_tracks.items():
                if tid in matched_tracks:
                    continue
                tcx, tcy = ent.center
                dist = math.hypot(det_cx - tcx, det_cy - tcy)
                if dist < best_dist:
                    best_dist = dist
                    best_tid = tid

            if best_tid is not None:
                matched_tracks.add(best_tid)
                ent = current_tracks[best_tid]
                ent.label = det.get("label", ent.label)
                ent.update(bbox, timestamp)
                if "ppe_vest" in det:
                    ent.ppe_vest = det["ppe_vest"]
                if "ppe_helmet" in det:
                    ent.ppe_helmet = det["ppe_helmet"]
                active_entities.append(ent)
            else:
                # Spawn new track
                tid = self.next_track_id
                self.next_track_id += 1
                new_ent = TrackedEntity(tid, det.get("label", "person"), bbox, timestamp)
                if "ppe_vest" in det:
                    new_ent.ppe_vest = det["ppe_vest"]
                if "ppe_helmet" in det:
                    new_ent.ppe_helmet = det["ppe_helmet"]
                current_tracks[tid] = new_ent
                active_entities.append(new_ent)

        # Cleanup expired tracks
        to_del = [tid for tid, ent in current_tracks.items() if (timestamp - ent.last_seen) > 2.0]
        for tid in to_del:
            del current_tracks[tid]

        return active_entities

    def compute_turbulence_index(self, cam_id: str, prev_gray: Optional[np.ndarray], curr_gray: np.ndarray) -> Dict[str, Any]:
        """
        Measure optical flow variance to detect crowd panic, turbulence, stampedes, and chaos.
        Returns turbulence score (0.0 - 100.0) and flow vector summary.
        """
        import cv2
        if prev_gray is None or prev_gray.shape != curr_gray.shape:
            return {"turbulence_score": 5.0, "status": "STABLE", "avg_magnitude": 0.0, "angle_deg": 0.0}

        # Subsample for blazing fast computation with minimal CPU footprint
        small_prev = cv2.resize(prev_gray, (120, 68))
        small_curr = cv2.resize(curr_gray, (120, 68))

        # Fast motion gate: if pixel difference is minimal, scene is calm -> skip heavy Farneback optical flow
        diff_mean = float(np.mean(cv2.absdiff(small_prev, small_curr)))
        if diff_mean < 2.5:
            return {"turbulence_score": 0.0, "status": "CALM", "avg_magnitude": 0.0, "angle_deg": 0.0}

        flow = cv2.calcOpticalFlowFarneback(
            small_prev, small_curr, None,
            pyr_scale=0.5, levels=1, winsize=11, iterations=1, poly_n=5, poly_sigma=1.1, flags=0
        )

        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        # Filter sensor noise: Require genuine macroscopic motion (mag > 1.8) across >5% of the frame
        active_mask = mag > 1.8
        if np.count_nonzero(active_mask) < 500:
            return {"turbulence_score": 0.0, "status": "CALM", "avg_magnitude": 0.0, "angle_deg": 0.0}

        active_mag = mag[active_mask]
        active_ang = ang[active_mask]

        avg_mag = float(np.mean(active_mag))
        var_ang = float(np.var(active_ang)) # High angular variance = chaotic multi-directional motion
        var_mag = float(np.var(active_mag))

        # Turbulence heuristic: require both high speed and high multi-directional variance
        raw_score = (avg_mag * 4.5) + (var_ang * 6.0)
        score = min(max(raw_score, 0.0), 100.0)

        mean_angle = float(np.rad2deg(np.mean(active_ang))) % 360.0

        status = "NORMAL"
        if score > 70.0:
            status = "CHAOTIC_TURBULENCE"
        elif score > 45.0:
            status = "IRREGULAR_AGITATION"

        return {
            "turbulence_score": round(score, 1),
            "status": status,
            "avg_magnitude": round(avg_mag, 2),
            "angle_deg": round(mean_angle, 1)
        }
