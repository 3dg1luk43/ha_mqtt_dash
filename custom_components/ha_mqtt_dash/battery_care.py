"""Battery care: keep an old iPad's battery between two levels.

Wall panels sit on the charger 24/7, which wears out an old Li-ion battery
fast. With a smart plug (any switch/light/input_boolean) powering the
charger, this turns charging on at the "start" level and off at the "stop"
level. The panel reports its battery even with the screen off (the app keeps
a tiny background MQTT link), so the screen never has to wake for a check.

Fail-safe: if the panel stops reporting (asleep without the background link,
Wi-Fi off, app crashed) the charger is switched ON — a dead battery is worse
than a few extra charge cycles.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.components import mqtt  # type: ignore
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.helpers.dispatcher import async_dispatcher_send  # type: ignore
from homeassistant.helpers.event import async_track_time_interval  # type: ignore

from .const import DOMAIN, FIXED_DEVICE_BASE

_LOGGER = logging.getLogger(__name__)

SIGNAL_BATTERY_CARE_UPDATED = f"{DOMAIN}_battery_care_updated"

DEFAULTS: Dict[str, Any] = {"enabled": False, "charger": "", "start": 35, "stop": 80}
CHECK_WHILE_CHARGING = 5 * 60   # ask for a fresh reading this often while charging
CHECK_WHILE_RESTING = 15 * 60   # …and while running on battery
STALE_AFTER = 45 * 60           # no reading for this long → fail-safe charging
STARTUP_GRACE = 10 * 60         # after HA start, wait this long before the fail-safe
MIN_GAP = 10                    # start must be at least this many % below stop


def clamp_levels(start: Any, stop: Any) -> tuple[int, int]:
    try:
        start = int(float(start))
    except (TypeError, ValueError):
        start = DEFAULTS["start"]
    try:
        stop = int(float(stop))
    except (TypeError, ValueError):
        stop = DEFAULTS["stop"]
    stop = max(20 + MIN_GAP, min(100, stop))
    start = max(10, min(stop - MIN_GAP, start))
    return start, stop


class BatteryCare:
    def __init__(self, hass: HomeAssistant, bridge) -> None:
        self.hass = hass
        self.bridge = bridge
        self._started = time.monotonic()
        self._last_report: Dict[str, float] = {}
        self._last_report_wall: Dict[str, float] = {}
        self._last_request: Dict[str, float] = {}
        self._status: Dict[str, Dict[str, Any]] = {}
        self._unsub = None

    async def async_setup(self) -> None:
        self._unsub = async_track_time_interval(self.hass, self._tick, timedelta(minutes=1))

    async def async_unload(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    # ── settings (persisted in the Store under device_settings[<id>]["battery"]) ──
    def settings(self, device_id: str) -> Dict[str, Any]:
        cur = self.bridge.get_device_settings(device_id) or {}
        cfg = dict(DEFAULTS)
        if isinstance(cur.get("battery"), dict):
            cfg.update(cur["battery"])
        cfg["start"], cfg["stop"] = clamp_levels(cfg.get("start"), cfg.get("stop"))
        return cfg

    async def async_update_settings(self, device_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self.settings(device_id)
        cfg.update({k: v for k, v in patch.items() if k in DEFAULTS})
        cfg["start"], cfg["stop"] = clamp_levels(cfg.get("start"), cfg.get("stop"))
        cfg["enabled"] = bool(cfg.get("enabled"))
        cfg["charger"] = str(cfg.get("charger") or "")
        await self.bridge._storage_helper.update_device_settings(device_id, {"battery": cfg})
        await self.async_evaluate(device_id)
        return cfg

    def status(self, device_id: str) -> Dict[str, Any]:
        return dict(self._status.get(device_id) or {"state": "disabled"})

    # ── inputs ─────────────────────────────────────────────────────────────
    def note_report(self, device_id: str) -> None:
        """Called by the bridge whenever the panel publishes its battery level."""
        self._last_report[device_id] = time.monotonic()
        self._last_report_wall[device_id] = time.time()
        self.hass.async_create_task(self.async_evaluate(device_id))

    async def async_request_report(self, device_id: str) -> None:
        """Ask the panel for a battery reading; does not turn the screen on."""
        self._last_request[device_id] = time.monotonic()
        await mqtt.async_publish(self.hass, f"{FIXED_DEVICE_BASE}/{device_id}/request",
                                 json.dumps({"action": "report"}), qos=0, retain=False)

    # ── control loop ───────────────────────────────────────────────────────
    def _device_ids(self):
        for d in list(self.bridge.cfg.get("devices", []) or []):
            did = (d.get("device_id") or "").strip() if isinstance(d, dict) else ""
            if did:
                yield did

    async def _tick(self, _now=None) -> None:
        now = time.monotonic()
        for did in self._device_ids():
            cfg = self.settings(did)
            if not cfg["enabled"] or not cfg["charger"]:
                continue
            charging = self._charger_on(cfg["charger"])
            every = CHECK_WHILE_CHARGING if charging else CHECK_WHILE_RESTING
            last = max(self._last_report.get(did, 0.0), self._last_request.get(did, 0.0))
            if now - last >= every:
                try:
                    await self.async_request_report(did)
                except Exception:
                    _LOGGER.debug("battery care: report request failed for %s", did, exc_info=True)
            await self.async_evaluate(did)

    def _charger_on(self, charger: str) -> Optional[bool]:
        st = self.hass.states.get(charger)
        if st is None or st.state in ("unavailable", "unknown"):
            return None
        return st.state == "on"

    async def async_evaluate(self, device_id: str) -> None:
        cfg = self.settings(device_id)
        tel = (self.bridge._telemetry or {}).get(device_id, {})
        battery = tel.get("battery")
        status: Dict[str, Any] = {
            "battery": battery,
            "panel_charging": tel.get("charging"),
            "charger": cfg["charger"] or None,
            "start": cfg["start"],
            "stop": cfg["stop"],
        }
        last = self._last_report.get(device_id)
        if device_id in self._last_report_wall:
            status["last_report"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self._last_report_wall[device_id]))

        if not cfg["enabled"]:
            status["state"] = "disabled"
            return self._publish_status(device_id, status)
        if not cfg["charger"]:
            status["state"] = "no_charger"
            status["reason"] = "Pick the charger plug in the integration options (Battery care)"
            return self._publish_status(device_id, status)

        charger_on = self._charger_on(cfg["charger"])
        now = time.monotonic()
        stale = last is None or (now - last) > STALE_AFTER
        in_grace = (now - self._started) < STARTUP_GRACE

        want: Optional[bool] = None
        if stale or battery is None:
            if in_grace:
                status["reason"] = "waiting for the first battery report"
            else:
                want = True
                status["reason"] = "no recent battery report — charging to be safe"
        elif battery <= cfg["start"]:
            want = True
            status["reason"] = f"battery {battery}% ≤ {cfg['start']}%"
        elif battery >= cfg["stop"]:
            want = False
            status["reason"] = f"battery {battery}% ≥ {cfg['stop']}%"
        else:
            status["reason"] = f"holding between {cfg['start']}% and {cfg['stop']}%"

        if want is not None and charger_on is not None and want != charger_on:
            service = "turn_on" if want else "turn_off"
            _LOGGER.info("battery care %s: %s charger %s (%s)", device_id, service, cfg["charger"], status["reason"])
            try:
                await self.hass.services.async_call("homeassistant", service, {"entity_id": cfg["charger"]}, blocking=False)
                charger_on = want
            except Exception:
                _LOGGER.warning("battery care: could not %s %s", service, cfg["charger"], exc_info=True)
        if charger_on is None:
            status["state"] = "charger_unavailable"
        else:
            status["state"] = "charging" if charger_on else "resting"
        # A charger that is on while the panel says it isn't charging usually
        # means a loose cable or a too-weak power brick.
        if charger_on and tel.get("charging") is False and not stale:
            status["warning"] = "charger is on but the panel reports not charging"
        self._publish_status(device_id, status)

    def _publish_status(self, device_id: str, status: Dict[str, Any]) -> None:
        if self._status.get(device_id) != status:
            self._status[device_id] = status
            async_dispatcher_send(self.hass, SIGNAL_BATTERY_CARE_UPDATED, device_id)
