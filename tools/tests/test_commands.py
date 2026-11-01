import json
import asyncio
from unittest.mock import AsyncMock

from helpers import FakeState, make_bridge


def _bridge_with_configs():
    mb, bridge, hass, states = make_bridge()
    mb.mqtt.async_publish = AsyncMock()
    asyncio.run(bridge.async_publish_all_configs())
    for e in ("light.living", "automation.night", "lock.front_door", "light.printer", "media_player.spotify"):
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


def test_media_player_controls_are_validated():
    bridge, hass = _bridge_with_configs()
    mp = "media_player.spotify"
    for cmd in (
        {"action": "volume_set", "volume_level": 1.7},
        {"action": "select_source", "source": " Kitchen speaker "},
        {"action": "repeat_set", "repeat": "one"},
        {"action": "shuffle_set", "shuffle": True},
        {"action": "repeat_set", "repeat": "sometimes"},   # rejected
        {"action": "volume_set", "volume_level": "loud"},  # rejected
        {"action": "select_source", "source": ""},         # rejected
    ):
        asyncio.run(bridge._handle_entity_command(mp, cmd))
    calls = [c.args[:3] for c in hass.services.async_call.call_args_list]
    assert calls == [
        ("media_player", "volume_set", {"entity_id": mp, "volume_level": 1.0}),
        ("media_player", "select_source", {"entity_id": mp, "source": "Kitchen speaker"}),
        ("media_player", "repeat_set", {"entity_id": mp, "repeat": "one"}),
        ("media_player", "shuffle_set", {"entity_id": mp, "shuffle": True}),
    ]


def test_video_requests_reach_the_panel():
    bridge, hass = _bridge_with_configs()
    from custom_components.ha_mqtt_dash import mqtt_bridge as mb
    mb.mqtt.async_publish.reset_mock()
    for action, extra in (("play_video", {"url": "http://x/master.m3u8"}), ("video_control", {"cmd": "pause"}), ("stop_video", None)):
        asyncio.run(bridge.async_send_device_request("kitchen", action, extra))
    sent = [json.loads(c.args[2]) for c in mb.mqtt.async_publish.call_args_list]
    assert [{k: v for k, v in p.items() if k != "rid"} for p in sent] == [
        {"action": "play_video", "url": "http://x/master.m3u8"}, {"action": "video_control", "cmd": "pause"}, {"action": "stop_video"}]
    assert all(p["rid"] for p in sent)                      # kept until the panel acknowledges each
    assert all(c.kwargs.get("qos") == 1 for c in mb.mqtt.async_publish.call_args_list)
    assert bridge.outbox.pending("kitchen") == 1            # the stop replaced the waiting play / pause
    asyncio.run(bridge._on_device_ack(type("M", (), {"topic": "mqttdash/dev/kitchen/ack", "payload": json.dumps({"rid": sent[2]["rid"]})})()))
    assert bridge.outbox.pending("kitchen") == 0


def test_a_command_resent_by_the_panel_runs_once():
    bridge, hass = _bridge_with_configs()
    calls = []

    async def handle(entity_id, cmd):
        calls.append(entity_id)
    bridge._handle_entity_command = handle
    msg = type("M", (), {"topic": "mqttdash/cmd/light.kitchen", "payload": '{"action": "turn_on", "cid": "kitchen-1"}'})()
    asyncio.run(bridge._on_cmd(msg))
    asyncio.run(bridge._on_cmd(msg))
    assert calls == ["light.kitchen"]
