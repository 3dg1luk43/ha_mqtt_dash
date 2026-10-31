"""Panel lifecycle: placeholder layout, settings ownership, mirroring, hello."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from helpers import make_bridge


def _published(mb):
    return {c.args[1]: c.args[2] for c in mb.mqtt.async_publish.call_args_list}


def test_panel_without_profile_gets_placeholder_not_another_panels_layout():
    mb, bridge, *_ = make_bridge(profiles={"other_panel": {"ui": {"widgets": [{"id": "x", "type": "clock"}]}}})
    doc = bridge._build_config_for_device({"device_id": "kitchen", "profile": ""}, bridge.cfg)
    (w,) = doc["ui"]["widgets"]
    assert w["id"] == "setup" and w["type"] == "label"
    assert "dashboard editor" in w["text"] and "kitchen" in w["text"]


def test_profile_device_settings_are_not_published():
    prof = {"kitchen": {"device": {"keep_awake": True, "screensaver_timeout": 30, "brightness": 0.2},
                        "ui": {"widgets": [{"id": "c", "type": "clock"}]}}}
    mb, bridge, *_ = make_bridge(profiles=prof)
    doc = bridge._build_config_for_device(bridge.cfg["devices"][0], bridge.cfg)
    assert not {"keep_awake", "screensaver_timeout", "brightness"} & set(doc["device"])


def test_mirror_uses_profile_entities_and_ignores_old_manual_list():
    mb, bridge, *_ = make_bridge()
    bridge.cfg.update({"mirror_auto": False, "mirror_entities": ["light.not_in_any_profile"]})
    bridge._relay.async_configure = AsyncMock()
    mb.async_track_state_change_event = MagicMock()
    asyncio.run(bridge._maybe_start_mirror(publish_snapshot=False))
    assert "light.living" in bridge._mirror_wanted
    assert "light.not_in_any_profile" not in bridge._mirror_wanted


class _Store:
    def __init__(self, settings=None):
        self.settings = {"kitchen": dict(settings or {})}

    def is_purged_device(self, **_):
        return False

    def get_device_settings(self, did):
        return dict(self.settings.get(did, {}))

    async def update_device_settings(self, did, patch):
        self.settings.setdefault(did, {}).update(patch)
        return dict(self.settings[did])


def test_settings_change_publishes_all_settings():
    mb, bridge, *_ = make_bridge()
    mb.mqtt.async_publish = AsyncMock()
    bridge._storage_helper = _Store({"keep_awake": False, "orientation": "landscape"})
    asyncio.run(bridge.async_publish_device_settings("kitchen", screensaver_timeout=30, brightness=2))
    payload = json.loads(_published(mb)["mqttdash/dev/kitchen/settings"])
    assert payload == {"keep_awake": False, "orientation": "landscape", "screensaver_timeout": 30, "brightness": 1.0}


def test_hello_registers_a_new_panel_on_a_fresh_entry():
    mb, bridge, hass, _ = make_bridge(profiles={})
    bridge.entry.options, bridge.entry.data = {}, {"devices": [], "profiles": {}}
    bridge.cfg = {"devices": [], "profiles": {}}
    bridge._storage_helper = _Store()
    mb.mqtt.async_publish = AsyncMock()
    msg = MagicMock(topic="mqttdash/dev/hallway/hello", payload=json.dumps({"guid": "G1"}), retain=False)
    asyncio.run(bridge._on_device_hello(msg))
    saved = hass.config_entries.async_update_entry.call_args.kwargs["options"]["devices"]
    assert [d["device_id"] for d in saved] == ["hallway"]
    cfg = json.loads(_published(mb)["mqttdash/config/hallway/config"])
    assert cfg["ui"]["widgets"][0]["id"] == "setup"


def test_brightness_percent_mapping():
    from custom_components.ha_mqtt_dash.entities.brightness import brightness_from_percent, percent_from_brightness
    assert brightness_from_percent(35) == 0.35 and brightness_from_percent(0) == 0.05
    assert percent_from_brightness(0.354) == 35 and percent_from_brightness(3) == 100


def test_diagnostics_redacts_secrets():
    from custom_components.ha_mqtt_dash.diagnostics import REDACTED, profile_summary, redact
    out = redact({"mealie_api_key": "abc", "w": [{"stream_url": "rtsp://admin:pw@cam/1", "token": ""}], "label": "Kitchen"})
    assert out["mealie_api_key"] == REDACTED and out["label"] == "Kitchen"
    assert out["w"][0]["stream_url"] == f"rtsp://{REDACTED}@cam/1" and out["w"][0]["token"] == ""
    from helpers import sample_profiles
    s = profile_summary(sample_profiles()["kitchen"])
    assert s["pages"] == 2 and s["widgets"] == 10 and s["types"]["light"] == 2
