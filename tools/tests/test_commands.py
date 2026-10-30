import asyncio
from unittest.mock import AsyncMock

from helpers import FakeState, make_bridge


def _bridge_with_configs():
    mb, bridge, hass, states = make_bridge()
    mb.mqtt.async_publish = AsyncMock()
    asyncio.run(bridge.async_publish_all_configs())
    for e in ("light.living", "automation.night", "lock.front_door", "light.printer"):
        states[e] = FakeState("on")
    return bridge, hass


def test_only_profile_widgets_are_commandable():
    bridge, hass = _bridge_with_configs()
    assert {"light.living", "automation.night", "light.printer", "climate.house", "media_player.spotify"} <= bridge._commandable
    asyncio.run(bridge._handle_entity_command("lock.front_door", {"action": "turn_off"}))
    hass.services.async_call.assert_not_called()


def test_light_brightness_and_fallback_domain():
    bridge, hass = _bridge_with_configs()
    asyncio.run(bridge._handle_entity_command("light.living", {"action": "turn_on", "brightness": 128}))
    asyncio.run(bridge._handle_entity_command("automation.night", {"action": "turn_off"}))
    calls = [c.args[:3] for c in hass.services.async_call.call_args_list]
    assert ("light", "turn_on", {"entity_id": "light.living", "brightness": 128}) in calls
    assert ("homeassistant", "turn_off", {"entity_id": "automation.night"}) in calls


def test_non_dict_payload_ignored():
    bridge, hass = _bridge_with_configs()
    asyncio.run(bridge._handle_entity_command("light.living", ["turn_on"]))
    hass.services.async_call.assert_not_called()
