"""Requests to panels that must arrive: video, casting, notifications.

MQTT only reaches a panel whose link is up, and the broker notices a dead link
late (a sleeping iPad's keepalive is 15 min). So each such request carries an
id ("rid") and stays here until the panel acknowledges it on
``mqttdash/dev/<id>/ack``. Until then it is re-sent, the panel is woken over
MQTT and then by its charger plug (the only thing that reaches an iPad whose
Wi-Fi is asleep), and everything waiting goes out again the moment the panel
shows up. A request that isn't acknowledged within its time to live is dropped.

No Home Assistant imports: the bridge passes in how to publish and to wake.
"""
from __future__ import annotations

import json
import logging
import secrets
import time
from typing import Any, Awaitable, Callable, Dict, Optional

_LOGGER = logging.getLogger(__name__)

RESEND_AT = (4, 10, 20)     # s after the first send; then every RESEND_EVERY
RESEND_EVERY = 15
MQTT_WAKE_AFTER = 4         # unanswered this long: ask the panel to wake (over MQTT)
POWER_WAKE_AFTER = 12       # …this long: wake it with the charger plug
POWER_WAKE_EVERY = 180      # charger wakes for requests at most this often per panel
FLUSH_GAP = 2               # re-sending everything on contact at most this often

# Time to live per kind: a video started minutes late is still wanted, a pause isn't
TTL = {"play_video": 180, "stop_video": 60, "video_control": 30, "notify": 900}
WAKE_FOR = ("play_video", "notify")   # a stop or a pause isn't worth waking a sleeping panel for


class PanelOutbox:
    def __init__(self, publish: Callable[[str, str], Awaitable[None]],
                 wake: Callable[[str, bool], Awaitable[bool]],
                 on_expired: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._publish, self._wake, self._on_expired, self._clock = publish, wake, on_expired, clock
        self._items: Dict[str, Dict[str, Dict[str, Any]]] = {}   # device -> rid -> item
        self._last_power_wake: Dict[str, float] = {}
        self._last_flush: Dict[str, float] = {}

    def pending(self, device_id: str) -> int:
        return len(self._items.get(device_id) or {})

    async def send(self, device_id: str, topic: str, payload: Dict[str, Any], kind: str) -> str:
        rid = secrets.token_hex(4)
        now = self._clock()
        item = {"topic": topic, "payload": {**payload, "rid": rid}, "kind": kind, "created": now,
                "ttl": TTL.get(kind, 60), "sends": 0, "last_sent": None, "mqtt_wake": False, "power_wake": False}
        # A newer request of the same kind replaces a waiting one (stop after play, seek after seek)
        mine = self._items.setdefault(device_id, {})
        if kind in ("stop_video", "video_control"):
            for old in [r for r, it in mine.items() if it["kind"] == kind]:
                mine.pop(old)
        if kind == "stop_video":   # a video that never started needn't start (or pause) now
            for old in [r for r, it in mine.items() if it["kind"] in ("play_video", "video_control")]:
                mine.pop(old)
        mine[rid] = item
        await self._send(item)
        return rid

    def ack(self, device_id: str, rid: Any) -> bool:
        item = (self._items.get(device_id) or {}).pop(str(rid), None)
        if item is None:
            return False
        _LOGGER.debug("panel %s acknowledged %s after %.1fs (%s sends)", device_id, item["kind"],
                      self._clock() - item["created"], item["sends"])
        return True

    async def flush(self, device_id: str) -> None:
        """The panel just showed up (hello, status, telemetry): send what's waiting now."""
        mine = self._items.get(device_id)
        now = self._clock()
        if not mine or now - self._last_flush.get(device_id, -FLUSH_GAP) < FLUSH_GAP:
            return
        self._last_flush[device_id] = now
        for item in list(mine.values()):
            await self._send(item)

    async def tick(self) -> None:
        now = self._clock()
        for device_id, mine in list(self._items.items()):
            for rid, item in list(mine.items()):
                age = now - item["created"]
                if age >= item["ttl"]:
                    mine.pop(rid, None)
                    _LOGGER.warning("panel %s didn't acknowledge %s within %ss: dropped", device_id, item["kind"], item["ttl"])
                    if self._on_expired:
                        try:
                            self._on_expired(device_id, item["payload"])
                        except Exception:
                            _LOGGER.exception("outbox expiry callback failed")
                    continue
                wakes = item["kind"] in WAKE_FOR
                if wakes and not item["mqtt_wake"] and age >= MQTT_WAKE_AFTER:
                    item["mqtt_wake"] = True
                    await self._safe_wake(device_id, False)
                if wakes and not item["power_wake"] and age >= POWER_WAKE_AFTER:
                    item["power_wake"] = True
                    if now - self._last_power_wake.get(device_id, -POWER_WAKE_EVERY) >= POWER_WAKE_EVERY:
                        if await self._safe_wake(device_id, True):
                            self._last_power_wake[device_id] = now
                if self._resend_due(item, age, now):
                    await self._send(item)
            if not mine:
                self._items.pop(device_id, None)

    def clear(self) -> None:
        self._items.clear()

    def _resend_due(self, item: Dict[str, Any], age: float, now: float) -> bool:
        n = item["sends"]
        if n <= len(RESEND_AT):
            return age >= RESEND_AT[n - 1] if n >= 1 else True
        return now - (item["last_sent"] or 0) >= RESEND_EVERY

    async def _send(self, item: Dict[str, Any]) -> None:
        item["sends"] += 1
        item["last_sent"] = self._clock()
        try:
            await self._publish(item["topic"], json.dumps(item["payload"]))
        except Exception as err:
            _LOGGER.debug("outbox: publish to %s failed: %s", item["topic"], err)

    async def _safe_wake(self, device_id: str, power: bool) -> bool:
        try:
            return bool(await self._wake(device_id, power))
        except Exception:
            _LOGGER.exception("outbox: waking %s failed", device_id)
            return False
