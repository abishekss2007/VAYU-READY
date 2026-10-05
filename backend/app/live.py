"""ISO 13374 block: Data Acquisition. Live feed: MQTT sensor replay in, WebSocket updates out."""
import asyncio
import json
import logging
from urllib.parse import urlparse

from .config import settings

log = logging.getLogger("vayu.live")
TOPIC = "vayu/sensors/#"


class Hub:
    """Keeps the open dashboards and pushes twin updates to them."""

    def __init__(self):
        self.clients: set = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.mqtt_connected = False
        self.messages = 0
        self.last_message_at = None

    async def _send(self, event: dict):
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def broadcast(self, event: dict):
        """Safe to call from any thread (routes run in a thread pool, MQTT has its own thread)."""
        if self.loop and self.clients:
            asyncio.run_coroutine_threadsafe(self._send(event), self.loop)

    def refresh(self, tails=(), reason: str = ""):
        self.broadcast({"type": "refresh", "tails": list(tails), "reason": reason})


hub = Hub()


def mqtt_client(client_id: str):
    """Returns a connected paho client, or None if MQTT_URL is not set or the broker is unreachable."""
    if not settings.mqtt_url:
        return None
    import paho.mqtt.client as mqtt
    u = urlparse(settings.mqtt_url)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    try:
        client.connect(u.hostname or "localhost", u.port or 1883, keepalive=30)
    except Exception as e:
        log.warning("MQTT broker not reachable (%s). Live feed disabled.", e)
        return None
    return client


def start_subscriber():
    client = mqtt_client("vayu-api")
    if not client:
        return None

    def on_connect(c, userdata, flags, rc, props=None):
        hub.mqtt_connected = True
        c.subscribe(TOPIC)

    def on_disconnect(c, userdata, flags, rc, props=None):
        hub.mqtt_connected = False

    def on_message(c, userdata, msg):
        from .db import iso, utcnow
        hub.messages += 1
        hub.last_message_at = iso(utcnow())
        try:
            hub.broadcast({"type": "sensor", **json.loads(msg.payload)})
        except Exception:
            pass

    client.on_connect, client.on_disconnect, client.on_message = on_connect, on_disconnect, on_message
    client.loop_start()
    return client
