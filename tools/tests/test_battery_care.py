import asyncio
import time
import types
from unittest.mock import AsyncMock

from helpers import FakeState, make_hass


def _care(start=35, stop=80):
    from custom_components.ha_mqtt_dash import battery_care as bc

    bc.mqtt.async_publish = AsyncMock()
    charger = {"state": "on"}
    hass, states = make_hass()
    hass.states.get = lambda e: FakeState(charger["state"]) if e == "switch.charger" else None

    async def svc(domain, service, data, blocking=False):
        charger["state"] = "on" if service == "turn_on" else "off"
    hass.services.async_call = svc
    hass.async_create_task = lambda coro: coro.close()
    store = {}

    class Helper:
        async def update_device_settings(self, dev, patch):
            store.setdefault(dev, {}).update(patch)
            return store[dev]

    bridge = types.SimpleNamespace(cfg={"devices": [{"device_id": "kitchen"}]}, _telemetry={"kitchen": {}},
                                   _storage_helper=Helper(), get_device_settings=lambda d: store.get(d, {}))
    care = bc.BatteryCare(hass, bridge)
    asyncio.run(care.async_update_settings("kitchen", {"enabled": True, "charger": "switch.charger", "start": start, "stop": stop}))
    return bc, care, bridge, charger


def _report(care, bridge, battery):
    bridge._telemetry["kitchen"]["battery"] = battery
    care._last_report["kitchen"] = time.monotonic()
    asyncio.run(care.async_evaluate("kitchen"))
    return care.status("kitchen")


def test_hysteresis():
    _, care, bridge, charger = _care()
    assert _report(care, bridge, 85)["state"] == "resting" and charger["state"] == "off"
    assert _report(care, bridge, 60)["state"] == "resting"          # holds between the levels
    assert _report(care, bridge, 35)["state"] == "charging" and charger["state"] == "on"
    assert _report(care, bridge, 60)["state"] == "charging"         # keeps charging up to stop
    assert _report(care, bridge, 80)["state"] == "resting"


def test_fail_safe_charges_when_reports_stop():
    _, care, bridge, charger = _care()
    _report(care, bridge, 90)
    assert charger["state"] == "off"
    care._last_report["kitchen"] = time.monotonic() - 3600
    care._started -= 3600  # past the startup grace period
    asyncio.run(care.async_evaluate("kitchen"))
    assert charger["state"] == "on"
    assert "charging to be safe" in care.status("kitchen")["reason"]


def test_waits_for_first_report_during_grace():
    _, care, bridge, charger = _care()
    charger["state"] = "off"
    asyncio.run(care.async_evaluate("kitchen"))
    assert charger["state"] == "off"


def test_levels_are_clamped():
    bc, *_ = _care()
    assert bc.clamp_levels(75, 70) == (60, 70)
    assert bc.clamp_levels(5, 200) == (10, 100)
    assert bc.clamp_levels("x", None) == (35, 80)
