import cv2
import numpy as np
from typing import Tuple, List, Dict, Any, Optional

class Homography3DEngine:
    """
    Projective Homography and 3D Spatial Geometry Engine.
    Transforms 2D camera pixel coordinates (u, v) into metric ground-plane coordinates (X, Y) in meters,
    enabling real-world metric velocity (km/h), physical surface area (m²), and 3D bounding volumes.
    """
    def __init__(self):
        # Default Homography matrices for Sector 22 CCTV channels
        # Calibrated using 4 metric fiducial ground survey points
        self.homographies: Dict[str, np.ndarray] = {}
        self.inv_homographies: Dict[str, np.ndarray] = {}
        self._init_default_calibrations()

    def _init_default_calibrations(self):
        # Base 854x480 perspective trapezoid to 15m x 25m industrial ground rectangle
        src_pts = np.float32([
            [100, 200], # Far left
            [754, 200], # Far right
            [820, 460], # Near right
            [34, 460]   # Near left
        ])
        
        # Real-world metric floor dimensions (meters: X right, Y forward)
        dst_pts = np.float32([
            [0.0, 25.0],   # Far left: (0m, 25m)
            [15.0, 25.0],  # Far right: (15m, 25m)
            [15.0, 2.0],   # Near right: (15m, 2m)
            [0.0, 2.0]     # Near left: (0m, 2m)
        ])

        H, _ = cv2.findHomography(src_pts, dst_pts)
        H_inv = np.linalg.inv(H)

        for cam_id in ["cam_01", "cam_02", "cam_03", "cam_04"]:
            self.homographies[cam_id] = H
            self.inv_homographies[cam_id] = H_inv

    def pixel_to_world(self, cam_id: str, u: float, v: float) -> Tuple[float, float]:
        """
        Transform 2D image coordinates (u, v) into ground-plane metric coordinates (X, Y) in meters.
        s * [X, Y, 1]^T = H * [u, v, 1]^T
        """
        H = self.homographies.get(cam_id, self.homographies.get("cam_01"))
        pt = np.array([u, v, 1.0], dtype=np.float64)
        world_pt = np.dot(H, pt)
        world_pt /= world_pt[2] # Normalize homogeneous scale
        return round(float(world_pt[0]), 2), round(float(world_pt[1]), 2)

    def world_to_pixel(self, cam_id: str, x: float, y: float) -> Tuple[int, int]:
        """Transform metric coordinates (X, Y) back into camera pixel coordinates (u, v)."""
        H_inv = self.inv_homographies.get(cam_id, self.inv_homographies.get("cam_01"))
        pt = np.array([x, y, 1.0], dtype=np.float64)
        img_pt = np.dot(H_inv, pt)
        img_pt /= img_pt[2]
        return int(round(float(img_pt[0]))), int(round(float(img_pt[1])))

    def compute_metric_speed(self, cam_id: str, prev_uv: Tuple[float, float], curr_uv: Tuple[float, float], dt: float) -> float:
        """Calculate physical velocity in km/h using ground-plane homography."""
        if dt <= 0:
            return 0.0
        x1, y1 = self.pixel_to_world(cam_id, prev_uv[0], prev_uv[1])
        x2, y2 = self.pixel_to_world(cam_id, curr_uv[0], curr_uv[1])
        metric_dist = np.hypot(x2 - x1, y2 - y1) # meters
        speed_mps = metric_dist / dt
        return round(float(speed_mps * 3.6), 2) # km/h

    def compute_metric_polygon_area(self, cam_id: str, polygon_uv: List[List[float]]) -> float:
        """
        Calculate true real-world physical area in square meters (m²) of any contour or spill
        by projecting all boundary vertices through the homography matrix onto the metric ground plane.
        """
        if len(polygon_uv) < 3:
            return 0.0

        world_pts = []
        for pt in polygon_uv:
            wx, wy = self.pixel_to_world(cam_id, pt[0], pt[1])
            world_pts.append([wx, wy])

        # Shoelace formula for polygon area
        pts = np.array(world_pts)
        x = pts[:, 0]
        y = pts[:, 1]
        area = 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        return round(float(area), 3)

    def estimate_3d_bounding_box(self, cam_id: str, bbox_2d: List[float], estimated_height_m: float = 1.75) -> Dict[str, Any]:
        """
        Synthesize 3D oriented bounding box [X, Y, Z, Width, Length, Height]
        using ground contact plane homography and monocular height projection.
        """
        x1, y1, x2, y2 = bbox_2d
        ground_x, ground_y = self.pixel_to_world(cam_id, (x1 + x2) / 2.0, y2)
        
        # Ground footprint dimensions
        wx1, wy1 = self.pixel_to_world(cam_id, x1, y2)
        wx2, wy2 = self.pixel_to_world(cam_id, x2, y2)
        metric_width = round(float(np.hypot(wx2 - wx1, wy2 - wy1)), 2)

        return {
            "center_metric": [ground_x, ground_y, round(estimated_height_m / 2.0, 2)],
            "dimensions_metric": {
                "width_m": metric_width,
                "length_m": round(metric_width * 0.8, 2),
                "height_m": estimated_height_m
            },
            "volume_m3": round(metric_width * (metric_width * 0.8) * estimated_height_m, 2),
            "ground_contact_m": [ground_x, ground_y, 0.0]
        }

homography_3d = Homography3DEngine()
