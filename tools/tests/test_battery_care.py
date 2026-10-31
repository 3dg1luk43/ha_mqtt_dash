import asyncio
import time
import types
from unittest.mock import AsyncMock

from helpers import FakeState, make_hass


def _care(start=35, stop=80, presence=None):
    from custom_components.ha_mqtt_dash import battery_care as bc

    bc.mqtt.async_publish = AsyncMock()
    bc.POWER_GAP = 0
    charger = {"state": "on", "calls": []}
    others = {}
    hass, states = make_hass()
    hass.states.get = lambda e: FakeState(charger["state"]) if e == "switch.charger" else others.get(e)

    async def svc(domain, service, data, blocking=False):
        charger["state"] = "on" if service == "turn_on" else "off"
        charger["calls"].append(service)
    hass.services.async_call = svc
    tasks = []
    hass.async_create_task = tasks.append
    store = {}

    class Helper:
        async def update_device_settings(self, dev, patch):
            store.setdefault(dev, {}).update(patch)
            return store[dev]

    bridge = types.SimpleNamespace(cfg={"devices": [{"device_id": "kitchen"}]}, _telemetry={"kitchen": {}},
                                   _storage_helper=Helper(), get_device_settings=lambda d: store.get(d, {}))
    care = bc.BatteryCare(hass, bridge)
    asyncio.run(care.async_update_settings("kitchen", {"enabled": True, "charger": "switch.charger", "start": start,
                                                       "stop": stop, "presence": presence or []}))
    care._tasks, care._others = tasks, others
    return bc, care, bridge, charger


def _run_tasks(care):
    while care._tasks:
        asyncio.run(care._tasks.pop(0))


def _published(bc):
    return [c.args[2] for c in bc.mqtt.async_publish.call_args_list]


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
    bc, care, bridge, charger = _care()
    _report(care, bridge, 90)
    assert charger["state"] == "off"
    care._last_report["kitchen"] = time.monotonic() - bc.STALE_AFTER - 60
    care._started -= 3600  # past the startup grace period
    asyncio.run(care.async_evaluate("kitchen"))
    assert charger["state"] == "on"
    assert "charging to be safe" in care.status("kitchen")["reason"]


def _due(bc, care):
    """Make a battery reading due and leave the startup grace period."""
    care._last_report["kitchen"] = time.monotonic() - bc.CHECK_WHILE_RESTING - 1
    care._started -= bc.STARTUP_GRACE + 1


def test_reachable_panel_is_asked_over_mqtt_only():
    bc, care, bridge, charger = _care()
    _report(care, bridge, 60)
    charger["state"], charger["calls"] = "off", []
    care.note_link("kitchen", "sleeping")
    _due(bc, care)
    asyncio.run(care._tick_device("kitchen"))
    assert _published(bc)[-1] == '{"action": "report"}'
    assert charger["calls"] == [] and care._pending["kitchen"]["kind"] == "report"


def test_unanswered_report_wakes_with_charger_then_restores_and_sleeps():
    bc, care, bridge, charger = _care()
    _report(care, bridge, 60)
    charger["state"], charger["calls"] = "off", []
    care.note_link("kitchen", "sleeping")
    _due(bc, care)
    asyncio.run(care._tick_device("kitchen"))
    care._pending["kitchen"]["since"] -= bc.REPORT_TIMEOUT
    asyncio.run(care._tick_device("kitchen"))
    assert charger["state"] == "on" and care.status("kitchen")["state"] == "checking"
    # the panel wakes up on power and reports: charger back off, screen back to sleep
    bridge._telemetry["kitchen"]["battery"] = 61
    care.note_report("kitchen")
    _run_tasks(care)
    assert charger["state"] == "off"
    assert '{"action": "sleep"}' in _published(bc)
    assert care.diagnostics("kitchen")["last_charger_wake_result"] == "answered"


def test_unreachable_panel_is_woken_but_rate_limited():
    bc, care, bridge, charger = _care()
    _report(care, bridge, 60)
    charger["state"], charger["calls"] = "on", []
    care.note_link("kitchen", "offline")
    _due(bc, care)
    asyncio.run(care._tick_device("kitchen"))
    assert charger["calls"] == ["turn_off", "turn_on"]   # power cycled: connecting it wakes the iPad
    care.note_report("kitchen")
    _run_tasks(care)
    charger["calls"] = []
    _due(bc, care)
    asyncio.run(care._tick_device("kitchen"))
    assert charger["calls"] == []                          # next automatic wake not due yet


def test_no_answer_keeps_charging():
    bc, care, bridge, charger = _care()
    _report(care, bridge, 60)
    charger["state"] = "off"
    care.note_link("kitchen", "offline")
    _due(bc, care)
    asyncio.run(care._tick_device("kitchen"))
    care._pending["kitchen"]["since"] -= bc.WAKE_TIMEOUT
    asyncio.run(care._tick_device("kitchen"))
    assert charger["state"] == "on"
    assert "didn't answer" in care.status("kitchen")["reason"]


def test_presence_pauses_battery_care():
    bc, care, bridge, charger = _care(presence=["person.a", "person.b"])
    care._others.update({"person.a": FakeState("not_home"), "person.b": FakeState("work")})
    charger["state"], charger["calls"] = "off", []
    care.note_link("kitchen", "offline")
    _due(bc, care)
    bridge._telemetry["kitchen"]["battery"] = 20
    asyncio.run(care._tick_device("kitchen"))
    assert care.status("kitchen")["state"] == "away"
    assert charger["calls"] == [] and not bc.mqtt.async_publish.called
    care._others["person.b"] = FakeState("home")
    _report(care, bridge, 20)
    assert charger["state"] == "on"


def test_unavailable_trackers_do_not_pause():
    _, care, *_ = _care(presence=["person.a"])
    care._others["person.a"] = FakeState("unavailable")
    assert care.someone_home(care.settings("kitchen"))


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
