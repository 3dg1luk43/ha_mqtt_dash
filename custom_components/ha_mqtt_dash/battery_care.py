"""Battery care: keep an old iPad's battery between two levels.

Wall panels sit on the charger 24/7, which wears out an old Li-ion battery
fast. With a smart plug (any switch/light/input_boolean) powering the
charger, this turns charging on at the "start" level and off at the "stop"
level.

Getting a reading, cheapest first:
1. A reachable panel (status ``online``, or ``sleeping`` over the app's
   background link) is asked over MQTT; that never turns the screen on.
2. Only when the panel doesn't answer (screen off with Wi-Fi asleep, link
   down) is it woken by power: connecting the charger turns the iPad's screen
   on, the app reconnects and reports, and then it is told to go back to sleep
   (quietly; the kiosk tweak mutes the chime while the panel is locked).
   Charger wakes are rate limited.

A check leaves the charger as it found it unless a level says otherwise.
Optional presence entities pause battery care (no checks, no switching) while
nobody is home. Fail-safe: a panel that doesn't answer a charger wake, or
hasn't reported for STALE_AFTER, gets the charger switched ON; a dead battery
is worse than a few extra charge cycles.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components import mqtt  # type: ignore
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.helpers.dispatcher import async_dispatcher_send  # type: ignore
from homeassistant.helpers.event import async_track_time_interval  # type: ignore

from .const import DOMAIN, FIXED_DEVICE_BASE

_LOGGER = logging.getLogger(__name__)

SIGNAL_BATTERY_CARE_UPDATED = f"{DOMAIN}_battery_care_updated"

DEFAULTS: Dict[str, Any] = {"enabled": False, "charger": "", "start": 35, "stop": 80, "presence": []}
CHECK_WHILE_CHARGING = 5 * 60   # want a fresh reading this often while charging
CHECK_WHILE_RESTING = 15 * 60   # …and while running on battery
REPORT_TIMEOUT = 90             # a reachable panel answers a report request within this
WAKE_TIMEOUT = 3 * 60           # after a charger wake, wait this long for the report
WAKE_EVERY_CHARGING = 30 * 60   # automatic charger wakes at most this often while charging
WAKE_EVERY_RESTING = 2 * 3600   # …and while resting (drain with the screen off is slow)
POWER_GAP = 5                   # off → on gap when the charger was already on
STALE_AFTER = 4 * 3600          # no reading for this long → fail-safe charging
STARTUP_GRACE = 10 * 60         # after HA start, wait this long before waking / fail-safe
MIN_GAP = 10                    # start must be at least this many % below stop
REACHABLE = ("online", "sleeping")


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


def _entity_list(value: Any) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [v for v in value if isinstance(v, str) and "." in v]


def _iso(wall: Optional[float]) -> Optional[str]:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(wall)) if wall else None


class BatteryCare:
    def __init__(self, hass: HomeAssistant, bridge) -> None:
        self.hass = hass
        self.bridge = bridge
        self._started = time.monotonic()
        self._last_report: Dict[str, float] = {}
        self._last_report_wall: Dict[str, float] = {}
        self._last_request: Dict[str, float] = {}
        self._link: Dict[str, str] = {}               # last status topic value per panel
        self._pending: Dict[str, Dict[str, Any]] = {}  # report request / charger wake in flight
        self._last_wake: Dict[str, float] = {}
        self._last_wake_wall: Dict[str, float] = {}
        self._last_wake_result: Dict[str, str] = {}
        self._restore: Dict[str, bool] = {}             # charger state to return to after a wake
        self._status: Dict[str, Dict[str, Any]] = {}
        self._unsub = None

    async def async_setup(self) -> None:
        self._unsub = async_track_time_interval(self.hass, self._tick, timedelta(seconds=30))

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
        cfg["presence"] = _entity_list(cfg.get("presence"))
        return cfg

    async def async_update_settings(self, device_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self.settings(device_id)
        cfg.update({k: v for k, v in patch.items() if k in DEFAULTS})
        cfg["start"], cfg["stop"] = clamp_levels(cfg.get("start"), cfg.get("stop"))
        cfg["enabled"] = bool(cfg.get("enabled"))
        cfg["charger"] = str(cfg.get("charger") or "")
        cfg["presence"] = _entity_list(cfg.get("presence"))
        await self.bridge._storage_helper.update_device_settings(device_id, {"battery": cfg})
        await self.async_evaluate(device_id)
        return cfg

    def status(self, device_id: str) -> Dict[str, Any]:
        return dict(self._status.get(device_id) or {"state": "disabled"})

    def diagnostics(self, device_id: str) -> Dict[str, Any]:
        """For the panel's "Last contact" sensor."""
        return {
            "link": self._link.get(device_id),
            "last_battery_report": _iso(self._last_report_wall.get(device_id)),
            "last_charger_wake": _iso(self._last_wake_wall.get(device_id)),
            "last_charger_wake_result": self._last_wake_result.get(device_id),
            "check_in_progress": (self._pending.get(device_id) or {}).get("kind"),
        }

    def someone_home(self, cfg: Dict[str, Any]) -> bool:
        """True without presence entities, or when any of them is home. Trackers
        that are all unavailable don't pause anything (fail open)."""
        known = []
        for eid in cfg.get("presence") or []:
            st = self.hass.states.get(eid)
            if st is not None and st.state not in ("unavailable", "unknown"):
                known.append(st.state)
        return not known or "home" in known

    # ── inputs ─────────────────────────────────────────────────────────────
    def note_report(self, device_id: str) -> None:
        """Called by the bridge whenever the panel publishes its battery level (live)."""
        self._last_report[device_id] = time.monotonic()
        self._last_report_wall[device_id] = time.time()
        pend = self._pending.pop(device_id, None)
        if pend and pend.get("kind") == "wake":
            self._last_wake_result[device_id] = "answered"
            self._restore[device_id] = bool(pend.get("was_on"))
            _LOGGER.debug("battery care %s: panel answered the charger wake", device_id)
        if pend and pend.get("sleep_after"):
            # We turned the screen on only to read the battery: put it back.
            self.hass.async_create_task(self._send_request(device_id, "sleep"))
        self.hass.async_create_task(self.async_evaluate(device_id))

    def note_link(self, device_id: str, state: str) -> None:
        """Status topic value: online / sleeping / offline."""
        if self._link.get(device_id) != state:
            self._link[device_id] = state
            async_dispatcher_send(self.hass, SIGNAL_BATTERY_CARE_UPDATED, device_id)

    def reachable(self, device_id: str) -> bool:
        return self._link.get(device_id) in REACHABLE

    async def _send_request(self, device_id: str, action: str) -> None:
        await mqtt.async_publish(self.hass, f"{FIXED_DEVICE_BASE}/{device_id}/request",
                                 json.dumps({"action": action}), qos=0, retain=False)

    async def async_request_report(self, device_id: str, *, manual: bool = False) -> None:
        """Ask the panel for a battery reading over MQTT; does not turn the screen on.
        Unanswered within REPORT_TIMEOUT, the next tick wakes it with the charger."""
        self._last_request[device_id] = time.monotonic()
        self._pending[device_id] = {"kind": "report", "since": time.monotonic(), "manual": manual}
        await self._send_request(device_id, "report")

    async def async_check_now(self, device_id: str) -> None:
        """"Check battery" button: MQTT if reachable, else wake with the charger."""
        cfg = self.settings(device_id)
        if self.reachable(device_id) or not cfg["charger"]:
            await self.async_request_report(device_id, manual=True)
        else:
            await self._charger_wake(device_id, cfg, sleep_after=True)

    async def async_wake_screen(self, device_id: str) -> bool:
        """"Wake screen" button. Over MQTT when the panel is reachable; otherwise by
        power, the only thing that reaches an iPad whose Wi-Fi is asleep. Returns
        False when there is no way to reach it."""
        await self._send_request(device_id, "wake")
        if self.reachable(device_id):
            return True
        cfg = self.settings(device_id)
        if not cfg["charger"]:
            return False
        await self._charger_wake(device_id, cfg, sleep_after=False)
        return True

    # ── charger wake ───────────────────────────────────────────────────────
    async def _switch(self, charger: str, on: bool) -> None:
        await self.hass.services.async_call("homeassistant", "turn_on" if on else "turn_off",
                                            {"entity_id": charger}, blocking=True)

    async def _charger_wake(self, device_id: str, cfg: Dict[str, Any], *, sleep_after: bool) -> None:
        charger = cfg["charger"]
        was_on = self._charger_on(charger)
        if was_on is None:
            _LOGGER.debug("battery care %s: charger %s unavailable, can't wake", device_id, charger)
            return
        now = time.monotonic()
        self._last_wake[device_id] = now
        self._last_wake_wall[device_id] = time.time()
        self._last_wake_result[device_id] = "waiting"
        self._pending[device_id] = {"kind": "wake", "since": now, "sleep_after": sleep_after, "was_on": was_on}
        _LOGGER.info("battery care %s: panel not answering, waking it with charger %s", device_id, charger)
        try:
            if was_on:
                # Connecting power is what turns the screen on: cycle it.
                await self._switch(charger, False)
                await asyncio.sleep(POWER_GAP)
            await self._switch(charger, True)
        except Exception:
            _LOGGER.warning("battery care: could not switch %s", charger, exc_info=True)
        await self.async_evaluate(device_id)

    def _wake_allowed(self, device_id: str, charging: Optional[bool]) -> bool:
        every = WAKE_EVERY_CHARGING if charging else WAKE_EVERY_RESTING
        last = self._last_wake.get(device_id)
        return last is None or time.monotonic() - last >= every

    # ── control loop ───────────────────────────────────────────────────────
    def _device_ids(self):
        for d in list(self.bridge.cfg.get("devices", []) or []):
            did = (d.get("device_id") or "").strip() if isinstance(d, dict) else ""
            if did:
                yield did

    async def _tick(self, _now=None) -> None:
        for did in self._device_ids():
            try:
                await self._tick_device(did)
            except Exception:
                _LOGGER.debug("battery care: tick failed for %s", did, exc_info=True)

    async def _tick_device(self, did: str) -> None:
        now = time.monotonic()
        pend = self._pending.get(did)
        if pend:  # time out whatever is in flight, manual ones included
            age = now - pend["since"]
            if pend["kind"] == "report" and age >= REPORT_TIMEOUT:
                self._pending.pop(did, None)
                cfg = self.settings(did)
                if cfg["charger"] and (pend.get("manual") or (cfg["enabled"] and self.someone_home(cfg)
                                                              and self._wake_allowed(did, self._charger_on(cfg["charger"])))):
                    await self._charger_wake(did, cfg, sleep_after=True)
            elif pend["kind"] == "wake" and age >= WAKE_TIMEOUT:
                self._pending.pop(did, None)
                self._last_wake_result[did] = "no answer"
                _LOGGER.warning("battery care %s: no report after the charger wake", did)
        cfg = self.settings(did)
        if not cfg["enabled"] or not cfg["charger"] or not self.someone_home(cfg):
            return await self.async_evaluate(did)
        if did not in self._pending:
            charging = self._charger_on(cfg["charger"])
            every = CHECK_WHILE_CHARGING if charging else CHECK_WHILE_RESTING
            last = self._last_report.get(did)
            if last is None or now - last >= every:  # a reading is due
                if self.reachable(did):
                    asked = self._last_request.get(did)
                    if asked is None or now - asked >= every:
                        await self.async_request_report(did)
                elif now - self._started >= STARTUP_GRACE and self._wake_allowed(did, charging):
                    await self._charger_wake(did, cfg, sleep_after=True)
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
            "presence": cfg["presence"] or None,
            "last_report": _iso(self._last_report_wall.get(device_id)),
        }
        last = self._last_report.get(device_id)

        if not cfg["enabled"]:
            status["state"] = "disabled"
            return self._publish_status(device_id, status)
        if not cfg["charger"]:
            status["state"] = "no_charger"
            status["reason"] = "Pick the charger plug in the integration options (Battery care)"
            return self._publish_status(device_id, status)
        if not self.someone_home(cfg):
            status["state"] = "away"
            status["reason"] = "nobody home: paused, charger left as it is"
            return self._publish_status(device_id, status)

        charger_on = self._charger_on(cfg["charger"])
        now = time.monotonic()
        unanswered = self._last_wake_result.get(device_id) == "no answer"
        stale = last is None or (now - last) > STALE_AFTER or unanswered
        in_grace = (now - self._started) < STARTUP_GRACE
        pend = self._pending.get(device_id) or {}
        restore = self._restore.pop(device_id, None)

        want: Optional[bool] = None
        if pend.get("kind") == "wake":
            status["reason"] = "woke the panel with the charger, waiting for its report"
        elif stale or battery is None:
            if in_grace:
                status["reason"] = "waiting for the first battery report"
            else:
                want = True
                status["reason"] = ("panel didn't answer the charger wake: charging to be safe" if unanswered
                                    else "no recent battery report: charging to be safe")
        elif battery <= cfg["start"]:
            want = True
            status["reason"] = f"battery {battery}% ≤ {cfg['start']}%"
        elif battery >= cfg["stop"]:
            want = False
            status["reason"] = f"battery {battery}% ≥ {cfg['stop']}%"
        else:
            status["reason"] = f"holding between {cfg['start']}% and {cfg['stop']}%"
            want = restore  # after a check-wake: back to how the charger was

        if want is not None and charger_on is not None and want != charger_on:
            service = "turn_on" if want else "turn_off"
            _LOGGER.info("battery care %s: %s charger %s (%s)", device_id, service, cfg["charger"], status["reason"])
            try:
                await self.hass.services.async_call("homeassistant", service, {"entity_id": cfg["charger"]}, blocking=False)
                charger_on = want
            except Exception:
                _LOGGER.warning("battery care: could not %s %s", service, cfg["charger"], exc_info=True)
        if pend.get("kind") == "wake":
            status["state"] = "checking"
        elif charger_on is None:
            status["state"] = "charger_unavailable"
        else:
            status["state"] = "charging" if charger_on else "resting"
        # A charger that is on while the panel says it isn't charging usually
        # means a loose cable or a too-weak power brick.
        if charger_on and tel.get("charging") is False and not stale and not pend:
            status["warning"] = "charger is on but the panel reports not charging"
        self._publish_status(device_id, status)

    def _publish_status(self, device_id: str, status: Dict[str, Any]) -> None:
        if self._status.get(device_id) != status:
            self._status[device_id] = status
            async_dispatcher_send(self.hass, SIGNAL_BATTERY_CARE_UPDATED, device_id)
