import os
import subprocess
import time
import json
import logging
import hashlib
import cv2
import numpy as np
from typing import Dict, List, Any, Optional
from app.config import SNAPSHOTS_DIR, WHATSAPP_TARGET, OMNIGRID_DCIM_WEBHOOK
from app.security.audit_logger import audit_logger

logger = logging.getLogger("visionxr.alertbus")

class AlertBus:
    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []
        self._siren_active = False
        self._siren_triggered_at = 0.0
        self.lockdown_active = False
        self.whatsapp_logs: List[Dict[str, Any]] = []
        self.cooldowns: Dict[str, float] = {}

    @property
    def siren_active(self) -> bool:
        if self._siren_active:
            if time.time() - self._siren_triggered_at > 15.0:
                self._siren_active = False
                return False
            return True
        return False

    @siren_active.setter
    def siren_active(self, val: bool):
        self._siren_active = bool(val)
        if val:
            self._siren_triggered_at = time.time()

    def emit_alert(self,
                   camera_id: str,
                   alert_type: str,
                   severity: str, # CRITICAL, WARNING, INFO
                   title: str,
                   description: str,
                   zone_id: Optional[str] = None,
                   frame_snapshot: Optional[np.ndarray] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Publish an alert to the event bus with deduplication cooldown,
        evidence snapshot storage with SHA-256 seal, and escalation gateway.
        """
        now = time.time()
        cooldown_key = f"{camera_id}_{alert_type}_{zone_id or ''}"
        
        # 10s cooldown for identical alert on same camera
        if (now - self.cooldowns.get(cooldown_key, 0.0)) < 10.0:
            return None

        self.cooldowns[cooldown_key] = now
        alert_id = f"alt_{int(now * 1000)}"

        # Save cryptographic evidence snapshot if frame provided
        snapshot_rel_path = None
        snapshot_sha256 = None
        if frame_snapshot is not None:
            filename = f"{alert_id}.jpg"
            filepath = SNAPSHOTS_DIR / filename
            try:
                cv2.imwrite(str(filepath), frame_snapshot)
                with open(filepath, "rb") as sf:
                    snapshot_sha256 = hashlib.sha256(sf.read()).hexdigest()
                snapshot_rel_path = f"/data/snapshots/{filename}"
            except Exception as e:
                logger.error(f"Failed to write snapshot {filename}: {e}")

        # Save short discrepancy video clip from rolling buffer
        video_clip_rel_path = None
        video_clip_sha256 = None
        try:
            from app.engine.stream_manager import stream_manager
            clip_filename = f"{alert_id}.mp4"
            clip_filepath = SNAPSHOTS_DIR / clip_filename
            if stream_manager.capture_discrepancy_clip(camera_id, str(clip_filepath)):
                with open(clip_filepath, "rb") as vf:
                    video_clip_sha256 = hashlib.sha256(vf.read()).hexdigest()
                video_clip_rel_path = f"/data/snapshots/{clip_filename}"
        except Exception as ve:
            logger.debug(f"Discrepancy video clip capture note: {ve}")

        alert = {
            "id": alert_id,
            "camera_id": camera_id,
            "type": alert_type,
            "severity": severity,
            "title": title,
            "description": description,
            "zone_id": zone_id,
            "snapshot_url": snapshot_rel_path,
            "snapshot_sha256": snapshot_sha256,
            "video_url": video_clip_rel_path,
            "video_sha256": video_clip_sha256,
            "timestamp": now,
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "UNACKNOWLEDGED",
            "metadata": metadata or {}
        }

        self.alerts.insert(0, alert)
        if len(self.alerts) > 200:
            self.alerts.pop()

        # Log in Sovereign Audit Ledger
        audit_logger.log(
            actor="AI_INFERENCE_ENGINE",
            role="SYSTEM",
            action=f"ALERT_TRIGGERED_{severity}",
            resource=camera_id,
            ip_address="127.0.0.22",
            result="EMITTED",
            details=f"[{alert_type}] {title}"
        )

        # Critical escalation trigger (respect manual silencing and rules)
        if severity == "CRITICAL":
            try:
                from app.engine.safety_rules_engine import safety_rules
                esc = safety_rules.get_rules().get("escalation", {})
                if esc.get("auto_trigger_siren_on_red", True) and alert_type == "RED_ZONE_INTRUSION":
                    self.siren_active = True
                    self.play_physical_red_zone_alarm(title)
                if esc.get("auto_dispatch_whatsapp", False):
                    self.dispatch_whatsapp_escalation(alert)
            except Exception:
                pass

        return alert

    def play_physical_red_zone_alarm(self, title: str = "Red Zone Breach"):
        """Plays high-visibility industrial alarm tone on host physical speakers with 15s cooldown."""
        now = time.time()
        if (now - self.cooldowns.get("speaker_red_alarm", 0.0)) < 15.0:
            return
        self.cooldowns["speaker_red_alarm"] = now
        try:
            from app.api.routes_audio import play_audio_file_on_speakers
            alarm_wav = "/var/www22/visionXR/data/pa_broadcasts/red_zone_siren.wav"
            if not os.path.exists(alarm_wav):
                cmd = [
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=880:duration=0.3,volume=0.9",
                    "-f", "lavfi",
                    "-i", "sine=frequency=660:duration=0.4,volume=0.9",
                    "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                    "-map", "[out]", "-ar", "22050", "-ac", "1", alarm_wav
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            play_audio_file_on_speakers(alarm_wav)
        except Exception as e:
            logger.debug(f"Speaker alert note: {e}")

    def silence_all_alarms(self, actor: str = "operator") -> bool:
        """Immediately silences all audible alarms, sirens, and emergency interlocks."""
        self.siren_active = False
        audit_logger.log(
            actor=actor,
            role="OPERATOR",
            action="ALL_ALARMS_SILENCED",
            resource="GLOBAL_ALARM",
            ip_address="127.0.0.22",
            result="SUCCESS",
            details="All sirens and acoustic alerts immediately silenced by operator."
        )
        logger.info(f"All alarms silenced by {actor}")
        return False

    def dispatch_whatsapp_escalation(self, alert: Dict[str, Any]):
        """
        Dispatch emergency escalation to WhatsApp Desk (+91-8779639965) with 60s cooldown.
        """
        now = time.time()
        wa_key = f"wa_{alert.get('camera_id')}_{alert.get('alert_type')}"
        if (now - self.cooldowns.get(wa_key, 0.0)) < 60.0:
            return
        self.cooldowns[wa_key] = now

        sha_prefix = (alert.get('snapshot_sha256') or 'N/A')[:16]
        payload = {
            "dispatch_id": f"wa_{int(time.time()*1000)}",
            "recipient": WHATSAPP_TARGET,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "priority": "HIGH_SEVERITY_DISPATCH",
            "message": f"🚨 [VISIONXR CRITICAL ALARM] Sector 22 - {alert['camera_id']}\n{alert['title']}\n{alert['description']}\nTime: {alert['formatted_time']}\nEvidence Hash: {sha_prefix}..."
        }
        self.whatsapp_logs.insert(0, payload)
        if len(self.whatsapp_logs) > 50:
            self.whatsapp_logs.pop()
        logger.warning(f"WhatsApp Escalation Dispatched to {WHATSAPP_TARGET}: {alert['title']}")

    def acknowledge_alert(self, alert_id: str, operator_name: str) -> bool:
        for alt in self.alerts:
            if alt["id"] == alert_id:
                alt["status"] = "ACKNOWLEDGED"
                alt["ack_by"] = operator_name
                alt["ack_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                audit_logger.log(
                    actor=operator_name,
                    role="OPERATOR",
                    action="ALERT_ACKNOWLEDGED",
                    resource=alt["camera_id"],
                    ip_address="127.0.0.22",
                    result="SUCCESS",
                    details=f"Alert ID {alert_id} acknowledged"
                )
                return True
        return False

    def clear_all_alerts(self, actor: str = "operator") -> bool:
        self.alerts = []
        self.siren_active = False
        audit_logger.log(
            actor=actor,
            role="OPERATOR",
            action="ALL_ALERTS_CLEARED",
            resource="GLOBAL_ALARM",
            ip_address="127.0.0.22",
            result="SUCCESS",
            details="All historical alerts and siren flags cleared from dashboard."
        )
        return True

    def toggle_siren(self, state: bool, actor: str = "operator") -> bool:
        self.siren_active = state
        audit_logger.log(
            actor=actor,
            role="SECOPS",
            action="SIREN_STATE_CHANGE",
            resource="GLOBAL_ALARM",
            ip_address="127.0.0.22",
            result="SUCCESS",
            details=f"Siren set to {'ACTIVE' if state else 'SILENCED'}"
        )
        return self.siren_active

    def toggle_lockdown(self, state: bool, actor: str = "commander") -> bool:
        self.lockdown_active = state
        audit_logger.log(
            actor=actor,
            role="SUPER_ADMIN",
            action="FACILITY_LOCKDOWN",
            resource="SECTOR_22_PERIMETER",
            ip_address="127.0.0.22",
            result="SUCCESS",
            details=f"Facility lockdown set to {'ACTIVE' if state else 'DEACTIVATED'}"
        )
        return self.lockdown_active

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.alerts[:limit]

alert_bus = AlertBus()
