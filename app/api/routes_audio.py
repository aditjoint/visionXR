import os
import time
import subprocess
import threading
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel
from app.engine.alert_bus import alert_bus
from app.security.audit_logger import audit_logger
from app.security.profile_manager import profile_manager, Role

router = APIRouter(prefix="/api/audio", tags=["Public Addressing & Facility Audio Broadcast"])

PA_DIR = "/var/www22/visionXR/data/pa_broadcasts"
os.makedirs(PA_DIR, exist_ok=True)

def play_audio_file_on_speakers(file_path: str):
    """
    Asynchronously plays audio on the physical host speakers / industrial sound card.
    Tries ALSA plughw:0,0 (ALC255 Analog) first, then PulseAudio/PipeWire fallback.
    """
    def _worker():
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return
            
            # Convert to clean WAV 22050Hz Mono if not already WAV
            wav_path = file_path
            if not file_path.endswith(".wav"):
                wav_path = file_path + ".wav"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", file_path, "-ar", "22050", "-ac", "1", wav_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                )

            # Play directly on physical hardware speakers
            played = False
            for cmd in [
                ["aplay", "-D", "plughw:0,0", wav_path],
                ["pw-play", wav_path],
                ["paplay", wav_path],
                ["aplay", "-D", "default", wav_path]
            ]:
                try:
                    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                    if res.returncode == 0:
                        played = True
                        break
                except Exception:
                    continue
        except Exception as e:
            pass

    threading.Thread(target=_worker, daemon=True).start()

def generate_chime_wav(output_path: str):
    """Generates an authentic dual-tone industrial facility PA chime."""
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=880:duration=0.25,volume=0.8",
        "-f", "lavfi",
        "-i", "sine=frequency=660:duration=0.35,volume=0.9",
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
        "-map", "[out]", "-ar", "22050", "-ac", "1", output_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass

class TTSBroadcastRequest(BaseModel):
    message: str
    target_zone: str = "FACILITY_WIDE"
    priority: str = "HIGH"
    chime: bool = True
    actor: str = "Commander"

@router.get("/status")
def get_pa_status():
    return {
        "status": "OPERATIONAL",
        "system": "VisionXR Sovereign Public Address & Voice Intercom",
        "audio_sink": "ALC255 Analog Hardware (plughw:0,0)",
        "modes": ["PUSH_TO_TALK_MIC", "EMERGENCY_TTS_BROADCAST", "ZONE_TARGETED"],
        "active_broadcast": False
    }

@router.post("/broadcast-voice")
async def broadcast_voice_recording(
    file: UploadFile = File(...),
    target_zone: str = Form("FACILITY_WIDE"),
    actor: str = Form("Commander"),
    request: Request = None
):
    """
    Accepts live microphone audio from the operator's browser (Push-to-Talk)
    and broadcasts it immediately across facility speakers.
    """
    ip = request.client.host if request and request.client else "127.0.0.1"
    timestamp = int(time.time() * 1000)
    ext = os.path.splitext(file.filename or "")[1] or ".webm"
    raw_path = os.path.join(PA_DIR, f"pa_voice_{timestamp}{ext}")

    # Save uploaded audio chunk
    contents = await file.read()
    with open(raw_path, "wb") as f:
        f.write(contents)

    # Convert to WAV
    wav_path = os.path.join(PA_DIR, f"pa_voice_{timestamp}.wav")
    try:
        res = subprocess.run(
            ["ffmpeg", "-y", "-i", raw_path, "-ar", "22050", "-ac", "1", wav_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
        )
        if res.returncode != 0 or not os.path.exists(wav_path):
            wav_path = raw_path
    except Exception as e:
        wav_path = raw_path

    # Play out of physical speakers immediately
    play_audio_file_on_speakers(wav_path)

    # Emit notification to alert bus and audit ledger
    alert_bus.emit_alert(
        camera_id="pa_system",
        alert_type="PA_VOICE_BROADCAST",
        severity="INFO",
        title="🎙️ Live PA Public Address Broadcast",
        description=f"Operator [{actor}] broadcast live voice announcement to zone: {target_zone}.",
        metadata={"target_zone": target_zone, "file": f"/data/pa_broadcasts/pa_voice_{timestamp}.wav"}
    )

    audit_logger.log(
        actor=actor,
        role="SUPER_ADMIN",
        action="PA_VOICE_BROADCAST",
        resource=target_zone,
        ip_address=ip,
        result="SUCCESS",
        details=f"Live Push-To-Talk voice broadcast completed ({len(contents)} bytes)"
    )

    return {
        "status": "BROADCASTED",
        "mode": "PUSH_TO_TALK_MIC",
        "target_zone": target_zone,
        "bytes_received": len(contents),
        "audio_url": f"/data/pa_broadcasts/pa_voice_{timestamp}.wav"
    }

@router.post("/broadcast-tts")
def broadcast_tts_announcement(req: TTSBroadcastRequest, request: Request):
    """
    Synthesizes emergency speech via espeak-ng, precedes with dual-tone chime,
    and broadcasts across facility speakers.
    """
    ip = request.client.host if request and request.client else "127.0.0.1"
    timestamp = int(time.time() * 1000)
    msg_cleaned = req.message.strip()
    if not msg_cleaned:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    chime_path = os.path.join(PA_DIR, f"chime_{timestamp}.wav")
    speech_path = os.path.join(PA_DIR, f"speech_{timestamp}.wav")
    final_path = os.path.join(PA_DIR, f"pa_tts_{timestamp}.wav")

    # 1. Synthesize speech using espeak-ng
    try:
        subprocess.run(
            ["espeak-ng", "-v", "en-us", "-s", "150", "-p", "50", "-w", speech_path, msg_cleaned],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis error: {e}")

    # 2. Add dual-tone chime intro if requested
    if req.chime:
        generate_chime_wav(chime_path)
        # Concatenate chime + speech
        try:
            concat_cmd = [
                "ffmpeg", "-y",
                "-i", chime_path, "-i", speech_path,
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                "-map", "[out]", "-ar", "22050", "-ac", "1", final_path
            ]
            subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except Exception:
            final_path = speech_path
    else:
        final_path = speech_path

    # 3. Play over physical speakers
    play_audio_file_on_speakers(final_path)

    # 4. Log alert and audit record
    alert_bus.emit_alert(
        camera_id="pa_system",
        alert_type="PA_EMERGENCY_ANNOUNCEMENT",
        severity="WARNING" if req.priority == "HIGH" else "INFO",
        title="📢 Public Address Facility Announcement",
        description=f"[{req.target_zone}] \"{msg_cleaned}\"",
        metadata={"message": msg_cleaned, "target_zone": req.target_zone, "audio_url": f"/data/pa_broadcasts/pa_tts_{timestamp}.wav"}
    )

    audit_logger.log(
        actor=req.actor,
        role="SUPER_ADMIN",
        action="PA_TTS_BROADCAST",
        resource=req.target_zone,
        ip_address=ip,
        result="SUCCESS",
        details=f"Broadcast message: '{msg_cleaned}'"
    )

    return {
        "status": "BROADCASTED",
        "mode": "EMERGENCY_TTS",
        "message": msg_cleaned,
        "target_zone": req.target_zone,
        "audio_url": f"/data/pa_broadcasts/pa_tts_{timestamp}.wav"
    }
