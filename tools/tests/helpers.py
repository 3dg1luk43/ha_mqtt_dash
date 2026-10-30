"""Shared fakes for the stubbed-HA tests."""
from unittest.mock import AsyncMock, MagicMock


class FakeState:
    def __init__(self, state, attributes=None):
        self.state = state
        self.attributes = attributes or {}


def make_hass(states=None):
    states = dict(states or {})
    hass = MagicMock()
    hass.states.get = lambda entity_id: states.get(entity_id)
    hass.services.async_call = AsyncMock()
    return hass, states


def sample_profiles():
    """A small multi-page profile touching every topic-injecting widget type."""
    return {
        "kitchen": {
            "ui": {
                "grid": {"columns": 7, "widget_dimensions": [146, 120]},
                "pages": [
                    {"name": "Main", "widgets": [
                        {"id": "l1", "type": "light", "entity_id": "light.living", "x": 0, "y": 0},
                        {"id": "l2", "type": "light", "entity_id": "light.plug", "dimmable": False, "x": 1, "y": 0},
                        {"id": "c1", "type": "climate", "entity_id": "climate.house", "temp_step": 0.5, "x": 2, "y": 0},
                        {"id": "t1", "type": "timer", "default_seconds": 180, "presets": [60, 300, "x", -5], "x": 3, "y": 0},
                        {"id": "a1", "type": "appliance", "entity_id": "sensor.washer_state",
                         "time_entity": "sensor.washer_time_remaining", "program_entity": "sensor.washer_program", "x": 0, "y": 1},
                        {"id": "s1", "type": "switch", "entity_id": "automation.night", "x": 1, "y": 1},
                    ]},
                    {"name": "Work", "widgets": [
                        {"id": "m1", "type": "mediaplayer", "entity_id": "media_player.spotify", "x": 0, "y": 0, "w": 3, "h": 3},
                        {"id": "cam", "type": "camera", "camera_entity": "camera.printer", "refresh_interval": 0.1,
                         "overlay_button": {"label": "Light", "action": "toggle", "entity_id": "light.printer"}, "x": 3, "y": 0},
                        {"id": "p1", "type": "printer", "status_entity": "sensor.k1c_status", "progress_entity": "sensor.k1c_progress",
                         "preview_entity": "image.k1c_preview", "layer_entity": "sensor.k1c_layer",
                         "nozzle_target_entity": "number.k1c_nozzle_target", "x": 5, "y": 0},
                        {"id": "sensor", "type": "sensor", "entity_id": "sensor.power", "x": 0, "y": 3},
                    ]},
                ],
            }
        }
    }


def make_bridge(states=None, profiles=None):
    from custom_components.ha_mqtt_dash import mqtt_bridge as mb

    hass, states = make_hass(states)
    profiles = profiles if profiles is not None else sample_profiles()
    entry = MagicMock()
    entry.data = {}
    entry.options = {"devices": [{"device_id": "kitchen", "profile": "kitchen"}], "profiles": profiles, "mirror_auto": True}
    bridge = mb.MqttBridge(hass, entry)
    bridge.cfg = {"devices": entry.options["devices"], "profiles": profiles}
    return mb, bridge, hass, states
