import time
import math
import cv2
import numpy as np
from typing import Dict, List, Tuple, Any, Optional

class VisionAIEngine:
    def __init__(self):
        self.privacy_blur_enabled = False
        self.face_cascade = None
        self._init_face_detector()
        self.yolo_model = None
        self._try_load_yolo()

    def _init_face_detector(self):
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception:
            self.face_cascade = None

    def _try_load_yolo(self):
        try:
            from ultralytics import YOLO
            # Try lightweight nano model if available
            self.yolo_model = YOLO("yolov8n.pt")
        except Exception:
            self.yolo_model = None

    def detect_faces(self, frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """Detect faces for intruder alerts, mugshots, and privacy obfuscation."""
        faces = []
        if self.face_cascade is None or frame_bgr is None:
            return faces

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        detected = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.15, minNeighbors=4, minSize=(30, 30)
        )
        for (x, y, w, h) in detected:
            faces.append({
                "bbox": [int(x), int(y), int(x + w), int(y + h)],
                "confidence": 0.88,
                "is_authorized": False, # Flagged as unknown intruder by default
                "face_id": f"FACE_{x}_{y}"
            })
        return faces

    def check_ppe_compliance(self, person_crop_bgr: np.ndarray) -> Tuple[bool, bool]:
        """
        Inspect person image for high-visibility vest and safety helmet.
        Returns (has_vest: bool, has_helmet: bool).
        """
        if person_crop_bgr is None or person_crop_bgr.size == 0:
            return False, False

        h, w = person_crop_bgr.shape[:2]
        if h < 40 or w < 20:
            return False, False

        hsv = cv2.cvtColor(person_crop_bgr, cv2.COLOR_BGR2HSV)

        # Upper 30% for helmet
        head_crop = hsv[0:int(h * 0.35), :]
        # Mid 50% for high-visibility vest
        torso_crop = hsv[int(h * 0.25):int(h * 0.75), :]

        # High-vis colors: Fluorescent Lime (H: 22-42) & Fluorescent Orange (H: 8-18)
        mask_yellow_green = cv2.inRange(torso_crop, np.array([22, 90, 90]), np.array([45, 255, 255]))
        mask_orange = cv2.inRange(torso_crop, np.array([6, 120, 100]), np.array([20, 255, 255]))
        vest_mask = cv2.bitwise_or(mask_yellow_green, mask_orange)

        vest_ratio = np.count_nonzero(vest_mask) / float(torso_crop.shape[0] * torso_crop.shape[1] + 1)
        has_vest = vest_ratio > 0.08  # at least 8% fluorescent pixels in torso

        # Helmet detection in head region (yellow, white, blue, red)
        mask_helmet_yellow = cv2.inRange(head_crop, np.array([20, 80, 100]), np.array([38, 255, 255]))
        mask_helmet_white = cv2.inRange(head_crop, np.array([0, 0, 180]), np.array([180, 45, 255]))
        mask_helmet_blue = cv2.inRange(head_crop, np.array([95, 100, 80]), np.array([130, 255, 255]))
        helmet_mask = cv2.bitwise_or(mask_helmet_yellow, cv2.bitwise_or(mask_helmet_white, mask_helmet_blue))

        helmet_ratio = np.count_nonzero(helmet_mask) / float(head_crop.shape[0] * head_crop.shape[1] + 1)
        has_helmet = helmet_ratio > 0.12

        return has_vest, has_helmet

    def detect_optical_fire_smoke(self, frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """
        Multimodal Optical Fire & Smoke Anomaly Detector.
        - Flame: High-energy chrominance in Red-Orange-Yellow spectrum.
        - Smoke: Low-saturation desaturated grayscale dispersion.
        """
        hazards = []
        if frame_bgr is None or frame_bgr.size == 0:
            return hazards

        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

        # 1. Optical Flame Detection (Orange / Red / Yellow high saturation)
        lower_flame = np.array([8, 140, 180])
        upper_flame = np.array([36, 255, 255])
        flame_mask = cv2.inRange(hsv, lower_flame, upper_flame)

        flame_contours, _ = cv2.findContours(flame_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in flame_contours:
            area = cv2.contourArea(cnt)
            if area > 350:
                x, y, w, h = cv2.boundingRect(cnt)
                conf = min(0.72 + (area / 3500.0), 0.98)
                hazards.append({
                    "label": "optical_flame",
                    "bbox": [x, y, x + w, y + h],
                    "confidence": round(conf, 2),
                    "severity": "CRITICAL"
                })

        # 2. Optical Smoke Plume Detection (Low Saturation, Medium-to-High Luminance Gray Cloud)
        lower_smoke = np.array([0, 0, 110])
        upper_smoke = np.array([180, 42, 230])
        smoke_mask = cv2.inRange(hsv, lower_smoke, upper_smoke)

        # Morphological filter to remove isolated noise pixels
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        smoke_clean = cv2.morphologyEx(smoke_mask, cv2.MORPH_OPEN, kernel)

        smoke_contours, _ = cv2.findContours(smoke_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in smoke_contours:
            area = cv2.contourArea(cnt)
            if area > 1200: # Smoke plumes have larger diffuse surface area
                x, y, w, h = cv2.boundingRect(cnt)
                conf = min(0.68 + (area / 8000.0), 0.95)
                hazards.append({
                    "label": "smoke_plume",
                    "bbox": [x, y, x + w, y + h],
                    "confidence": round(conf, 2),
                    "severity": "HIGH"
                })

        return hazards

    def apply_privacy_obfuscation(self, frame_bgr: np.ndarray, faces: List[Dict[str, Any]]) -> np.ndarray:
        """
        Dynamic sovereign privacy obfuscation (DPDP / GDPR):
        Applies gaussian blur or mosaic to faces when enabled on monitor wall.
        """
        if not self.privacy_blur_enabled or frame_bgr is None or not faces:
            return frame_bgr

        output = frame_bgr.copy()
        for f in faces:
            x1, y1, x2, y2 = f["bbox"]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame_bgr.shape[1], x2), min(frame_bgr.shape[0], y2)
            if (x2 - x1) > 10 and (y2 - y1) > 10:
                roi = output[y1:y2, x1:x2]
                # Heavy mosaic pixelation
                small = cv2.resize(roi, (8, 8), interpolation=cv2.INTER_LINEAR)
                mosaic = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
                output[y1:y2, x1:x2] = mosaic
                # Draw privacy privacy boundary
                cv2.rectangle(output, (x1, y1), (x2, y2), (200, 200, 200), 1)

        return output

vision_ai = VisionAIEngine()
