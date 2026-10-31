"""Image relays for the iPad dashboard.

The iPad 1 (iOS 5) can't fetch images from Home Assistant itself: HA is often
HTTPS-only with modern TLS, proxy URLs need rotating tokens, and cameras such
as go2rtc/WebRTC streams are unplayable on the device. So the integration does
the fetching and ships small JPEGs over the existing MQTT link:

* Album art / thumbnails — `mqttdash/art/<entity_id>` (retained). Published for
  media players and `image.*` entities referenced by profiles, whenever the
  picture changes; an empty payload clears it.
* Camera frames — `mqttdash/camera/<entity_id>/frame` (not retained). Only
  streamed while a device is actually showing the camera: devices publish
  `{"entity_id", "active", "width", "interval"}` to
  `mqttdash/dev/<device_id>/camera` and refresh it every ~15 s.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import time
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp

from homeassistant.components import mqtt  # type: ignore
from homeassistant.core import HomeAssistant, Event, callback  # type: ignore
from homeassistant.helpers.event import async_track_state_change_event  # type: ignore

from .const import FIXED_DEVICE_BASE

_LOGGER = logging.getLogger(__name__)

ART_BASE = "mqttdash/art"
CAMERA_BASE = "mqttdash/camera"

ART_MAX_PX = 320            # album art / thumbnails are shown at ≤ ~200 pt
ART_MAX_RAW_BYTES = 200_000 # without Pillow, only pass through reasonably small images
VIEWER_TTL = 45.0           # a viewer that hasn't refreshed in this long is gone
FRAME_MAX_PX = 1024
FRAME_MIN_INTERVAL = 0.5
FRAME_MAX_INTERVAL = 10.0
FRAME_BACKOFF_MAX = 30.0


def art_topic(entity_id: str) -> str:
    return f"{ART_BASE}/{entity_id}"


def frame_topic(entity_id: str) -> str:
    return f"{CAMERA_BASE}/{entity_id}/frame"


def _strip_token(url: Optional[str]) -> str:
    """Dedupe key for entity_picture: proxy URLs carry a rotating access token."""
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if k != "token"]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    except Exception:  # pragma: no cover - defensive
        return url


def _to_jpeg(data: bytes, max_px: int) -> Optional[bytes]:
    """Downscale to max_px (longest side) baseline JPEG. Runs in the executor."""
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return data if len(data) <= ART_MAX_RAW_BYTES else None
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        if img.mode not in ("RGB", "L"):
            # Flatten transparency onto black (the dashboard background)
            bg = Image.new("RGB", img.size, (0, 0, 0))
            rgba = img.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            img = bg
        if max(img.size) > max_px:
            img.thumbnail((max_px, max_px))
        out = io.BytesIO()
        # Baseline (non-progressive) JPEG decodes everywhere, including iOS 5
        img.save(out, format="JPEG", quality=82, progressive=False, optimize=True)
        return out.getvalue()
    except Exception:
        _LOGGER.debug("image conversion failed", exc_info=True)
        return None


class MediaRelay:
    """Fetches art/thumbnails and camera frames and publishes them over MQTT."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._unsubs: list = []
        # Art
        self._art_entities: Set[str] = set()
        self._art_unsub = None
        self._art_keys: Dict[str, str] = {}
        self._art_tasks: Dict[str, asyncio.Task] = {}
        # Camera
        self._camera_allowed: Set[str] = set()
        self._viewers: Dict[str, Dict[str, Tuple[float, int, float]]] = {}
        self._streams: Dict[str, asyncio.Task] = {}

    async def async_setup(self) -> None:
        self._unsubs.append(
            await mqtt.async_subscribe(self.hass, f"{FIXED_DEVICE_BASE}/+/camera", self._on_camera_request)
        )

    async def async_unload(self) -> None:
        for u in self._unsubs:
            try:
                u()
            except Exception:
                pass
        self._unsubs.clear()
        if self._art_unsub:
            self._art_unsub()
            self._art_unsub = None
        for t in list(self._art_tasks.values()) + list(self._streams.values()):
            t.cancel()
        self._art_tasks.clear()
        self._streams.clear()

    # ── configuration ──────────────────────────────────────────────────────
    async def async_configure(self, art_entities: Set[str], camera_entities: Set[str]) -> None:
        """(Re)configure which entities the relay serves (derived from profiles)."""
        self._camera_allowed = set(camera_entities)
        for ent in list(self._streams):
            if ent not in self._camera_allowed:
                self._viewers.pop(ent, None)
                self._streams.pop(ent).cancel()

        art_entities = set(art_entities)
        removed = self._art_entities - art_entities
        for ent in removed:
            self._art_keys.pop(ent, None)
            task = self._art_tasks.pop(ent, None)
            if task:
                task.cancel()  # else an in-flight fetch re-publishes the art after the clear
            await mqtt.async_publish(self.hass, art_topic(ent), "", qos=0, retain=True)
        if art_entities != self._art_entities or self._art_unsub is None:
            if self._art_unsub:
                self._art_unsub()
                self._art_unsub = None
            if art_entities:
                self._art_unsub = async_track_state_change_event(self.hass, list(art_entities), self._on_art_state)
        added = art_entities - self._art_entities
        self._art_entities = art_entities
        for ent in added:
            self._schedule_art(ent, force=True)

    # ── album art / thumbnails ──────────────────────────────────────────────
    @callback
    def _on_art_state(self, event: Event) -> None:
        ent = event.data.get("entity_id")
        if isinstance(ent, str) and ent in self._art_entities:
            self._schedule_art(ent)

    def _art_key(self, entity_id: str) -> str:
        st = self.hass.states.get(entity_id)
        if st is None:
            return ""
        pic = _strip_token(st.attributes.get("entity_picture"))
        if entity_id.startswith("image."):
            # image.* state is the last-updated timestamp; the URL token rotates
            return f"{st.state}|{pic}"
        if st.state in ("off", "idle", "standby", "unavailable", "unknown"):
            return ""
        return pic

    def _schedule_art(self, entity_id: str, force: bool = False) -> None:
        key = self._art_key(entity_id)
        if not force and self._art_keys.get(entity_id) == key:
            return
        self._art_keys[entity_id] = key
        prev = self._art_tasks.pop(entity_id, None)
        if prev:
            prev.cancel()
        self._art_tasks[entity_id] = self.hass.async_create_task(self._publish_art(entity_id, key))

    async def _publish_art(self, entity_id: str, key: str) -> None:
        try:
            payload: bytes = b""
            if key:
                raw = await self._fetch_image(entity_id)
                if raw:
                    payload = await self.hass.async_add_executor_job(_to_jpeg, raw, ART_MAX_PX) or b""
            await mqtt.async_publish(self.hass, art_topic(entity_id), payload, qos=0, retain=True)
            _LOGGER.debug("art: %s -> %d bytes", entity_id, len(payload))
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.debug("art: publish failed for %s", entity_id, exc_info=True)
        finally:
            if self._art_tasks.get(entity_id) is asyncio.current_task():
                self._art_tasks.pop(entity_id, None)

    def _entity_object(self, entity_id: str) -> Any:
        comp = self.hass.data.get(entity_id.split(".", 1)[0])
        get = getattr(comp, "get_entity", None)
        return get(entity_id) if callable(get) else None

    async def _fetch_image(self, entity_id: str) -> Optional[bytes]:
        ent = self._entity_object(entity_id)
        try:
            if ent is not None and entity_id.startswith("media_player."):
                data, _ctype = await ent.async_get_media_image()
                if data:
                    return data
            elif ent is not None and entity_id.startswith("image."):
                data = await ent.async_image()
                if data:
                    return data
        except Exception:
            _LOGGER.debug("art: entity fetch failed for %s, trying URL", entity_id, exc_info=True)
        return await self._fetch_picture_url(entity_id)

    async def _fetch_picture_url(self, entity_id: str) -> Optional[bytes]:
        st = self.hass.states.get(entity_id)
        pic = st.attributes.get("entity_picture") if st else None
        if not isinstance(pic, str) or not pic:
            return None
        from homeassistant.helpers.aiohttp_client import async_get_clientsession  # type: ignore
        url = pic
        if pic.startswith("/"):
            from homeassistant.helpers.network import get_url  # type: ignore
            url = get_url(self.hass, prefer_external=False) + pic
        try:
            session = async_get_clientsession(self.hass, verify_ssl=False)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                return await resp.read()
        except Exception:
            _LOGGER.debug("art: URL fetch failed for %s", entity_id, exc_info=True)
            return None

    # ── camera frames ───────────────────────────────────────────────────────
    async def _on_camera_request(self, msg) -> None:
        topic = getattr(msg, "topic", "") or ""
        parts = topic.split("/")
        device_id = parts[2] if len(parts) >= 4 else ""
        raw = msg.payload.decode("utf-8", "ignore") if isinstance(msg.payload, bytes) else str(msg.payload or "")
        try:
            req = json.loads(raw) if raw else {}
        except ValueError:
            return
        if not isinstance(req, dict):
            return
        ent = req.get("entity_id")
        if not isinstance(ent, str) or not ent.startswith("camera.") or ent not in self._camera_allowed:
            _LOGGER.debug("camera: ignoring request for %r from %s", ent, device_id)
            return
        viewers = self._viewers.setdefault(ent, {})
        if req.get("active"):
            try:
                width = int(req.get("width") or 0)
            except (TypeError, ValueError):
                width = 0
            try:
                interval = float(req.get("interval") or 1.0)
            except (TypeError, ValueError):
                interval = 1.0
            viewers[device_id] = (time.monotonic() + VIEWER_TTL, max(0, min(width, FRAME_MAX_PX)),
                                  max(FRAME_MIN_INTERVAL, min(interval, FRAME_MAX_INTERVAL)))
            task = self._streams.get(ent)
            if task is None or task.done():
                # Background task: a long-lived relay must not block HA startup/shutdown
                self._streams[ent] = self.hass.async_create_background_task(
                    self._stream(ent), name=f"ha_mqtt_dash camera relay {ent}")
        else:
            viewers.pop(device_id, None)

    def _live_viewers(self, ent: str) -> Dict[str, Tuple[float, int, float]]:
        now = time.monotonic()
        viewers = self._viewers.get(ent, {})
        for dev in [d for d, v in viewers.items() if v[0] < now]:
            viewers.pop(dev, None)
        return viewers

    async def _stream(self, ent: str) -> None:
        from homeassistant.components.camera import async_get_image  # type: ignore
        backoff = 0.0
        _LOGGER.debug("camera: start relay for %s", ent)
        try:
            while True:
                viewers = self._live_viewers(ent)
                if not viewers:
                    break
                width = max(v[1] for v in viewers.values()) or None
                interval = min(v[2] for v in viewers.values())
                started = time.monotonic()
                try:
                    image = await async_get_image(self.hass, ent, timeout=8, width=width)
                    data = image.content
                    if width and len(data) > 150_000:
                        # Camera ignored the width hint (no TurboJPEG): shrink ourselves
                        data = await self.hass.async_add_executor_job(_to_jpeg, data, width) or data
                    await mqtt.async_publish(self.hass, frame_topic(ent), data, qos=0, retain=False)
                    backoff = 0.0
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    # Back off so an unreachable camera isn't hammered (go2rtc
                    # leaks resources on every failed dial).
                    backoff = min(FRAME_BACKOFF_MAX, max(2.0, backoff * 2))
                    _LOGGER.debug("camera: frame failed for %s (%s); retry in %.0fs", ent, err, backoff)
                elapsed = time.monotonic() - started
                await asyncio.sleep(max(backoff, interval - elapsed, 0.05))
        finally:
            if self._streams.get(ent) is asyncio.current_task():
                self._streams.pop(ent, None)
            _LOGGER.debug("camera: stop relay for %s", ent)
