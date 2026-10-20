import time
import cv2
import numpy as np
import threading
import logging
from typing import Dict, List, Any
from app.config import DEFAULT_CURFEW
from app.engine.stream_manager import stream_manager
from app.engine.spatial_zones import SpatialZoneEngine, ZoneType
from app.engine.behavior_tracker import BehaviorEngine
from app.engine.vision_ai import VisionAIEngine
from app.engine.acoustic_engine import acoustic_engine
from app.engine.alert_bus import alert_bus
from app.engine.material_hazard_engine import material_hazard_tracker
from app.engine.safety_rules_engine import safety_rules
from app.engine.license_manager import license_manager
from app.engine.traffic_anpr_engine import traffic_engine
from app.engine.face_recognition_engine import face_engine
from app.engine.spatial_analytics_engine import spatial_analytics

logger = logging.getLogger("visionxr.inference")


class InferencePipeline:
    def __init__(self):
        self.spatial_engine = SpatialZoneEngine()
        self.behavior_engine = BehaviorEngine()
        self.vision_ai = VisionAIEngine()
        self.running = True
        self.is_active = True # Super Admin master surveillance switch
        self.telemetry_cache: Dict[str, Dict[str, Any]] = {}
        self.curfew_config = DEFAULT_CURFEW.copy()
        self.alert_cooldowns: Dict[str, float] = {}
        self.last_turb_eval: Dict[str, float] = {}
        self.last_turb_data: Dict[str, Dict[str, Any]] = {}

        # Start background processing thread
        self.worker_thread = threading.Thread(target=self._pipeline_loop, daemon=True)
        self.worker_thread.start()

    def _can_emit_alert(self, key: str, cooldown_sec: float = 30.0) -> bool:
        now = time.time()
        last = self.alert_cooldowns.get(key, 0.0)
        if (now - last) >= cooldown_sec:
            self.alert_cooldowns[key] = now
            return True
        return False

    def start_surveillance(self):
        self.is_active = True
        logger.info("Super Admin started AI Surveillance Engine.")

    def stop_surveillance(self):
        self.is_active = False
        logger.info("Super Admin stopped AI Surveillance Engine.")

    def toggle_surveillance(self) -> bool:
        self.is_active = not self.is_active
        logger.info(f"Super Admin toggled AI Surveillance Engine: {'ACTIVE' if self.is_active else 'STOPPED'}")
        return self.is_active

    def is_curfew_active(self) -> bool:
        curfew_cfg = safety_rules.get_rules().get("subject", {})
        if not curfew_cfg.get("curfew_enabled", True):
            return False
        current_hour = time.localtime().tm_hour
        start = curfew_cfg.get("curfew_start_hour", 20)
        end = curfew_cfg.get("curfew_end_hour", 6)
        if start > end: # Overnight curfew 20:00 - 06:00
            return current_hour >= start or current_hour < end
        return start <= current_hour < end

    def _pipeline_loop(self):
        logger.info("Starting VisionXR Real-time AI Inference Pipeline...")
        while self.running:
            if not self.is_active:
                time.sleep(0.3)
                continue
            t0 = time.time()
            now = time.time()
            is_curfew = self.is_curfew_active()

            for cam in stream_manager.list_cameras():
                cam_id = cam["id"]
                frame = stream_manager.get_latest_frame(cam_id)
                if frame is None:
                    continue

                detections = stream_manager.get_latest_detections(cam_id)
                
                # 1. Behavior & Track Updates
                tracked_entities = self.behavior_engine.update_tracks(cam_id, detections, now)

                # 2. Optical Flow Turbulence Index (Only evaluate if task is enabled & physical camera is live)
                is_live = stream_manager.is_physical_active(cam_id)
                turb_enabled = license_manager.is_task_enabled(cam_id, "HUMAN_BEHAVIOR_THEFT_SLEEP")
                if not is_live or not turb_enabled:
                    turbulence_data = {"turbulence_score": 0.0, "status": "STANDBY" if not is_live else "CALM", "avg_magnitude": 0.0, "angle_deg": 0.0}
                else:
                    last_eval = self.last_turb_eval.get(cam_id, 0.0)
                    if (now - last_eval) >= 2.0:
                        prev_gray = stream_manager.get_prev_gray(cam_id)
                        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        turbulence_data = self.behavior_engine.compute_turbulence_index(cam_id, prev_gray, curr_gray)
                        stream_manager.set_prev_gray(cam_id, curr_gray)
                        self.last_turb_eval[cam_id] = now
                        self.last_turb_data[cam_id] = turbulence_data
                    else:
                        turbulence_data = self.last_turb_data.get(cam_id, {"turbulence_score": 0.0, "status": "CALM", "avg_magnitude": 0.0, "angle_deg": 0.0})

                if turb_enabled and turbulence_data["turbulence_score"] > 88.0 and self._can_emit_alert(f"turb_{cam_id}", 60.0):
                    alert_bus.emit_alert(
                        camera_id=cam_id,
                        alert_type="TURBULENCE_PANIC",
                        severity="CRITICAL",
                        title="High Turbulence / Crowd Chaos Detected",
                        description=f"Optical flow variance reached {turbulence_data['turbulence_score']}. Possible stampede, fight, or machine destabilization.",
                        frame_snapshot=frame,
                        metadata=turbulence_data
                    )

                # 3. Spatial Tri-Zone Validation for each active entity
                violations_count = 0
                ppe_compliant_count = 0
                total_workers = 0

                tri_zone_enabled = license_manager.is_task_enabled(cam_id, "TRI_ZONE_PERIMETER")
                subject_rules = safety_rules.get_rules().get("subject", {})
                req_vest = subject_rules.get("require_ppe_vest", True)
                req_helmet = subject_rules.get("require_ppe_helmet", True)
                ppe_rule_active = req_vest or req_helmet
                ppe_enabled = license_manager.is_task_enabled(cam_id, "WORKER_PPE_SAFETY") and ppe_rule_active

                for ent in tracked_entities:
                    gx, gy = ent.ground_point
                    zones = self.spatial_engine.check_point(cam_id, gx, gy) if tri_zone_enabled else []

                    for zone in zones:
                        z_type = zone["type"]
                        z_id = zone["id"]
                        z_name = zone["name"]

                        # RED ZONE: Zero Tolerance Intrusion (with verified human persistence)
                        if z_type == ZoneType.RED:
                            if getattr(ent, 'red_zone_id', None) != z_id:
                                ent.red_zone_id = z_id
                                ent.red_zone_start = now
                            red_dwell = now - getattr(ent, 'red_zone_start', now)
                            
                            # Require at least 5 consecutive observations, 1.0s tracked time, and 0.8s red zone dwell
                            # to eliminate instantaneous sensor flickers, shadow noise, or fleeting transitions
                            if len(ent.history) >= 5 and (now - ent.first_seen) >= 1.0 and red_dwell >= 0.8:
                                violations_count += 1
                                if self._can_emit_alert(f"red_{cam_id}_{z_id}", 30.0):
                                    alert_bus.emit_alert(
                                        camera_id=cam_id,
                                        alert_type="RED_ZONE_INTRUSION",
                                        severity="CRITICAL",
                                        title=f"🚨 Critical Red Zone Breach: {z_name}",
                                        description=f"Unauthorized entity [{ent.label} #{ent.track_id}] penetrated zero-tolerance perimeter '{z_name}'. Instant lock & siren triggered.",
                                        zone_id=z_id,
                                        frame_snapshot=frame,
                                        metadata={"track_id": ent.track_id, "entity": ent.label, "coords": [gx, gy]}
                                    )

                        # AMBER ZONE: Buffer perimeter & Dwell / Loitering check
                        elif z_type == ZoneType.AMBER:
                            if ent.dwell_zone_id != z_id:
                                ent.dwell_zone_id = z_id
                                ent.dwell_start = now
                            dwell_time = now - ent.dwell_start
                            max_dwell = zone.get("max_dwell_sec", 6)
                            if dwell_time > max_dwell:
                                violations_count += 1
                                alert_bus.emit_alert(
                                    camera_id=cam_id,
                                    alert_type="AMBER_ZONE_LOITERING",
                                    severity="WARNING",
                                    title=f"⚠️ Cautionary Buffer Loitering: {z_name}",
                                    description=f"Entity [{ent.label} #{ent.track_id}] exceeded permitted dwell time ({int(dwell_time)}s > {max_dwell}s) in warning zone.",
                                    zone_id=z_id,
                                    frame_snapshot=frame
                                )
                        else:
                            # Green Zone: Safe Corridor
                            ent.dwell_zone_id = z_id

                    # Check Intent & Man-Down
                    if ent.intent == "MAN_DOWN" and ppe_enabled:
                        alert_bus.emit_alert(
                            camera_id=cam_id,
                            alert_type="MAN_DOWN_RESCUE",
                            severity="CRITICAL",
                            title="🆘 MAN-DOWN: Solitary Motionless Worker Alert",
                            description=f"Worker #{ent.track_id} has been horizontal and motionless for > 15 seconds. Immediate emergency response team required!",
                            frame_snapshot=frame
                        )

                    # Worker PPE Compliance Tracking
                    if ent.label == "person":
                        total_workers += 1
                        if ppe_enabled:
                            is_compliant = True
                            missing_items = []
                            if req_vest and not ent.ppe_vest:
                                is_compliant = False
                                missing_items.append("Vest")
                            if req_helmet and not ent.ppe_helmet:
                                is_compliant = False
                                missing_items.append("Helmet")

                            if is_compliant:
                                ppe_compliant_count += 1
                            else:
                                violations_count += 1
                                if self._can_emit_alert(f"ppe_{cam_id}_{ent.track_id}", 30.0):
                                    missing_str = " & ".join(missing_items)
                                    alert_bus.emit_alert(
                                        camera_id=cam_id,
                                        alert_type="PPE_VIOLATION",
                                        severity="WARNING",
                                        title="🦺 PPE Non-Compliance Warning",
                                        description=f"Worker #{ent.track_id} observed without required {missing_str} (Vest: {'✓' if ent.ppe_vest else '✗'}, Helmet: {'✓' if ent.ppe_helmet else '✗'}).",
                                        frame_snapshot=frame
                                    )

                    # Curfew violation
                    if is_curfew and zones:
                        alert_bus.emit_alert(
                            camera_id=cam_id,
                            alert_type="CURFEW_VIOLATION",
                            severity="CRITICAL",
                            title="🌙 Industrial Night Curfew Violation",
                            description=f"Unauthorized activity detected during active curfew hours ({self.curfew_config['start_hour']}:00 - {self.curfew_config['end_hour']}:00).",
                            frame_snapshot=frame
                        )

                    # --- ADVANCED CAPABILITIES SUITE INTEGRATION ---
                    bx1, by1, bx2, by2 = [int(b) for b in ent.bbox]
                    bx1, by1 = max(0, bx1), max(0, by1)
                    bx2, by2 = min(frame.shape[1], bx2), min(frame.shape[0], by2)
                    ent_crop = frame[by1:by2, bx1:bx2] if (bx2 > bx1 and by2 > by1) else None

                    # A. Vehicle & Traffic Analytics (ANPR, Speed, Cabin, Two-Wheeler)
                    traffic_rules = safety_rules.get_rules().get("traffic", {})
                    if ent.label in ["car", "truck", "vehicle", "bus", "forklift"] and ent_crop is not None:
                        # 1. ANPR Number Plate Detection & Watchlist
                        if traffic_rules.get("anpr_enabled", True):
                            anpr_res = traffic_engine.detect_and_recognize_plate(ent_crop)
                            if anpr_res:
                                ent.plate = anpr_res["plate_number"]
                                watch_hit = traffic_engine.check_watchlist(ent.plate)
                                if watch_hit and self._can_emit_alert(f"watch_{cam_id}_{ent.plate}", 45.0):
                                    alert_bus.emit_alert(
                                        camera_id=cam_id,
                                        alert_type="SUSPECTED_VEHICLE",
                                        severity="CRITICAL",
                                        title=f"🚨 Suspected Vehicle Blacklist Match: {ent.plate}",
                                        description=f"Flagged license plate '{ent.plate}' matched intelligence watchlist ({watch_hit.get('reason')}).",
                                        frame_snapshot=frame,
                                        metadata={"plate": ent.plate, "details": watch_hit}
                                    )
                        # 2. Speed Violation
                        spd_lim = traffic_rules.get("speed_limit_kmh", 40.0)
                        if ent.speed > spd_lim and self._can_emit_alert(f"spd_{cam_id}_{ent.track_id}", 30.0):
                            alert_bus.emit_alert(
                                camera_id=cam_id,
                                alert_type="SPEED_VIOLATION",
                                severity="WARNING",
                                title=f"⚡ High Speed Violation: {int(ent.speed)} km/h",
                                description=f"Vehicle #{ent.track_id} exceeded maximum speed limit ({int(ent.speed)} km/h > {int(spd_lim)} km/h).",
                                frame_snapshot=frame
                            )
                        # 3. In-Cabin Driver on Call & Seatbelt
                        if traffic_rules.get("enforce_driver_phone", True) or traffic_rules.get("enforce_seatbelt", True):
                            cabin_res = traffic_engine.inspect_driver_cabin(ent_crop)
                            if cabin_res["driver_on_phone"] and traffic_rules.get("enforce_driver_phone", True) and self._can_emit_alert(f"phone_{cam_id}_{ent.track_id}", 30.0):
                                alert_bus.emit_alert(
                                    camera_id=cam_id,
                                    alert_type="DRIVER_ON_PHONE",
                                    severity="WARNING",
                                    title="📱 Driver on Call Violation",
                                    description=f"Vehicle #{ent.track_id} driver observed using mobile phone while in transit.",
                                    frame_snapshot=frame
                                )
                            if cabin_res["no_seatbelt"] and traffic_rules.get("enforce_seatbelt", True) and self._can_emit_alert(f"seatbelt_{cam_id}_{ent.track_id}", 30.0):
                                alert_bus.emit_alert(
                                    camera_id=cam_id,
                                    alert_type="NO_SEATBELT",
                                    severity="WARNING",
                                    title="🛑 No Seatbelt Compliance Violation",
                                    description=f"Vehicle #{ent.track_id} driver observed without safety seatbelt fastened.",
                                    frame_snapshot=frame
                                )

                    elif ent.label in ["motorcycle", "bike", "two_wheeler"] and ent_crop is not None:
                        bike_res = traffic_engine.inspect_two_wheeler_violations(ent_crop)
                        if bike_res["triple_riding"] and traffic_rules.get("enforce_triple_riding", True) and self._can_emit_alert(f"triple_{cam_id}_{ent.track_id}", 30.0):
                            alert_bus.emit_alert(
                                camera_id=cam_id,
                                alert_type="TRIPLE_RIDING",
                                severity="WARNING",
                                title=f"🏍️ Triple Riding Violation ({bike_res['rider_count']} Passengers)",
                                description=f"Two-wheeler #{ent.track_id} observed carrying {bike_res['rider_count']} passengers exceeding capacity limit.",
                                frame_snapshot=frame
                            )
                        if bike_res["no_helmet"] and traffic_rules.get("enforce_helmet", True) and self._can_emit_alert(f"no_helm_{cam_id}_{ent.track_id}", 30.0):
                            alert_bus.emit_alert(
                                camera_id=cam_id,
                                alert_type="NO_HELMET_RIDER",
                                severity="WARNING",
                                title="🪖 Two-Wheeler Rider Without Helmet",
                                description=f"Motorcycle rider on #{ent.track_id} observed without head protection helmet.",
                                frame_snapshot=frame
                            )

                    # B. Facial Recognition (FRSS), Mask Compliance & Fence Jumping
                    biom_rules = safety_rules.get_rules().get("biometrics", {})
                    if ent.label == "person" and ent_crop is not None:
                        # 1. Fence Jumping
                        if spatial_analytics.evaluate_fence_jumping(ent) and self._can_emit_alert(f"fence_{cam_id}_{ent.track_id}", 30.0):
                            alert_bus.emit_alert(
                                camera_id=cam_id,
                                alert_type="FENCE_JUMPING",
                                severity="CRITICAL",
                                title="🏃 Dynamic Fence Vaulting / Jumping Detected",
                                description=f"Subject #{ent.track_id} exhibited dynamic vertical trajectory vaulting over perimeter boundary.",
                                frame_snapshot=frame
                            )
                        # 2. FRSS Biometric Verification
                        if biom_rules.get("frss_enabled", True):
                            face_crop = ent_crop[:int(ent_crop.shape[0] * 0.40), :]
                            match_res = face_engine.match_face(face_crop, threshold=biom_rules.get("match_threshold", 0.65))
                            ent.identity = match_res.get("person_name", "Unknown")
                            if not match_res["is_authorized"] and len(zones) > 0 and biom_rules.get("alert_on_unknown", True) and self._can_emit_alert(f"frss_unauth_{cam_id}_{ent.track_id}", 45.0):
                                alert_bus.emit_alert(
                                    camera_id=cam_id,
                                    alert_type="UNAUTHORIZED_TRESPASSER",
                                    severity="CRITICAL",
                                    title="👤 Unauthorized Facial Identity in Restricted Sector",
                                    description=f"Unrecognized individual detected without valid biometric credentials in monitored sector.",
                                    frame_snapshot=frame,
                                    metadata=match_res
                                )
                            # 3. Mask Compliance
                            if biom_rules.get("enforce_mask", False):
                                mask_res = face_engine.detect_face_mask(face_crop)
                                if not mask_res["has_mask"] and self._can_emit_alert(f"mask_{cam_id}_{ent.track_id}", 30.0):
                                    alert_bus.emit_alert(
                                        camera_id=cam_id,
                                        alert_type="MASK_VIOLATION",
                                        severity="WARNING",
                                        title="😷 Face Mask Compliance Violation",
                                        description=f"Worker #{ent.track_id} detected with exposed lower facial respiratory zone.",
                                        frame_snapshot=frame
                                    )

                    # C. Index Visual Attributes & Line Crossing
                    if ent_crop is not None:
                        spatial_analytics.extract_and_index_attributes(cam_id, ent, ent_crop, now)
                        prev_y = ent.history[-2][1] if len(ent.history) >= 2 else ent.ground_point[1]
                        spatial_analytics.update_tripwire_crossing(cam_id, prev_y, ent.ground_point[1], frame.shape[0] * 0.55, ent.label)


                # 4. Process Ambient Acoustics
                acoustic_event = acoustic_engine.process_ambient_telemetry(cam_id)
                if acoustic_event:
                    alert_bus.emit_alert(
                        camera_id=cam_id,
                        alert_type=acoustic_event["subtype"],
                        severity=acoustic_event["severity"],
                        title=f"🔊 Acoustic Anomaly: {acoustic_event['label']}",
                        description=f"Acoustic threshold exceeded: {acoustic_event['decibel_db']} dB in frequency band {acoustic_event['freq_band']}.",
                        frame_snapshot=frame,
                        metadata=acoustic_event
                    )

                # 5. Spatial Analytics: Crowd Gathering & Density
                analytics_rules = safety_rules.get_rules().get("analytics", {})
                crowd_res = spatial_analytics.evaluate_crowd_clustering(cam_id, tracked_entities, min_cluster_size=analytics_rules.get("crowd_min_cluster", 4))
                if crowd_res and self._can_emit_alert(f"crowd_{cam_id}", 45.0):
                    alert_bus.emit_alert(
                        camera_id=cam_id,
                        alert_type="CROWD_GATHERING",
                        severity="WARNING",
                        title=f"👥 Crowd Gathering / Density Alert ({crowd_res['cluster_size']} Persons)",
                        description=f"High-density cluster of {crowd_res['cluster_size']} individuals gathered at coordinates {crowd_res['center']}.",
                        frame_snapshot=frame,
                        metadata=crowd_res
                    )

                # 6. Inspect Optical Variables, Physical Homography & Material Hazards
                material_hazard_tracker.inspect_frame_optical_variables(cam_id, frame)

                # 7. Compile live telemetry snapshot for dashboard
                # When PPE rule is disabled or 0 workers are in frame, PPE compliance is N/A (None)
                ppe_rate = None if (not ppe_enabled or total_workers == 0) else round((ppe_compliant_count / total_workers) * 100.0, 1)
                self.telemetry_cache[cam_id] = {
                    "camera_id": cam_id,
                    "timestamp": now,
                    "active_tracks_count": len(tracked_entities),
                    "total_workers": total_workers,
                    "ppe_compliance_pct": ppe_rate,
                    "violations_count": violations_count,
                    "turbulence": turbulence_data,
                    "curfew_active": is_curfew,
                    "occupancy": spatial_analytics.get_counts(cam_id),
                    "entities": [
                        {
                            "id": ent.track_id,
                            "label": ent.label,
                            "bbox": [int(b) for b in ent.bbox],
                            "speed": round(ent.speed, 1),
                            "intent": ent.intent,
                            "is_horizontal": ent.is_horizontal,
                            "ppe_vest": ent.ppe_vest,
                            "ppe_helmet": ent.ppe_helmet
                        }
                        for ent in tracked_entities
                    ],
                    "zones": self.spatial_engine.get_zones_for_camera(cam_id)
                }

            elapsed = time.time() - t0
            time.sleep(max(0.30 - elapsed, 0.10)) # ~3.3Hz balanced sovereign AI inference cadence

    def get_camera_telemetry(self, cam_id: str) -> Dict[str, Any]:
        return self.telemetry_cache.get(cam_id, {
            "camera_id": cam_id,
            "active_tracks_count": 0,
            "total_workers": 0,
            "ppe_compliance_pct": None,
            "violations_count": 0,
            "turbulence": {"turbulence_score": 0.0, "status": "CALM"},
            "entities": [],
            "zones": self.spatial_engine.get_zones_for_camera(cam_id)
        })

pipeline = InferencePipeline()
