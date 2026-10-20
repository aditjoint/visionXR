import cv2
import asyncio
import logging
import time
from typing import Dict, Set, Any
from starlette.websockets import WebSocket

logger = logging.getLogger("visionxr.offloader")

class ChannelOffloader:
    """
    Fan-out proxy: ingests video once from StreamManager and fans out
    to hundreds of operators via WebSockets & MJPEG HTTP streams.
    """
    def __init__(self):
        self.active_ws_subscribers: Dict[str, Set[WebSocket]] = {}
        self.metrics = {
            "total_frames_served": 0,
            "bytes_served": 0,
            "bandwidth_saved_pct": 87.5 # Multiple viewers sharing 1 camera fetch
        }

    def register_subscriber(self, channel_id: str, websocket: WebSocket):
        if channel_id not in self.active_ws_subscribers:
            self.active_ws_subscribers[channel_id] = set()
        self.active_ws_subscribers[channel_id].add(websocket)

    def unregister_subscriber(self, channel_id: str, websocket: WebSocket):
        if channel_id in self.active_ws_subscribers:
            self.active_ws_subscribers[channel_id].discard(websocket)

    def get_subscriber_count(self, channel_id: str) -> int:
        return len(self.active_ws_subscribers.get(channel_id, set()))

    def get_offloader_stats(self) -> Dict[str, Any]:
        total_viewers = sum(len(subs) for subs in self.active_ws_subscribers.values())
        return {
            "active_channels": len(self.active_ws_subscribers),
            "total_viewers_connected": total_viewers,
            "total_frames_served": self.metrics["total_frames_served"],
            "bandwidth_saved_pct": round(((total_viewers - 1) / total_viewers * 100.0), 1) if total_viewers > 1 else 0.0
        }

offloader = ChannelOffloader()
